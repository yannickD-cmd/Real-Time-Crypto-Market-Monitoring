# Real-Time Crypto Market Monitoring — Full Presentation

---

## Part 1 — Understanding the Project

---

### 1. The Dataset

#### Context

The dataset is **live streaming market data** from the Binance exchange — the world's largest cryptocurrency exchange by trading volume. Data is sourced directly from Binance's official public WebSocket API (`wss://stream.binance.com:9443`) in real time, with no third-party intermediary.

There is no static file to download. The dataset is **continuously generated** as long as the pipeline is running, and it grows at a rate of hundreds to thousands of events per second depending on market activity.

#### What it Contains

The pipeline captures **three types of events** across **three trading pairs** (BTCUSDT, ETHUSDT, BNBUSDT):

| Stream Type | Content |
|---|---|
| `trade` | Individual trades: price, quantity, trade ID, buyer/seller side, trade timestamp |
| `aggTrade` | Aggregated trades: same as trade but bundles fills within the same millisecond at the same price (reduces noise) |
| `bookTicker` | Best bid/ask snapshot: best available buy price + quantity and sell price + quantity at that instant |

This gives **9 concurrent streams** (3 symbols × 3 types) funneled through a single WebSocket connection.

Each event is enriched with an `ingestion_timestamp` (stamped the moment it is received by the pipeline), which allows measuring the end-to-end latency from Binance to storage.

**The stored tables in TimescaleDB:**

| Table | Columns | Volume |
|---|---|---|
| `trades` | event_time, symbol, event_type, trade_id, price, quantity, is_buyer_maker | Very high (hundreds/sec) |
| `book_ticker` | ingestion_timestamp, symbol, update_id, best_bid_price, best_bid_qty, best_ask_price, best_ask_qty | Very high (hundreds/sec) |
| `trade_metrics` | window_start/end, symbol, vwap, price_stddev, trade_count, volatility_alert, volume_spike | 1 row per symbol per minute |
| `spread_metrics` | window_start/end, symbol, avg_spread, max_spread, min_spread, spread_warning | 1 row per symbol per 30 sec |

---

### 2. Questions the Project Wanted to Answer

> *Can we build a low-latency, fault-tolerant pipeline that captures every trade and book-ticker update from Binance in real time, computes market microstructure metrics (VWAP, volatility, bid-ask spread), detects anomalies, and makes everything queryable and visualized — with zero data loss on crash?*

More specifically:

- What is the **Volume-Weighted Average Price (VWAP)** per symbol per minute? (more stable than raw last price)
- Is price **volatility** (standard deviation within a 1-min window) abnormally high right now?
- Is the **bid-ask spread** widening beyond its normal range? (spread > 3× its recent minimum = liquidity warning)
- Is there a **volume spike** relative to the 5-minute baseline?

---

### 3. How It Was Achieved

#### Overall Architecture

The system is built as a **four-phase streaming pipeline**:

```
Binance WebSocket (9 streams)
        │
        ▼ Phase 1 — Ingestion
  ws_consumer.py  ──►  Kafka (2 topics, 3 partitions each)
        │
        ├──────────────────────────────────────┐
        ▼ Phase 2 — Buffering                  ▼ Phase 3 — Processing
  worker.py  ──►  TimescaleDB (raw tables)     streaming_job.py (PySpark)
  (bulk INSERT, batch 500 msgs or 2s)          ──► TimescaleDB (metrics tables)
                                               (VWAP, stddev, spread windows)
        │                                      │
        └──────────────────────────────────────┘
                        ▼ Phase 4 — Visualization
                  Grafana (dashboards + email alerts)
```

#### Key Design Decisions

**1. WebSocket over polling:** Binance provides a push-based combined-stream endpoint. One persistent TCP connection delivers all 9 streams, which is far more efficient than polling 9 REST endpoints and avoids rate limits.

**2. Kafka as a buffer between ingestion and storage:** The WebSocket produces events faster than the database can absorb them. Kafka decouples the producer speed from the consumer speed. It also provides 7-day replay — if the consumer crashes, it replays from the last committed offset without losing data.

**3. Partition key = symbol:** Each symbol gets its own Kafka partition, guaranteeing that BTCUSDT events are always processed in order, independently of ETH or BNB.

**4. Batch writes with `ON CONFLICT DO NOTHING`:** Instead of one INSERT per event (which would be too slow), the consumer accumulates up to 500 messages or 2 seconds of data, then does one bulk insert. The `ON CONFLICT` clause makes restarts idempotent — if the consumer replays messages Kafka already committed, duplicates are silently ignored at the DB level.

