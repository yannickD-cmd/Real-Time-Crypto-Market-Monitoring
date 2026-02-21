"""Main ingestion service orchestrator."""
import sys
import signal
import time
from typing import Optional
import structlog

from config.settings import settings
from src.logger import setup_logging
from src.binance_client import BinanceWebSocketClient


logger: Optional[structlog.BoundLogger] = None
websocket_client: Optional[BinanceWebSocketClient] = None


def setup() -> None:
    """Initialize logging and configuration."""
    global logger
    
    setup_logging(
        log_level=settings.logging.log_level,
        log_format=settings.logging.log_format
    )
    logger = structlog.get_logger(__name__)
    
    logger.info(
        "ingestion_service_initialized",
        binance_symbols=settings.binance.symbols,
        kafka_brokers=settings.kafka.bootstrap_servers,
        log_level=settings.logging.log_level,
    )


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("shutdown_signal_received", signal=sig)
    shutdown()


def shutdown() -> None:
    """Gracefully shutdown the service."""
    global websocket_client
    
    logger.info("shutting_down_service")
    
    if websocket_client:
        try:
            websocket_client.stop()
        except Exception as e:
            logger.exception("error_during_shutdown", error=str(e))
    
    logger.info("service_shutdown_complete")
    sys.exit(0)


def start_service() -> None:
    """Start the ingestion service."""
    global websocket_client
    
    try:
        # Create WebSocket client
        websocket_client = BinanceWebSocketClient(
            binance_config=settings.binance,
            kafka_config=settings.kafka,
            connection_config=settings.connection,
        )
        
        # Start in background thread
        ws_thread = websocket_client.start_in_background()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("ingestion_service_started")
        
        # Main monitoring loop
        try:
            while True:
                time.sleep(30)
                metrics = websocket_client.get_metrics()
                logger.info(
                    "service_metrics",
                    messages_received=metrics["messages_received"],
                    messages_processed=metrics["messages_processed"],
                    messages_buffered=metrics["messages_buffered"],
                    connected=metrics["connected"],
                    reconnect_count=metrics["reconnect_count"],
                )
        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")
            shutdown()
    
    except Exception as e:
        logger.exception("service_startup_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    setup()
    start_service()
