"""
Quick start guide for running the ingestion service.

This script demonstrates the complete setup process.
"""

import subprocess
import time
import sys
import os


def run_command(cmd: str, description: str) -> bool:
    """Run a shell command.
    
    Args:
        cmd: Command to run
        description: Description of what's happening
        
    Returns:
        True if successful
    """
    print(f"\n{'='*60}")
    print(f"📋 {description}")
    print(f"{'='*60}")
    print(f"$ {cmd}\n")
    
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def main():
    """Run complete setup."""
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║  Binance Real-Time Ingestion Service - Quick Start         ║
    ║  Production-grade WebSocket → Kafka Pipeline              ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    steps = [
        ("pip install -r requirements.txt", "Installing dependencies"),
        ("python setup_kafka.py", "Creating Kafka topics"),
        ("python main.py", "Starting ingestion service"),
    ]
    
    for cmd, desc in steps:
        if not run_command(cmd, desc):
            print(f"\n❌ Failed at: {desc}")
            return False
        time.sleep(2)
    
    print("""
    ✅ Ingestion service is running!
    
    📊 Monitoring:
       - Check logs in main.py output
       - Access Kafka UI: http://localhost:8080
       - View metrics: docker-compose logs binance-ingestion
    
    📝 To stop: Press Ctrl+C
    """)
    
    return True


if __name__ == "__main__":
    if sys.platform == "win32":
        print("Note: For Windows, ensure Kafka is running separately")
        print("Run: docker-compose up -d")
    
    success = main()
    sys.exit(0 if success else 1)
