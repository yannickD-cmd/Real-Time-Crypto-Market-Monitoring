import json
import logging
from confluent_kafka import Producer
from ingestion.config import KAFKA_BOOTSTRAP_SERVERS

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
                # acks=all: leader + all in-sync replicas confirm before ack
                "acks": "all",
                "linger.ms": 5,
                "batch.num.messages": 1000,
                "compression.type": "lz4",
            }
        )

    def send(self, topic: str, key: str, value: dict) -> None:
        """Serialize value to JSON and produce to the given Kafka topic."""
        self._producer.produce(
            topic=topic,
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
