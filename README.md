# Binance Real-Time Ingestion Service

Production-grade Python WebSocket client for streaming Binance market data to Apache Kafka.

## Architecture

```
Binance WebSocket Streams
         ↓
Python WebSocket Client (auto-reconnect, batching)
         ↓
Kafka Topics (raw-events, trades, depth)
         ↓
Stream & PySpark Processing (next phase)
```

## Features

✅ **Real-time Streaming**
- Multi-symbol Binance WebSocket subscriptions
- Aggregate trades, depth updates, and kline data
- Raw JSON event ingestion

✅ **Production Readiness**
- Auto-reconnection with exponential backoff
- Graceful shutdown and signal handling
- Comprehensive structured logging (JSON format)
- Error handling and metrics collection

✅ **Performance**
- Message batching (configurable size and timeout)
- Snappy compression for Kafka messages
- Efficient threading and resource management

✅ **Monitoring**
- Real-time metrics (messages received, processed, buffered)
- Connection status tracking
- Producer performance metrics
- Health checks

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Binance symbols to monitor
BINANCE_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,XRPUSDT

# Stream types
BINANCE_STREAM_TYPES=aggTrade,depth@100ms,trade,kline_1m

# Kafka brokers
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Kafka topics
KAFKA_TOPIC_RAW_EVENTS=binance-raw-events
KAFKA_TOPIC_TRADES=binance-trades
KAFKA_TOPIC_DEPTH=binance-depth

# Connection settings
RECONNECT_INTERVAL=5
MAX_RETRIES=5
BATCH_SIZE=100
BATCH_TIMEOUT_SECONDS=5

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Installation

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Initialize Kafka topics
python setup_kafka.py

# Run the service
python main.py
```

### Docker Deployment

```bash
# Start all services (Kafka, Zookeeper, UI, Ingestion)
docker-compose up -d

# View logs
docker-compose logs -f binance-ingestion

# Access Kafka UI
open http://localhost:8080

# Stop services
docker-compose down
```

## Usage

### As Main Entry Point

```bash
python main.py
```

### As a Module

```python
from config.settings import settings
from src.binance_client import BinanceWebSocketClient

# Create client
client = BinanceWebSocketClient(
    binance_config=settings.binance,
    kafka_config=settings.kafka,
    connection_config=settings.connection,
)

# Start in background
thread = client.start_in_background()

# Monitor
while True:
    metrics = client.get_metrics()
    print(f"Messages: {metrics['messages_processed']}")
    
# Shutdown
client.stop()
```

## Kafka Topics

### binance-raw-events
All raw events from Binance streams. Retention: 7 days.

**Example message:**
```json
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
  "ingestion_timestamp": 1677000000123,
  "source": "binance_websocket",
  "event_type": "aggregate_trade"
}
```

### binance-trades
Trade events (aggregate trades and individual trades). Retention: 30 days.

Partition key: Symbol (e.g., BTCUSDT)

### binance-depth
Order book depth updates. Retention: 7 days.

Partition key: Symbol

## Monitoring

### Real-time Metrics

The service logs metrics every 30 seconds:

```json
{
  "level": "info",
  "event": "service_metrics",
  "messages_received": 45000,
  "messages_processed": 45000,
  "messages_buffered": 5,
  "connected": true,
  "reconnect_count": 0
}
```

### Check Health

```bash
# View logs
docker-compose logs binance-ingestion

# Check Kafka topics
docker exec ingestion_kafka_1 kafka-topics --list --bootstrap-server localhost:29092

# Console consumer (debugging)
docker exec ingestion_kafka_1 kafka-console-consumer \
  --bootstrap-server localhost:29092 \
  --topic binance-trades \
  --from-beginning \
  --max-messages 10
```

## Performance Tuning

### Batch Configuration
```python
BATCH_SIZE=100           # Process 100 messages per batch
BATCH_TIMEOUT_SECONDS=5  # Or every 5 seconds
```

### Kafka Producer
- Compression: snappy (configurable in settings.py)
- Acks: all (durability)
- Retries: 3 (automatic retry)

### Connection
- Auto-reconnect with exponential backoff (5s, 10s, 20s, etc.)
- Max retries: 5
- Max backoff: 5 minutes

## Testing

```bash
# Run unit tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov=config
```

## Architecture Decisions

1. **Batching**: Messages buffered in memory for 5 seconds or 100 messages, whichever comes first
2. **Async Kafka Sends**: Non-blocking sends with callback error handling
3. **Multi-threading**: WebSocket runs in separate thread, main thread monitors
4. **Partition Keys**: Symbol used as key to ensure trade sequence per symbol
5. **Topic Routing**: Events routed to specific topics by type (trades, depth, raw)

## Next Steps

1. **PySpark Processing**: Build streaming aggregations for volume and volatility
2. **Delta Lake Storage**: Persist processed features
3. **Real-time Alerts**: Detect anomalies and trigger alerts
4. **Grafana Dashboards**: Visualize streaming metrics
5. **Advanced Features**:
   - VWAP calculation
   - Order book imbalance detection
   - Liquidity stress detection
   - Machine learning models for prediction

## Troubleshooting

### Connection Issues
```
ERROR websocket_connection_failed: Connection refused
→ Check Binance WebSocket accessibility: wss://stream.binance.com:9443/ws
```

### Kafka Connection Issues
```
ERROR kafka_producer_creation_failed: NoBrokersAvailable
→ Ensure Kafka is running: docker-compose up -d kafka
```

### Memory Issues
- Reduce BATCH_SIZE
- Increase BATCH_TIMEOUT_SECONDS
- Reduce number of BINANCE_SYMBOLS

## License

MIT

## Support

For issues or questions, refer to:
- [Binance API Documentation](https://binance-docs.github.io/apidocs/spot/en/)
- [Kafka Documentation](https://kafka.apache.org/documentation/)
