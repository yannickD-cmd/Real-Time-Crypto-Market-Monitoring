"""Unit tests for Binance WebSocket client."""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from config.settings import BinanceConfig, KafkaConfig, ConnectionConfig
from src.binance_client import BinanceWebSocketClient
from src.kafka_producer import MarketEventProducer


@pytest.fixture
def binance_config():
    return BinanceConfig(
        symbols=["BTCUSDT", "ETHUSDT"],
        stream_types=["aggTrade", "depth@100ms"]
    )


@pytest.fixture
def kafka_config():
    return KafkaConfig(
        bootstrap_servers=["localhost:9092"],
        topic_raw_events="binance-raw-events",
        topic_trades="binance-trades",
        topic_depth="binance-depth",
    )


@pytest.fixture
def connection_config():
    return ConnectionConfig(
        reconnect_interval=5,
        max_retries=3,
        batch_size=10,
        batch_timeout_seconds=5,
    )


@pytest.fixture
def websocket_client(binance_config, kafka_config, connection_config):
    with patch('src.binance_client.MarketEventProducer'):
        return BinanceWebSocketClient(binance_config, kafka_config, connection_config)


class TestBinanceWebSocketClient:
    """Tests for BinanceWebSocketClient."""
    
    def test_build_stream_url(self, websocket_client):
        """Test multi-stream URL building."""
        url = websocket_client._build_stream_url()
        
        assert "wss://stream.binance.com:9443/ws" in url
        assert "btcusdt@aggtrade" in url
        assert "ethusdt@aggtrade" in url
        assert "depth@100ms" in url
    
    def test_enrich_event(self, websocket_client):
        """Test event enrichment."""
        raw_event = {
            'e': 'aggTrade',
            's': 'BTCUSDT',
            'p': '45000.00',
            'q': '0.5'
        }
        
        enriched = websocket_client._enrich_event(raw_event)
        
        assert enriched['event_type'] == 'aggregate_trade'
        assert enriched['source'] == 'binance_websocket'
        assert 'ingestion_timestamp' in enriched
        assert enriched['s'] == 'BTCUSDT'
    
    def test_message_buffering(self, websocket_client):
        """Test message buffering."""
        event1 = {
            'e': 'trade',
            's': 'BTCUSDT',
            'timestamp': 1234567890
        }
        event2 = {
            'e': 'aggTrade',
            's': 'ETHUSDT',
            'timestamp': 1234567891
        }
        
        websocket_client._on_message(None, json.dumps(event1))
        websocket_client._on_message(None, json.dumps(event2))
        
        assert websocket_client.metrics["messages_received"] == 2
        assert len(websocket_client.message_buffer) == 2
    
    def test_metrics(self, websocket_client):
        """Test metrics collection."""
        metrics = websocket_client.get_metrics()
        
        assert 'messages_received' in metrics
        assert 'messages_processed' in metrics
        assert 'connection_attempts' in metrics
        assert 'connected' in metrics
    
    def test_initial_state(self, websocket_client):
        """Test initial state."""
        assert websocket_client.running is False
        assert websocket_client.connected is False
        assert len(websocket_client.message_buffer) == 0


class TestMarketEventProducer:
    """Tests for MarketEventProducer."""
    
    @patch('src.kafka_producer.KafkaProducer')
    def test_producer_creation(self, mock_kafka_producer):
        """Test producer creation."""
        kafka_config = KafkaConfig()
        
        with patch('src.kafka_producer.kafka'):
            producer = MarketEventProducer(kafka_config)
            assert producer.metrics["messages_sent"] == 0
    
    @patch('src.kafka_producer.KafkaProducer')
    def test_send_event(self, mock_kafka_producer):
        """Test single event send."""
        kafka_config = KafkaConfig()
        
        with patch.object(MarketEventProducer, '_create_producer', return_value=MagicMock()):
            producer = MarketEventProducer(kafka_config)
            producer.producer.send = MagicMock(return_value=MagicMock())
            
            event = {'symbol': 'BTCUSDT', 'price': 45000}
            result = producer.send_event('test-topic', event)
            
            assert result is True
            assert producer.metrics["messages_sent"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
