"""
pytest configuration and fixtures for BDD tests

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/conftest.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Test Configuration

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  pytest-bdd configuration with fixtures for
                                sync engine, handlers, and mock services.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import pytest
import json
import hashlib
from typing import Any, Dict, Generator, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock, patch


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_records() -> List[Dict]:
    """Sample KVStore records for testing"""
    return [
        {"_key": "user-001", "name": "Alice", "email": "alice@example.com", "status": "active"},
        {"_key": "user-002", "name": "Bob", "email": "bob@example.com", "status": "active"},
        {"_key": "user-003", "name": "Charlie", "email": "charlie@example.com", "status": "inactive"},
        {"_key": "user-004", "name": "Diana", "email": "diana@example.com", "status": "active"},
        {"_key": "user-005", "name": "Eve", "email": "eve@example.com", "status": "pending"},
    ]


@pytest.fixture
def sample_destination_config() -> Dict:
    """Sample destination configuration"""
    return {
        "name": "test-destination",
        "destination_type": "splunk_rest",
        "host": "localhost",
        "port": 8089,
        "use_ssl": True,
        "verify_ssl": False,
        "auth_type": "token",
        "username": None,
        "password": "test-token-12345",
        "target_app": "search",
        "target_owner": "nobody",
        "connection_timeout": 30,
        "max_retries": 3,
    }


@pytest.fixture
def sample_sync_profile() -> Dict:
    """Sample sync profile configuration"""
    return {
        "name": "test-profile",
        "sync_mode": "incremental",
        "conflict_resolution": "source_wins",
        "batch_size": 100,
        "delete_orphans": False,
        "preserve_key": True,
        "timestamp_field": "_updated",
        "key_fields": ["_key"],
        "field_mappings": {},
        "field_exclusions": ["_user", "_raw"],
        "filter_query": {},
    }


@pytest.fixture
def sample_collection_mapping() -> Dict:
    """Sample collection mapping"""
    return {
        "name": "users-mapping",
        "source_app": "search",
        "source_collection": "users",
        "source_owner": "nobody",
        "destination_collection": "users",
        "auto_create_collection": True,
        "sync_schema": True,
        "enabled": True,
    }


# =============================================================================
# Mock Handler Fixtures
# =============================================================================

@dataclass
class MockKVStore:
    """In-memory KVStore for testing"""
    collections: Dict[str, Dict[str, Dict]] = field(default_factory=dict)
    schemas: Dict[str, Dict] = field(default_factory=dict)

    def get_collection(self, name: str, app: str, owner: str) -> Dict[str, Dict]:
        key = f"{app}:{owner}:{name}"
        if key not in self.collections:
            self.collections[key] = {}
        return self.collections[key]

    def set_collection(self, name: str, app: str, owner: str, records: List[Dict]) -> None:
        key = f"{app}:{owner}:{name}"
        self.collections[key] = {r["_key"]: r for r in records}

    def get_record(self, collection: str, app: str, owner: str, record_key: str) -> Optional[Dict]:
        coll = self.get_collection(collection, app, owner)
        return coll.get(record_key)

    def set_record(self, collection: str, app: str, owner: str, record: Dict) -> None:
        coll = self.get_collection(collection, app, owner)
        coll[record["_key"]] = record

    def delete_record(self, collection: str, app: str, owner: str, record_key: str) -> bool:
        coll = self.get_collection(collection, app, owner)
        if record_key in coll:
            del coll[record_key]
            return True
        return False

    def list_records(self, collection: str, app: str, owner: str) -> List[Dict]:
        coll = self.get_collection(collection, app, owner)
        return list(coll.values())

    def count_records(self, collection: str, app: str, owner: str) -> int:
        return len(self.get_collection(collection, app, owner))

    def clear_collection(self, collection: str, app: str, owner: str) -> None:
        key = f"{app}:{owner}:{collection}"
        self.collections[key] = {}


@pytest.fixture
def mock_kvstore() -> MockKVStore:
    """Create a fresh mock KVStore"""
    return MockKVStore()


@pytest.fixture
def source_kvstore(mock_kvstore, sample_records) -> MockKVStore:
    """Mock KVStore with sample data as source"""
    mock_kvstore.set_collection("users", "search", "nobody", sample_records)
    return mock_kvstore


@pytest.fixture
def empty_dest_kvstore() -> MockKVStore:
    """Empty mock KVStore as destination"""
    return MockKVStore()


# =============================================================================
# Mock Handler Class
# =============================================================================

class MockSyncHandler:
    """
    Mock sync handler for testing.

    Implements the same interface as BaseSyncHandler but uses MockKVStore.
    """

    def __init__(self, kvstore: MockKVStore, name: str = "mock"):
        self.kvstore = kvstore
        self.name = name
        self._connected = False
        self._cancelled = False
        self.destination = MagicMock()
        self.destination.name = name

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def test_connection(self) -> tuple:
        return True, f"Mock connection to {self.name} successful"

    def collection_exists(self, collection: str, app: str, owner: str) -> bool:
        key = f"{app}:{owner}:{collection}"
        return key in self.kvstore.collections

    def create_collection(self, collection: str, app: str, owner: str, schema: Optional[Dict] = None) -> bool:
        key = f"{app}:{owner}:{collection}"
        if key not in self.kvstore.collections:
            self.kvstore.collections[key] = {}
        if schema:
            self.kvstore.schemas[key] = schema
        return True

    def get_collection_schema(self, collection: str, app: str, owner: str) -> Optional[Dict]:
        key = f"{app}:{owner}:{collection}"
        return self.kvstore.schemas.get(key)

    def read_records(self, collection: str, app: str, owner: str,
                     query: Optional[Dict] = None, fields: Optional[List[str]] = None,
                     skip: int = 0, limit: int = 0) -> Generator[Dict, None, None]:
        records = self.kvstore.list_records(collection, app, owner)

        # Apply query filter
        if query:
            records = [r for r in records if all(r.get(k) == v for k, v in query.items())]

        # Apply skip and limit
        if skip:
            records = records[skip:]
        if limit:
            records = records[:limit]

        # Apply field filter
        for record in records:
            if self._cancelled:
                break
            if fields:
                yield {k: v for k, v in record.items() if k in fields}
            else:
                yield record

    def write_records(self, collection: str, app: str, owner: str,
                      records: List[Dict], preserve_key: bool = True) -> tuple:
        written = 0
        errors = []

        for record in records:
            try:
                self.kvstore.set_record(collection, app, owner, record)
                written += 1
            except Exception as e:
                errors.append(str(e))

        return written, errors

    def update_record(self, collection: str, app: str, owner: str,
                      key: str, record: Dict) -> bool:
        record["_key"] = key
        self.kvstore.set_record(collection, app, owner, record)
        return True

    def delete_records(self, collection: str, app: str, owner: str,
                       keys: List[str]) -> tuple:
        deleted = 0
        errors = []

        for key in keys:
            if self.kvstore.delete_record(collection, app, owner, key):
                deleted += 1

        return deleted, errors

    def get_record_count(self, collection: str, app: str, owner: str,
                         query: Optional[Dict] = None) -> int:
        if query:
            records = list(self.read_records(collection, app, owner, query))
            return len(records)
        return self.kvstore.count_records(collection, app, owner)

    def get_record_by_key(self, collection: str, app: str, owner: str,
                          key: str) -> Optional[Dict]:
        return self.kvstore.get_record(collection, app, owner, key)

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def reset_cancelled(self) -> None:
        self._cancelled = False


@pytest.fixture
def mock_source_handler(source_kvstore) -> MockSyncHandler:
    """Mock handler for source with data"""
    return MockSyncHandler(source_kvstore, "source")


@pytest.fixture
def mock_dest_handler(empty_dest_kvstore) -> MockSyncHandler:
    """Mock handler for empty destination"""
    return MockSyncHandler(empty_dest_kvstore, "destination")


# =============================================================================
# BDD Context Fixtures
# =============================================================================

@dataclass
class BDDContext:
    """Shared context for BDD step definitions"""
    # Configuration
    destinations: Dict[str, Dict] = field(default_factory=dict)
    sync_profiles: Dict[str, Dict] = field(default_factory=dict)
    collection_mappings: Dict[str, Dict] = field(default_factory=dict)

    # Handlers
    source_handler: Optional[MockSyncHandler] = None
    dest_handlers: Dict[str, MockSyncHandler] = field(default_factory=dict)

    # Results
    last_result: Optional[Any] = None
    last_error: Optional[str] = None
    finger_results: Dict[str, Dict] = field(default_factory=dict)
    integrity_report: Optional[Dict] = None

    # UI State
    current_page: str = ""
    form_data: Dict[str, Any] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)

    # Audit
    audit_log: List[Dict] = field(default_factory=list)


@pytest.fixture
def bdd_context() -> BDDContext:
    """Fresh BDD context for each scenario"""
    return BDDContext()


# =============================================================================
# Utility Functions
# =============================================================================

def compute_checksum(record: Dict, exclude_fields: Optional[set] = None) -> str:
    """Compute SHA-256 checksum for a record"""
    exclude = exclude_fields or {"_user", "_raw"}
    filtered = {k: v for k, v in sorted(record.items()) if k not in exclude}
    json_str = json.dumps(filtered, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


def compute_merkle_root(checksums: List[str]) -> str:
    """Compute Merkle root from list of checksums"""
    if not checksums:
        return hashlib.sha256(b"").hexdigest()

    hashes = checksums.copy()

    while len(hashes) > 1:
        next_level = []
        for i in range(0, len(hashes), 2):
            if i + 1 < len(hashes):
                combined = hashes[i] + hashes[i + 1]
            else:
                combined = hashes[i] + hashes[i]
            next_level.append(hashlib.sha256(combined.encode()).hexdigest())
        hashes = next_level

    return hashes[0]


@pytest.fixture
def checksum_utils():
    """Expose checksum utilities to tests"""
    return {
        "compute_checksum": compute_checksum,
        "compute_merkle_root": compute_merkle_root,
    }


# =============================================================================
# pytest-bdd Hooks
# =============================================================================

def pytest_bdd_step_error(request, feature, scenario, step, step_func, step_func_args, exception):
    """Log step errors for debugging"""
    print(f"\nStep failed: {step}")
    print(f"Exception: {exception}")


def pytest_bdd_after_scenario(request, feature, scenario):
    """Cleanup after each scenario"""
    # Could add cleanup logic here
    pass
