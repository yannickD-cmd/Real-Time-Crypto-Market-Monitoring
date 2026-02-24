import logging
from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values

from consumer.config import (
    TIMESCALEDB_HOST,
    TIMESCALEDB_PORT,
    TIMESCALEDB_DB,
    TIMESCALEDB_USER,
    TIMESCALEDB_PASSWORD,
)

logger = logging.getLogger(__name__)

_INSERT_TRADES = """
    INSERT INTO trades (
        event_time,
        ingestion_timestamp,
        symbol,
        event_type,
        trade_id,
        price,
        quantity,
        is_buyer_maker,
        first_trade_id,
        last_trade_id
    )
    VALUES %s
    ON CONFLICT (event_time, symbol, trade_id) DO NOTHING
"""

_TRADES_ROW_TEMPLATE = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

_INSERT_BOOK_TICKER = """
    INSERT INTO book_ticker (
        ingestion_timestamp,
        symbol,
        update_id,
        best_bid_price,
        best_bid_qty,
        best_ask_price,
        best_ask_qty
    )
    VALUES %s
    ON CONFLICT (ingestion_timestamp, symbol, update_id) DO NOTHING
"""

_BOOK_TICKER_ROW_TEMPLATE = "(%s, %s, %s, %s, %s, %s, %s)"


def _parse_ts(ms: int) -> datetime:
    """Convert a Binance millisecond epoch integer to an aware UTC datetime."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _parse_ingestion_ts(iso: str) -> datetime:
    """Parse the ISO-8601 ingestion_timestamp stamped by the ingestion layer."""
    return datetime.fromisoformat(iso)


class TimescaleDBClient:
    """
    Manages a psycopg2 connection pool and exposes bulk INSERT methods.

    Context manager pattern mirrors KafkaProducerClient:
        with TimescaleDBClient() as db:
            db.insert_trades(batch)
            db.insert_book_ticker(batch)
    """

    def __init__(self):
        self._pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=4,
            host=TIMESCALEDB_HOST,
            port=TIMESCALEDB_PORT,
            dbname=TIMESCALEDB_DB,
            user=TIMESCALEDB_USER,
            password=TIMESCALEDB_PASSWORD,
        )
        logger.info(
            "TimescaleDB pool ready (%s:%s/%s)",
            TIMESCALEDB_HOST,
            TIMESCALEDB_PORT,
            TIMESCALEDB_DB,
        )

    def insert_trades(self, batch: list[dict]) -> int:
        """Bulk-insert trade/aggTrade dicts. Returns number of rows processed."""
        if not batch:
            return 0

        rows: list[tuple[Any, ...]] = []
        for msg in batch:
            event_type = msg.get("e", "trade")
            trade_id = msg.get("t") if event_type == "trade" else msg.get("a")
            rows.append((
                _parse_ts(msg["T"]),
                _parse_ingestion_ts(msg["ingestion_timestamp"]),
                msg["s"],
                event_type,
                trade_id,
                msg["p"],
                msg["q"],
                msg["m"],
                msg.get("f"),
                msg.get("l"),
            ))

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                execute_values(cur, _INSERT_TRADES, rows, template=_TRADES_ROW_TEMPLATE)
            conn.commit()
            logger.debug("Inserted %d trade rows.", len(rows))
            return len(rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def insert_book_ticker(self, batch: list[dict]) -> int:
        """Bulk-insert bookTicker dicts. Returns number of rows processed."""
        if not batch:
            return 0

        rows: list[tuple[Any, ...]] = []
        for msg in batch:
            rows.append((
                _parse_ingestion_ts(msg["ingestion_timestamp"]),
                msg["s"],
                msg["u"],
                msg["b"],
                msg["B"],
                msg["a"],
                msg["A"],
            ))

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                execute_values(
                    cur, _INSERT_BOOK_TICKER, rows, template=_BOOK_TICKER_ROW_TEMPLATE
                )
            conn.commit()
            logger.debug("Inserted %d book_ticker rows.", len(rows))
            return len(rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def close(self) -> None:
        self._pool.closeall()
        logger.info("TimescaleDB connection pool closed.")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
