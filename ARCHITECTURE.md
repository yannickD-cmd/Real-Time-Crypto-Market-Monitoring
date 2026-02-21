"""Architecture and Design Document for Binance Ingestion Service."""

ARCHITECTURE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              BINANCE REAL-TIME STREAMING PIPELINE - PHASE 1                  ║
║                      Python Ingestion Layer                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│ COMPLETE STREAM ARCHITECTURE                                                │
└─────────────────────────────────────────────────────────────────────────────┘

    Binance API Endpoints
    ┌─────────────────────┐
    │ Stream.binance.com  │
    │ (WebSocket)         │
    │ wss://stream:9443   │
    └──────────┬──────────┘
               │
               ├─→ BTCUSDT@aggTrade
               ├─→ ETHUSDT@aggTrade
               ├─→ BNBUSDT@depth@100ms
               ├─→ ADAUSDT@trade
               └─→ XRPUSDT@kline_1m
               │
               ▼
    ┌─────────────────────────────────────────────────┐
    │  Python WebSocket Client (binance_client.py)    │
    │  - Multi-stream subscription                    │
    │  - JSON event parsing                           │
    │  - Event enrichment (timestamps, metadata)      │
    │  - Message batching (100 msgs or 5s timeout)    │
    │  - Auto-reconnect (exp backoff: 5s, 10s, 20s)  │
    │  - Graceful shutdown                            │
    │  - Structured logging (JSON format)             │
    │  - Metrics collection                           │
    └──────────────────┬──────────────────────────────┘
                       │
                       ├─→ In-Memory Buffer (thread-safe)
                       │   ├─ Max 100 messages
                       │   ├─ 5 second timeout
                       │   └─ Lock-based synchronization
                       │
                       ▼
    ┌─────────────────────────────────────────────────┐
    │  Kafka Producer Wrapper (kafka_producer.py)     │
    │  - Batch sending (max_in_flight=5)              │
    │  - Snappy compression                           │
    │  - Acks=all (durability)                        │
    │  - Auto-retry (3 attempts)                      │
    │  - Async callbacks for success/failure          │
    │  - Producer metrics tracking                    │
    └──────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────────┐
    │ Kafka    │ │ Kafka    │ │ Kafka        │
    │ Topic:   │ │ Topic:   │ │ Topic:       │
    │ RAW-     │ │ TRADES   │ │ DEPTH        │
    │ EVENTS   │ │ (idx:    │ │ (idx: Symbol)│
    │ (7 days) │ │ Symbol)  │ │ (7 days)     │
    │ (3 part) │ │ (30 days)│ │ (3 part)     │
    │ (repl:1) │ │ (3 part) │ │ (repl:1)     │
    │          │ │ (repl:1) │ │              │
    └──────────┘ └──────────┘ └──────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ KEY COMPONENTS                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

1. BINANCE_CLIENT.PY
   - Multi-stream WebSocket subscription
   - Event enrichment with ingestion timestamps
   - Message buffering with batching strategy
   - Auto-reconnection with exponential backoff (max 5 attempts)
   - Graceful shutdown on SIGINT/SIGTERM

2. KAFKA_PRODUCER.PY
   - Batch message sending to Kafka
   - Topic routing by event type (trades, depth, raw)
   - Partition key selection (Symbol for consistency)
   - Callback-based async error handling
   - Producer metrics tracking

3. CONFIG/SETTINGS.PY
   - Pydantic-based configuration management
   - Environment variable loading (.env support)
   - Type validation and defaults
   - Binance, Kafka, and connection configs

4. SRC/LOGGER.PY
   - Structured logging (JSON format)
   - Context-aware logging with LogContext manager
   - Integration with structlog
   - Exception and traceback capture

5. MAIN.PY
   - Service orchestration
   - Signal handling (graceful shutdown)
   - Metrics reporting loop (30-second intervals)
   - Health monitoring

┌─────────────────────────────────────────────────────────────────────────────┐
│ DATA FLOW EXAMPLE                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

Binance Event (Raw):
{
    "e": "aggTrade",          # Event type
    "E": 1677000000000,       # Event time
    "s": "BTCUSDT",           # Symbol
    "a": 123456,              # Aggregate trade ID
    "p": "45000.00",          # Price
    "q": "0.5",               # Quantity
    "f": 123456,              # First trade ID
    "l": 123456,              # Last trade ID
    "T": 1677000000000,       # Trade time
    "m": false,               # Buyer is maker
    "M": true                 # Maker order
}

↓ ENRICHED BY INGESTION CLIENT ↓

{
    "e": "aggTrade",
    "E": 1677000000000,
    "s": "BTCUSDT",
    "a": 123456,
    "p": "45000.00",
    "q": "0.5",
    "f": 123456,
    "l": 123456,
    "T": 1677000000000,
    "m": false,
    "M": true,
    "ingestion_timestamp": 1677000000123,    # ← Added
    "source": "binance_websocket",            # ← Added
    "event_type": "aggregate_trade",          # ← Added (mapped)
    "pipeline_version": "1.0.0"               # ← Added
}

↓ SENT TO KAFKA TOPIC binance-trades ↓
   Partition Key: "BTCUSDT" (ensures ordering per symbol)

┌─────────────────────────────────────────────────────────────────────────────┐
│ CONFIGURATION PARAMETERS                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

