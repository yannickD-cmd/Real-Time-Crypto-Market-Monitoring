"""Initialize config package."""
from config.settings import settings
from src.logger import setup_logging

__all__ = ['settings', 'setup_logging']
