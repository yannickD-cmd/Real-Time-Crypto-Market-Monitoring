import json
import logging
from confluent_kafka import Producer
from ingestion.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC

logger = logging.getLogger(__name__)


def _delivery_report(err, msg):
    """Callback invoked on message delivery success or failure."""
    if err:
        logger.error("Delivery failed for record %s: %s", msg.key(), err)
    else:
        logger.debug(
            "Record delivered to %s [partition %s] @ offset %s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


class KafkaProducerClient:
    def __init__(self):
        self._producer = Producer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "linger.ms": 5,
                "batch.num.messages": 1000,
                "compression.type": "lz4",
            }
        )
        self.topic = KAFKA_TOPIC

    def send(self, key: str, value: dict) -> None:
        """Serialize value to JSON and produce to Kafka."""
        self._producer.produce(
            topic=self.topic,
            key=key.encode("utf-8"),
            value=json.dumps(value).encode("utf-8"),
            callback=_delivery_report,
        )
        self._producer.poll(0)

    def flush(self) -> None:
        self._producer.flush()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.flush()
