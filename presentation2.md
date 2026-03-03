# Real-Time Crypto Market Monitoring — Slide Presentation

---

## Slide 1 — Title

# Real-Time Crypto Market Monitoring

### A streaming data pipeline from Binance to live dashboards

---

**Stack:** Python · Apache Kafka · PySpark · TimescaleDB · Grafana · Docker

**Scope:** Ingest, process, and visualize live trade and order-book data
for three cryptocurrency pairs — with anomaly detection and email alerting.

---

---

## Slide 2 — Dataset Context

### What Is the Data Source?

**Binance** is the world's largest cryptocurrency exchange by trading volume,
processing millions of trades per day across hundreds of asset pairs.

---

**How the data is collected:**

- Binance exposes a **public WebSocket API** — no authentication required
- A single persistent connection subscribes to a **combined-stream endpoint**:

```
wss://stream.binance.com:9443/stream?streams=...
```

- Data is **push-based**: Binance sends every event the moment it occurs
- There is **no static dataset** — the pipeline generates data continuously as long as it runs

---

**Why real-time streaming?**

> Cryptocurrency markets move in milliseconds.
> A REST polling approach would miss events, introduce lag,
> and hit rate limits. WebSocket streaming is the only viable model.

---

---

## Slide 3 — Dataset Contents

### What Does the Data Contain?

**3 trading pairs monitored:**

| Symbol | Pair |
|---|---|
| BTCUSDT | Bitcoin vs. US Dollar |
| ETHUSDT | Ethereum vs. US Dollar |
| BNBUSDT | BNB vs. US Dollar |

---

**3 stream types per symbol = 9 concurrent streams:**

| Stream | What it captures |
|---|---|
| `trade` | Every individual fill: price, quantity, trade ID, buyer/seller side, exact trade timestamp |
| `aggTrade` | Aggregated fills: multiple trades at the same price within the same millisecond, bundled into one event — reduces noise |
| `bookTicker` | Best bid & ask snapshot: best buy price + quantity and best sell price + quantity, updated on every order-book change |

---

**Each event is stamped with an `ingestion_timestamp`** at the moment it arrives at the pipeline —
this allows measuring the end-to-end latency from Binance to storage.

---

---

## Slide 4 — Dataset Schema

### How Is the Data Stored?

All data lands in **TimescaleDB** — a time-series extension on top of PostgreSQL.
Tables are **hypertables** with automatic 1-day partitioning chunks for fast range queries.

---

**Raw tables (every event stored as-is):**

| Table | Key Columns |
|---|---|
| `trades` | event_time, symbol, event_type, trade_id, price, quantity, is_buyer_maker |
| `book_ticker` | ingestion_timestamp, symbol, update_id, best_bid_price, best_bid_qty, best_ask_price, best_ask_qty |

---

**Aggregated metrics tables (computed by PySpark):**

| Table | Key Columns | Granularity |
|---|---|---|
| `trade_metrics` | window_start/end, symbol, vwap, price_stddev, trade_count, volatility_alert, volume_spike | 1 row per symbol per minute |
| `spread_metrics` | window_start/end, symbol, avg_spread, max_spread, min_spread, spread_warning | 1 row per symbol per 30 seconds |

---

> Raw tables capture **what happened**.
> Metric tables capture **what it means**.

---

---

## Slide 5 — Research Questions

### What Did We Want to Answer?

**Core question:**

> *Can we build a low-latency, fault-tolerant pipeline that captures every trade
> and order-book update in real time, computes market microstructure metrics,
> detects anomalies, and visualizes everything — with zero data loss on crash?*

---

**Specific analytical questions:**

| # | Question | Metric |
|---|---|---|
| 1 | What is the true average price, weighted by trade volume? | **VWAP** (Volume-Weighted Average Price) per symbol per minute |
| 2 | Is price volatility abnormally high right now? | **Price standard deviation** within a 1-min window → `volatility_alert` flag |
| 3 | Is the bid-ask spread widening beyond its normal range? | **Spread** = ask − bid; warning when `avg_spread > 3 × min_spread` |
| 4 | Is trading volume spiking relative to the recent baseline? | **Volume spike** flag based on 5-min rolling average |

---

**Why these metrics?**

- **VWAP** is preferred over last price by institutional traders — it reflects where money actually traded
- **Volatility** and **spread** anomalies are early warning signs of market stress or manipulation
- **Volume spikes** precede large price moves in most market regimes

---

---

## Slide 6 — Architecture Overview

### How We Built It — The 4-Phase Pipeline

```
┌──────────────────────────────────────────────┐
│              BINANCE EXCHANGE                │
│  BTCUSDT · ETHUSDT · BNBUSDT                 │
│  9 streams: trade · aggTrade · bookTicker    │
└──────────────────┬───────────────────────────┘
                   │  WebSocket  (1 connection)
                   ▼
          ┌────────────────────┐
          │  PHASE 1           │  ws_consumer.py
          │  INGESTION         │  → stamps ingestion_timestamp
          │                    │  → routes by stream type
          └────────┬───────────┘  → produces to Kafka (key = symbol)
                   │
                   ▼
          ┌────────────────────────────────────┐
          │  KAFKA BROKER  :9092               │
          │  binance.trades      (3 partitions)│
          │  binance.book_ticker (3 partitions)│
          └──────┬─────────────────┬───────────┘
                 │                 │
     ▼ Phase 2   │                 │  Phase 3 ▼
┌────────────────┐         ┌───────────────────────┐
│  BUFFERING     │         │  STREAM PROCESSING    │
│  worker.py     │         │  streaming_job.py     │
│                │         │  (PySpark)            │
│  Batch INSERT  │         │                       │
│  500 msgs/2s   │         │  1-min VWAP windows   │
│                │         │  30-sec spread windows│
└───────┬────────┘         └──────────┬────────────┘
        │                             │
        └──────────┬──────────────────┘
                   ▼
          ┌────────────────────┐
          │  TIMESCALEDB :5433 │
          │  trades            │
          │  book_ticker       │
          │  trade_metrics     │
          │  spread_metrics    │
          └────────┬───────────┘
                   ▼
          ┌────────────────────┐
          │  GRAFANA  :3001    │
          │  Live dashboards   │
          │  Email alerts      │
          └────────────────────┘
```

