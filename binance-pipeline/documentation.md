# Binance Ingestion Pipeline — Design Decisions

---

## 1. WebSocket over REST polling

Binance streams are push-based. REST polling would add artificial latency (you only know about a trade after you ask), waste quota on empty responses, and create bursty load. A persistent WebSocket connection receives every event the instant the exchange emits it.

---

## 2. Combined-streams endpoint (`/stream?streams=…`)

Binance has two WebSocket modes:

| Mode | URL | Envelope |
|------|-----|----------|
| Single stream | `/ws/btcusdt@trade` | raw payload |
| Combined | `/stream?streams=btcusdt@trade/…` | `{"stream":"…","data":{…}}` |

Combined means **one TCP connection for all 9 streams** (3 symbols × 3 stream types). One connection = one place to manage reconnect, one set of ping/pong frames, no per-stream connection limit concerns.

The trade-off is a thin envelope wrapper — the `stream` field is used to route to the right Kafka topic, so it's not wasted.

---

## 3. Three stream types: `trade`, `aggTrade`, `bookTicker`

- **`trade`** — every individual fill. Needed for tick-level reconstruction.
- **`aggTrade`** — fills from the same taker order collapsed into one event. Lower volume, useful for downstream aggregations without losing price/size accuracy.
- **`bookTicker`** — best bid/ask update on every change. Required for spread monitoring and mid-price calculations without subscribing to the full order book.

They go to two topics because: trades (`trade` + `aggTrade`) share a schema and have the same consumers; book ticker has a completely different schema and different consumers. Mixing them in one topic would force every consumer to deserialize and discard events it doesn't need.

---

## 4. `ingestion_timestamp` injected at receipt

Binance events carry an **event time** (`E`) set by Binance's servers and a **trade time** (`T`) set at matching. Neither tells you when your process received the message. `ingestion_timestamp` is stamped at the moment `json.loads` returns, making it possible to measure:

- **Pipeline latency**: `ingestion_timestamp - E` = network + serialisation delay.
- **Consumer lag**: downstream processing time - `ingestion_timestamp`.

Without this field the pipeline is a black box.

---

## 5. Partition key = symbol

Kafka guarantees ordering only **within a partition**. If `BTCUSDT` events scatter across partitions, a consumer could process event at offset 5 before offset 3, breaking any stateful aggregation (e.g. VWAP, order-book state). Keying on symbol hashes each symbol deterministically to one partition, so:

- Per-symbol ordering is preserved end-to-end.
- Different symbols land on different partitions, so parallelism is preserved across the consumer group.

---

## 6. Three partitions per topic

3 symbols, 3 partitions. With murmur2 hashing (confluent-kafka default), each symbol maps to exactly one partition. Consumers in a group are assigned whole partitions — so up to 3 consumers can work in parallel with no symbol split across workers.

Partitions can only be increased, never decreased. Starting at 3 is the minimum that matches the workload. If more symbols are added later, the same 3 partitions absorb them (still ordered per symbol, parallelism per partition).

---

## 7. `acks=all`

Three settings exist:

| acks | Guarantee |
|------|-----------|
| `0` | Fire and forget — data loss on any failure |
| `1` | Leader wrote it — data loss if leader crashes before replication |
| `all` | Leader + all in-sync replicas confirmed — no data loss unless the entire ISR fails simultaneously |

This is a financial data pipeline. The cost of `acks=all` is a small increase in produce latency (~low ms with a single-broker local setup). The benefit is zero silent message loss.

---

## 8. Exponential backoff on reconnect

Immediate retry on disconnect would:
1. Hammer Binance's rate limiter → IP ban.
2. Produce a thundering-herd if multiple instances restart simultaneously.

Backoff starts at 1 s, doubles each failure, caps at 60 s. On a successful connection it resets to 1 s, so recovery after a brief blip is fast.

---

## 9. Health-check HTTP server (stdlib `http.server`)

The `_healthy` flag is `False` until the WebSocket connects. It flips back to `False` on any disconnect. An HTTP `GET /` returns:

- `200 ok` — connected and producing.
- `503 starting` — disconnected or backing off.

No extra dependency (stdlib only). Compatible with Docker `HEALTHCHECK`, Kubernetes liveness probes, and load-balancer health checks without any changes.

---

## 10. `confluent-kafka` over `kafka-python`

`confluent-kafka` wraps `librdkafka`, a C library. It handles:
- Batching, compression, and retry internally at C speed.
- `linger.ms` + `batch.num.messages` for throughput tuning without application-level buffering.
- Thread-safe producer that can be called from the async loop via `poll(0)` (non-blocking drain).

