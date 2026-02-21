"""
Example: Consuming messages from Kafka topics.

This demonstrates how downstream services would consume
the streaming market data.
"""

import json
import time
from kafka import KafkaConsumer
from config.settings import settings
from src.logger import setup_logging, get_logger


logger = get_logger(__name__)


def consume_raw_events(max_messages: int = 10):
    """Consume raw market events.
    
    Args:
        max_messages: Number of messages to consume
    """
    consumer = KafkaConsumer(
        settings.kafka.topic_raw_events,
        bootstrap_servers=settings.kafka.bootstrap_servers,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='raw-events-consumer',
        auto_offset_reset='latest',
        max_poll_records=1,
    )
    
    print(f"\n📥 Consuming {max_messages} messages from '{settings.kafka.topic_raw_events}'...\n")
    
    count = 0
    for message in consumer:
        count += 1
        event = message.value
        
        print(f"[{count}] Event Type: {event.get('event_type', 'unknown')}")
        print(f"    Symbol: {event.get('s', 'N/A')}")
        print(f"    Timestamp: {event.get('ingestion_timestamp', 'N/A')}")
        print(f"    Data: {json.dumps(event, indent=6)}\n")
        
        if count >= max_messages:
            break
    
    consumer.close()


def consume_trades(max_messages: int = 10):
    """Consume trade events.
    
    Args:
        max_messages: Number of messages to consume
    """
    consumer = KafkaConsumer(
        settings.kafka.topic_trades,
        bootstrap_servers=settings.kafka.bootstrap_servers,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='trades-consumer',
        auto_offset_reset='latest',
    )
    
    print(f"\n📊 Consuming {max_messages} trade events from '{settings.kafka.topic_trades}'...\n")
    
    count = 0
    for message in consumer:
        count += 1
        trade = message.value
        
        symbol = trade.get('s', 'N/A')
        price = trade.get('p', 'N/A')
        quantity = trade.get('q', 'N/A')
        
        print(f"[{count}] {symbol}: {quantity} @ {price}")
        
        if count >= max_messages:
            break
    
    consumer.close()


def consume_depth(max_messages: int = 10):
    """Consume depth updates.
    
    Args:
        max_messages: Number of messages to consume
    """
    consumer = KafkaConsumer(
        settings.kafka.topic_depth,
        bootstrap_servers=settings.kafka.bootstrap_servers,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='depth-consumer',
        auto_offset_reset='latest',
    )
    
    print(f"\n📈 Consuming {max_messages} depth updates from '{settings.kafka.topic_depth}'...\n")
    
    count = 0
    for message in consumer:
        count += 1
        depth = message.value
        
        symbol = depth.get('s', 'N/A')
        print(f"[{count}] Depth update for {symbol}: {len(depth.get('b', []))} bids, {len(depth.get('a', []))} asks")
        
        if count >= max_messages:
            break
    
    consumer.close()


if __name__ == "__main__":
    setup_logging()
    
    import sys
    
    if len(sys.argv) > 1:
        topic_type = sys.argv[1].lower()
        max_msgs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        
        if topic_type == 'raw':
            consume_raw_events(max_msgs)
        elif topic_type == 'trades':
            consume_trades(max_msgs)
        elif topic_type == 'depth':
            consume_depth(max_msgs)
        else:
            print(f"Unknown topic type: {topic_type}")
    else:
        print("""
        Usage: python consumer_example.py <topic_type> [max_messages]
        
        Topic types:
            raw     - Raw market events
            trades  - Trade events
            depth   - Depth updates
        
        Examples:
            python consumer_example.py raw 20
            python consumer_example.py trades
            python consumer_example.py depth 15
        """)
