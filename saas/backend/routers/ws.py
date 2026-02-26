import asyncio
import json
import math
import random
import threading
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_lock = threading.Lock()
_msg_counts: dict = defaultdict(int)
_prices: dict = {}
_kafka_live = False


def _kafka_reader():
    global _kafka_live
    try:
        from confluent_kafka import Consumer, KafkaError

        consumer = Consumer({
            "bootstrap.servers": "localhost:9092",
            "group.id": "saas-metrics-v1",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        })
        consumer.subscribe(["binance.trades", "binance.book_ticker"])
        _kafka_live = True

        while True:
            msg = consumer.poll(0.05)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != -191:  # _PARTITION_EOF
                    print(f"[ws] Kafka error: {msg.error()}")
                continue
            try:
                data = json.loads(msg.value().decode("utf-8"))
                symbol = (data.get("s") or data.get("symbol") or "UNKNOWN").upper()
                price_raw = data.get("p") or data.get("b") or data.get("price") or 0
                price = float(price_raw) if price_raw else 0
                with _lock:
                    _msg_counts[symbol] += 1
                    if price > 0:
                        _prices[symbol] = price
            except Exception:
                pass
    except Exception as e:
        print(f"[ws] Kafka unavailable ({e}). Running in demo mode.")
        _kafka_live = False
        _demo_mode()


def _demo_mode():
    """Synthetic data feed when Kafka is not running."""
    t = 0
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    base = {"BTCUSDT": 65_000.0, "ETHUSDT": 3_500.0, "BNBUSDT": 580.0}
    while True:
        t += 1
        with _lock:
            for sym in symbols:
                count = int(40 + 20 * math.sin(t * 0.3) + random.randint(0, 15))
                _msg_counts[sym] += count
                noise = random.uniform(-0.002, 0.002)
                base[sym] *= 1 + noise
                _prices[sym] = round(base[sym], 2)
        time.sleep(0.1)


threading.Thread(target=_kafka_reader, daemon=True).start()


@router.websocket("/ws/metrics")
async def metrics_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(1)
            with _lock:
                counts = dict(_msg_counts)
                prices = dict(_prices)
                _msg_counts.clear()
            await websocket.send_json({
                "ts": time.time(),
                "total_per_sec": sum(counts.values()),
                "per_symbol": counts,
                "prices": prices,
                "kafka_live": _kafka_live,
            })
    except (WebSocketDisconnect, Exception):
        pass