`kafka-python` is pure Python, single-threaded, and has known issues with async loops. At high tick rates (Binance trades can exceed 1 000/s per symbol) the difference is material.

---

## 11. `PLAINTEXT` + `PLAINTEXT_HOST` dual listeners

Docker containers address the broker as `kafka:29092` (internal Docker DNS). The host machine addresses it as `localhost:9092`. A single `PLAINTEXT://localhost:9092` listener breaks container-to-container communication because `localhost` inside a container resolves to the container itself, not the broker.

Two listeners solve this without any application-level branching:

| Listener | Used by |
|----------|---------|
| `PLAINTEXT://kafka:29092` | kafka-init, kafka-ui, future containers |
| `PLAINTEXT_HOST://localhost:9092` | Python ingestion process on the host |

---

## 12. `kafka-init` one-shot container

Topics must exist before the producer's first `produce()` call, or Kafka auto-creates them with default settings (1 partition, which breaks the 3-partition requirement).

A one-shot container runs `kafka-topics --create --if-not-exists` after `cub kafka-ready` confirms the broker is up, then exits. This is idempotent — running `docker compose up` a second time is safe because `--if-not-exists` is a no-op for already-created topics.

---

## 13. Topics & Partitions — full routing map

```
Binance WebSocket (1 connection, 9 streams)
│
├── btcusdt@trade      ─┐
├── ethusdt@trade      ─┤
├── bnbusdt@trade      ─┤
├── btcusdt@aggTrade   ─┼──▶  Topic: binance.trades
├── ethusdt@aggTrade   ─┤      ├── Partition 0  →  [BTCUSDT events, ordered]
├── bnbusdt@aggTrade   ─┘      ├── Partition 1  →  [ETHUSDT events, ordered]
│                               └── Partition 2  →  [BNBUSDT events, ordered]
├── btcusdt@bookTicker ─┐
├── ethusdt@bookTicker ─┼──▶  Topic: binance.book_ticker
└── bnbusdt@bookTicker ─┘      ├── Partition 0  →  [BTCUSDT events, ordered]
                                ├── Partition 1  →  [ETHUSDT events, ordered]
                                └── Partition 2  →  [BNBUSDT events, ordered]
```

**Topic** = what type of data. Split by schema and consumer need:
- `binance.trades` — trade fills (`trade` + `aggTrade` share the same shape: price, quantity, time).
- `binance.book_ticker` — best bid/ask updates (different shape: bid price, bid qty, ask price, ask qty).

**Partition** = who the data is about. Split by symbol via murmur2 hash of the key:
- Each symbol always lands on the same partition → ordering guaranteed per symbol.
- The hash decides which partition number (0, 1, or 2) — not manually assigned.

| Dimension | Split by | Reason |
|-----------|----------|--------|
| **Topic** | Event type | Different schemas, different consumers. A VWAP calculator doesn't need book tickers. A spread monitor doesn't need trades. |
| **Partition** | Symbol | Ordering per symbol. Parallel processing across symbols. One consumer can own one or more partitions independently. |

### Why hash-based partitioning, not explicit (one symbol = one partition)?

1. **Scales without code changes** — add a new symbol to `.env`, Kafka distributes it automatically. No partition map to maintain.
2. **No manual load balancing** — with 20+ symbols the hash spreads them across partitions evenly without you deciding which goes where.
3. **Works with Kafka's ecosystem** — consumer groups, log compaction, and Kafka Streams all expect key-based partitioning. Explicit partition assignment bypasses the key and breaks downstream tooling.
4. **Decoupled from internals** — your producer doesn't need to know how many partitions exist. If you increase from 3 to 6, hashing adapts (existing keys may remap, but no code rewrite needed).

Explicit assignment would only be better if you had a fixed, permanent set of symbols and needed guaranteed isolation (e.g. regulatory requirement that BTCUSDT never shares a partition). That's not this use case.

---

## File map

| File | Responsibility |
|------|----------------|
| `ingestion/config.py` | All env-driven config in one place — nothing is hardcoded elsewhere |
| `ingestion/ws_consumer.py` | WebSocket loop, event enrichment, topic routing, backoff, health server |
| `ingestion/kafka_producer.py` | Thin wrapper over confluent-kafka; topic is a parameter not a property |
| `docker/docker-compose.yml` | Broker + ZooKeeper + topic init + UI |
| `.env` | Runtime overrides — never committed with secrets |

---

# Phase 2 — Buffering Layer (Kafka → TimescaleDB)

