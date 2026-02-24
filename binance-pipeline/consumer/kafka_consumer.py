import logging
from confluent_kafka import Consumer, KafkaError

from consumer.config import KAFKA_BOOTSTRAP_SERVERS, CONSUMER_GROUP_ID

logger = logging.getLogger(__name__)


class KafkaConsumerClient:
    """
    Thin wrapper around confluent_kafka.Consumer.

    Mirrors KafkaProducerClient structure: context manager, same logger pattern.

    enable.auto.commit = False: offsets are committed explicitly by the worker
    ONLY after a successful database write (at-least-once semantics).

    auto.offset.reset = latest: on first run (no committed offset) start from
    the most recent message, not the beginning of the log.
    """

    def __init__(self, topics: list[str]):
        self._consumer = Consumer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "group.id": CONSUMER_GROUP_ID,
                "enable.auto.commit": False,
                "auto.offset.reset": "latest",
            }
        )
        self._consumer.subscribe(topics)
        logger.info("Subscribed to topics: %s (group=%s)", topics, CONSUMER_GROUP_ID)

    def poll(self, timeout: float = 1.0):
        """Poll for a single message. Returns a confluent_kafka.Message or None."""
        return self._consumer.poll(timeout=timeout)

    def commit(self) -> None:
        """Synchronous offset commit — called only after a successful DB flush."""
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        """Leave the consumer group cleanly, triggering partition rebalance."""
        self._consumer.close()
        logger.info("KafkaConsumerClient closed.")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