**5. TimescaleDB hypertables (1-day chunks):** TimescaleDB partitions the data automatically by time. Each day becomes a compressed chunk, making time-range queries dramatically faster than plain PostgreSQL on a single large table.

**6. PySpark Structured Streaming with event-time windows:** Using Spark Structured Streaming instead of processing data at query-time means the aggregations (VWAP, stddev) are computed incrementally as data arrives, with a 10-second watermark to handle late events. Two parallel queries run simultaneously:
   - **Trade metrics:** 1-minute tumbling windows, triggered every 10 seconds
   - **Spread metrics:** 30-second tumbling windows, triggered every 10 seconds

**7. `ON CONFLICT … DO UPDATE` for metrics:** Because Spark triggers output every 10 seconds even for incomplete windows, the metrics table uses upsert semantics — a partial 1-minute window is stored and progressively updated until the window closes.

**8. Grafana alert rules as code:** Alert rules (VolatilityAlert, SpreadWarning) and the TimescaleDB datasource are provisioned from YAML/JSON files in the repository. The entire monitoring stack can be torn down and recreated with `docker compose up` with no manual configuration.

#### Difficulties Encountered

| Problem | Solution |
|---|---|
| **Windows + PySpark + Hadoop DLLs** — Spark's Hadoop JNI layer (`hadoop.dll`, `winutils.exe`) is not bundled on Windows, causing `java.io.IOException` on startup | Manually set `HADOOP_HOME` to a folder containing the DLLs and explicitly set the Spark temporary directory path to avoid Unicode path issues |
| **Kafka offsets and crash recovery** — naively committing before flushing would lose data; committing after a partial batch would replay already-stored events | Implemented manual offset commit *only after* a successful database flush, combined with `ON CONFLICT DO NOTHING` for idempotent replay |
| **Spark window upserts** — tumbling windows emit partial results before they close (every 10s trigger), causing duplicate rows per window | Used `ON CONFLICT (window_start, symbol) DO UPDATE SET vwap=EXCLUDED.vwap, ...` in the TimescaleDB writer |
| **Event-time vs. ingestion-time for book_ticker** — bookTicker events have no exchange-side timestamp (only an update ID), so windowing requires using `current_timestamp` (processing time) instead of event time | Added explicit watermark on `current_timestamp` column for the spread query |
| **Binance WebSocket drops** — Binance closes idle or long-lived connections periodically | Implemented exponential backoff reconnect (1s → 2s → 4s → ... → 60s cap), resetting the delay on each successful reconnect |

---

### 4. Results

**Pipeline throughput:**
- Ingestion: hundreds of events per second per symbol at peak market hours
- Kafka buffer: handles traffic spikes without back-pressure to the WebSocket
- Consumer batch latency: ≤ 2 seconds from Kafka to TimescaleDB for raw trades
- Spark metric latency: ≤ 10 seconds from event to metric update in DB

**Metrics computed in real time:**
- VWAP per symbol per minute (more stable than last price, used by institutional traders)
- Price standard deviation per minute → volatility alert flag when `stddev > threshold`
- Bid-ask spread (ask − bid) per 30-second window → spread warning when `avg > 3 × min`
- Trade count and total volume per minute

**Visualization:**
- Grafana Market Overview: VWAP time-series + trade count bar gauge + spread line, auto-refreshing every 10s
- Grafana Risk Monitor: anomaly counts + event table with full details
- Grafana email alerts: fires when volatility or spread warnings are sustained for 1 minute

---

## Part 2 — Code, Architecture, and Running a Subset

---

### Code Structure

```
Real-Time-Crypto-Market-Monitoring/
│
└── binance-pipeline/
    ├── ingestion/
    │   ├── ws_consumer.py              # WebSocket → Kafka producer
    │   ├── kafka_producer.py           # Kafka producer config wrapper
    │   └── config.py                   # Symbols, topics, WS URL
    │
    ├── consumer/
    │   ├── worker.py                   # Kafka consumer → TimescaleDB (raw)
    │   ├── batch_writer.py             # Accumulate + flush on size/time
    │   ├── kafka_consumer.py           # Consumer wrapper
    │   ├── db.py                       # psycopg2 bulk insert
    │   └── config.py                   # Consumer group, batch settings
    │
    ├── spark/
    │   ├── streaming_job.py            # PySpark Structured Streaming
    │   └── config.yaml                 # Anomaly thresholds
    │
    └── docker/
        ├── docker-compose.yml          # Zookeeper, Kafka, TimescaleDB, Grafana
        ├── init-db.sql                 # Schema + hypertables
        └── grafana/
            ├── custom.ini              # Branding
            ├── provisioning/datasources/   # Auto-configure TimescaleDB
            ├── provisioning/alerting/      # Alert rules (YAML)
            └── dashboards/             # market_overview.json, risk_monitor.json
```

