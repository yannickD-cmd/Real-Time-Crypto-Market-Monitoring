"""
Phase 3 — PySpark Structured Streaming
Reads from Kafka, computes windowed trade and spread metrics, writes to TimescaleDB.
"""

import os
# Windows: PySpark requires winutils.exe and hadoop.dll.
# HADOOP_HOME must be set AND its bin/ must be on PATH so the JVM
# can load hadoop.dll via System.loadLibrary at runtime.
if os.name == "nt":
    hadoop_home = r"C:\hadoop"
    os.environ.setdefault("HADOOP_HOME", hadoop_home)
    hadoop_bin = os.path.join(hadoop_home, "bin")
    if hadoop_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = hadoop_bin + os.pathsep + os.environ.get("PATH", "")

import yaml
import psycopg2
from psycopg2.extras import execute_values
from datetime import timezone

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, LongType, DoubleType, BooleanType,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, "config.yaml")) as f:
    CFG = yaml.safe_load(f)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_TRADES    = os.getenv("TOPIC_TRADES",      "binance.trades")
TOPIC_TICKER    = os.getenv("TOPIC_BOOK_TICKER", "binance.book_ticker")

DB_HOST = os.getenv("TIMESCALEDB_HOST",     "localhost")
DB_PORT = os.getenv("TIMESCALEDB_PORT",     "5433")
DB_NAME = os.getenv("TIMESCALEDB_DB",       "crypto")
DB_USER = os.getenv("TIMESCALEDB_USER",     "crypto")
DB_PASS = os.getenv("TIMESCALEDB_PASSWORD", "crypto_secret")

VOLUME_SPIKE_MUL   = float(CFG["trade_metrics"]["volume_spike_multiplier"])
VOLATILITY_MUL     = float(CFG["trade_metrics"]["volatility_stddev_multiplier"])
SPREAD_WARNING_MUL = float(CFG["spread_metrics"]["spread_warning_multiplier"])

# ---------------------------------------------------------------------------
# Schemas — separate for trades and bookTicker
# ---------------------------------------------------------------------------

# binance.trades topic carries both "trade" and "aggTrade" payloads.
# We only need the fields present in both event types.
TRADE_SCHEMA = StructType([
    StructField("e", StringType()),   # event type: "trade" or "aggTrade"
    StructField("E", LongType()),     # event time (ms) — used as event_time
    StructField("s", StringType()),   # symbol
    StructField("p", StringType()),   # price (string from Binance)
    StructField("q", StringType()),   # quantity (string from Binance)
    StructField("T", LongType()),     # trade time (ms)
])

# binance.book_ticker topic: best bid / ask snapshot
TICKER_SCHEMA = StructType([
    StructField("u", LongType()),     # update ID
    StructField("s", StringType()),   # symbol
    StructField("b", StringType()),   # best bid price
    StructField("B", StringType()),   # best bid qty
    StructField("a", StringType()),   # best ask price
    StructField("A", StringType()),   # best ask qty
])

# ---------------------------------------------------------------------------
# DB helpers — psycopg2 inside foreachBatch (runs on the driver)
# ---------------------------------------------------------------------------

def _db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS,
    )


def _write_trade_metrics(df: DataFrame, epoch_id: int) -> None:
    rows = df.collect()
    if not rows:
        return

    data = [(
        r["window_start"].astimezone(timezone.utc),
        r["window_end"].astimezone(timezone.utc),
        r["symbol"],
        r["window_seconds"],
        int(r["trade_count"]),
        float(r["total_volume"]),
        float(r["vwap"]),
        float(r["price_high"]),
        float(r["price_low"]),
        float(r["price_stddev"]) if r["price_stddev"] is not None else None,
        bool(r["volume_spike"]),
        bool(r["volatility_alert"]),
    ) for r in rows]

    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO trade_metrics
                    (window_start, window_end, symbol, window_seconds,
                     trade_count, total_volume, vwap,
                     price_high, price_low, price_stddev,
                     volume_spike, volatility_alert)
                VALUES %s
                ON CONFLICT (window_start, symbol, window_seconds) DO UPDATE SET
                    trade_count      = EXCLUDED.trade_count,
                    total_volume     = EXCLUDED.total_volume,
                    vwap             = EXCLUDED.vwap,
                    price_high       = EXCLUDED.price_high,
                    price_low        = EXCLUDED.price_low,
                    price_stddev     = EXCLUDED.price_stddev,
                    volume_spike     = EXCLUDED.volume_spike,
                    volatility_alert = EXCLUDED.volatility_alert
            """, data)
        conn.commit()
    finally:
        conn.close()


def _write_spread_metrics(df: DataFrame, epoch_id: int) -> None:
    rows = df.collect()
    if not rows:
        return

    data = [(
        r["window_start"].astimezone(timezone.utc),
        r["window_end"].astimezone(timezone.utc),
        r["symbol"],
        float(r["avg_spread"]),
        float(r["max_spread"]),
        float(r["min_spread"]),
        bool(r["spread_warning"]),
    ) for r in rows]

    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO spread_metrics
                    (window_start, window_end, symbol,
                     avg_spread, max_spread, min_spread, spread_warning)
                VALUES %s
                ON CONFLICT (window_start, symbol) DO UPDATE SET
                    avg_spread     = EXCLUDED.avg_spread,
                    max_spread     = EXCLUDED.max_spread,
                    min_spread     = EXCLUDED.min_spread,
                    spread_warning = EXCLUDED.spread_warning
            """, data)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SparkSession
# ---------------------------------------------------------------------------

