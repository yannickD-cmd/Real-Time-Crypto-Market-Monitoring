"""Configuration settings for Binance ingestion service."""
from typing import List
from pydantic import BaseSettings, Field


class BinanceConfig(BaseSettings):
    """Binance API configuration."""
    symbols: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        description="Trading pairs to monitor"
    )
    stream_types: List[str] = Field(
        default=["aggTrade", "depth@100ms", "trade"],
        description="Types of streams to subscribe to"
    )
    api_baseurl: str = Field(
        default="https://api.binance.com/api/v3",
        description="Binance API base URL"
    )
    ws_base_url: str = Field(
        default="wss://stream.binance.com:9443/ws",
        description="Binance WebSocket base URL"
    )

    class Config:
        env_file = ".env"
        env_prefix = "BINANCE_"


class KafkaConfig(BaseSettings):
    """Kafka configuration."""
    bootstrap_servers: List[str] = Field(
        default=["localhost:9092"],
        description="Kafka broker addresses"
    )
    topic_raw_events: str = Field(
        default="binance-raw-events",
        description="Topic for raw market events"
    )
    topic_trades: str = Field(
        default="binance-trades",
        description="Topic for trade events"
    )
    topic_depth: str = Field(
        default="binance-depth",
        description="Topic for depth updates"
    )
    partitions: int = Field(
        default=3,
        description="Number of partitions for topics"
    )
    replication_factor: int = Field(
        default=1,
        description="Replication factor for topics"
    )
    compression: str = Field(
        default="snappy",
        description="Compression type: snappy, gzip, lz4"
    )

    class Config:
        env_file = ".env"
        env_prefix = "KAFKA_"


class ConnectionConfig(BaseSettings):
    """Connection and retry configuration."""
    reconnect_interval: int = Field(
        default=5,
        description="Seconds to wait before reconnecting"
    )
    max_retries: int = Field(
        default=5,
        description="Maximum reconnection attempts"
    )
    batch_size: int = Field(
        default=100,
        description="Number of messages to batch before sending"
    )
    batch_timeout_seconds: int = Field(
        default=5,
        description="Timeout for batching messages"
    )

    class Config:
        env_file = ".env"
        env_prefix = ""


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR"
    )
    log_format: str = Field(
        default="json",
        description="Log format: json, text"
    )

    class Config:
        env_file = ".env"


class Settings(BaseSettings):
    """Combined application settings."""
    binance: BinanceConfig = BinanceConfig()
    kafka: KafkaConfig = KafkaConfig()
    connection: ConnectionConfig = ConnectionConfig()
    logging: LoggingConfig = LoggingConfig()

    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()
