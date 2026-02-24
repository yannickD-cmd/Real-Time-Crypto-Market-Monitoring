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
└─────────────────────────────────────────────────────────────────────┘
```

---

## What each phase solves

| Phase | Component | Problem it solves |
|-------|-----------|-------------------|
| **1 — Ingestion** | `ws_consumer.py` → Kafka | Gets data out of Binance instantly, never misses an event |
| **Buffer** | Kafka | Absorbs traffic spikes; decouples producer speed from consumer speed |
| **2 — Buffering** | `worker.py` → TimescaleDB | Drains Kafka at a safe pace; makes data queryable permanently |

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
Terminal 1                     Terminal 2
──────────────────────         ──────────────────────
python -m ingestion.ws_consumer    python -m consumer.worker

Binance → Kafka                Kafka → TimescaleDB
Port :8081 health              Port :8082 health
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
        └── timescaledb   :5433   PostgreSQL + time-series storage
```
