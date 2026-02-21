"""
DIRECTORY TREE - Complete Project Structure

This shows the complete file organization of the Binance Ingestion Service.
"""

DIRECTORY_TREE = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║        COMPLETE DIRECTORY TREE - BINANCE INGESTION SERVICE                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

ingestion/
│
├── 📚 DOCUMENTATION
│   ├── README.md ................................. Main documentation (252 lines)
│   ├── ARCHITECTURE.md ............................ System design (341 lines)
│   ├── GETTING_STARTED.md ......................... Quick start guide (387 lines)
│   ├── FEATURES.md ............................... Feature checklist (470 lines)
│   ├── PROJECT_SUMMARY.md ......................... Project summary (420 lines)
│   ├── FILE_MANIFEST.md .......................... This file manifest (280 lines)
│   └── DIRECTORY_TREE.md ......................... Directory tree (this file)
│
├── 🔧 APPLICATION ENTRY POINT
│   ├── main.py ................................... Service orchestration (102 lines)
│   │   ├─ setup_logging()
│   │   ├─ signal_handler()
│   │   ├─ shutdown()
│   │   └─ start_service()
│   │
│   ├── setup_kafka.py ............................. Kafka initialization (74 lines)
│   │   └─ create_topics()
│   │
│   ├── consumer_example.py ........................ Example consumer (152 lines)
│   │   ├─ consume_raw_events()
│   │   ├─ consume_trades()
│   │   └─ consume_depth()
│   │
│   └── monitoring.py ............................. Metrics utilities (89 lines)
│       ├─ ServiceMonitor class
│       └─ get_summary()
│
├── 📁 src/ ....................................... Source code package
│   ├── __init__.py ............................... Package exports
│   │
│   ├── binance_client.py .......................... WebSocket client (444 lines) ⭐
│   │   ├─ BinanceWebSocketClient
│   │   │  ├─ connect()
│   │   │  ├─ run()
│   │   │  ├─ start_in_background()
│   │   │  ├─ stop()
│   │   │  ├─ get_metrics()
│   │   │  ├─ _build_stream_url()
│   │   │  ├─ _on_message()
│   │   │  ├─ _enrich_event()
│   │   │  ├─ _check_and_flush()
│   │   │  ├─ _flush_buffer()
│   │   │  ├─ _on_error()
│   │   │  ├─ _on_close()
│   │   │  ├─ _on_open()
│   │   │  ├─ _handle_reconnect()
│   │   │  └─ Comprehensive metrics tracking
│   │   │
│   │   └─ Features:
│   │       • Multi-stream subscription
│   │       • Auto-reconnection (exponential backoff)
│   │       • Event enrichment & batching
│   │       • Thread-safe buffering
│   │       • Graceful shutdown
│   │       • Signal handling (SIGINT, SIGTERM)
│   │
│   ├── kafka_producer.py ......................... Kafka client (233 lines) ⭐
│   │   ├─ MarketEventProducer
│   │   │  ├─ send_event()
│   │   │  ├─ send_batch()
│   │   │  ├─ flush()
│   │   │  ├─ close()
│   │   │  ├─ get_metrics()
│   │   │  ├─ _create_producer()
│   │   │  ├─ _on_send_success()
│   │   │  └─ _on_send_error()
│   │   │
│   │   └─ Features:
│   │       • JSON serialization
│   │       • Compression (snappy/gzip)
│   │       • Topic routing
│   │       • Partition key (symbol)
│   │       • Async callbacks
│   │       • Error retry
│   │
│   └── logger.py ................................. Logging setup (65 lines)
│       ├─ setup_logging()
│       ├─ get_logger()
│       └─ LogContext (context manager)
│           ├─ __enter__()
│           └─ __exit__()
│
├── 📁 config/ .................................... Configuration package
│   ├── __init__.py ............................... Package exports
│   │
│   └── settings.py ............................... Configuration (101 lines)
│       ├─ BinanceConfig (Pydantic model)
│       │  ├── symbols: List[str]
│       │  ├── stream_types: List[str]
│       │  ├── api_baseurl: str
│       │  └── ws_base_url: str
│       │
│       ├─ KafkaConfig (Pydantic model)
│       │  ├── bootstrap_servers: List[str]
│       │  ├── topic_raw_events: str
│       │  ├── topic_trades: str
│       │  ├── topic_depth: str
│       │  ├── partitions: int
│       │  ├── replication_factor: int
│       │  └── compression: str
│       │
│       ├─ ConnectionConfig (Pydantic model)
│       │  ├── reconnect_interval: int
│       │  ├── max_retries: int
│       │  ├── batch_size: int
│       │  └── batch_timeout_seconds: int
│       │
│       ├─ LoggingConfig (Pydantic model)
│       │  ├── log_level: str
│       │  └── log_format: str
│       │
│       └─ Settings (master class)
│           ├── binance: BinanceConfig
│           ├── kafka: KafkaConfig
│           ├── connection: ConnectionConfig
│           └── logging: LoggingConfig
│
├── 🧪 tests/ ..................................... Test suite
│   ├── __init__.py (implicit)
│   │
│   ├── conftest.py ............................... Pytest config (5 lines)
│   │   └─ Project root setup
│   │
│   └── test_ingestion.py ......................... Unit tests (126 lines)
│       ├─ Fixtures:
│       │  ├── binance_config
│       │  ├── kafka_config
│       │  ├── connection_config
│       │  └── websocket_client
│       │
│       ├─ TestBinanceWebSocketClient
│       │  ├─ test_build_stream_url()
│       │  ├─ test_enrich_event()
│       │  ├─ test_message_buffering()
│       │  ├─ test_metrics()
│       │  └─ test_initial_state()
│       │
│       └─ TestMarketEventProducer
│           ├─ test_producer_creation()
│           └─ test_send_event()
│
├── 🐳 DEPLOYMENT
│   ├── Dockerfile ................................ Container image (18 lines)
│   │   ├─ FROM python:3.11-slim
│   │   ├─ System dependencies
│   │   ├─ Python dependencies
│   │   ├─ App code
│   │   ├─ Health check
│   │   └─ CMD: python main.py
│   │
│   └── docker-compose.yml ........................ Orchestration (51 lines)
│       ├─ Zookeeper service
│       ├─ Kafka broker service
│       ├─ Kafka UI (web interface)
│       ├─ Binance ingestion service
│       ├─ Environment variables
│       ├─ Service dependencies
│       ├─ Port mappings
│       ├─ Volumes
│       └─ Network bridging
│
├── ⚙️  CONFIGURATION
│   ├── .env ...................................... Local config (8 lines)
│   │   ├─ KAFKA_BOOTSTRAP_SERVERS
│   │   ├─ BINANCE_SYMBOLS
│   │   ├─ BINANCE_STREAM_TYPES
│   │   ├─ BATCH_SIZE
│   │   ├─ BATCH_TIMEOUT_SECONDS
│   │   ├─ LOG_LEVEL
│   │   └─ Other environment variables
│   │
│   ├── .env.example .............................. Config template (20 lines)
│   │   └─ All options with descriptions
│   │
│   └── requirements.txt .......................... Dependencies (7 packages)
│       ├─ websocket-client==1.7.0
│       ├─ kafka-python==2.0.2
│       ├─ pydantic==2.5.3
│       ├─ python-dotenv==1.0.0
│       ├─ structlog==24.1.0
│       ├─ prometheus-client==0.19.0
│       └─ requests==2.31.0
│
└── 📋 PROJECT FILES
    ├── .gitignore ............................... (implicit - to add)
    │   ├─ .env
    │   ├─ __pycache__/
    │   ├─ *.pyc
    │   ├─ venv/
    │   ├─ .pytest_cache/
    │   ├─ .coverage
    │   └─ *.log
    │
    └── .vscode/ ................................. (optional)
        ├─ settings.json
        ├─ launch.json
        └─ extensions.json