---

### How to Run — Step by Step

#### Prerequisites

- Docker Desktop running
- Python 3.10+ with pip
- (Windows only) `winutils.exe` and `hadoop.dll` in a folder referenced by `HADOOP_HOME`

---

#### Step 1 — Start Infrastructure (Docker)

```bash
cd binance-pipeline/docker
docker compose up -d
```

This starts:

| Service | URL | Purpose |
|---|---|---|
| Kafka | `localhost:9092` | Message broker |
| Kafka-UI | `http://localhost:8080` | Browse topics + messages |
| TimescaleDB | `localhost:5433` | Time-series database |
| Grafana | `http://localhost:3001` | Dashboards (admin/admin) |

Wait ~15 seconds for all services to be healthy.

---

#### Step 2 — Run on a Subset of the Dataset

To observe data evolving without ingesting all three symbols at full speed, use a **single symbol** with a **short flush interval**.

**Edit `binance-pipeline/.env`:**

```env
# Restrict to one symbol only
SYMBOLS=BTCUSDT

# Aggressive batching so you see DB rows quickly
CONSUMER_BATCH_SIZE=20
CONSUMER_FLUSH_INTERVAL=1.0
```

**Install dependencies:**

```bash
cd binance-pipeline
pip install -r requirements.txt
```

**Terminal 1 — Ingestion (WebSocket → Kafka):**

```bash
cd binance-pipeline
python -m ingestion.ws_consumer
```

Events are printed every second. Health check available at `http://localhost:8081`.

**Terminal 2 — Consumer (Kafka → TimescaleDB raw tables):**

```bash
cd binance-pipeline
python -m consumer.worker
```

With `CONSUMER_BATCH_SIZE=20` and `CONSUMER_FLUSH_INTERVAL=1.0`, a flush log appears every ~1 second.

**Terminal 3 — Spark Streaming (Kafka → metrics tables):**

```bash
cd binance-pipeline
python -m spark.streaming_job
```

Spark takes ~20 seconds to start. After that, `trade_metrics` and `spread_metrics` rows appear every 10 seconds.

---

#### Step 3 — Observe Data Evolving

**Option A — Kafka-UI (visual):**

Open `http://localhost:8080` → Topics → `binance.trades` → Messages tab.
Watch messages arriving in real time, partitioned by symbol.

**Option B — TimescaleDB SQL:**

```bash
psql -h localhost -p 5433 -U crypto -d crypto
```

Watch raw trades arriving:

```sql
SELECT event_time, symbol, price, quantity
FROM trades
ORDER BY event_time DESC
LIMIT 10;
```

Watch metrics being computed every 10 seconds:

```sql
-- Latest VWAP windows
SELECT window_start, symbol, vwap, trade_count, volatility_alert
FROM trade_metrics
ORDER BY window_start DESC
LIMIT 5;

-- Spread metrics
SELECT window_start, symbol, avg_spread, spread_warning
FROM spread_metrics
ORDER BY window_start DESC
LIMIT 5;
```

See VWAP evolving over the last 10 minutes:

```sql
SELECT window_start,
       round(vwap::numeric, 2) AS vwap,
       trade_count,
       volatility_alert
FROM trade_metrics
WHERE symbol = 'BTCUSDT'
  AND window_start > now() - interval '10 minutes'
ORDER BY window_start;
```

**Option C — Grafana:**

Open `http://localhost:3001` (admin / admin) → Market Overview dashboard.
The chart auto-refreshes every 10 seconds. After ~2 minutes the VWAP time-series builds up visibly.

---

#### Ports at a Glance

| Service | URL / Port | Credentials |
|---|---|---|
| Kafka-UI | `http://localhost:8080` | none |
| TimescaleDB | `localhost:5433` | crypto / crypto_secret |
| Grafana | `http://localhost:3001` | admin / admin |

---

### Data Flow Summary — One Event, End to End

