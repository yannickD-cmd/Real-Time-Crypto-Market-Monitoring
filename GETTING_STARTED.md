"""
PROJECT STRUCTURE AND GETTING STARTED GUIDE

This file provides a comprehensive overview of the ingestion service structure
and quick-start instructions.
"""

PROJECT_STRUCTURE = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║         BINANCE REAL-TIME INGESTION SERVICE - PROJECT STRUCTURE              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

ingestion/
│
├── 📄 README.md                              # Main documentation
├── 📄 ARCHITECTURE.md                        # Detailed architecture document
├── 📄 requirements.txt                       # Python dependencies
├── 📄 .env                                   # Environment variables (local)
├── 📄 .env.example                           # Environment template
├── 📄 Dockerfile                             # Docker container definition
├── 📄 docker-compose.yml                     # Docker Compose for full stack
│
├── 🔧 main.py                                # Service entry point
├── 🔧 setup_kafka.py                         # Kafka topic initialization
├── 🔧 quickstart.py                          # Quick start guide
├── 🔧 monitoring.py                          # Metrics and monitoring utilities
├── 🔧 consumer_example.py                    # Example Kafka consumer
│
├── 📁 config/                                # Configuration management
│   ├── __init__.py
│   └── settings.py                           # Pydantic settings (BinanceConfig, KafkaConfig, etc.)
│
├── 📁 src/                                   # Source code
│   ├── __init__.py
│   ├── logger.py                             # Structured logging setup
│   ├── binance_client.py                     # Main WebSocket client (CORE)
│   └── kafka_producer.py                     # Kafka producer wrapper (CORE)
│
└── 📁 tests/                                 # Unit tests
    ├── conftest.py                           # Pytest configuration
    └── test_ingestion.py                     # Test suite


CORE COMPONENTS EXPLAINED:

1️⃣  binance_client.py (444 lines)
    ════════════════════════════════════════════════════════════════════
    Main component: BinanceWebSocketClient
    
    Features:
    • Multi-stream WebSocket subscription to Binance
    • Automatic reconnection with exponential backoff
    • Event enrichment (timestamps, metadata, event type mapping)
    • Message batching (configurable size and timeout)
    • Thread-safe in-memory buffering
    • Graceful shutdown on signals
    • Comprehensive metrics collection
    
    Key Methods:
    • connect()                    - Establish WebSocket connection
    • run()                        - Main async loop with auto-reconnect
    • start_in_background()        - Run in background thread
    • stop()                       - Graceful shutdown
    • get_metrics()                - Retrieve performance metrics
    
    Configuration:
    • BINANCE_SYMBOLS              - Trading pairs to monitor
    • BINANCE_STREAM_TYPES         - Event types (aggTrade, depth, etc)
    • RECONNECT_INTERVAL           - Base reconnect delay (5s default)
    • MAX_RETRIES                  - Max reconnection attempts (5 default)
    • BATCH_SIZE                   - Messages per batch (100 default)
    • BATCH_TIMEOUT_SECONDS        - Batch flush timeout (5s default)


2️⃣  kafka_producer.py (233 lines)
    ════════════════════════════════════════════════════════════════════
    Main component: MarketEventProducer
    
    Features:
    • JSON serialization of market events
    • Snappy compression for efficient transport
    • Async callbacks for success/error handling
    • Automatic retry (3 attempts)
    • Topic routing by event type
    • Partition key selection (Symbol for ordering)
    • Producer metrics tracking
    
    Key Methods:
    • send_event()                 - Send single event to Kafka
    • send_batch()                 - Send batch of events
    • flush()                      - Force pending message flush
    • close()                      - Graceful shutdown
    • get_metrics()                - Retrieve producer metrics
    
    Kafka Configuration:
    • KAFKA_BOOTSTRAP_SERVERS      - Broker addresses
    • KAFKA_TOPIC_RAW_EVENTS       - Raw events topic
    • KAFKA_TOPIC_TRADES           - Trade events topic
    • KAFKA_TOPIC_DEPTH            - Depth updates topic
    • KAFKA_PARTITIONS             - Number of partitions (3 default)
    • KAFKA_COMPRESSION            - Compression type (snappy default)