BINANCE Configuration:
  - SYMBOLS: Trading pairs (BTCUSDT, ETHUSDT, ...)
  - STREAM_TYPES: aggTrade, depth@100ms, trade, kline_1m
  - WS_BASE_URL: wss://stream.binance.com:9443/ws

KAFKA Configuration:
  - BOOTSTRAP_SERVERS: localhost:9092 (single or comma-separated)
  - TOPIC_RAW_EVENTS: binance-raw-events (all events)
  - TOPIC_TRADES: binance-trades (trade events only)
  - TOPIC_DEPTH: binance-depth (depth updates only)
  - PARTITIONS: 3 (for parallel processing)
  - REPLICATION_FACTOR: 1-3 (for HA)
  - COMPRESSION: snappy (default; also gzip, lz4)

CONNECTION Configuration:
  - RECONNECT_INTERVAL: 5 seconds (base backoff)
  - MAX_RETRIES: 5 attempts
  - BATCH_SIZE: 100 messages per batch
  - BATCH_TIMEOUT_SECONDS: 5 second flush interval

LOGGING Configuration:
  - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR
  - LOG_FORMAT: json (structured) or text

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERROR HANDLING & RESILIENCE                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

1. WEBSOCKET FAILURES
   ├─ Auto-reconnect with exponential backoff
   │   ├─ Attempt 1: 5 seconds
   │   ├─ Attempt 2: 10 seconds
   │   ├─ Attempt 3: 20 seconds
   │   ├─ Attempt 4: 40 seconds
   │   ├─ Attempt 5: 80 seconds → FAIL (max 5)
   │   └─ Max backoff: 300 seconds (5 minutes)
   │
   └─ Metrics tracked: connection_failures, reconnect_count

2. KAFKA PRODUCER FAILURES
   ├─ Automatic retry (3 attempts)
   ├─ Callback error handling
   ├─ Per-message success/failure tracking
   ├─ Metrics: messages_failed, bytes_sent
   └─ Graceful degradation (log and continue)

3. MESSAGE PROCESSING ERRORS
   ├─ JSON parsing errors → logged, skipped
   ├─ Enrichment errors → logged, original message sent
   ├─ Buffer overflow → handled (timeout-based flush)
   └─ Structured logging with exception context

┌─────────────────────────────────────────────────────────────────────────────┐
│ MONITORING & OBSERVABILITY                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

METRICS (logged every 30 seconds):
  - messages_received: Total WebSocket messages received
  - messages_processed: Total messages sent to Kafka
  - messages_buffered: Current buffer size
  - kafka_produced: Total Kafka messages sent successfully
  - kafka_failed: Total Kafka send failures
  - connected: Current WebSocket connection status
  - reconnect_count: Number of reconnection attempts
  - last_message_time: Timestamp of last received message

LOGGING OUTPUT (JSON structured):
{
    "timestamp": "2024-02-22T10:00:00Z",
    "level": "info",
    "event": "service_metrics",
    "messages_received": 45000,
    "messages_processed": 45000,
    "messages_buffered": 5,
    "connected": true,
    "reconnect_count": 0
}

┌─────────────────────────────────────────────────────────────────────────────┐
│ DEPLOYMENT OPTIONS                                                          │
└─────────────────────────────────────────────────────────────────────────────┘

1. LOCAL DEVELOPMENT
   docker-compose up -d
   python main.py

2. DOCKER CONTAINERS
   docker build -t binance-ingestion:latest .
   docker run -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
              -e BINANCE_SYMBOLS=BTCUSDT,ETHUSDT \
              binance-ingestion:latest

3. KUBERNETES (Future)
   kubectl apply -f deployment.yaml
   - ConfigMaps for configuration
   - StatefulSet for Kafka
   - Deployment for ingestion service

┌─────────────────────────────────────────────────────────────────────────────┐
│ PERFORMANCE CHARACTERISTICS                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Throughput (per second):
  - WebSocket connections: ~50,000 messages/sec (typical)
  - Kafka sends: Batched (100 msgs → 1 request)
  - Network I/O: ~5-10 MB/sec (with compression)

Latency:
  - WebSocket→Buffer: <1ms
  - Buffer→Kafka: varies (5-second batch timeout)
  - End-to-end: 50-100ms typical (at batch timeout)

Resource Usage:
  - Memory: ~100MB idle, ~500MB under load (3 symbols, default config)
  - CPU: ~10-20% single core (2024+ CPU)
  - Network: ~1-2 Mbps bandwidth per symbol

Scalability:
  - 1 instance: 3-5 symbols comfortably
  - 5 instances: 50+ symbols with distributed brokers
  - Kafka: 3 node cluster recommended for HA

┌─────────────────────────────────────────────────────────────────────────────┐
│ NEXT PHASES                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Phase 2: Stream Processing (PySpark)
  - Aggregate trades → VWAP, volume profiles
  - Detect volume spikes (>2σ deviation)
  - Calculate volatility (rolling standard deviation)
  - Order book imbalance ratios

Phase 3: Storage (Delta Lake)
  - Append events to Delta tables
  - Partitioned by date and symbol
  - Time travel and schema evolution support
  - Data quality metrics

Phase 4: Real-time Alerts
  - Threshold-based alerting
  - Volume spike detection
  - Volatility surge alerts
  - Liquidity stress indicators

Phase 5: Visualization (Grafana)
  - Live price feeds with overlay metrics
  - Volume spike heat maps
  - Volatility term structure
  - Liquidity dashboard

"""

if __name__ == "__main__":
    print(ARCHITECTURE)
