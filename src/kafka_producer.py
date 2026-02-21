"""Kafka producer wrapper for publishing market events."""
import json
from typing import Optional, Dict, Any
from kafka import KafkaProducer
from kafka.errors import KafkaError
import structlog
from config.settings import KafkaConfig


logger = structlog.get_logger(__name__)


class MarketEventProducer:
    """Kafka producer for market events with batching and error handling."""
    
    def __init__(self, config: KafkaConfig):
        """Initialize Kafka producer.
        
        Args:
            config: Kafka configuration
        """
        self.config = config
        self.producer = self._create_producer()
        self.metrics = {
            "messages_sent": 0,
            "messages_failed": 0,
            "bytes_sent": 0,
        }
    
    def _create_producer(self) -> KafkaProducer:
        """Create and configure Kafka producer."""
        try:
            producer = KafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                compression_type=self.config.compression,
                max_in_flight_requests_per_connection=5,
                retries=3,
                acks='all',
                batch_size=16384,
                linger_ms=10,
            )
            logger.info(
                "kafka_producer_created",
                bootstrap_servers=self.config.bootstrap_servers
            )
            return producer
        except Exception as e:
            logger.exception("kafka_producer_creation_failed", error=str(e))
            raise
    
    def send_event(
        self,
        topic: str,
        event: Dict[str, Any],
        key: Optional[str] = None
    ) -> bool:
        """Send single event to Kafka.
        
        Args:
            topic: Kafka topic name
            event: Event data to send
            key: Optional partition key
            
        Returns:
            True if send was queued successfully
        """
        try:
            key_bytes = key.encode('utf-8') if key else None
            future = self.producer.send(
                topic,
                value=event,
                key=key_bytes,
                timestamp_ms=int(event.get('timestamp', 0))
            )
            
            # Handle async success/failure
            future.add_callback(
                self._on_send_success,
                topic=topic,
                event_type=event.get('event_type', 'unknown')
            )
            future.add_errback(
                self._on_send_error,
                topic=topic
            )
            
            self.metrics["messages_sent"] += 1
            self.metrics["bytes_sent"] += len(json.dumps(event).encode('utf-8'))
            return True
            
        except Exception as e:
            logger.error(
                "send_event_failed",
                topic=topic,
                error=str(e)
            )
            self.metrics["messages_failed"] += 1
            return False
    
    def send_batch(
        self,
        topic: str,
        events: list,
        key_field: Optional[str] = None
    ) -> int:
        """Send batch of events to Kafka.
        
        Args:
            topic: Kafka topic name
            events: List of events to send
            key_field: Optional field to use as partition key
            
        Returns:
            Number of events successfully queued
        """
        success_count = 0
        for event in events:
            key = event.get(key_field) if key_field else None
            if self.send_event(topic, event, key=key):
                success_count += 1
        
        return success_count
    
    def _on_send_success(self, metadata, topic: str, event_type: str):
        """Callback on successful send."""
        logger.debug(
            "message_sent",
            topic=topic,
            partition=metadata.partition,
            offset=metadata.offset,
            event_type=event_type
        )
    
    def _on_send_error(self, exc, topic: str):
        """Callback on send error."""
        logger.error(
            "message_send_failed",
            topic=topic,
            error=str(exc)
        )
        self.metrics["messages_failed"] += 1
    
    def flush(self, timeout_ms: int = 30000) -> bool:
        """Flush pending messages.
        
        Args:
            timeout_ms: Timeout in milliseconds
            
        Returns:
            True if flush successful
        """
        try:
            self.producer.flush(timeout_ms=timeout_ms)
            logger.info("kafka_producer_flushed")
            return True
        except Exception as e:
            logger.error("kafka_flush_failed", error=str(e))
            return False
    
    def close(self) -> None:
        """Close Kafka producer."""
        try:
            self.producer.close()
            logger.info(
                "kafka_producer_closed",
                metrics=self.metrics
            )
        except Exception as e:
            logger.error("kafka_producer_close_failed", error=str(e))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics."""
        return self.metrics.copy()
