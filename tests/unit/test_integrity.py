"""
Unit tests for data integrity verification

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/unit/test_integrity.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Unit Test Suite

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Unit tests for checksums, Merkle trees,
                                parity verification, and finger probes.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import pytest
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from functools import reduce
import operator


# =============================================================================
# Checksum Tests
# =============================================================================

class TestRecordChecksum:
    """Tests for record checksum computation"""

    def compute_checksum(self, record: Dict, exclude_fields: set = None) -> str:
        """Compute SHA-256 checksum for a record"""
        exclude = exclude_fields or {"_user", "_raw", "_batchID"}
        filtered = {}
        for key in sorted(record.keys()):
            if key not in exclude:
                filtered[key] = record[key]
        json_str = json.dumps(filtered, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

    def test_checksum_basic_record(self):
        """Basic record produces valid checksum"""
        record = {"_key": "rec-1", "name": "Test", "value": 42}

        checksum = self.compute_checksum(record)

        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 hex length

    def test_checksum_excludes_default_fields(self):
        """Checksum excludes _user, _raw, _batchID by default"""
        record1 = {"_key": "rec-1", "name": "Test", "_user": "admin", "_raw": "data", "_batchID": "123"}
        record2 = {"_key": "rec-1", "name": "Test"}

        assert self.compute_checksum(record1) == self.compute_checksum(record2)

    def test_checksum_custom_exclusions(self):
        """Checksum respects custom exclusion list"""
        record1 = {"_key": "rec-1", "name": "Test", "internal": "value"}
        record2 = {"_key": "rec-1", "name": "Test"}

        checksum1 = self.compute_checksum(record1, exclude_fields={"internal"})
        checksum2 = self.compute_checksum(record2, exclude_fields=set())

        assert checksum1 == checksum2

    def test_checksum_different_values_differ(self):
        """Different values produce different checksums"""
        record1 = {"_key": "rec-1", "value": 1}
        record2 = {"_key": "rec-1", "value": 2}

        assert self.compute_checksum(record1) != self.compute_checksum(record2)

    def test_checksum_handles_nested_data(self):
        """Checksum works with nested objects and arrays"""
        record = {
            "_key": "rec-1",
            "metadata": {
                "created": "2026-01-01",
                "tags": ["tag1", "tag2"],
            },
            "values": [1, 2, 3],
        }

        checksum = self.compute_checksum(record)

        assert len(checksum) == 64

    def test_checksum_handles_special_characters(self):
        """Checksum handles unicode and special characters"""
        record = {"_key": "rec-1", "name": "Tëst Üñîcödé 日本語"}

        checksum = self.compute_checksum(record)

        assert len(checksum) == 64

    def test_checksum_handles_null_values(self):
        """Checksum handles None/null values"""
        record = {"_key": "rec-1", "name": None, "value": None}

        checksum = self.compute_checksum(record)

        assert len(checksum) == 64


# =============================================================================
# Merkle Tree Tests
# =============================================================================

class TestMerkleTree:
    """Tests for Merkle tree computation"""

    def compute_merkle_root(self, checksums: List[str]) -> str:
        """Compute Merkle root from list of checksums"""
        if not checksums:
            return hashlib.sha256(b"").hexdigest()

        hashes = checksums.copy()

        # Handle single element by hashing with itself
        if len(hashes) == 1:
            combined = hashes[0] + hashes[0]
            return hashlib.sha256(combined.encode()).hexdigest()

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

    def test_merkle_root_empty_list(self):
        """Empty list produces consistent empty hash"""
        root = self.compute_merkle_root([])
        expected = hashlib.sha256(b"").hexdigest()

        assert root == expected

    def test_merkle_root_single_element(self):
        """Single element hashed with itself"""
        checksum = "abc123"
        root = self.compute_merkle_root([checksum])

        expected = hashlib.sha256((checksum + checksum).encode()).hexdigest()
        assert root == expected

    def test_merkle_root_two_elements(self):
        """Two elements combined correctly"""
        checksums = ["abc", "def"]
        root = self.compute_merkle_root(checksums)

        expected = hashlib.sha256(("abc" + "def").encode()).hexdigest()
        assert root == expected

    def test_merkle_root_power_of_two(self):
        """Power of two elements balanced correctly"""
        checksums = ["a", "b", "c", "d"]
        root = self.compute_merkle_root(checksums)

        # Level 1: hash(a+b), hash(c+d)
        # Level 2: hash(level1[0] + level1[1])
        level1_0 = hashlib.sha256("ab".encode()).hexdigest()
        level1_1 = hashlib.sha256("cd".encode()).hexdigest()
        expected = hashlib.sha256((level1_0 + level1_1).encode()).hexdigest()

        assert root == expected

    def test_merkle_root_odd_elements(self):
        """Odd number of elements handled by duplication"""
        checksums = ["a", "b", "c"]
        root = self.compute_merkle_root(checksums)

        # Level 1: hash(a+b), hash(c+c)
        level1_0 = hashlib.sha256("ab".encode()).hexdigest()
        level1_1 = hashlib.sha256("cc".encode()).hexdigest()
        expected = hashlib.sha256((level1_0 + level1_1).encode()).hexdigest()

        assert root == expected

    def test_merkle_root_deterministic(self):
        """Same input produces same root"""
        checksums = ["abc", "def", "ghi"]

        roots = [self.compute_merkle_root(checksums) for _ in range(5)]

        assert all(r == roots[0] for r in roots)

    def test_merkle_root_detects_changes(self):
        """Changing one checksum changes the root"""
        checksums1 = ["abc", "def", "ghi"]
        checksums2 = ["abc", "DEF", "ghi"]

        root1 = self.compute_merkle_root(checksums1)
        root2 = self.compute_merkle_root(checksums2)

        assert root1 != root2


# =============================================================================
# Parity Block Tests
# =============================================================================

class TestParityBlocks:
    """Tests for parity block computation"""

    def compute_parity(self, data_blocks: List[bytes]) -> bytes:
        """Compute XOR parity block from data blocks"""
        if not data_blocks:
            return b""

        # All blocks must be same length, pad if necessary
        max_len = max(len(b) for b in data_blocks)
        padded = [b.ljust(max_len, b'\x00') for b in data_blocks]

        result = bytearray(max_len)
        for block in padded:
            for i, byte in enumerate(block):
                result[i] ^= byte

        return bytes(result)

    def verify_parity(self, data_blocks: List[bytes], parity: bytes) -> bool:
        """Verify data blocks against parity"""
        computed = self.compute_parity(data_blocks)
        return computed == parity

    def test_parity_empty_list(self):
        """Empty list produces empty parity"""
        parity = self.compute_parity([])
        assert parity == b""

    def test_parity_single_block(self):
        """Single block is its own parity"""
        block = b"hello"
        parity = self.compute_parity([block])

        assert parity == block

    def test_parity_two_blocks(self):
        """XOR of two identical blocks is zeros"""
        block = b"hello"
        parity = self.compute_parity([block, block])

        assert parity == b"\x00" * len(block)

    def test_parity_verification(self):
        """Parity verifies unchanged data"""
        blocks = [b"block1", b"block2", b"block3"]
        parity = self.compute_parity(blocks)

        assert self.verify_parity(blocks, parity) is True

    def test_parity_detects_corruption(self):
        """Parity detects corrupted block"""
        blocks = [b"block1", b"block2", b"block3"]
        parity = self.compute_parity(blocks)

        # Corrupt one block
        corrupted = [b"BLOCK1", b"block2", b"block3"]

        assert self.verify_parity(corrupted, parity) is False

    def test_parity_different_length_blocks(self):
        """Handles blocks of different lengths"""
        blocks = [b"short", b"medium_len", b"very_long_block"]
        parity = self.compute_parity(blocks)

        assert len(parity) == len(b"very_long_block")

    def test_parity_recovery(self):
        """Can recover missing block from parity"""
        blocks = [b"aaaa", b"bbbb", b"cccc"]
        parity = self.compute_parity(blocks)

        # To recover block 1, XOR parity with other blocks
        remaining = [blocks[0], blocks[2]]
        remaining_parity = self.compute_parity(remaining)
        recovered = self.compute_parity([remaining_parity, parity])

        assert recovered == blocks[1]


# =============================================================================
# Finger Probe Tests
# =============================================================================

@dataclass
class FingerProbeResult:
    """Result of a finger probe check"""
    destination: str
    collection: str
    status: str = "pending"  # "ok", "mismatch", "unreachable", "error"
    source_count: int = 0
    dest_count: int = 0
    source_checksum: str = ""
    dest_checksum: str = ""
    latency_ms: float = 0
    error_message: str = ""


class MockFingerProbeService:
    """Mock finger probe service for testing"""

    def __init__(self):
        self.source_data: Dict[str, Dict[str, List[Dict]]] = {}  # collection -> app:owner -> records
        self.dest_data: Dict[str, Dict[str, Dict[str, List[Dict]]]] = {}  # dest -> collection -> records

    def set_source_collection(self, collection: str, app: str, owner: str, records: List[Dict]):
        """Set source collection data"""
        key = f"{app}:{owner}"
        if collection not in self.source_data:
            self.source_data[collection] = {}
        self.source_data[collection][key] = records

    def set_dest_collection(self, dest: str, collection: str, records: List[Dict]):
        """Set destination collection data"""
        if dest not in self.dest_data:
            self.dest_data[dest] = {}
        self.dest_data[dest][collection] = records

    def compute_collection_checksum(self, records: List[Dict]) -> str:
        """Compute checksum for entire collection"""
        if not records:
            return hashlib.sha256(b"").hexdigest()

        checksums = []
        for record in sorted(records, key=lambda r: r.get("_key", "")):
            filtered = {k: v for k, v in sorted(record.items()) if not k.startswith("_") or k == "_key"}
            json_str = json.dumps(filtered, sort_keys=True, default=str)
            checksums.append(hashlib.sha256(json_str.encode()).hexdigest())

        return hashlib.sha256("".join(checksums).encode()).hexdigest()

    def probe(self, destination: str, collection: str, app: str = "search",
              owner: str = "nobody") -> FingerProbeResult:
        """Execute finger probe against destination"""
        result = FingerProbeResult(destination=destination, collection=collection)

        # Get source data
        source_key = f"{app}:{owner}"
        if collection not in self.source_data or source_key not in self.source_data[collection]:
            result.status = "error"
            result.error_message = "Source collection not found"
            return result

        source_records = self.source_data[collection][source_key]
        result.source_count = len(source_records)
        result.source_checksum = self.compute_collection_checksum(source_records)

        # Get destination data
        if destination not in self.dest_data:
            result.status = "unreachable"
            result.error_message = "Destination not reachable"
            return result

        if collection not in self.dest_data[destination]:
            result.status = "mismatch"
            result.dest_count = 0
            result.dest_checksum = hashlib.sha256(b"").hexdigest()
            return result

        dest_records = self.dest_data[destination][collection]
        result.dest_count = len(dest_records)
        result.dest_checksum = self.compute_collection_checksum(dest_records)

        # Compare
        if result.source_checksum == result.dest_checksum:
            result.status = "ok"
        else:
            result.status = "mismatch"

        return result


class TestFingerProbe:
    """Tests for finger probe functionality"""

    @pytest.fixture
    def probe_service(self):
        return MockFingerProbeService()

    def test_probe_matching_collections(self, probe_service):
        """Probe returns OK for matching collections"""
        records = [{"_key": "rec-1", "value": 1}, {"_key": "rec-2", "value": 2}]
        probe_service.set_source_collection("users", "search", "nobody", records)
        probe_service.set_dest_collection("dest1", "users", records)

        result = probe_service.probe("dest1", "users")

        assert result.status == "ok"
        assert result.source_count == 2
        assert result.dest_count == 2
        assert result.source_checksum == result.dest_checksum

    def test_probe_mismatched_collections(self, probe_service):
        """Probe returns mismatch for different collections"""
        source_records = [{"_key": "rec-1", "value": 1}]
        dest_records = [{"_key": "rec-1", "value": 2}]

        probe_service.set_source_collection("users", "search", "nobody", source_records)
        probe_service.set_dest_collection("dest1", "users", dest_records)

        result = probe_service.probe("dest1", "users")

        assert result.status == "mismatch"
        assert result.source_checksum != result.dest_checksum

    def test_probe_unreachable_destination(self, probe_service):
        """Probe returns unreachable for missing destination"""
        probe_service.set_source_collection("users", "search", "nobody", [{"_key": "1"}])

        result = probe_service.probe("nonexistent", "users")

        assert result.status == "unreachable"

    def test_probe_missing_collection_at_dest(self, probe_service):
        """Probe returns mismatch when collection missing at destination"""
        probe_service.set_source_collection("users", "search", "nobody", [{"_key": "1"}])
        probe_service.dest_data["dest1"] = {}  # Destination exists but no collection

        result = probe_service.probe("dest1", "users")

        assert result.status == "mismatch"
        assert result.dest_count == 0

    def test_probe_different_record_counts(self, probe_service):
        """Probe detects different record counts"""
        source_records = [{"_key": f"rec-{i}"} for i in range(10)]
        dest_records = [{"_key": f"rec-{i}"} for i in range(5)]

        probe_service.set_source_collection("users", "search", "nobody", source_records)
        probe_service.set_dest_collection("dest1", "users", dest_records)

        result = probe_service.probe("dest1", "users")

        assert result.status == "mismatch"
        assert result.source_count == 10
        assert result.dest_count == 5


# =============================================================================
# Integrity Report Tests
# =============================================================================

@dataclass
class IntegrityReport:
    """Integrity verification report"""
    timestamp: str
    source: str
    destinations: Dict[str, Dict] = field(default_factory=dict)
    overall_status: str = "unknown"
    total_collections: int = 0
    collections_in_sync: int = 0
    collections_mismatched: int = 0

    def add_destination_result(self, dest: str, collection: str, result: FingerProbeResult):
        """Add probe result to report"""
        if dest not in self.destinations:
            self.destinations[dest] = {"collections": {}, "status": "unknown"}

        self.destinations[dest]["collections"][collection] = {
            "status": result.status,
            "source_count": result.source_count,
            "dest_count": result.dest_count,
            "source_checksum": result.source_checksum[:16] + "...",
            "dest_checksum": result.dest_checksum[:16] + "...",
        }

    def compute_overall_status(self):
        """Compute overall status from all results"""
        all_ok = True
        any_error = False

        for dest, data in self.destinations.items():
            for coll, result in data["collections"].items():
                self.total_collections += 1
                if result["status"] == "ok":
                    self.collections_in_sync += 1
                elif result["status"] == "mismatch":
                    self.collections_mismatched += 1
                    all_ok = False
                else:
                    any_error = True
                    all_ok = False

        if all_ok:
            self.overall_status = "ok"
        elif any_error:
            self.overall_status = "error"
        else:
            self.overall_status = "degraded"


class TestIntegrityReport:
    """Tests for integrity report generation"""

    def test_empty_report(self):
        """Empty report has unknown status"""
        report = IntegrityReport(timestamp="2026-02-03T10:00:00", source="localhost")

        assert report.overall_status == "unknown"

    def test_all_ok_report(self):
        """All OK results produce OK overall status"""
        report = IntegrityReport(timestamp="2026-02-03T10:00:00", source="localhost")

        result = FingerProbeResult(
            destination="dest1",
            collection="users",
            status="ok",
            source_count=100,
            dest_count=100,
            source_checksum="abc123",
            dest_checksum="abc123",
        )
        report.add_destination_result("dest1", "users", result)
        report.compute_overall_status()

        assert report.overall_status == "ok"
        assert report.collections_in_sync == 1

    def test_mismatch_produces_degraded(self):
        """Mismatch produces degraded status"""
        report = IntegrityReport(timestamp="2026-02-03T10:00:00", source="localhost")

        ok_result = FingerProbeResult(destination="dest1", collection="users", status="ok",
                                      source_checksum="abc", dest_checksum="abc")
        mismatch_result = FingerProbeResult(destination="dest1", collection="groups", status="mismatch",
                                           source_checksum="abc", dest_checksum="def")

        report.add_destination_result("dest1", "users", ok_result)
        report.add_destination_result("dest1", "groups", mismatch_result)
        report.compute_overall_status()

        assert report.overall_status == "degraded"
        assert report.collections_in_sync == 1
        assert report.collections_mismatched == 1

    def test_error_produces_error_status(self):
        """Error result produces error overall status"""
        report = IntegrityReport(timestamp="2026-02-03T10:00:00", source="localhost")

        error_result = FingerProbeResult(destination="dest1", collection="users", status="error",
                                        source_checksum="", dest_checksum="", error_message="Connection failed")

        report.add_destination_result("dest1", "users", error_result)
        report.compute_overall_status()

        assert report.overall_status == "error"
