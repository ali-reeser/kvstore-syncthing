"""
Core Sync Engine - Orchestrates KVStore synchronization

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/sync_engine.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Sync engine orchestrator with support for
                                full, incremental, append-only, and
                                master/slave sync modes.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class SyncMode(Enum):
    """Synchronization modes"""
    FULL_SYNC = "full_sync"
    INCREMENTAL = "incremental"
    APPEND_ONLY = "append_only"
    MASTER_SLAVE = "master_slave"


class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    SOURCE_WINS = "source_wins"
    DESTINATION_WINS = "destination_wins"
    NEWEST_WINS = "newest_wins"
    MERGE = "merge"
    MANUAL_REVIEW = "manual_review"


@dataclass
class SyncProfile:
    """Configuration for a sync profile"""
    name: str
    sync_mode: SyncMode
    conflict_resolution: ConflictResolution = ConflictResolution.SOURCE_WINS
    batch_size: int = 1000
    delete_orphans: bool = False
    preserve_key: bool = True
    timestamp_field: str = "_updated"
    key_fields: List[str] = field(default_factory=lambda: ["_key"])
    field_mappings: Dict[str, str] = field(default_factory=dict)
    field_exclusions: List[str] = field(default_factory=list)
    filter_query: Dict = field(default_factory=dict)


@dataclass
class SyncResult:
    """Result of a sync operation"""
    success: bool
    mode: SyncMode
    collection: str
    app: str
    owner: str
    records_read: int = 0
    records_written: int = 0
    records_deleted: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    batches_processed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    checkpoints: List[Dict] = field(default_factory=list)


@dataclass
class Checkpoint:
    """Sync checkpoint for resume capability"""
    batch_number: int
    last_key: str
    timestamp: datetime
    records_processed: int


# =============================================================================
# Core Utility Functions
# =============================================================================

def compute_checksum(record: Dict, exclude_fields: Optional[Set[str]] = None) -> str:
    """
    Compute SHA-256 checksum for a record.

    Args:
        record: The record to compute checksum for
        exclude_fields: Fields to exclude from checksum computation

    Returns:
        SHA-256 hex digest of the record
    """
    exclude = exclude_fields or {"_user", "_raw", "_batchID"}
    filtered = {}
    for key in sorted(record.keys()):
        if key not in exclude:
            filtered[key] = record[key]
    json_str = json.dumps(filtered, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def batch_records(records: List[Dict], batch_size: int = 100) -> List[List[Dict]]:
    """
    Split records into batches.

    Args:
        records: List of records to batch
        batch_size: Maximum records per batch

    Returns:
        List of record batches
    """
    return [records[i:i + batch_size] for i in range(0, len(records), batch_size)]


def resolve_conflict(source: Dict, dest: Dict, strategy: ConflictResolution,
                    timestamp_field: str = "_updated") -> Dict:
    """
    Resolve conflict between source and destination records.

    Args:
        source: Source record
        dest: Destination record
        strategy: Conflict resolution strategy
        timestamp_field: Field to use for timestamp comparison

    Returns:
        Resolved record
    """
    if strategy == ConflictResolution.SOURCE_WINS:
        return source
    elif strategy == ConflictResolution.DESTINATION_WINS:
        return dest
    elif strategy == ConflictResolution.NEWEST_WINS:
        src_time = source.get(timestamp_field, 0)
        dest_time = dest.get(timestamp_field, 0)
        return source if src_time >= dest_time else dest
    elif strategy == ConflictResolution.MERGE:
        # Merge: destination provides base, source overwrites
        merged = dest.copy()
        merged.update(source)
        return merged
    else:
        # Default to source wins
        return source


def transform_record(record: Dict, profile: SyncProfile) -> Dict:
    """
    Transform record according to profile configuration.

    Args:
        record: Record to transform
        profile: Sync profile with transformation rules

    Returns:
        Transformed record
    """
    result = {}

    for key, value in record.items():
        # Apply field exclusions
        if key in profile.field_exclusions:
            continue

        # Apply field mappings
        dest_key = profile.field_mappings.get(key, key)
        result[dest_key] = value

    return result


def filter_records(records: List[Dict], query: Dict) -> List[Dict]:
    """
    Filter records by query.

    Args:
        records: Records to filter
        query: Query dict with field:value pairs

    Returns:
        Filtered records
    """
    if not query:
        return records

    return [r for r in records if all(r.get(k) == v for k, v in query.items())]


def find_orphans(source_keys: Set[str], dest_keys: Set[str]) -> Set[str]:
    """
    Find orphaned records in destination not present in source.

    Args:
        source_keys: Set of source record keys
        dest_keys: Set of destination record keys

    Returns:
        Set of orphaned keys
    """
    return dest_keys - source_keys


def records_equal(r1: Dict, r2: Dict, exclude_fields: Optional[Set[str]] = None) -> bool:
    """
    Compare two records for equality.

    Args:
        r1: First record
        r2: Second record
        exclude_fields: Fields to exclude from comparison

    Returns:
        True if records are equal
    """
    exclude = exclude_fields or {"_user", "_raw"}
    f1 = {k: v for k, v in r1.items() if k not in exclude}
    f2 = {k: v for k, v in r2.items() if k not in exclude}
    return f1 == f2


# =============================================================================
# Sync Engine Class
# =============================================================================

class SyncEngine:
    """
    Core sync engine that orchestrates synchronization operations.

    The sync engine coordinates between source and destination handlers,
    applying the configured sync profile to determine how records are
    synchronized.
    """

    def __init__(self, source_handler, dest_handler, profile: SyncProfile):
        """
        Initialize sync engine.

        Args:
            source_handler: Handler for source KVStore
            dest_handler: Handler for destination KVStore
            profile: Sync profile configuration
        """
        self.source = source_handler
        self.destination = dest_handler
        self.profile = profile
        self._cancelled = False
        self.conflict_queue: List[Dict] = []

    def cancel(self):
        """Cancel the current sync operation"""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if sync has been cancelled"""
        return self._cancelled

    def reset(self):
        """Reset engine state for new sync"""
        self._cancelled = False
        self.conflict_queue = []

    def sync(self, collection: str, app: str = "search", owner: str = "nobody",
             checkpoint: Optional[Checkpoint] = None) -> SyncResult:
        """
        Execute synchronization.

        Args:
            collection: Collection name to sync
            app: Splunk app context
            owner: Splunk owner context
            checkpoint: Optional checkpoint to resume from

        Returns:
            SyncResult with operation details
        """
        self.reset()

        result = SyncResult(
            success=False,
            mode=self.profile.sync_mode,
            collection=collection,
            app=app,
            owner=owner,
            started_at=datetime.now(),
        )

        try:
            # Connect to both handlers
            if not self.source.connect():
                result.error_message = "Failed to connect to source"
                return result

            if not self.destination.connect():
                result.error_message = "Failed to connect to destination"
                return result

            # Ensure destination collection exists
            if not self.destination.collection_exists(collection, app, owner):
                schema = self.source.get_collection_schema(collection, app, owner)
                self.destination.create_collection(collection, app, owner, schema)

            # Execute sync based on mode
            if self.profile.sync_mode == SyncMode.FULL_SYNC:
                self._full_sync(collection, app, owner, result)
            elif self.profile.sync_mode == SyncMode.INCREMENTAL:
                self._incremental_sync(collection, app, owner, result)
            elif self.profile.sync_mode == SyncMode.APPEND_ONLY:
                self._append_only_sync(collection, app, owner, result)
            elif self.profile.sync_mode == SyncMode.MASTER_SLAVE:
                self._master_slave_sync(collection, app, owner, result)

            result.success = len(result.errors) == 0

        except Exception as e:
            logger.exception(f"Sync failed: {e}")
            result.error_message = str(e)
            result.errors.append(str(e))

        finally:
            self.source.disconnect()
            self.destination.disconnect()
            result.completed_at = datetime.now()

        return result

    def _full_sync(self, collection: str, app: str, owner: str, result: SyncResult):
        """Execute full sync - replace all destination records"""
        logger.info(f"Starting full sync for {collection}")

        # Read all source records
        source_records = list(self.source.read_records(collection, app, owner,
                                                       query=self.profile.filter_query))
        result.records_read = len(source_records)

        if self._cancelled:
            return

        # Get destination keys for orphan detection
        dest_keys = set()
        for record in self.destination.read_records(collection, app, owner):
            dest_keys.add(record.get("_key", ""))

        source_keys = {r.get("_key", "") for r in source_records}

        # Transform and write records in batches
        batches = batch_records(source_records, self.profile.batch_size)

        for batch_num, batch in enumerate(batches):
            if self._cancelled:
                break

            transformed = [transform_record(r, self.profile) for r in batch]
            written, errors = self.destination.write_records(collection, app, owner, transformed)

            result.records_written += written
            result.errors.extend(errors)
            result.batches_processed += 1

            # Save checkpoint
            if batch:
                result.checkpoints.append({
                    "batch": batch_num,
                    "last_key": batch[-1].get("_key", ""),
                    "records_processed": result.records_written,
                })

        # Delete orphans if enabled
        if self.profile.delete_orphans and not self._cancelled:
            orphans = find_orphans(source_keys, dest_keys)
            if orphans:
                deleted, errors = self.destination.delete_records(collection, app, owner, list(orphans))
                result.records_deleted += deleted
                result.errors.extend(errors)

    def _incremental_sync(self, collection: str, app: str, owner: str, result: SyncResult):
        """Execute incremental sync - only sync changed records"""
        logger.info(f"Starting incremental sync for {collection}")

        # Build destination checksum map
        dest_checksums: Dict[str, str] = {}
        for record in self.destination.read_records(collection, app, owner):
            key = record.get("_key", "")
            dest_checksums[key] = compute_checksum(record)

        # Process source records
        source_records = list(self.source.read_records(collection, app, owner,
                                                       query=self.profile.filter_query))
        result.records_read = len(source_records)

        # Find changed records
        to_write = []
        for record in source_records:
            if self._cancelled:
                break

            key = record.get("_key", "")
            source_checksum = compute_checksum(record)

            if key not in dest_checksums:
                # New record
                to_write.append(record)
            elif source_checksum != dest_checksums[key]:
                # Changed record
                to_write.append(record)
            else:
                result.records_skipped += 1

        # Write changed records in batches
        batches = batch_records(to_write, self.profile.batch_size)

        for batch in batches:
            if self._cancelled:
                break

            transformed = [transform_record(r, self.profile) for r in batch]
            written, errors = self.destination.write_records(collection, app, owner, transformed)

            result.records_written += written
            result.errors.extend(errors)
            result.batches_processed += 1

    def _append_only_sync(self, collection: str, app: str, owner: str, result: SyncResult):
        """Execute append-only sync - add new records, never update"""
        logger.info(f"Starting append-only sync for {collection}")

        # Get existing destination keys
        dest_keys = set()
        for record in self.destination.read_records(collection, app, owner):
            dest_keys.add(record.get("_key", ""))

        # Process source records
        source_records = list(self.source.read_records(collection, app, owner,
                                                       query=self.profile.filter_query))
        result.records_read = len(source_records)

        # Find new records only
        to_add = []
        for record in source_records:
            key = record.get("_key", "")
            if key not in dest_keys:
                to_add.append(record)
            else:
                result.records_skipped += 1

        # Write new records in batches
        batches = batch_records(to_add, self.profile.batch_size)

        for batch in batches:
            if self._cancelled:
                break

            transformed = [transform_record(r, self.profile) for r in batch]
            written, errors = self.destination.write_records(collection, app, owner, transformed)

            result.records_written += written
            result.errors.extend(errors)
            result.batches_processed += 1

    def _master_slave_sync(self, collection: str, app: str, owner: str, result: SyncResult):
        """Execute master/slave sync - destination exactly matches source"""
        logger.info(f"Starting master/slave sync for {collection}")

        # This is essentially full sync with delete_orphans forced on
        original_delete_orphans = self.profile.delete_orphans
        self.profile.delete_orphans = True

        try:
            self._full_sync(collection, app, owner, result)
        finally:
            self.profile.delete_orphans = original_delete_orphans
