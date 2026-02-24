import json
import logging
import signal
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from confluent_kafka import KafkaError

from consumer.config import (
    CONSUMER_HEALTH_PORT,
    TOPIC_TRADES,
    TOPIC_BOOK_TICKER,
)
from consumer.kafka_consumer import KafkaConsumerClient
from consumer.db import TimescaleDBClient
from consumer.batch_writer import BatchWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_healthy = False  # toggled by run(); read by health-check handler


# ---------------------------------------------------------------------------
# Health-check HTTP server (runs in a daemon thread)
# Mirrors ingestion/ws_consumer.py _HealthHandler exactly
# ---------------------------------------------------------------------------

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        code = 200 if _healthy else 503
        self.send_response(code)
        self.end_headers()
        self.wfile.write(b"ok" if _healthy else b"starting")

    def log_message(self, *_):  # silence default access log
        pass


def _start_health_server() -> None:
    server = HTTPServer(("", CONSUMER_HEALTH_PORT), _HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health-check listening on :%s", CONSUMER_HEALTH_PORT)


# ---------------------------------------------------------------------------
# Main consume loop
# ---------------------------------------------------------------------------

def _run_consume_loop(
    consumer: KafkaConsumerClient,
    batch_writer: BatchWriter,
    stop_flag: list[bool],
) -> None:
    global _healthy
    _healthy = True
    has_offset = False  # True once we've polled at least one real message

    while not stop_flag[0]:
        msg = consumer.poll(timeout=1.0)

        if msg is None:
            pass  # poll timeout — still check time-based flush below
        elif msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                logger.debug(
                    "End of partition %s [%d]", msg.topic(), msg.partition()
                )
            else:
                logger.error("Kafka error: %s", msg.error())
        else:
            has_offset = True  # a real message means an offset exists to commit
            try:
                value = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("Could not decode message: %s", exc)
                continue

            topic = msg.topic()
            if topic == TOPIC_TRADES:
                batch_writer.add_trade(value)
            elif topic == TOPIC_BOOK_TICKER:
                batch_writer.add_book_ticker(value)
            else:
                logger.warning("Unexpected topic: %s", topic)

        if has_offset and batch_writer.should_flush():
            try:
                batch_writer.flush()
                consumer.commit()
            except Exception as exc:
                logger.error("Flush failed: %s. Offsets NOT committed.", exc)
                raise

    logger.info("Stop flag set — exiting consume loop.")


# ---------------------------------------------------------------------------
# Entry point (mirrors ingestion/ws_consumer.py run())
# ---------------------------------------------------------------------------

def run() -> None:
    global _healthy
    _start_health_server()

    stop_flag = [False]

    def _shutdown(*_):
        global _healthy
        logger.info("Shutdown signal received.")
        _healthy = False
        stop_flag[0] = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    with TimescaleDBClient() as db:
        with KafkaConsumerClient(topics=[TOPIC_TRADES, TOPIC_BOOK_TICKER]) as consumer:
            batch_writer = BatchWriter(db)
            try:
                _run_consume_loop(consumer, batch_writer, stop_flag)
            finally:
                if batch_writer.pending() > 0:
                    logger.info(
                        "Flushing remaining %d messages before shutdown.",
                        batch_writer.pending(),
                    )
                    try:
                        batch_writer.flush()
                        consumer.commit()
                    except Exception as exc:
                        logger.error(
                            "Final flush failed (%s). These messages will be "
                            "re-consumed on next startup.", exc
                        )

    logger.info("Consumer worker shut down cleanly.")


if __name__ == "__main__":
    run()
