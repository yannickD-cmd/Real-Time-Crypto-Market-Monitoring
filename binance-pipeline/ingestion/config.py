import os
from dotenv import load_dotenv

load_dotenv()

# Binance WebSocket
WS_BASE_URL = "wss://stream.binance.com:9443/ws"
SYMBOLS = os.getenv("SYMBOLS", "btcusdt,ethusdt,bnbusdt").split(",")
STREAM_TYPE = os.getenv("STREAM_TYPE", "trade")  # trade | kline_1m | depth

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "binance-trades")
