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
| `docker/docker-compose.yml` | Broker + ZooKeeper + topic init + UI + TimescaleDB |
| `docker/init-db.sql` | Schema DDL: CREATE TABLE + hypertable conversion |
| `.env` | Runtime overrides for both layers |