STATISTICS
════════════════════════════════════════════════════════════════════════════════

Directory Breakdown:
  • Root level: 8 configuration/setup files
                1 README
                1 PROJECT_SUMMARY
                1 FILE_MANIFEST
  • /src: 4 files (1,200+ lines of production code)
  • /config: 2 files (101 lines of configuration)
  • /tests: 2 files (135+ lines of tests)
  • Documentation: 6 files (1,450+ lines)
  • Deployment: 2 files (Docker config)

File Counts:
  • Python files (.py): 13
  • Documentation (.md): 6
  • Configuration: 3
  • Docker/Deployment: 2
  • Total: 24 files

Line Counts by Type:
  • Production code: 1,200+ lines
  • Documentation: 1,450+ lines
  • Tests: 135+ lines
  • Configuration: 50+ lines
  • Total: 2,835+ lines

Package Structure:
  • src/__init__.py ...................... Exports main classes
  • src/binance_client.py ............... WebSocket implementation
  • src/kafka_producer.py ............... Kafka implementation
  • src/logger.py ...................... Logging setup
  • config/__init__.py ................. Config exports
  • config/settings.py ................. Configuration models

Entry Points:
  • python main.py ..................... Start the service
  • python setup_kafka.py .............. Initialize topics
  • python consumer_example.py ......... Consume messages
  • docker-compose up -d ............... Docker deployment


