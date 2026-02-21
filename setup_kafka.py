"""Kafka topic management and initialization."""
from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError, KafkaError
import structlog

from config.settings import settings


logger = structlog.get_logger(__name__)


def create_topics() -> bool:
    """Create required Kafka topics.
    
    Returns:
        True if successful
    """
    admin_client = KafkaAdminClient(
        bootstrap_servers=settings.kafka.bootstrap_servers,
        client_id="binance-ingestion-admin"
    )
    
    topics = [
        NewTopic(
            name=settings.kafka.topic_raw_events,
            num_partitions=settings.kafka.partitions,
            replication_factor=settings.kafka.replication_factor,
            topic_configs={
                'retention.ms': '604800000',  # 7 days
                'compression.type': settings.kafka.compression,
                'segment.ms': '86400000',  # 1 day
            }
        ),
        NewTopic(
            name=settings.kafka.topic_trades,
            num_partitions=settings.kafka.partitions,
            replication_factor=settings.kafka.replication_factor,
            topic_configs={
                'retention.ms': '2592000000',  # 30 days
                'compression.type': settings.kafka.compression,
            }
        ),
        NewTopic(
            name=settings.kafka.topic_depth,
            num_partitions=settings.kafka.partitions,
            replication_factor=settings.kafka.replication_factor,
            topic_configs={
                'retention.ms': '604800000',  # 7 days
                'compression.type': settings.kafka.compression,
            }
        ),
    ]
    
    try:
        fs = admin_client.create_topics(new_topics=topics, validate_only=False)
        
        for topic, f in fs.items():
            try:
                f.result()
                logger.info("topic_created", topic=topic)
            except TopicAlreadyExistsError:
                logger.info("topic_already_exists", topic=topic)
            except KafkaError as e:
                logger.error("topic_creation_failed", topic=topic, error=str(e))
                return False
        
        admin_client.close()
        return True
    
    except Exception as e:
        logger.exception("topic_creation_error", error=str(e))
        return False


if __name__ == "__main__":
    from src.logger import setup_logging
    setup_logging()
    create_topics()
