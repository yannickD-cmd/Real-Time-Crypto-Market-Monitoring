import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import websockets

from ingestion.config import (
    HEALTH_PORT,
    STREAM_TYPES,
    SYMBOLS,
    TOPIC_BOOK_TICKER,
    TOPIC_TRADES,
    WS_BASE_URL,
)
from ingestion.kafka_producer import KafkaProducerClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Map stream suffix → Kafka topic
STREAM_TOPIC_MAP: dict[str, str] = {
    "trade": TOPIC_TRADES,
    "aggTrade": TOPIC_TRADES,
    "bookTicker": TOPIC_BOOK_TICKER,
}

_healthy = False  # toggled by consume(); read by health-check handler


# ---------------------------------------------------------------------------
# Health-check HTTP server (runs in a daemon thread)
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
    server = HTTPServer(("", HEALTH_PORT), _HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health-check listening on :%s", HEALTH_PORT)


# ---------------------------------------------------------------------------
# Stream helpers
# ---------------------------------------------------------------------------

def _build_stream_url() -> str:
    """Combined-streams URL covering all symbols × stream types."""
    streams = "/".join(
        f"{sym.lower()}@{st}" for sym in SYMBOLS for st in STREAM_TYPES
    )
    return f"{WS_BASE_URL}?streams={streams}"


def _route_topic(stream_name: str) -> str:
    """Derive Kafka topic from the stream name, e.g. 'btcusdt@aggTrade'."""
    suffix = stream_name.split("@")[-1] if "@" in stream_name else ""
    return STREAM_TOPIC_MAP.get(suffix, TOPIC_TRADES)


# ---------------------------------------------------------------------------
# Main async consumer with exponential backoff
# ---------------------------------------------------------------------------

async def consume(producer: KafkaProducerClient) -> None:
    global _healthy
    url = _build_stream_url()
    backoff = 1  # seconds; doubles on each failure, capped at 60 s

    while True:
        try:
            logger.info("Connecting to %s", url)
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                _healthy = True
                backoff = 1  # reset after a successful connection
                async for raw in ws:
                    envelope = json.loads(raw)
                    # Combined-streams wraps payload: {"stream": "...", "data": {...}}
                    stream_name: str = envelope.get("stream", "")
                    data: dict = envelope.get("data", envelope)

                    # Stamp the moment this process received the event
                    data["ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()

                    symbol: str = data.get("s", stream_name.split("@")[0].upper())
                    topic = _route_topic(stream_name)
                    producer.send(topic=topic, key=symbol, value=data)
                    logger.debug("→ %s  key=%s", topic, symbol)

        except websockets.ConnectionClosedError as exc:
            _healthy = False
            logger.warning("Connection closed (%s). Retrying in %ss…", exc, backoff)
        except Exception as exc:  # noqa: BLE001
            _healthy = False
            logger.error("Unexpected error: %s. Retrying in %ss…", exc, backoff)

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    _start_health_server()
    producer = KafkaProducerClient()
    loop = asyncio.new_event_loop()

    def _shutdown(*_):
        global _healthy
        logger.info("Shutdown signal received.")
        _healthy = False
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
