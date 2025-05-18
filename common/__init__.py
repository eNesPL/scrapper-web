# Common package for shared components
"""Common utilities and shared modules for the real estate scraper application.

This package contains:
- DatabaseManager: Handles all database operations
- NotificationManager: Handles Discord notifications  
- config: Application configuration
"""
from .database_manager import DatabaseManager
from .notification_manager import NotificationManager
from .config import TRACKED_FIELDS_FOR_NOTIFICATION

__all__ = ['DatabaseManager', 'NotificationManager', 'TRACKED_FIELDS_FOR_NOTIFICATION']
