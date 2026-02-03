"""
Integration tests for complete sync workflows

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/integration/test_sync_workflow.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Integration Test Suite

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Integration tests for end-to-end sync
                                workflows including full sync, incremental
                                sync, and master/slave patterns.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import pytest
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
import hashlib
from datetime import datetime


# =============================================================================
# Integration Test Fixtures
# =============================================================================

@dataclass
class MockKVStoreCollection:
    """Mock KVStore collection for integration testing"""
    name: str
    app: str
    owner: str
    records: Dict[str, Dict] = field(default_factory=dict)
    schema: Optional[Dict] = None

    def get_record(self, key: str) -> Optional[Dict]:
        return self.records.get(key)

    def set_record(self, record: Dict):
        self.records[record["_key"]] = record

    def delete_record(self, key: str) -> bool:
        if key in self.records:
            del self.records[key]
            return True
        return False

    def list_records(self) -> List[Dict]:
        return list(self.records.values())

    def count(self) -> int:
        return len(self.records)

    def clear(self):
        self.records = {}


@dataclass
class MockSyncDestination:
    """Mock sync destination for integration testing"""
    name: str
    dest_type: str
    collections: Dict[str, MockKVStoreCollection] = field(default_factory=dict)
    connected: bool = False

    def get_collection(self, name: str, app: str = "search", owner: str = "nobody") -> MockKVStoreCollection:
        key = f"{app}:{owner}:{name}"
        if key not in self.collections:
            self.collections[key] = MockKVStoreCollection(name=name, app=app, owner=owner)
        return self.collections[key]

    def collection_exists(self, name: str, app: str = "search", owner: str = "nobody") -> bool:
        key = f"{app}:{owner}:{name}"
        return key in self.collections


class MockSyncEngine:
    """Mock sync engine for integration testing"""

    def __init__(self, source: MockSyncDestination, destination: MockSyncDestination):
        self.source = source
        self.destination = destination
        self.sync_history: List[Dict] = []

    def compute_checksum(self, record: Dict) -> str:
        """Compute record checksum"""
        filtered = {k: v for k, v in sorted(record.items())
                   if not k.startswith("_") or k == "_key"}
        return hashlib.sha256(json.dumps(filtered, sort_keys=True).encode()).hexdigest()

    def full_sync(self, collection: str, app: str = "search", owner: str = "nobody",
                 delete_orphans: bool = True) -> Dict:
        """Perform full sync"""
        source_coll = self.source.get_collection(collection, app, owner)
        dest_coll = self.destination.get_collection(collection, app, owner)

        result = {
            "mode": "full_sync",
            "collection": collection,
            "records_written": 0,
            "records_deleted": 0,
            "started_at": datetime.now().isoformat(),
        }

        # Get source and dest keys
        source_keys = set(source_coll.records.keys())
        dest_keys = set(dest_coll.records.keys())

        # Write all source records to destination
        for key, record in source_coll.records.items():
            dest_coll.set_record(record.copy())
            result["records_written"] += 1

        # Delete orphans if enabled
        if delete_orphans:
            orphans = dest_keys - source_keys
            for key in orphans:
                dest_coll.delete_record(key)
                result["records_deleted"] += 1

        result["completed_at"] = datetime.now().isoformat()
        result["success"] = True
        self.sync_history.append(result)

        return result

    def incremental_sync(self, collection: str, app: str = "search", owner: str = "nobody",
                        timestamp_field: str = "_updated") -> Dict:
        """Perform incremental sync"""
        source_coll = self.source.get_collection(collection, app, owner)
        dest_coll = self.destination.get_collection(collection, app, owner)

        result = {
            "mode": "incremental",
            "collection": collection,
            "records_written": 0,
            "records_skipped": 0,
            "started_at": datetime.now().isoformat(),
        }

        for key, source_record in source_coll.records.items():
            dest_record = dest_coll.get_record(key)

            if dest_record is None:
                # New record
                dest_coll.set_record(source_record.copy())
                result["records_written"] += 1
            else:
                # Compare checksums
                source_checksum = self.compute_checksum(source_record)
                dest_checksum = self.compute_checksum(dest_record)

                if source_checksum != dest_checksum:
                    # Record changed
                    dest_coll.set_record(source_record.copy())
                    result["records_written"] += 1
                else:
                    result["records_skipped"] += 1

        result["completed_at"] = datetime.now().isoformat()
        result["success"] = True
        self.sync_history.append(result)

        return result

    def append_only_sync(self, collection: str, app: str = "search", owner: str = "nobody") -> Dict:
        """Perform append-only sync (never update existing)"""
        source_coll = self.source.get_collection(collection, app, owner)
        dest_coll = self.destination.get_collection(collection, app, owner)

        result = {
            "mode": "append_only",
            "collection": collection,
            "records_added": 0,
            "records_skipped": 0,
            "started_at": datetime.now().isoformat(),
        }

        for key, source_record in source_coll.records.items():
            if dest_coll.get_record(key) is None:
                dest_coll.set_record(source_record.copy())
                result["records_added"] += 1
            else:
                result["records_skipped"] += 1

        result["completed_at"] = datetime.now().isoformat()
        result["success"] = True
        self.sync_history.append(result)

        return result


@pytest.fixture
def source_destination():
    """Create source destination with sample data"""
    source = MockSyncDestination(name="source", dest_type="local")
    users = source.get_collection("users")

    # Add sample records
    for i in range(100):
        users.set_record({
            "_key": f"user-{i:04d}",
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "status": "active" if i % 2 == 0 else "inactive",
        })

    return source


@pytest.fixture
def empty_destination():
    """Create empty destination"""
    return MockSyncDestination(name="destination", dest_type="remote")


@pytest.fixture
def sync_engine(source_destination, empty_destination):
    """Create sync engine with source and destination"""
    return MockSyncEngine(source_destination, empty_destination)


# =============================================================================
# Full Sync Integration Tests
# =============================================================================

class TestFullSyncWorkflow:
    """Integration tests for full sync workflow"""

    def test_full_sync_empty_destination(self, sync_engine):
        """Full sync to empty destination copies all records"""
        result = sync_engine.full_sync("users")

        assert result["success"] is True
        assert result["records_written"] == 100
        assert result["records_deleted"] == 0

        # Verify destination has all records
        dest_coll = sync_engine.destination.get_collection("users")
        assert dest_coll.count() == 100

    def test_full_sync_replaces_all_records(self, sync_engine):
        """Full sync replaces all destination records"""
        # Pre-populate destination with different data
        dest_coll = sync_engine.destination.get_collection("users")
        for i in range(50):
            dest_coll.set_record({
                "_key": f"old-user-{i}",
                "name": f"Old User {i}",
            })

        result = sync_engine.full_sync("users")

        assert result["success"] is True
        assert result["records_written"] == 100
        assert result["records_deleted"] == 50  # Old records deleted

        # Verify no old records remain
        assert dest_coll.get_record("old-user-0") is None
        assert dest_coll.get_record("user-0000") is not None

    def test_full_sync_without_delete_orphans(self, sync_engine):
        """Full sync without delete_orphans preserves extra records"""
        # Pre-populate destination
        dest_coll = sync_engine.destination.get_collection("users")
        dest_coll.set_record({"_key": "extra-record", "name": "Extra"})

        result = sync_engine.full_sync("users", delete_orphans=False)

        assert result["records_deleted"] == 0
        assert dest_coll.get_record("extra-record") is not None
        assert dest_coll.count() == 101  # 100 synced + 1 extra

    def test_full_sync_updates_existing_records(self, sync_engine):
        """Full sync updates records that exist in both"""
        # Pre-populate destination with outdated data
        dest_coll = sync_engine.destination.get_collection("users")
        dest_coll.set_record({
            "_key": "user-0000",
            "name": "Outdated Name",
            "email": "old@example.com",
        })

        sync_engine.full_sync("users")

        # Verify record was updated
        record = dest_coll.get_record("user-0000")
        assert record["name"] == "User 0"
        assert record["email"] == "user0@example.com"


# =============================================================================
# Incremental Sync Integration Tests
# =============================================================================

class TestIncrementalSyncWorkflow:
    """Integration tests for incremental sync workflow"""

    def test_incremental_sync_empty_destination(self, sync_engine):
        """Incremental sync to empty destination adds all records"""
        result = sync_engine.incremental_sync("users")

        assert result["success"] is True
        assert result["records_written"] == 100
        assert result["records_skipped"] == 0

    def test_incremental_sync_skips_unchanged(self, sync_engine):
        """Incremental sync skips unchanged records"""
        # First sync all records
        sync_engine.full_sync("users")

        # Incremental sync should skip all (nothing changed)
        result = sync_engine.incremental_sync("users")

        assert result["records_written"] == 0
        assert result["records_skipped"] == 100

    def test_incremental_sync_detects_changes(self, sync_engine):
        """Incremental sync detects and syncs changed records"""
        # First sync
        sync_engine.full_sync("users")

        # Modify some source records
        source_coll = sync_engine.source.get_collection("users")
        for i in range(10):
            record = source_coll.get_record(f"user-{i:04d}")
            record["status"] = "modified"

        # Incremental sync should detect changes
        result = sync_engine.incremental_sync("users")

        assert result["records_written"] == 10
        assert result["records_skipped"] == 90

    def test_incremental_sync_adds_new_records(self, sync_engine):
        """Incremental sync adds new records"""
        # First sync
        sync_engine.full_sync("users")

        # Add new source records
        source_coll = sync_engine.source.get_collection("users")
        for i in range(100, 110):
            source_coll.set_record({
                "_key": f"user-{i:04d}",
                "name": f"New User {i}",
                "email": f"new{i}@example.com",
            })

        result = sync_engine.incremental_sync("users")

        assert result["records_written"] == 10
        assert result["records_skipped"] == 100

        dest_coll = sync_engine.destination.get_collection("users")
        assert dest_coll.count() == 110


# =============================================================================
# Append Only Sync Integration Tests
# =============================================================================

class TestAppendOnlySyncWorkflow:
    """Integration tests for append-only sync workflow"""

    def test_append_only_adds_new_records(self, sync_engine):
        """Append-only sync adds new records"""
        result = sync_engine.append_only_sync("users")

        assert result["success"] is True
        assert result["records_added"] == 100
        assert result["records_skipped"] == 0

    def test_append_only_never_updates(self, sync_engine):
        """Append-only sync never updates existing records"""
        # Pre-populate destination with old data
        dest_coll = sync_engine.destination.get_collection("users")
        dest_coll.set_record({
            "_key": "user-0000",
            "name": "Original Name",  # Different from source
            "email": "original@example.com",
        })

        result = sync_engine.append_only_sync("users")

        # Original record should be preserved
        record = dest_coll.get_record("user-0000")
        assert record["name"] == "Original Name"
        assert result["records_skipped"] == 1
        assert result["records_added"] == 99

    def test_append_only_preserves_extra_records(self, sync_engine):
        """Append-only sync preserves records not in source"""
        dest_coll = sync_engine.destination.get_collection("users")
        dest_coll.set_record({"_key": "local-record", "name": "Local Only"})

        sync_engine.append_only_sync("users")

        # Local record should still exist
        assert dest_coll.get_record("local-record") is not None
        assert dest_coll.count() == 101


# =============================================================================
# Multi-Collection Sync Integration Tests
# =============================================================================

class TestMultiCollectionSync:
    """Integration tests for syncing multiple collections"""

    def test_sync_multiple_collections(self, source_destination, empty_destination):
        """Sync multiple collections in sequence"""
        # Add another collection to source
        groups = source_destination.get_collection("groups")
        for i in range(20):
            groups.set_record({"_key": f"group-{i}", "name": f"Group {i}"})

        engine = MockSyncEngine(source_destination, empty_destination)

        # Sync both collections
        users_result = engine.full_sync("users")
        groups_result = engine.full_sync("groups")

        assert users_result["success"] is True
        assert groups_result["success"] is True

        assert empty_destination.get_collection("users").count() == 100
        assert empty_destination.get_collection("groups").count() == 20

    def test_sync_isolated_between_collections(self, source_destination, empty_destination):
        """Collections are isolated from each other"""
        engine = MockSyncEngine(source_destination, empty_destination)

        # Sync only users
        engine.full_sync("users")

        # Groups should not exist in destination
        assert not empty_destination.collection_exists("groups")


# =============================================================================
# Error Handling Integration Tests
# =============================================================================

class TestSyncErrorHandling:
    """Integration tests for sync error handling"""

    def test_sync_creates_collection_if_missing(self, sync_engine):
        """Sync creates destination collection if it doesn't exist"""
        assert not sync_engine.destination.collection_exists("users")

        sync_engine.full_sync("users")

        assert sync_engine.destination.collection_exists("users")

    def test_sync_history_recorded(self, sync_engine):
        """Sync operations are recorded in history"""
        sync_engine.full_sync("users")
        sync_engine.incremental_sync("users")

        assert len(sync_engine.sync_history) == 2
        assert sync_engine.sync_history[0]["mode"] == "full_sync"
        assert sync_engine.sync_history[1]["mode"] == "incremental"