---

---

## Slide 7 — Key Design Decisions

### How We Built It — Engineering Choices

---

**1. WebSocket over REST polling**
One persistent TCP connection delivers all 9 streams simultaneously.
Polling would miss events, introduce latency, and hit Binance rate limits.

---

**2. Kafka as a decoupling buffer**
The WebSocket produces data faster than the database can absorb.
Kafka sits in between: absorbs traffic spikes, stores events for 7 days,
and allows independent consumers at different speeds.

---

**3. Partition key = symbol**
Each symbol (BTC, ETH, BNB) gets its own Kafka partition.
This guarantees ordering of events per symbol across all consumers.

---

**4. Batch writes + `ON CONFLICT DO NOTHING`**
Instead of one INSERT per event, events accumulate into batches of 500 (or 2 seconds).
`ON CONFLICT` makes replays idempotent — if the consumer restarts and replays
messages already committed, the database silently ignores duplicates.

---

**5. TimescaleDB hypertables**
Automatic 1-day time partitioning.
Each day's data becomes a compressed chunk.
Time-range queries are orders of magnitude faster than plain PostgreSQL.

---

**6. PySpark Structured Streaming**
Two parallel streaming queries run continuously:
- **Trade metrics** — 1-minute tumbling windows, output every 10 seconds
- **Spread metrics** — 30-second tumbling windows, output every 10 seconds

Using event-time windowing with a 10-second watermark handles out-of-order arrivals correctly.

---

**7. Grafana as code**
Dashboards, alert rules, and the datasource connection are all provisioned
from YAML/JSON files in the repository.
The entire monitoring stack is reproducible with a single `docker compose up`.

---

---

## Slide 8 — Difficulties Encountered

### What Went Wrong and How We Fixed It

---

| # | Problem | Root Cause | Solution |
|---|---|---|---|
| 1 | **PySpark crashes on Windows** | Spark's Hadoop JNI layer (`hadoop.dll`, `winutils.exe`) not bundled on Windows — throws `java.io.IOException` at startup | Manually set `HADOOP_HOME` pointing to a folder with the DLLs; set Spark temp dir to an ASCII path to avoid Unicode issues |
| 2 | **Data loss on consumer crash** | Committing Kafka offsets before the database flush means unwritten events are skipped on restart | Implemented manual offset commit *only after* a confirmed successful database flush |
| 3 | **Duplicate rows in metrics tables** | Spark emits partial window results every 10 seconds before a window closes, creating multiple rows for the same window | Changed inserts to `ON CONFLICT (window_start, symbol) DO UPDATE` — partial windows are progressively overwritten |
| 4 | **No timestamp on bookTicker events** | Binance bookTicker only carries an `update_id` (no event time), so event-time windowing is impossible | Used `current_timestamp` (processing time) as the window dimension for spread queries, with an explicit watermark |
| 5 | **WebSocket disconnections** | Binance periodically closes long-lived connections (idle timeout, server restart) | Implemented exponential backoff reconnect: 1s → 2s → 4s → … → 60s cap, resetting on each successful reconnect |

---

---

## Slide 9 — Results

### What the Pipeline Delivers

---

**Throughput & latency:**

| Metric | Value |
|---|---|
| Events ingested | Hundreds per second per symbol at peak hours |
| Raw data latency (Binance → TimescaleDB) | ≤ 2 seconds (batch flush interval) |
| Metric update latency (Kafka → trade_metrics) | ≤ 10 seconds (Spark trigger interval) |
| Crash recovery | Zero data loss — Kafka offset replay + idempotent inserts |

---

**Metrics produced in real time:**

- **VWAP** per symbol per minute — weighted average price reflecting actual traded value
- **Price standard deviation** per minute — volatility flag when `stddev > 2.0`
- **Bid-ask spread** per 30 seconds — liquidity warning when `avg > 3 × min`
- **Trade count and total volume** per minute

---

**Grafana dashboards:**

| Dashboard | Content |
|---|---|
| Market Overview | VWAP time-series · trade count bar gauge · avg spread line · auto-refresh 10s |
| Risk Monitor | Volatility alert count · volume spike count · spread warning count · anomaly events table |

---

**Alerting:**

- `VolatilityAlert` — fires when `price_stddev > 2.0` is sustained for 1 minute → email via SMTP
- `SpreadWarning` — fires when `avg_spread > 3 × min_spread` is sustained for 1 minute → email via SMTP
- All alert rules are provisioned as code — no manual Grafana configuration needed

---

> The pipeline turns a raw firehose of exchange events into structured,
> queryable, alertable market intelligence — in under 10 seconds end to end.
