import logging
import time

from consumer.db import TimescaleDBClient
from consumer.config import CONSUMER_BATCH_SIZE, CONSUMER_FLUSH_INTERVAL

logger = logging.getLogger(__name__)


class BatchWriter:
    """
    Accumulates Kafka messages in memory and flushes them to TimescaleDB.

    Flush is triggered by whichever condition arrives first:
      1. Size threshold: a buffer reaches CONSUMER_BATCH_SIZE (500 messages).
      2. Time threshold: CONSUMER_FLUSH_INTERVAL (2.0 s) elapsed since last flush.

    Offset commit is the caller's responsibility: worker.py calls
    consumer.commit() AFTER a successful flush() — never before.
    If flush() raises, the offset is NOT committed and the batch will be
    re-consumed on restart (at-least-once semantics).
    """

    def __init__(self, db: TimescaleDBClient):
        self._db = db
        self._trades_buffer: list[dict] = []
        self._tickers_buffer: list[dict] = []
        self._last_flush: float = time.monotonic()

    def add_trade(self, msg: dict) -> None:
        self._trades_buffer.append(msg)

    def add_book_ticker(self, msg: dict) -> None:
        self._tickers_buffer.append(msg)

    def should_flush(self) -> bool:
        if len(self._trades_buffer) >= CONSUMER_BATCH_SIZE:
            return True
        if len(self._tickers_buffer) >= CONSUMER_BATCH_SIZE:
            return True
        if (time.monotonic() - self._last_flush) >= CONSUMER_FLUSH_INTERVAL:
            return True
        return False

    def flush(self) -> tuple[int, int]:
        """
        Write both buffers to TimescaleDB and clear them.

        Returns (trades_written, tickers_written).
        Raises on DB error — caller must NOT commit offsets if this raises.
        """
        trades_written = self._db.insert_trades(self._trades_buffer)
        tickers_written = self._db.insert_book_ticker(self._tickers_buffer)

        self._trades_buffer.clear()
        self._tickers_buffer.clear()
        self._last_flush = time.monotonic()

        logger.info(
            "Flush complete: %d trade rows, %d book_ticker rows.",
            trades_written,
            tickers_written,
        )
        return trades_written, tickers_written

    def pending(self) -> int:
        """Total messages waiting to be flushed across both buffers."""
        return len(self._trades_buffer) + len(self._tickers_buffer)