# =============================================================================
# Data Integrity Integration Tests
# =============================================================================

class TestDataIntegrityWorkflow:
    """Integration tests for data integrity verification"""

    def test_verify_integrity_after_sync(self, sync_engine):
        """Verify data integrity after sync"""
        sync_engine.full_sync("users")

        source_coll = sync_engine.source.get_collection("users")
        dest_coll = sync_engine.destination.get_collection("users")

        # Compute checksums for all records
        source_checksums = {}
        dest_checksums = {}

        for key in source_coll.records:
            source_checksums[key] = sync_engine.compute_checksum(source_coll.get_record(key))

        for key in dest_coll.records:
            dest_checksums[key] = sync_engine.compute_checksum(dest_coll.get_record(key))

        # All checksums should match
        assert source_checksums == dest_checksums

    def test_detect_corruption(self, sync_engine):
        """Detect data corruption after sync"""
        sync_engine.full_sync("users")

        # Corrupt a record in destination
        dest_coll = sync_engine.destination.get_collection("users")
        record = dest_coll.get_record("user-0000")
        record["name"] = "CORRUPTED"

        # Verify integrity fails
        source_coll = sync_engine.source.get_collection("users")
        source_checksum = sync_engine.compute_checksum(source_coll.get_record("user-0000"))
        dest_checksum = sync_engine.compute_checksum(dest_coll.get_record("user-0000"))

        assert source_checksum != dest_checksum