DIRECTORY RELATIONSHIPS
════════════════════════════════════════════════════════════════════════════════

main.py
  ├─ imports: config.settings
  ├─ imports: src.logger
  ├─ imports: src.binance_client
  ├─ creates: BinanceWebSocketClient
  ├─ creates: MarketEventProducer
  └─ monitors: Metrics collection

src/binance_client.py
  ├─ imports: config.settings
  ├─ imports: src.logger
  ├─ imports: src.kafka_producer
  ├─ uses: websocket library
  └─ creates: MarketEventProducer instance

src/kafka_producer.py
  ├─ imports: config.settings
  ├─ imports: src.logger
  └─ uses: kafka library

config/settings.py
  ├─ Pydantic models
  ├─ Environment variable loading
  └─ Singleton: settings instance

src/logger.py
  ├─ uses: structlog library
  └─ provides: get_logger(), setup_logging()

tests/
  ├─ imports: config.settings
  ├─ imports: src.binance_client
  ├─ imports: src.kafka_producer
  └─ uses: pytest, unittest.mock

Dockerfile
  └─ executes: python main.py

docker-compose.yml
  ├─ services: zookeeper, kafka, kafka-ui
  ├─ depends_on: Proper ordering
  └─ runs: ./Dockerfile


KEY FEATURES BY LOCATION
════════════════════════════════════════════════════════════════════════════════

WebSocket Management:
  └─ src/binance_client.py
     ├─ Multi-stream subscription
     ├─ Auto-reconnection
     ├─ Event enrichment
     ├─ Message buffering
     └─ Graceful shutdown

Message Processing:
  ├─ src/binance_client.py
  │  └─ Event enrichment, buffering, batching
  └─ src/kafka_producer.py
     └─ Serialization, compression, topic routing

Configuration Management:
  └─ config/settings.py
     ├─ Pydantic models
     ├─ Environment variables
     └─ Type validation

Logging & Monitoring:
  ├─ src/logger.py
  │  └─ Structured logging setup
  ├─ main.py
  │  └─ Metrics reporting loop
  └─ monitoring.py
     └─ Metrics export utilities

Error Handling:
  ├─ src/binance_client.py
  │  ├─ WebSocket errors
  │  └─ Reconnection logic
  └─ src/kafka_producer.py
     ├─ Send failures
     └─ Retry callbacks

Deployment:
  ├─ Dockerfile
  │  └─ Container image
  ├─ docker-compose.yml
  │  └─ Full stack orchestration
  └─ requirements.txt
     └─ Python dependencies


────────────────────────────────────────────────────────────────────────────────

✅ COMPLETE PROJECT STRUCTURE VISUALIZATION

This directory tree shows the complete organization of the Binance Ingestion
Service, with file sizes, purposes, and relationships between components.

All files are production-ready and fully documented.

────────────────────────────────────────────────────────────────────────────────
"""

if __name__ == "__main__":
    print(DIRECTORY_TREE)
