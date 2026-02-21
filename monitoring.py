"""Monitoring and metrics export for ingestion service."""
import json
import time
from typing import Dict, Any
from datetime import datetime
import structlog

from src.binance_client import BinanceWebSocketClient


logger = structlog.get_logger(__name__)


class ServiceMonitor:
    """Monitor and export service metrics."""
    
    def __init__(self, client: BinanceWebSocketClient, export_interval: int = 60):
        """Initialize monitor.
        
        Args:
            client: WebSocket client instance
            export_interval: Seconds between exports
        """
        self.client = client
        self.export_interval = export_interval
        self.export_history: list = []
    
    def export_metrics_json(self, filepath: str = "metrics.json") -> bool:
        """Export metrics to JSON file.
        
        Args:
            filepath: Path to save metrics
            
        Returns:
            True if successful
        """
        try:
            metrics = self.client.get_metrics()
            metrics['timestamp'] = datetime.utcnow().isoformat()
            
            self.export_history.append(metrics)
            
            with open(filepath, 'w') as f:
                json.dump(self.export_history[-100:], f, indent=2)  # Keep last 100
            
            logger.info("metrics_exported", filepath=filepath)
            return True
        except Exception as e:
            logger.exception("metrics_export_failed", error=str(e))
            return False
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary.
        
        Returns:
            Dictionary with key metrics
        """
        metrics = self.client.get_metrics()
        
        # Calculate rates (messages per second)
        if self.export_history:
            prev_metrics = self.export_history[-1]
            time_diff = 1  # Assuming 1 second intervals in production
            
            msg_rate = (metrics['messages_processed'] - prev_metrics.get('messages_processed', 0)) / max(time_diff, 1)
        else:
            msg_rate = 0
        
        return {
            'status': 'connected' if metrics['connected'] else 'disconnected',
            'messages_received': metrics['messages_received'],
            'messages_processed': metrics['messages_processed'],
            'messages_pending': metrics['messages_buffered'],
            'message_rate_per_sec': msg_rate,
            'kafka_produced': metrics['producer_metrics']['messages_sent'],
            'kafka_failed': metrics['producer_metrics']['messages_failed'],
            'uptime_metrics': {
                'reconnections': metrics['reconnect_count'],
                'last_message': metrics['last_message_time'],
            }
        }


if __name__ == "__main__":
    # Example usage
    from config.settings import settings
    from src.logger import setup_logging
    
    setup_logging()
    
    print("Service monitoring example:")
    print("In production, integrate ServiceMonitor with your observability platform")
