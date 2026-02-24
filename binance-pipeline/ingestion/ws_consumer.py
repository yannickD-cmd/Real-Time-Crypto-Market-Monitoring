import asyncio
import json
import logging
import signal

import websockets

from ingestion.config import SYMBOLS, STREAM_TYPE, WS_BASE_URL
from ingestion.kafka_producer import KafkaProducerClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _build_stream_url() -> str:
    """Build a combined stream URL for all configured symbols."""
    streams = "/".join(f"{s.lower()}@{STREAM_TYPE}" for s in SYMBOLS)
    return f"{WS_BASE_URL}/{streams}"


async def consume(producer: KafkaProducerClient) -> None:
    url = _build_stream_url()
    logger.info("Connecting to %s", url)

    async for websocket in websockets.connect(url, ping_interval=20, ping_timeout=10):
        try:
            async for raw in websocket:
                data = json.loads(raw)
                symbol = data.get("s", "UNKNOWN")
                producer.send(key=symbol, value=data)
                logger.debug("Produced: %s", symbol)
        except websockets.ConnectionClosedError as exc:
            logger.warning("Connection closed (%s). Reconnecting…", exc)


def run() -> None:
    producer = KafkaProducerClient()
    loop = asyncio.new_event_loop()

    def _shutdown(*_):
        logger.info("Shutdown signal received.")
        loop.stop()
        producer.flush()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(consume(producer))
    finally:
        loop.close()


if __name__ == "__main__":
    run()
