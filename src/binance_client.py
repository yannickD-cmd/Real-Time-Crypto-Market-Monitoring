"""Binance WebSocket client for streaming market data."""
import json
import threading
import time
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime
import websocket
import structlog

from config.settings import BinanceConfig, ConnectionConfig
from src.kafka_producer import MarketEventProducer
from config.settings import KafkaConfig


logger = structlog.get_logger(__name__)


class BinanceWebSocketClient:
    """Production-grade Binance WebSocket client with reconnection and batching."""
    
    def __init__(
        self,
        binance_config: BinanceConfig,
        kafka_config: KafkaConfig,
        connection_config: ConnectionConfig
    ):
        """Initialize Binance WebSocket client.
        
        Args:
            binance_config: Binance configuration
            kafka_config: Kafka configuration
            connection_config: Connection and retry configuration
        """
        self.binance_config = binance_config
        self.kafka_config = kafka_config
        self.connection_config = connection_config
        
        self.ws: Optional[websocket.WebSocket] = None
        self.producer = MarketEventProducer(kafka_config)
        
        self.running = False
        self.connected = False
        self.reconnect_count = 0
        
        self.message_buffer: List[Dict[str, Any]] = []
        self.buffer_lock = threading.Lock()
        self.last_flush = time.time()
        
        self.metrics = {
            "messages_received": 0,
            "messages_processed": 0,
            "messages_buffered": 0,
            "connection_attempts": 0,
            "connection_failures": 0,
            "last_message_time": None,
        }
    
    def _build_stream_url(self) -> str:
        """Build multi-stream subscription URL.
        
        Returns:
            WebSocket URL with all subscribed streams
        """
        streams = []
        
        # Build stream subscriptions for each symbol
        for symbol in self.binance_config.symbols:
            symbol_lower = symbol.lower()
            for stream_type in self.binance_config.stream_types:
                streams.append(f"{symbol_lower}@{stream_type}")
        
        stream_path = "/".join(streams)
        url = f"{self.binance_config.ws_base_url}/{stream_path}"
        
        logger.info(
            "stream_url_built",
            symbols_count=len(self.binance_config.symbols),
            stream_types_count=len(self.binance_config.stream_types),
            total_streams=len(streams)
        )
        
        return url
    
    def _on_message(self, ws: websocket.WebSocket, message: str) -> None:
        """Handle incoming WebSocket message.
        
        Args:
            ws: WebSocket connection
            message: Raw message data
        """
        try:
            data = json.loads(message)
            self.metrics["messages_received"] += 1
            self.metrics["last_message_time"] = datetime.utcnow().isoformat()
            
            # Enrich event with metadata
            enriched_event = self._enrich_event(data)
            
            # Buffer message
            with self.buffer_lock:
                self.message_buffer.append(enriched_event)
                self.metrics["messages_buffered"] = len(self.message_buffer)
            
            # Check if we should flush
            self._check_and_flush()
            
        except json.JSONDecodeError as e:
            logger.error("message_parse_error", error=str(e), raw_message=message[:100])
        except Exception as e:
            logger.exception("message_processing_error", error=str(e))
    
    def _enrich_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich event with additional metadata.
        
        Args:
            event: Raw event from Binance
            
        Returns:
            Enriched event with metadata
        """
        enriched = {
            **event,
            "ingestion_timestamp": int(datetime.utcnow().timestamp() * 1000),
            "source": "binance_websocket",
            "pipeline_version": "1.0.0",
        }
        
        # Determine event type
        if 'e' in event:
            event_type_map = {
                'aggTrade': 'aggregate_trade',
                'trade': 'trade',
                'depthUpdate': 'depth_update',
                'kline': 'kline',
            }
            enriched['event_type'] = event_type_map.get(event['e'], event['e'])
        
        return enriched
    
    def _check_and_flush(self) -> None:
        """Check if buffer should be flushed."""
        current_time = time.time()
        time_since_flush = current_time - self.last_flush
        
        should_flush = (
            len(self.message_buffer) >= self.connection_config.batch_size
            or time_since_flush >= self.connection_config.batch_timeout_seconds
        )
        
        if should_flush:
            self._flush_buffer()
    
    def _flush_buffer(self) -> None:
        """Flush buffered messages to Kafka."""
        with self.buffer_lock:
            if not self.message_buffer:
                return
            
            buffer_copy = self.message_buffer.copy()
            self.message_buffer.clear()
        
        try:
            # Route events to appropriate topics
            for event in buffer_copy:
                event_type = event.get('event_type', 'unknown')
                
                if event_type == 'aggregate_trade' or event_type == 'trade':
                    topic = self.kafka_config.topic_trades
                    key = event.get('s')  # Symbol as partition key
                elif event_type == 'depth_update':
                    topic = self.kafka_config.topic_depth
                    key = event.get('s')
                else:
                    topic = self.kafka_config.topic_raw_events
                    key = event.get('s')
                
                self.producer.send_event(topic, event, key=key)
            
            self.metrics["messages_processed"] += len(buffer_copy)
            self.last_flush = time.time()
            
            logger.debug(
                "buffer_flushed",
                message_count=len(buffer_copy),
                messages_processed_total=self.metrics["messages_processed"]
            )
            
        except Exception as e:
            logger.exception("buffer_flush_failed", error=str(e), buffer_size=len(buffer_copy))
    
    def _on_error(self, ws: websocket.WebSocket, error: Exception) -> None:
        """Handle WebSocket error.
        
        Args:
            ws: WebSocket connection
            error: Error exception
        """
        logger.error(
            "websocket_error",
            error=str(error),
            connected=self.connected
        )
        self.connected = False
        self.metrics["connection_failures"] += 1
    
    def _on_close(self, ws: websocket.WebSocket, close_status_code: int, close_msg: str) -> None:
        """Handle WebSocket close.
        
        Args:
            ws: WebSocket connection
            close_status_code: Close status code
            close_msg: Close message
        """
        logger.info(
            "websocket_closed",
            status_code=close_status_code,
            message=close_msg
        )
        self.connected = False
        
        # Flush remaining buffer
        self._flush_buffer()
    
    def _on_open(self, ws: websocket.WebSocket) -> None:
        """Handle WebSocket open.
        
        Args:
            ws: WebSocket connection
        """
        logger.info(
            "websocket_connected",
            symbols=self.binance_config.symbols,
            streams=self.binance_config.stream_types
        )
        self.connected = True
        self.reconnect_count = 0
    
    def connect(self) -> bool:
        """Connect to Binance WebSocket.
        
        Returns:
            True if connection successful
        """
        if self.connected:
            logger.warning("already_connected")
            return True
        
        self.metrics["connection_attempts"] += 1
        url = self._build_stream_url()
        
        try:
            websocket.enableTrace(False)
            self.ws = websocket.WebSocketApp(
                url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
            )
            
            logger.info("initiating_websocket_connection", url=url[:50] + "...")
            return True
            
        except Exception as e:
            logger.exception("websocket_connection_failed", error=str(e))
            self.metrics["connection_failures"] += 1
            return False
    
    def run(self) -> None:
        """Run WebSocket connection with auto-reconnect loop."""
        self.running = True
        
        while self.running:
            try:
                if not self.connect():
                    self._handle_reconnect()
                    continue
                
                # Run WebSocket (blocking)
                self.ws.run_forever()
                
            except Exception as e:
                logger.exception("websocket_run_error", error=str(e))
                self._handle_reconnect()
        
        logger.info("websocket_stopped")
    
    def _handle_reconnect(self) -> None:
        """Handle reconnection with exponential backoff."""
        self.reconnect_count += 1
        
        if self.reconnect_count > self.connection_config.max_retries:
            logger.error(
                "max_reconnection_attempts_exceeded",
                attempts=self.reconnect_count
            )
            self.running = False
            return
        
        # Exponential backoff: 5s, 10s, 20s, etc.
        wait_time = min(
            self.connection_config.reconnect_interval * (2 ** (self.reconnect_count - 1)),
            300  # Max 5 minutes
        )
        
        logger.warning(
            "reconnecting",
            attempt=self.reconnect_count,
            wait_seconds=wait_time,
            max_retries=self.connection_config.max_retries
        )
        
        time.sleep(wait_time)
    
    def start_in_background(self) -> threading.Thread:
        """Start WebSocket in background thread.
        
        Returns:
            Thread object
        """
        thread = threading.Thread(target=self.run, daemon=False)
        thread.start()
        logger.info("websocket_started_in_background")
        return thread
    
    def stop(self) -> None:
        """Stop WebSocket connection gracefully."""
        logger.info("stopping_websocket")
        self.running = False
        
        # Flush remaining messages
        self._flush_buffer()
        
        # Close WebSocket
        if self.ws:
            self.ws.close()
            time.sleep(1)
        
        # Close Kafka producer
        self.producer.close()
        
        logger.info("websocket_stopped", final_metrics=self.metrics)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            "producer_metrics": self.producer.get_metrics(),
            "buffer_size": len(self.message_buffer),
            "reconnect_count": self.reconnect_count,
            "connected": self.connected,
        }