---

## 15. Why a separate consumer layer

Kafka already acts as a buffer between Binance and everything downstream. The consumer layer drains that buffer at a controlled pace and writes to a database. Decoupling ingestion from storage means:

- A slow DB write does not block the WebSocket or cause Binance to close the connection.
- A consumer crash replays from the last committed offset — no data is lost.
- Ingestion and storage can be scaled and restarted independently.

---

## 16. Batch accumulation before writing (500 msgs or 2 s)

Writing one row to TimescaleDB per Kafka message would mean thousands of individual `INSERT` round-trips per second. Each round-trip adds network + lock overhead. Instead, messages are held in memory and flushed as a single `execute_values` bulk `INSERT` when either:

1. **500 messages** have accumulated (size cap — prevents unbounded memory use during traffic spikes), or
2. **2 seconds** have elapsed since the last flush (time cap — ensures data is never more than 2 s stale on low-volume periods).

One bulk `INSERT` per batch = one DB round-trip instead of 500. At Binance tick rates this is the difference between the DB keeping up and falling behind indefinitely.

---

## 17. At-least-once delivery via manual offset commit

`enable.auto.commit = False`. Offsets are committed **only after** a successful DB write:

```
poll message → accumulate → flush to DB → commit offset
```

If the process crashes between flush and commit, the same messages are re-delivered on restart. The DB write must therefore be idempotent — see §18. If the process crashes before flush, no data is lost and no offset is advanced.

`auto.offset.reset = latest`: on first run (no prior committed offset) the consumer starts from the current head of the topic, not the beginning. This avoids replaying hours of backlog on initial deployment.

---

## 18. Idempotent writes with `ON CONFLICT DO NOTHING`

Because of at-least-once delivery, the same Kafka message can be written twice (after a restart). The unique constraints prevent duplicate rows silently:

| Table | Unique constraint |
|-------|-------------------|
| `trades` | `(event_time, symbol, trade_id)` |
| `book_ticker` | `(ingestion_timestamp, symbol, update_id)` |

`ON CONFLICT DO NOTHING` skips any row that already exists rather than raising an error or overwriting data. The partition column (`event_time` / `ingestion_timestamp`) must be included in the unique constraint because TimescaleDB enforces uniqueness per chunk — a constraint without the time column would span all chunks and cannot be maintained by the hypertable engine.

---

## 19. TimescaleDB hypertables

TimescaleDB extends PostgreSQL with **hypertables**: tables that are transparently partitioned into fixed time-interval chunks on disk. Benefits relevant here:

- Time-range queries (e.g. "all BTCUSDT trades in the last hour") touch only the relevant chunks, not the entire table.
- Old chunks can be compressed or dropped without touching live data.
- The interface is standard SQL — no new query language.

Both tables use **1-day chunks**, the TimescaleDB recommended default for high-frequency append-only data.

`NUMERIC(20, 8)` is used for prices and quantities rather than `FLOAT` — Binance sends values like `"63239.39000000"` as strings, and `NUMERIC` stores them exactly. Floating-point would introduce rounding errors on financial values.

---

## 20. Connection pool (`ThreadedConnectionPool`)

A single psycopg2 connection is re-used across flushes rather than opening and closing a connection per batch. `ThreadedConnectionPool(min=1, max=4)` keeps one live connection for the normal single-threaded worker with headroom for future parallelism. On exception, the connection is rolled back before being returned to the pool so it remains reusable.

---

## 21. `time.monotonic()` for flush timing

`time.time()` can go backward (NTP corrections, VM clock drift). A backward jump would make `now - last_flush` negative, disabling the time-based flush permanently until the next size-triggered flush. `time.monotonic()` is guaranteed to be strictly non-decreasing regardless of wall-clock adjustments.

---

---

## 22. PySpark Structured Streaming (Phase 3)

Phase 3 adds a **real-time analytics layer** on top of the raw data already stored by the consumer.

**Why PySpark instead of SQL queries on TimescaleDB?**
TimescaleDB is excellent for point-in-time lookups and historical aggregation, but Spark's Structured Streaming operates on the *live Kafka stream* — it reacts to each event as it arrives rather than polling the database. This means metrics are computed within seconds of the trade occurring, with no coupling to the consumer's write latency.

**Two streaming queries run in parallel:**

| Query | Source | Window | Output table |
|-------|--------|--------|-------------|
| Trade metrics | `binance.trades` | 1-minute tumbling | `trade_metrics` |
| Spread metrics | `binance.book_ticker` | 30-second tumbling | `spread_metrics` |

