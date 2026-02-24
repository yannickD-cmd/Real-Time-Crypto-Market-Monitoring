# Real-Time Crypto Market Monitoring — Architecture

---

## Full Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BINANCE EXCHANGE                            │
│                                                                     │
│   BTCUSDT ──┐                                                       │
│   ETHUSDT ──┼──  9 streams  (3 symbols × 3 types)                  │
│   BNBUSDT ──┘   trade │ aggTrade │ bookTicker                       │
└─────────────────────┬───────────────────────────────────────────────┘
                      │  WebSocket (1 persistent connection)
                      │  wss://stream.binance.com:9443/stream
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 1 — INGESTION                              │
│                  ingestion/ws_consumer.py                           │
│                                                                     │
│   1. Receive raw event                                              │
│   2. Add  ingestion_timestamp  (UTC, stamped at receipt)            │
│   3. Route by stream type:                                          │
│       trade / aggTrade  ──▶  binance.trades                         │
│       bookTicker        ──▶  binance.book_ticker                    │
│   4. Produce to Kafka   (key = symbol, acks = all)                  │
│                                                                     │
│   ✦ Exponential backoff on reconnect (1s → 60s)                    │
│   ✦ Health-check HTTP on :8081                                      │
└─────────────────────────────┬───────────────────────────────────────┘
                              │  confluent-kafka producer
                              │  lz4 compression │ batch 1 000 msgs
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         KAFKA BROKER                                │
│                        localhost:9092                               │
│                                                                     │
│   Topic: binance.trades          Topic: binance.book_ticker         │
│   ┌──────────────────────┐       ┌──────────────────────┐          │
│   │ Partition 0 (BTCUSDT)│       │ Partition 0 (BTCUSDT)│          │
│   │ Partition 1 (ETHUSDT)│       │ Partition 1 (ETHUSDT)│          │
│   │ Partition 2 (BNBUSDT)│       │ Partition 2 (BNBUSDT)│          │
│   └──────────────────────┘       └──────────────────────┘          │
│                                                                     │
│   ✦ Ordered per symbol (partition key = symbol)                     │
│   ✦ 7-day retention                                                 │
│   ✦ Absorbs traffic spikes — backpressure buffer                    │
│   ✦ Kafka-UI visible at http://localhost:8080                       │
└─────────────────────────────┬───────────────────────────────────────┘
                              │  confluent-kafka consumer
                              │  group: binance-buffer
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 2 — BUFFERING                              │
│                    consumer/worker.py                               │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────┐      │
│   │  POLL  (every 1s)                                       │      │
│   │    msg.topic == binance.trades      → trades_buffer     │      │
│   │    msg.topic == binance.book_ticker → tickers_buffer    │      │
│   └────────────────────────┬────────────────────────────────┘      │
│                            │                                        │
│   ┌────────────────────────▼────────────────────────────────┐      │
│   │  FLUSH TRIGGER  (whichever comes first)                 │      │
│   │    ├── 500 messages accumulated   (size cap)            │      │
│   │    └── 2 seconds elapsed          (time cap)            │      │
│   └────────────────────────┬────────────────────────────────┘      │
│                            │                                        │
│   ┌────────────────────────▼────────────────────────────────┐      │
│   │  BULK INSERT  (one DB round-trip per batch)             │      │
│   │    execute_values → ON CONFLICT DO NOTHING              │      │
│   └────────────────────────┬────────────────────────────────┘      │
│                            │  only on success                       │
│   ┌────────────────────────▼────────────────────────────────┐      │
│   │  COMMIT OFFSET  (manual, synchronous)                   │      │
│   │    crash before here → replay from last offset          │      │
│   └─────────────────────────────────────────────────────────┘      │
│                                                                     │
│   ✦ Health-check HTTP on :8082                                      │
└─────────────────────────────┬───────────────────────────────────────┘
                              │  psycopg2  (bulk INSERT)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       TIMESCALEDB                                   │