3️⃣  config/settings.py (101 lines)
    ════════════════════════════════════════════════════════════════════
    Configuration Management using Pydantic
    
    Classes:
    • BinanceConfig               - Binance API settings
    • KafkaConfig                 - Kafka broker settings
    • ConnectionConfig            - Retry and batching settings
    • LoggingConfig               - Logging configuration
    • Settings                    - Master settings class
    
    Features:
    • Type validation
    • Environment variable loading
    • Default values
    • Centralized configuration


4️⃣  src/logger.py (65 lines)
    ════════════════════════════════════════════════════════════════════
    Structured Logging Setup
    
    Features:
    • JSON-formatted logs
    • Context-aware logging
    • Exception capture with stack traces
    • Integration with structlog
    
    Functions:
    • setup_logging()              - Initialize logging system
    • get_logger()                 - Get logger instance
    • LogContext                   - Context manager for operation logging


================================================================================
QUICK START GUIDE
================================================================================

OPTION 1: Docker Compose (Recommended for Development)
─────────────────────────────────────────────────────────────────────────────

1. Start all services:
   $ docker-compose up -d
   
   This starts:
   • Zookeeper (metadata storage)
   • Kafka broker (message queue)
   • Kafka UI (web interface at http://localhost:8080)
   • Binance ingestion service

2. View logs:
   $ docker-compose logs -f binance-ingestion

3. Access Kafka UI:
   Open http://localhost:8080 in your browser
   
4. Inspect topics:
   $ docker exec ingestion_kafka_1 kafka-topics --list --bootstrap-server localhost:29092

5. View messages:
   $ docker exec ingestion_kafka_1 kafka-console-consumer \\
       --bootstrap-server localhost:29092 \\
       --topic binance-trades \\
       --from-beginning \\
       --max-messages 5

6. Stop services:
   $ docker-compose down


OPTION 2: Local Development with Python
─────────────────────────────────────────────────────────────────────────────

Prerequisites:
• Python 3.11+
• Kafka and Zookeeper running (docker-compose up -d kafka zookeeper)

1. Create virtual environment:
   $ python -m venv venv
   $ source venv/bin/activate          # macOS/Linux
   # OR
   $ venv\\Scripts\\activate            # Windows

2. Install dependencies:
   $ pip install -r requirements.txt

3. Copy and edit configuration:
   $ cp .env.example .env
   # Edit .env with your settings

4. Initialize Kafka topics:
   $ python setup_kafka.py

5. Run the service:
   $ python main.py

6. In another terminal, consume messages:
   $ python consumer_example.py trades 10


OPTION 3: Production Kubernetes Deployment
─────────────────────────────────────────────────────────────────────────────

(Coming in next phase - manifests for ConfigMaps, Services, Deployments)


================================================================================
ENVIRONMENT CONFIGURATION
================================================================================

Key variables in .env:

# Binance symbols to monitor (comma-separated)
BINANCE_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,XRPUSDT

# WebSocket stream types
BINANCE_STREAM_TYPES=aggTrade,depth@100ms,trade,kline_1m

# Kafka broker addresses
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Kafka topics for different event types
KAFKA_TOPIC_RAW_EVENTS=binance-raw-events
KAFKA_TOPIC_TRADES=binance-trades
KAFKA_TOPIC_DEPTH=binance-depth

# Connection resilience
RECONNECT_INTERVAL=5          # Base reconnect delay (seconds)
MAX_RETRIES=5                 # Max reconnection attempts
BATCH_SIZE=100                # Messages per batch
BATCH_TIMEOUT_SECONDS=5       # Batch flush timeout

# Logging
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json               # json or text


================================================================================
TESTING
================================================================================

Run unit tests:
$ pytest tests/ -v

Run with coverage:
$ pytest tests/ --cov=src --cov=config

Individual test files:
$ pytest tests/test_ingestion.py::TestBinanceWebSocketClient -v


================================================================================
MONITORING & DEBUGGING
================================================================================

View service metrics (logged every 30 seconds):
$ docker-compose logs binance-ingestion | grep service_metrics

Example metric output:
{
  "level": "info",
  "event": "service_metrics",
  "messages_received": 45000,
  "messages_processed": 45000,
  "messages_buffered": 5,
  "connected": true,
  "reconnect_count": 0
}

Inspect Kafka topics:
$ docker exec kafka kakfa-topics --list --bootstrap-server localhost:29092

Check topic configuration:
$ docker exec kafka kafka-topics --describe \\
    --topic binance-trades \\
    --bootstrap-server localhost:29092


================================================================================
ARCHITECTURE FLOW
================================================================================

                  ┌──────────────────┐
                  │   Binance API    │
                  │   WebSocket      │
                  └────────┬─────────┘
                           │
                    Raw market events
                    (JSON bytes)
                           │
                           ▼
         ┌─────────────────────────────────────┐
         │  BinanceWebSocketClient             │
         │  - Multi-stream subscription        │
         │  - Auto reconnect                   │
         │  - Event enrichment                 │
         │  - Batching (100 msgs / 5 sec)      │
         └─────────────────┬───────────────────┘
                           │
                  Enriched JSON events
                  (with timestamps)
                           │
                           ▼
         ┌─────────────────────────────────────┐
         │  MarketEventProducer                │
         │  - Kafka serialization              │
         │  - Compression (snappy)             │
         │  - Topic routing                    │
         │  - Error handling & retry           │
         └─────────────────┬───────────────────┘
                           │
                ┌──────────┼──────────┐
                │          │          │
                ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ RAW      │ │ TRADES   │ │ DEPTH    │
        │ EVENTS   │ │ TOPIC    │ │ TOPIC    │
        │ TOPIC    │ │          │ │          │
        └──────────┘ └──────────┘ └──────────┘

Downstream (ready for Phase 2):
- PySpark Streaming for real-time aggregations
- Delta Lake for time-travel queries
- Grafana for dashboards


================================================================================
TROUBLESHOOTING
================================================================================

Issue: WebSocket connection refused
├─ Check Binance is accessible: curl https://stream.binance.com
├─ Verify network/firewall settings
└─ Check logs for detailed error

Issue: Kafka broker not found
├─ Ensure Kafka is running: docker-compose up kafka
├─ Check KAFKA_BOOTSTRAP_SERVERS in .env
├─ Verify Docker network connectivity

Issue: Topics not created
├─ Run manually: python setup_kafka.py
├─ Check Kafka broker status
├─ Verify topic creation permissions

Issue: Memory usage too high
├─ Reduce BATCH_SIZE to 50 or 25
├─ Increase BATCH_TIMEOUT_SECONDS to 10
├─ Reduce number of BINANCE_SYMBOLS

Issue: Message processing is slow
├─ Check Kafka broker capacity
├─ Verify network bandwidth
├─ Increase BATCH_SIZE to 200
├─ Scale to multiple consumer instances


================================================================================
SUCCESS INDICATORS
================================================================================

✅ Service started successfully:
   - "ingestion_service_initialized" log message
   - No connection errors in logs

✅ WebSocket connected:
   - "websocket_connected" log message
   - Connection status shows "true" in metrics

✅ Data flowing:
   - "service_metrics" logged every 30 seconds
   - messages_received > 0
   - messages_processed > 0

✅ Kafka working:
   - Messages visible in Kafka UI (http://localhost:8080)
   - Console consumer shows events
   - Topic metrics show message counts


================================================================================
NEXT STEPS
================================================================================

1. Monitor the ingestion service
   - Check metrics in logs every 30 seconds
   - Access Kafka UI to see message flow

2. Verify Kafka topics are receiving data
   - Use consumer_example.py to inspect messages
   - Sample events from different topic types

3. Scale the configuration
   - Add more symbols: LTCUSDT, DOTUSDT, etc.
   - Add more stream types: spot@balance, listenKey updates
   - Increase partitions for parallel processing

4. Prepare for Phase 2: PySpark Processing
   - Design aggregation windows (1m, 5m, 1h)
   - Plan feature engineering (volume spikes, volatility)
   - Set up Delta Lake storage

5. Monitor in production
   - Set up alerting on connection failures
   - Track message lag (Kafka lag monitoring)
   - Monitor resource usage (CPU, memory, network)

"""

GETTING_STARTED = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║     BINANCE REAL-TIME INGESTION - GETTING STARTED IN 5 MINUTES               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

FASTEST START (Docker Compose):
═════════════════════════════════════════════════════════════════════════════

1. Start all services:
   
   $ cd ingestion
   $ docker-compose up -d
   
   ✓ Zookeeper started on port 2181
   ✓ Kafka started on port 9092
   ✓ Kafka UI running on http://localhost:8080
   ✓ Binance ingestion service started and connecting
   

2. Wait 10 seconds for connection, then check status:
   
   $ docker-compose logs binance-ingestion
   
   Look for:
   "ingestion_service_initialized"
   "websocket_connected"
   

3. View messages in Kafka UI:
   
   Open http://localhost:8080 in browser
   ↓
   Click "Topics" in left menu
   ↓
   Select "binance-trades" topic
   ↓
   Scroll to Messages section
   ↓
   Click "Fetch messages" - you should see real-time trades!
   

4. Test with consumer script:
   
   $ python consumer_example.py trades 10
   
   Example output:
   [1] BTCUSDT: 0.5 @ 45000.00
   [2] ETHUSDT: 2.0 @ 2500.00
   [3] BNBUSDT: 10.0 @ 300.00
   ...
   

5. Monitor metrics (every 30 seconds):
   
   $ docker-compose logs -f binance-ingestion | grep service_metrics
   
   Example output:
   {
     "messages_received": 45000,
     "messages_processed": 45000,
     "connected": true
   }
   

6. Stop when done:
   
   $ docker-compose down
   
   All containers shut down gracefully


═════════════════════════════════════════════════════════════════════════════════

WHAT'S HAPPENING BEHIND THE SCENES:

  Binance WebSocket (50K+ msg/sec)
           ↓ [parsed, enriched]
  Python WebSocket Client
           ↓ [batched: 100 msgs or 5 sec]
  In-Memory Buffer
           ↓
  Kafka Producer
           ↓
  Kafka Broker (3 topics with compression)
           ↓
  Ready for downstream processing (PySpark, etc.)


═════════════════════════════════════════════════════════════════════════════════

KEY FILES TO UNDERSTAND:

  src/binance_client.py (444 lines) - Main WebSocket client
    ├─ Connects to Binance streams
    ├─ Handles reconnections automatically
    ├─ Buffers and batches messages
    └─ Sends to Kafka producer

  src/kafka_producer.py (233 lines) - Kafka producer
    ├─ Serializes events to JSON
    ├─ Routes to appropriate topics
    ├─ Handles errors and retries
    └─ Tracks metrics

  main.py - Entry point
    ├─ Initializes configuration
    ├─ Starts WebSocket client
    ├─ Logs metrics every 30 seconds
    └─ Handles shutdown signals


═════════════════════════════════════════════════════════════════════════════════

CUSTOMIZATION:

Edit .env file to:

1. Add more symbols:
   BINANCE_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,XRPUSDT,LTCUSDT,DOTUSDT

2. Change stream types:
   BINANCE_STREAM_TYPES=aggTrade,depth@100ms

3. Adjust batching:
   BATCH_SIZE=200
   BATCH_TIMEOUT_SECONDS=10

4. Change log verbosity:
   LOG_LEVEL=DEBUG


═════════════════════════════════════════════════════════════════════════════════

NEXT: EXPLORE THE ARCHITECTURE

  Read: ARCHITECTURE.md - for complete system design
  Read: README.md - for full documentation
  
  You're now ready to build Phase 2: PySpark Stream Processing! 🚀


"""

if __name__ == "__main__":
    print(PROJECT_STRUCTURE)
    print("\n\n")
    print(GETTING_STARTED)
