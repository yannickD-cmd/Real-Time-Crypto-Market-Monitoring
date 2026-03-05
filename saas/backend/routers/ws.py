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
_last_real_msg = 0.0  # timestamp of last real Kafka message


# ── Demo thread — always running, feeds data when Kafka is silent ─────────────
def _demo_thread():
    t = 0
    base = {"BTCUSDT": 65_000.0, "ETHUSDT": 3_500.0, "BNBUSDT": 580.0}
    while True:
        t += 1
        # Write demo data only when Kafka has been silent for more than 5 seconds
        if time.time() - _last_real_msg > 5:
            with _lock:
                for sym in list(base.keys()):
                    count = int(40 + 20 * math.sin(t * 0.3) + random.randint(0, 15))
                    _msg_counts[sym] += count
                    noise = random.uniform(-0.002, 0.002)
                    base[sym] = round(base[sym] * (1 + noise), 2)
                    _prices[sym] = base[sym]
        time.sleep(0.1)


threading.Thread(target=_demo_thread, daemon=True).start()


# ── Kafka reader — connects and reads real data ───────────────────────────────
def _kafka_reader():
    global _kafka_live, _last_real_msg
    try:
        from confluent_kafka import Consumer

        consumer = Consumer({
            "bootstrap.servers": "localhost:9092",
            "group.id": "saas-metrics-v1",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        })
        consumer.subscribe(["binance.trades", "binance.book_ticker"])

        while True:
            msg = consumer.poll(0.05)
            if msg is None or msg.error():
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
                _kafka_live = True
                _last_real_msg = time.time()
            except Exception:
                pass
    except Exception as e:
        print(f"[ws] Kafka unavailable ({e}). Demo mode active.")


threading.Thread(target=_kafka_reader, daemon=True).start()


# ── WebSocket endpoint ────────────────────────────────────────────────────────
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
            live = _kafka_live and (time.time() - _last_real_msg < 5)
            await websocket.send_json({
                "ts": time.time(),
                "total_per_sec": sum(counts.values()),
                "per_symbol": counts,
                "prices": prices,
                "kafka_live": live,
            })
    except (WebSocketDisconnect, Exception):
        pass
