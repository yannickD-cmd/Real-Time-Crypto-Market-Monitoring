import os
from dotenv import load_dotenv

load_dotenv()

# Kafka — topics to consume (reuse same defaults as ingestion layer)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_TRADES = os.getenv("TOPIC_TRADES", "binance.trades")
TOPIC_BOOK_TICKER = os.getenv("TOPIC_BOOK_TICKER", "binance.book_ticker")

# Consumer group — changing this resets offsets to latest for this group
CONSUMER_GROUP_ID = os.getenv("CONSUMER_GROUP_ID", "binance-buffer")

# Batch flush settings
CONSUMER_BATCH_SIZE = int(os.getenv("CONSUMER_BATCH_SIZE", "500"))
CONSUMER_FLUSH_INTERVAL = float(os.getenv("CONSUMER_FLUSH_INTERVAL", "2.0"))  # seconds

# TimescaleDB connection
TIMESCALEDB_HOST = os.getenv("TIMESCALEDB_HOST", "localhost")
TIMESCALEDB_PORT = int(os.getenv("TIMESCALEDB_PORT", "5433"))
TIMESCALEDB_DB = os.getenv("TIMESCALEDB_DB", "crypto")
TIMESCALEDB_USER = os.getenv("TIMESCALEDB_USER", "crypto")
TIMESCALEDB_PASSWORD = os.getenv("TIMESCALEDB_PASSWORD", "crypto_secret")

# Health-check HTTP server port (distinct from ingestion's 8081)
CONSUMER_HEALTH_PORT = int(os.getenv("CONSUMER_HEALTH_PORT", "8082"))
