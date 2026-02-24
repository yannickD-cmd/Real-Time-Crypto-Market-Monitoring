import os
from dotenv import load_dotenv

load_dotenv()

# Binance WebSocket — combined-streams endpoint (wraps each event in {stream, data})
WS_BASE_URL = "wss://stream.binance.com:9443/stream"
# Normalise to uppercase; producer uses symbol as partition key
SYMBOLS = [s.strip().upper() for s in os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT").split(",")]
# Three stream types subscribed per symbol
STREAM_TYPES = ["trade", "aggTrade", "bookTicker"]

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_TRADES = os.getenv("TOPIC_TRADES", "binance.trades")
TOPIC_BOOK_TICKER = os.getenv("TOPIC_BOOK_TICKER", "binance.book_ticker")

# Health-check HTTP server port
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8081"))