def _build_spark() -> SparkSession:
    # The kafka JAR is fetched automatically from Maven on first run.
    # spark-sql-kafka-0-10 must match the Spark version (3.5.x) and
    # Scala version (2.12).
    return (
        SparkSession.builder
        .appName("binance-streaming")
        .master("local[*]")
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
        )
        # Reduce log noise for local runs
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.streaming.stopGracefullyOnShutdown", "true")
        .getOrCreate()
    )


# ---------------------------------------------------------------------------
# Trade streaming query
# ---------------------------------------------------------------------------

def _build_trade_query(spark: SparkSession):
    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", TOPIC_TRADES)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    # Use get_json_object (case-sensitive JSON path) to avoid Spark's
    # case-insensitive ambiguity between fields "e" and "E".
    value_col = F.col("value").cast("string")
    parsed = (
        raw.select(
            F.get_json_object(value_col, "$.e").alias("event_type"),
            F.get_json_object(value_col, "$.E").cast(LongType()).alias("event_time_ms"),
            F.get_json_object(value_col, "$.s").alias("symbol"),
            F.get_json_object(value_col, "$.p").cast(DoubleType()).alias("price"),
            F.get_json_object(value_col, "$.q").cast(DoubleType()).alias("qty"),
        )
        .filter(F.col("symbol").isNotNull())
        .withColumn("event_time", (F.col("event_time_ms") / 1000).cast("timestamp"))
        .withWatermark("event_time", "10 seconds")
    )

    def _agg_window(df, window_duration: str, window_seconds: int):
        """Aggregate trades over a tumbling window, returning metric columns."""
        agg = (
            df.groupBy(F.window("event_time", window_duration), F.col("symbol"))
            .agg(
                F.count("*").alias("trade_count"),
                F.sum("qty").alias("total_volume"),
                # VWAP = sum(price * qty) / sum(qty)
                (F.sum(F.col("price") * F.col("qty")) / F.sum("qty")).alias("vwap"),
                F.max("price").alias("price_high"),
                F.min("price").alias("price_low"),
                F.stddev_pop("price").alias("price_stddev"),
                # 5-min rolling context: track the sum and count for spike detection
                F.sum(F.col("qty")).alias("_vol_sum"),
            )
            .withColumn("window_start",   F.col("window.start"))
            .withColumn("window_end",     F.col("window.end"))
            .withColumn("window_seconds", F.lit(window_seconds))
            .drop("window", "_vol_sum")
        )
        return agg

    # 1-minute tumbling window
    agg_1m = _agg_window(parsed, "1 minute", 60)

    # Add anomaly flags using thresholds from config.yaml.
    # For a self-contained streaming query we compare stddev to a fixed
    # threshold (config multiplier × a reasonable baseline).
    # More sophisticated: compare across windows using stream-stream joins,
    # but that requires stateful joins and adds complexity.
    agg_1m_flagged = (
        agg_1m
        .withColumn(
            "volume_spike",
            F.col("total_volume") > (F.lit(VOLUME_SPIKE_MUL) * F.col("total_volume"))
            # Placeholder — true spike detection requires a 5-min moving average.
            # Set to False here; the column exists for downstream consumers.
            # Replace with: total_volume > MULTIPLIER * avg_5min_volume
        )
        .withColumn(
            "volatility_alert",
            F.when(
                F.col("price_stddev").isNotNull(),
                F.col("price_stddev") > F.lit(VOLATILITY_MUL)
            ).otherwise(F.lit(False))
        )
        # Recalculate volume_spike as False (self-join needed for real baseline)
        .withColumn("volume_spike", F.lit(False))
    )

    return (
        agg_1m_flagged.writeStream
        .outputMode("update")
        .trigger(processingTime="10 seconds")
        .foreachBatch(_write_trade_metrics)
        .option("checkpointLocation", "/tmp/spark-checkpoints/trade_metrics")
        .start()
    )


# ---------------------------------------------------------------------------
# Spread streaming query
# ---------------------------------------------------------------------------

def _build_spread_query(spark: SparkSession):
    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", TOPIC_TICKER)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    ticker_val = F.col("value").cast("string")
    parsed = (
        raw.select(
            F.get_json_object(ticker_val, "$.s").alias("symbol"),
            F.get_json_object(ticker_val, "$.a").cast(DoubleType()).alias("ask"),
            F.get_json_object(ticker_val, "$.b").cast(DoubleType()).alias("bid"),
        )
        .filter(F.col("symbol").isNotNull())
        .withColumn("spread", F.col("ask") - F.col("bid"))
        # bookTicker has no exchange-side timestamp — use ingestion time
        .withColumn("event_time", F.current_timestamp())
        .withWatermark("event_time", "10 seconds")
    )

    agg = (
        parsed
        .groupBy(F.window("event_time", "30 seconds"), F.col("symbol"))
        .agg(
            F.avg("spread").alias("avg_spread"),
            F.max("spread").alias("max_spread"),
            F.min("spread").alias("min_spread"),
        )
        .withColumn("window_start", F.col("window.start"))
        .withColumn("window_end",   F.col("window.end"))
        .drop("window")
        .withColumn(
            "spread_warning",
            F.col("avg_spread") > (F.lit(SPREAD_WARNING_MUL) * F.col("min_spread"))
        )
    )

    return (
        agg.writeStream
        .outputMode("update")
        .trigger(processingTime="10 seconds")
        .foreachBatch(_write_spread_metrics)
        .option("checkpointLocation", "/tmp/spark-checkpoints/spread_metrics")
        .start()
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    spark = _build_spark()
    spark.sparkContext.setLogLevel("WARN")

    print("Starting trade metrics query...")
    trade_query = _build_trade_query(spark)

    print("Starting spread metrics query...")
    spread_query = _build_spread_query(spark)

    print("Both queries running. Awaiting termination...")
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    run()
