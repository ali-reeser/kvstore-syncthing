"""
Base Sync Handler - Abstract interface for all sync handlers

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/base.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Abstract base class defining the handler
                                interface for all sync destination types.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class DestinationConfig:
    """Base configuration for sync destinations"""
    name: str
    destination_type: str
    host: str = ""
    port: int = 8089
    use_ssl: bool = True
    verify_ssl: bool = False
    auth_type: str = "token"  # token, basic, none
    username: Optional[str] = None
    password: Optional[str] = None
    connection_timeout: int = 30
    read_timeout: int = 60
    max_retries: int = 3
    target_app: str = "search"
    target_owner: str = "nobody"


class BaseSyncHandler(ABC):
    """
    Abstract base class for sync handlers.

    All sync handlers must implement this interface to ensure
    consistent behavior across different destination types.
    """

    def __init__(self, destination: DestinationConfig):
        """
        Initialize handler with destination configuration.

        Args:
            destination: Destination configuration
        """
        self.destination = destination
        self._connected = False
        self._cancelled = False

    @property
    def name(self) -> str:
        """Get handler name"""
        return self.destination.name

    @property
    def is_connected(self) -> bool:
        """Check if handler is connected"""
        return self._connected

    def cancel(self):
        """Cancel current operation"""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if operation was cancelled"""
        return self._cancelled

    def reset_cancelled(self):
        """Reset cancelled flag"""
        self._cancelled = False

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to destination.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to destination"""
        pass

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to destination.

        Returns:
            Tuple of (success, message)
        """
        pass

    @abstractmethod
    def collection_exists(self, collection: str, app: str, owner: str) -> bool:
        """
        Check if collection exists at destination.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context

        Returns:
            True if collection exists
        """
        pass

    @abstractmethod
    def create_collection(self, collection: str, app: str, owner: str,
                         schema: Optional[Dict] = None) -> bool:
        """
        Create a collection at destination.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context
            schema: Optional collection schema

        Returns:
            True if creation successful
        """
        pass

    @abstractmethod
    def get_collection_schema(self, collection: str, app: str, owner: str) -> Optional[Dict]:
        """
        Get collection schema.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context

        Returns:
            Schema dict or None
        """
        pass

    @abstractmethod
    def read_records(self, collection: str, app: str, owner: str,
                    query: Optional[Dict] = None, fields: Optional[List[str]] = None,
                    skip: int = 0, limit: int = 0) -> Generator[Dict, None, None]:
        """
        Read records from collection.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context
            query: Optional query filter
            fields: Optional field projection
            skip: Records to skip
            limit: Maximum records to return (0 = unlimited)

        Yields:
            Record dicts
        """
        pass

    @abstractmethod
    def write_records(self, collection: str, app: str, owner: str,
                     records: List[Dict], preserve_key: bool = True) -> Tuple[int, List[str]]:
        """
        Write records to collection.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context
            records: Records to write
            preserve_key: Whether to preserve _key field

        Returns:
            Tuple of (records_written, errors)
        """
        pass

    @abstractmethod
    def update_record(self, collection: str, app: str, owner: str,
                     key: str, record: Dict) -> bool:
        """
        Update a single record.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context
            key: Record key
            record: Updated record data

        Returns:
            True if update successful
        """
        pass

    @abstractmethod
    def delete_records(self, collection: str, app: str, owner: str,
                      keys: List[str]) -> Tuple[int, List[str]]:
        """
        Delete records by key.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context
            keys: Record keys to delete

        Returns:
            Tuple of (records_deleted, errors)
        """
        pass

    @abstractmethod
    def get_record_count(self, collection: str, app: str, owner: str,
                        query: Optional[Dict] = None) -> int:
        """
        Get record count for collection.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context
            query: Optional query filter

        Returns:
            Record count
        """
        pass

    @abstractmethod
    def get_record_by_key(self, collection: str, app: str, owner: str,
                         key: str) -> Optional[Dict]:
        """
        Get a single record by key.

        Args:
            collection: Collection name
            app: Splunk app context
            owner: Splunk owner context
            key: Record key

        Returns:
            Record dict or None
        """
        pass