**`get_json_object` instead of `from_json` + schema:** Spark's SQL engine is case-insensitive. The Binance trade payload has two fields `e` (event type, string) and `E` (event time, integer) — identical after lowercasing. Using `from_json` with a `StructType` schema causes an `AMBIGUOUS_REFERENCE` error. `get_json_object("$.e")` / `get_json_object("$.E")` are evaluated with case-sensitive JSON path expressions, bypassing Spark's column resolution entirely.

**Event-time watermark (10 seconds):** Structured Streaming needs a timestamp column to assign events to windows and to know when a window is "done" (safe to emit). We derive `event_time` from Binance's `E` field (milliseconds → timestamp). The 10-second watermark means Spark waits up to 10 seconds past the window end before finalising that window's aggregate, accommodating minor out-of-order delivery.

**`foreachBatch` sink to TimescaleDB:** Spark's built-in JDBC sink does one INSERT per row. `foreachBatch` gives us a full DataFrame per micro-batch, so we call `df.collect()` once and use `psycopg2.execute_values` for a single bulk INSERT — same pattern as the consumer layer.

**`ON CONFLICT … DO UPDATE`:** The 10-second trigger fires multiple times per 1-minute window while the window is still open (partial aggregates in `update` output mode). Each trigger upserts the latest aggregate for that window, so the DB always has the most recent values.

**Anomaly flags:**
- `volatility_alert = True` when `price_stddev > config_multiplier` (default: 2.0). BTCUSDT regularly triggers this (high-dollar price variance), lower-priced symbols rarely do.
- `volume_spike` placeholder is `False` — true spike detection requires comparing the current window's volume against a rolling 5-minute baseline, which needs a stream-stream self-join or stateful processing. The column exists for downstream consumers.
- `spread_warning = True` when `avg_spread > spread_warning_multiplier × min_spread` (default: 3×). Flags widening spreads that indicate momentary illiquidity.

**Windows PySpark on Windows (the native library problem):** Spark's checkpoint manager calls `NativeIO$Windows.access0`, a JNI method in `hadoop.dll`, to check file permissions on the local filesystem. Without this DLL in the JVM's `java.library.path`, every streaming query fails at startup. The fix: copy `hadoop.dll` (and `winutils.exe`) into a directory that is already in the system PATH and therefore in `java.library.path` at JVM startup (`C:\Users\<user>\bin`). Placing them only in a dynamically-added PATH entry is unreliable because `java.library.path` is derived from the PATH at JVM launch, not from runtime modifications via `os.environ`.

---

---

# Phase 4 — Grafana Visualisation & Alerting

---

## 23. Why Grafana over a custom frontend

Grafana has a native PostgreSQL datasource plugin that speaks directly to TimescaleDB (which is PostgreSQL-compatible). That means zero ETL, zero sync jobs, zero extra services — the same rows Spark just upserted are immediately queryable via the standard `postgres` plugin. A custom frontend would need its own backend API, session management, chart library, and alert dispatcher. Grafana provides all of that out of the box, with a battle-tested alerting engine and SMTP integration.

---

## 24. Provisioning-as-code (YAML + JSON)

Grafana supports two setup modes:

| Mode | How |
|------|-----|
| Manual (UI) | Click through Connections → New datasource → save |
| Provisioning | Mount YAML/JSON files into `/etc/grafana/provisioning/` at container start |

Provisioning is used here because the pipeline must be reproducible with a single `docker compose up`. If you delete the container and recreate it, all datasources, dashboards, contact points, and alert rules reappear automatically — no re-clicking, no state stored only in Grafana's internal SQLite database.

The trade-off: provisioned dashboards are read-only in the UI by default (the JSON on disk is the source of truth). That is acceptable here — edits should go through the file.

---

## 25. Datasource UID `timescaledb`

Every dashboard panel and alert rule references the datasource by UID (`"uid": "timescaledb"`), not by name. Names can change; UIDs are stable. Hardcoding the UID in provisioning means no manual "select datasource" step when importing dashboards into a fresh Grafana instance.

---

## 26. Alert rule pipeline: Query → Reduce → Threshold

Grafana Unified Alerting requires a specific evaluation pipeline:

```
Step A — SQL query   →  returns a time_series or table
Step B — Reduce      →  collapses the series to a single scalar (e.g. last value)
Step C — Threshold   →  evaluates the scalar against a condition (e.g. > 0)
```