│                    localhost:5433                                    │
│                                                                     │
│   Table: trades                    Table: book_ticker               │
│   ┌──────────────────────────┐     ┌──────────────────────────┐    │
│   │ event_time   TIMESTAMPTZ │     │ ingestion_ts  TIMESTAMPTZ│    │
│   │ symbol       TEXT        │     │ symbol        TEXT       │    │
│   │ event_type   TEXT        │     │ update_id     BIGINT     │    │
│   │ trade_id     BIGINT      │     │ best_bid_price NUMERIC   │    │
│   │ price        NUMERIC(20,8│     │ best_bid_qty   NUMERIC   │    │
│   │ quantity     NUMERIC(20,8│     │ best_ask_price NUMERIC   │    │
│   │ is_buyer_mak BOOLEAN     │     │ best_ask_qty   NUMERIC   │    │
│   └──────────────────────────┘     └──────────────────────────┘    │
│        Hypertable (1-day chunks)        Hypertable (1-day chunks)   │
│        Index: (symbol, event_time)      Index: (symbol, ingest_ts)  │
│                                                                     │
│   ✦ Permanent queryable storage                                     │
│   ✦ Full SQL — time_bucket(), aggregations, JOINs                  │
└───────────────────────┬──────────────────────────┬──────────────────┘
                        │  psycopg2 (JDBC)          │  PostgreSQL plugin
                        ▼                           ▼
┌──────────────────────────────────┐   ┌──────────────────────────────┐
│     PHASE 3 — STREAM PROCESSING  │   │    PHASE 4 — VISUALISATION   │
│       spark/streaming_job.py     │   │            GRAFANA            │
│                                  │   │        localhost:3000         │
│  Source: Kafka (Structured       │   │                              │
│          Streaming)              │   │  Datasource: TimescaleDB     │
│                                  │   │  (PostgreSQL plugin, auto-   │
│  Query 1 — Trade Metrics         │   │   provisioned)               │
│    Window : 1-minute tumbling    │   │                              │
│    Trigger: every 10 seconds     │   │  Dashboard 1: Market Overview│
│    Output : trade_metrics table  │   │    VWAP time-series          │
│    Fields : vwap, price_stddev,  │   │    Trade count bar gauge     │
│             trade_count,         │   │    Avg spread line           │
│             volatility_alert,    │   │    (one row per symbol)      │
│             volume_spike         │   │                              │
│                                  │   │  Dashboard 2: Risk Monitor   │
│  Query 2 — Spread Metrics        │   │    Volatility Alerts stat    │
│    Window : 30-second tumbling   │   │    Volume Spikes stat        │
│    Trigger: every 10 seconds     │   │    Spread Warnings stat      │
│    Output : spread_metrics table │   │    Anomaly events table      │
│    Fields : avg_spread,          │   │    Spread warnings table     │
│             max_spread,          │   │                              │
│             min_spread,          │   │  Alerting (every 30 s):      │
│             spread_warning       │   │    VolatilityAlert — fires   │
│                                  │   │      when stddev > 2.0       │
│  ✦ Event-time watermark (10s)    │   │    SpreadWarning — fires     │
│  ✦ ON CONFLICT … DO UPDATE       │   │      when spread > 3× min    │
│    (partial window upserts)      │   │    → Email via SMTP          │
│  ✦ Checkpoint in ~/spark-        │   │                              │
│    checkpoints/ (cross-platform) │   │  ✦ Auto-refresh every 10s   │
│  ✦ winutils + hadoop.dll needed  │   │  ✦ All config as code (YAML  │
│    on Windows (JNI path issue)   │   │    + JSON, no manual setup)  │
└──────────────────────────────────┘   └──────────────────────────────┘
```

---

## What each phase solves

| Phase | Component | Problem it solves |
|-------|-----------|-------------------|
| **1 — Ingestion** | `ws_consumer.py` → Kafka | Gets data out of Binance instantly, never misses an event |
| **Buffer** | Kafka | Absorbs traffic spikes; decouples producer speed from consumer speed |
| **2 — Buffering** | `worker.py` → TimescaleDB | Drains Kafka at a safe pace; makes data queryable permanently |
| **3 — Processing** | `streaming_job.py` → TimescaleDB | Computes VWAP, volatility, spread metrics per rolling window in real time |
| **4 — Visualisation** | Grafana → dashboards + alerts | Turns raw DB rows into live charts and fires email on anomaly conditions |

---

## Crash safety

```
Scenario: consumer crashes mid-batch

  Kafka offset:  ──────────[committed]────────[crash here]────▶
                                    ↑                ↑
                              last safe point     not committed

  On restart: consumer replays from [committed]
              DB has ON CONFLICT DO NOTHING → no duplicates
```

---

## Processes to run

```
Terminal 1                     Terminal 2                     Terminal 3
──────────────────────         ──────────────────────         ──────────────────────
python -m ingestion.ws_consumer    python -m consumer.worker      python -m spark.streaming_job

Binance → Kafka                Kafka → TimescaleDB (raw)      Kafka → TimescaleDB (metrics)
Port :8081 health              Port :8082 health              Spark UI :4040
```

---

## Docker services

```
docker compose up -d
        │
        ├── zookeeper     :2181   Kafka coordination
        ├── kafka         :9092   Message broker
        ├── kafka-init            Creates topics (one-shot, exits)
        ├── kafka-ui      :8080   Visual Kafka browser
        ├── timescaledb   :5433   PostgreSQL + time-series storage
        └── grafana       :3000   Dashboards + email alerting
```