```
1. Binance emits a trade at 14:32:07.843 UTC
   {"e":"trade","s":"BTCUSDT","p":"67420.50","q":"0.012","T":1714654327843,...}

2. ws_consumer.py receives it at 14:32:07.851 UTC  (+8 ms latency)
   → adds ingestion_timestamp = "2024-05-02T14:32:07.851Z"
   → produces to Kafka topic binance.trades, partition 0 (BTCUSDT key)

3. Kafka stores the message (7-day retention)

4. worker.py polls and accumulates in trades_buffer
   After 1 second or 20 messages (subset config):
   → bulk INSERT into trades table
   → commits Kafka offset  (no data loss on crash from this point)

5. streaming_job.py reads from Kafka (parallel, independent offset)
   → 1-min tumbling window [14:32:00–14:33:00] accumulating
   → every 10 seconds: upserts to trade_metrics
     vwap=67415.22, trade_count=143, volatility_alert=False

6. Grafana queries trade_metrics every 10s
   → VWAP line chart updates with new point at 14:32:00

7. If volatility_alert becomes True, Grafana fires an email alert.
```

---

### Full Pipeline Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BINANCE EXCHANGE                            │
│                                                                     │
│   BTCUSDT ──┐                                                       │
│   ETHUSDT ──┼──  9 streams  (3 symbols × 3 types)                  │
│   BNBUSDT ──┘   trade │ aggTrade │ bookTicker                       │
└─────────────────────┬───────────────────────────────────────────────┘
                      │  WebSocket (1 persistent connection)
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
                              │  confluent-kafka  │  lz4  │  batch 1 000
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         KAFKA BROKER  :9092                         │
│                                                                     │
│   Topic: binance.trades          Topic: binance.book_ticker         │
│   ├── Partition 0  (BTCUSDT)     ├── Partition 0  (BTCUSDT)        │
│   ├── Partition 1  (ETHUSDT)     ├── Partition 1  (ETHUSDT)        │
│   └── Partition 2  (BNBUSDT)     └── Partition 2  (BNBUSDT)        │
│                                                                     │
│   ✦ Ordered per symbol  (partition key = symbol)                    │
│   ✦ 7-day retention                                                 │
│   ✦ Absorbs traffic spikes — decouples producer from consumer       │
└─────────────────────────────┬───────────────────────────────────────┘
              ┌───────────────┴───────────────┐
              ▼ Phase 2                        ▼ Phase 3
┌─────────────────────────┐     ┌──────────────────────────────────┐
│  BUFFERING              │     │  STREAM PROCESSING               │
│  consumer/worker.py     │     │  spark/streaming_job.py          │
│                         │     │                                  │
│  Poll every 1s          │     │  Query 1 — Trade Metrics         │
│  Batch: 500 msgs / 2s   │     │    Window : 1-min tumbling       │
│  Bulk INSERT            │     │    Trigger: every 10 s           │
│  ON CONFLICT DO NOTHING │     │    Output : trade_metrics table  │
│  Commit offset (safe)   │     │    VWAP, stddev, count, alerts   │
│                         │     │                                  │
│  ✦ Health-check :8082   │     │  Query 2 — Spread Metrics        │
└──────────┬──────────────┘     │    Window : 30-sec tumbling      │
           │                    │    Trigger: every 10 s           │
           │                    │    Output : spread_metrics table │
           │                    │    avg/max/min spread, warning   │
           │                    │                                  │
           │                    │  ✦ Event-time watermark (10 s)   │
           │                    │  ✦ ON CONFLICT … DO UPDATE       │
           │                    │  ✦ Checkpoint recovery           │
           └──────────┬─────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       TIMESCALEDB  :5433                            │
│                                                                     │
│   trades          (hypertable, 1-day chunks)                        │
│   book_ticker     (hypertable, 1-day chunks)                        │
│   trade_metrics   (vwap, stddev, count, volatility_alert, ...)      │
│   spread_metrics  (avg/max/min spread, spread_warning)              │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          GRAFANA  :3001                             │
│                                                                     │
│   Market Overview dashboard                                         │
│     VWAP time-series per symbol                                     │
│     Trade count bar gauge                                           │
│     Avg bid-ask spread line                                         │
│                                                                     │
│   Risk Monitor dashboard                                            │
│     Volatility alerts stat                                          │
│     Volume spike stat                                               │
│     Spread warnings stat                                            │
│     Anomaly events table                                            │
│                                                                     │
│   Alerting (evaluated every 30 s):                                  │
│     VolatilityAlert — fires when stddev > 2.0                       │
│     SpreadWarning   — fires when avg_spread > 3 × min_spread        │
│     → Email notification via SMTP                                   │
│                                                                     │
│   ✦ Auto-refresh every 10 s                                         │
│   ✦ All config provisioned as code (YAML + JSON)                    │
└─────────────────────────────────────────────────────────────────────┘
```