An alert rule with only A and C (skipping B) fails with `no variable specified` — Grafana cannot apply a threshold to a multi-row result set directly. Adding the `reduce` step (type `last`, dropNN mode to ignore nulls) bridges the gap. This is the minimum viable pipeline for SQL-backed alerts.

---

## 27. `env_file` vs YAML variable substitution for SMTP credentials

Docker Compose resolves `${VAR}` in the YAML at `docker compose up` time, reading from the `.env` file in the **same directory as `docker-compose.yml`** (i.e. `docker/`). The pipeline's `.env` lives one level up in `binance-pipeline/`. Two solutions:

1. Copy `.env` into `docker/` — breaks the project layout and risks accidental commits.
2. `env_file: ../.env` in the Grafana service definition — Docker reads the file and injects every `KEY=VALUE` line as a container environment variable **without needing YAML substitution**.

Solution 2 is used. Grafana natively picks up `GF_SMTP_*` environment variables, so naming the vars `GF_SMTP_HOST`, `GF_SMTP_USER`, etc. in `.env` means they are both:
- Injected by `env_file` into the container environment.
- Automatically recognised by Grafana's config loader (no extra `environment:` mapping needed).

---

## 28. Alert evaluation timing

| Setting | Value | Rationale |
|---------|-------|-----------|
| `interval` (group) | 30 seconds | Spark emits partial aggregates every 10 s; 30 s gives three data points per evaluation — enough signal without over-firing |
| `for` (rule) | 1 minute | Prevents a single anomalous window from sending an email. The condition must hold for a full minute (two consecutive 30 s evaluations) before the alert fires |

The `for` duration is the standard way to avoid alert flapping on transient spikes.

---

## 29. `noDataState: OK` on alert rules

If TimescaleDB has no qualifying rows (e.g. no `volatility_alert=true` events in the last minute), the SQL query returns zero rows. `noDataState: OK` treats this as a resolved condition rather than firing a `NoData` alert. The intent is: silence = everything is fine. An alternative (`noDataState: Alerting`) would fire when the Spark job is stopped or the DB is empty, which would generate false positives during normal maintenance.

---

## 30. Dashboard refresh and time range

Both dashboards use `refresh: "10s"` and `time: { from: "now-30m", to: "now" }`. Ten seconds matches the Spark trigger interval — refreshing faster would show the same data. Thirty minutes is a sliding window that always shows the most recent activity without needing to manually scroll the time range. Both values are configurable in the JSON.

---

## Updated file map

| File | Responsibility |
|------|----------------|
| `ingestion/config.py` | Ingestion env-driven config |
| `ingestion/ws_consumer.py` | WebSocket loop, enrichment, topic routing, backoff, health server |
| `ingestion/kafka_producer.py` | Thin confluent-kafka producer wrapper |
| `consumer/config.py` | Consumer + TimescaleDB env-driven config |
| `consumer/kafka_consumer.py` | confluent-kafka Consumer wrapper, manual offset commit |
| `consumer/db.py` | psycopg2 connection pool, bulk INSERT for both tables |
| `consumer/batch_writer.py` | In-memory buffers, flush trigger logic (size + time) |
| `consumer/worker.py` | Main entry point, consume loop, signal handling, health server |
| `spark/streaming_job.py` | PySpark Structured Streaming: trade + spread windowed aggregation |
| `spark/config.yaml` | Anomaly flag thresholds (volume spike, volatility, spread) |
| `docker/docker-compose.yml` | Broker + ZooKeeper + topic init + UI + TimescaleDB + Grafana |
| `docker/init-db.sql` | Schema DDL: CREATE TABLE + hypertable conversion for all 4 tables |
| `docker/grafana/provisioning/datasources/timescaledb.yaml` | Auto-wires TimescaleDB as default datasource on container start |
| `docker/grafana/provisioning/dashboards/provider.yaml` | Tells Grafana where to load dashboard JSON files from |
| `docker/grafana/provisioning/alerting/contact_points.yaml` | Defines the email contact point (SMTP address from env) |
| `docker/grafana/provisioning/alerting/notification_policies.yaml` | Routes all alerts to the email contact point |
| `docker/grafana/provisioning/alerting/rules.yaml` | Two alert rules: VolatilityAlert and SpreadWarning |
| `docker/grafana/dashboards/market_overview.json` | Dashboard 1: VWAP, trade count, avg spread per symbol |
| `docker/grafana/dashboards/risk_monitor.json` | Dashboard 2: anomaly stat panels, alert timeline, events table |
| `.env` | Runtime overrides for all layers (SMTP credentials, DB passwords) |
| `.env.example` | Safe template — copy to `.env` and fill in real values |
