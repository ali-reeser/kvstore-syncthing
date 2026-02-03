"""
HTTP Event Collector (HEC) Handler - Index & Rehydrate Pattern

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/hec.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  HEC handler for Index & Rehydrate pattern.
                                Sends KVStore records to HEC for archival,
                                and supports rehydration from indexed events.
                                Uses splunk-sdk for search operations.
-------------------------------------------------------------------------------

License: MIT

PATTERN: Index & Rehydrate
1. EXPORT: KVStore records -> HEC -> Splunk Index (with metadata)
2. ARCHIVE: Events persist in index with retention policy
3. REHYDRATE: Search index -> Extract records -> Write to KVStore

This pattern enables:
- Point-in-time recovery
- Cross-cluster sync via indexes
- Disaster recovery
- Compliance archival
===============================================================================
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)


# =============================================================================
# SDK Imports
# =============================================================================

# HEC uses requests for the collector endpoint
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

# Rehydration uses splunk-sdk for search
try:
    import splunklib.client as splunk_client
    import splunklib.results as splunk_results
    SPLUNK_SDK_AVAILABLE = True
except ImportError:
    SPLUNK_SDK_AVAILABLE = False
    splunk_client = None


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class HECConfig:
    """Configuration for HEC destination"""
    name: str
    hec_url: str  # e.g., https://splunk.example.com:8088
    hec_token: str  # HEC token (encrypted via UCC)

    # Event metadata
    index: str = "kvstore_archive"
    source: str = "kvstore_syncthing"
    sourcetype: str = "kvstore_sync"
    host: Optional[str] = None  # Defaults to source host

    # SSL settings
    use_ssl: bool = True
    verify_ssl: bool = False

    # Batching
    batch_size: int = 100
    max_batch_bytes: int = 1024 * 1024  # 1MB
    flush_interval_seconds: int = 5

    # HEC features
    use_acknowledgment: bool = True
    ack_timeout_seconds: int = 30
    ack_poll_interval: float = 0.5

    # Retry settings
    max_retries: int = 3
    retry_backoff: float = 1.0

    # Performance
    num_threads: int = 4


@dataclass
class RehydrationConfig:
    """Configuration for rehydration from index"""
    # Source Splunk connection
    host: str
    port: int = 8089
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    use_ssl: bool = True
    verify_ssl: bool = False
    app: str = "search"
    owner: str = "nobody"

    # Search settings
    index: str = "kvstore_archive"
    source: str = "kvstore_syncthing"
    sourcetype: str = "kvstore_sync"

    # Time range for rehydration
    earliest: str = "-7d"
    latest: str = "now"

    # Target collection
    target_collection: Optional[str] = None  # None = use original
    target_app: str = "search"
    target_owner: str = "nobody"

    # Options
    verify_checksums: bool = True
    conflict_resolution: str = "newest_wins"  # newest_wins, source_wins, skip


# =============================================================================
# HEC Event Builder
# =============================================================================

class HECEventBuilder:
    """Builds HEC events from KVStore records"""

    @staticmethod
    def build_event(
        record: Dict[str, Any],
        collection: str,
        app: str,
        owner: str,
        source_host: str,
        config: HECConfig
    ) -> Dict[str, Any]:
        """
        Build a HEC event from a KVStore record.

        The event includes metadata for later rehydration.
        """
        # Calculate checksum for integrity verification
        record_json = json.dumps(record, sort_keys=True, separators=(',', ':'))
        checksum = hashlib.sha256(record_json.encode()).hexdigest()

        # Build event payload
        event_data = {
            "_kvstore_record": record,
            "_kvstore_meta": {
                "collection": collection,
                "app": app,
                "owner": owner,
                "key": record.get("_key", ""),
                "source_host": source_host,
                "sync_time": datetime.utcnow().isoformat(),
                "checksum": f"sha256:{checksum}",
            }
        }

        # Build HEC event structure
        hec_event = {
            "event": event_data,
            "source": config.source,
            "sourcetype": config.sourcetype,
            "index": config.index,
            "time": time.time(),  # Event time
        }

        if config.host:
            hec_event["host"] = config.host
        else:
            hec_event["host"] = source_host

        return hec_event

    @staticmethod
    def extract_record(event: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract KVStore record and metadata from indexed event.

        Returns:
            Tuple of (record, metadata)
        """
        if isinstance(event.get("_raw"), str):
            # Event from search results - parse _raw
            try:
                event_data = json.loads(event["_raw"])
            except json.JSONDecodeError:
                return {}, {}
        else:
            event_data = event

        record = event_data.get("_kvstore_record", {})
        meta = event_data.get("_kvstore_meta", {})

        return record, meta


# =============================================================================
# HEC Client with Acknowledgment
# =============================================================================

class HECClient:
    """
    HEC client with indexer acknowledgment support.

    Uses the /services/collector endpoint for events
    and /services/collector/ack for acknowledgments.
    """

    def __init__(self, config: HECConfig):
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests is required for HEC. Install: pip install requests")

        self.config = config
        self._session = self._create_session()
        self._pending_acks: Dict[int, List[Dict]] = {}  # channel_id -> events
        self._ack_lock = threading.Lock()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic"""
        session = requests.Session()

        # Configure retries
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        session.headers.update({
            "Authorization": f"Splunk {self.config.hec_token}",
            "Content-Type": "application/json",
        })

        return session

    def send_events(
        self,
        events: List[Dict[str, Any]],
        wait_for_ack: bool = True
    ) -> Tuple[bool, str, int]:
        """
        Send events to HEC.

        Args:
            events: List of HEC events
            wait_for_ack: Whether to wait for indexer acknowledgment

        Returns:
            Tuple of (success, error_message, events_sent)
        """
        if not events:
            return True, "", 0

        # Build URL
        url = f"{self.config.hec_url}/services/collector/event"

        # Generate channel for ack tracking
        channel = None
        if self.config.use_acknowledgment and wait_for_ack:
            import uuid
            channel = str(uuid.uuid4())
            url = f"{url}?channel={channel}"

        # Build payload (newline-delimited JSON)
        payload_lines = [json.dumps(event) for event in events]
        payload = "\n".join(payload_lines)

        try:
            response = self._session.post(
                url,
                data=payload,
                verify=self.config.verify_ssl,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                if self.config.use_acknowledgment and wait_for_ack and channel:
                    # Wait for acknowledgment
                    ack_id = result.get("ackId")
                    if ack_id is not None:
                        ack_success = self._wait_for_ack(channel, ack_id)
                        if not ack_success:
                            return False, "Acknowledgment timeout", 0

                return True, "", len(events)

            elif response.status_code == 400:
                return False, f"Bad request: {response.text}", 0
            elif response.status_code == 401:
                return False, "Invalid HEC token", 0
            elif response.status_code == 403:
                return False, "HEC token disabled or insufficient permissions", 0
            else:
                return False, f"HEC error {response.status_code}: {response.text}", 0

        except requests.exceptions.RequestException as e:
            return False, f"Request error: {e}", 0

    def _wait_for_ack(self, channel: str, ack_id: int) -> bool:
        """Wait for indexer acknowledgment"""
        url = f"{self.config.hec_url}/services/collector/ack?channel={channel}"
        deadline = time.time() + self.config.ack_timeout_seconds

        while time.time() < deadline:
            try:
                response = self._session.post(
                    url,
                    json={"acks": [ack_id]},
                    verify=self.config.verify_ssl,
                    timeout=10
                )

                if response.status_code == 200:
                    result = response.json()
                    acks = result.get("acks", {})

                    if str(ack_id) in acks and acks[str(ack_id)]:
                        logger.debug(f"HEC ack received for {ack_id}")
                        return True

                time.sleep(self.config.ack_poll_interval)

            except Exception as e:
                logger.warning(f"Ack poll error: {e}")
                time.sleep(self.config.ack_poll_interval)

        logger.error(f"Ack timeout for {ack_id}")
        return False

    def health_check(self) -> Tuple[bool, str]:
        """Check HEC health"""
        url = f"{self.config.hec_url}/services/collector/health"

        try:
            response = self._session.get(
                url,
                verify=self.config.verify_ssl,
                timeout=10
            )

            if response.status_code == 200:
                return True, "HEC is healthy"
            else:
                return False, f"HEC unhealthy: {response.status_code}"

        except Exception as e:
            return False, f"HEC connection error: {e}"


# =============================================================================
# HEC Sync Handler
# =============================================================================

class HECSyncHandler:
    """
    Handler for syncing KVStore to index via HEC.

    Implements the "export" phase of Index & Rehydrate pattern.
    """

    def __init__(self, config: HECConfig):
        self.config = config
        self._client = HECClient(config)
        self._event_builder = HECEventBuilder()

        # Batch queue
        self._batch_queue: Queue = Queue()
        self._batch: List[Dict] = []
        self._batch_bytes = 0
        self._batch_lock = threading.Lock()

        # Stats
        self._events_sent = 0
        self._events_failed = 0
        self._last_flush = time.time()

    def test_connection(self) -> Tuple[bool, str]:
        """Test HEC connection"""
        return self._client.health_check()

    def sync_collection(
        self,
        records: Generator[Dict[str, Any], None, None],
        collection: str,
        app: str,
        owner: str,
        source_host: str
    ) -> Tuple[int, int, List[str]]:
        """
        Sync a collection to HEC.

        Args:
            records: Generator of records to sync
            collection: Collection name
            app: Splunk app
            owner: Splunk owner
            source_host: Source host name

        Returns:
            Tuple of (events_sent, events_failed, errors)
        """
        errors = []
        sent = 0
        failed = 0

        batch = []
        batch_bytes = 0

        for record in records:
            # Build HEC event
            event = self._event_builder.build_event(
                record, collection, app, owner, source_host, self.config
            )

            event_bytes = len(json.dumps(event).encode())

            # Check if batch should be flushed
            if (len(batch) >= self.config.batch_size or
                batch_bytes + event_bytes > self.config.max_batch_bytes):

                success, error, count = self._client.send_events(batch)
                if success:
                    sent += count
                else:
                    failed += len(batch)
                    errors.append(error)

                batch = []
                batch_bytes = 0

            batch.append(event)
            batch_bytes += event_bytes

        # Flush remaining batch
        if batch:
            success, error, count = self._client.send_events(batch)
            if success:
                sent += count
            else:
                failed += len(batch)
                errors.append(error)

        logger.info(f"HEC sync complete: {sent} sent, {failed} failed")
        return sent, failed, errors

    def sync_record(
        self,
        record: Dict[str, Any],
        collection: str,
        app: str,
        owner: str,
        source_host: str
    ) -> Tuple[bool, str]:
        """Sync a single record to HEC"""
        event = self._event_builder.build_event(
            record, collection, app, owner, source_host, self.config
        )

        success, error, _ = self._client.send_events([event])
        return success, error


# =============================================================================
# Rehydration Handler
# =============================================================================

class RehydrationHandler:
    """
    Handler for rehydrating KVStore from indexed events.

    Implements the "import" phase of Index & Rehydrate pattern.
    Uses splunk-sdk for search operations.
    """

    def __init__(self, config: RehydrationConfig):
        if not SPLUNK_SDK_AVAILABLE:
            raise ImportError(
                "splunk-sdk is required for rehydration. Install: pip install splunk-sdk"
            )

        self.config = config
        self._service: Optional[splunk_client.Service] = None
        self._event_builder = HECEventBuilder()

    def connect(self) -> bool:
        """Connect to Splunk using splunk-sdk"""
        try:
            connect_kwargs = {
                "host": self.config.host,
                "port": self.config.port,
                "scheme": "https" if self.config.use_ssl else "http",
                "app": self.config.app,
                "owner": self.config.owner,
            }

            if self.config.token:
                connect_kwargs["splunkToken"] = self.config.token
            elif self.config.username and self.config.password:
                connect_kwargs["username"] = self.config.username
                connect_kwargs["password"] = self.config.password

            self._service = splunk_client.connect(**connect_kwargs)

            # Verify connection
            info = self._service.info
            logger.info(f"Connected to Splunk {info.get('version')} for rehydration")
            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Splunk"""
        if self._service:
            try:
                self._service.logout()
            except Exception:
                pass
        self._service = None

    def search_events(
        self,
        collection: Optional[str] = None,
        earliest: Optional[str] = None,
        latest: Optional[str] = None
    ) -> Generator[Tuple[Dict[str, Any], Dict[str, Any]], None, None]:
        """
        Search for KVStore events to rehydrate.

        Args:
            collection: Optional collection filter
            earliest: Search earliest time
            latest: Search latest time

        Yields:
            Tuples of (record, metadata)
        """
        if not self._service:
            return

        # Build search query
        search_query = (
            f'search index="{self.config.index}" '
            f'source="{self.config.source}" '
            f'sourcetype="{self.config.sourcetype}"'
        )

        if collection:
            search_query += f' "_kvstore_meta.collection"="{collection}"'

        # Use splunk-sdk search
        search_kwargs = {
            "earliest_time": earliest or self.config.earliest,
            "latest_time": latest or self.config.latest,
            "output_mode": "json",
        }

        try:
            job = self._service.jobs.create(search_query, **search_kwargs)

            # Wait for job to complete
            while not job.is_done():
                time.sleep(0.5)

            # Read results
            results = splunk_results.JSONResultsReader(job.results(output_mode="json"))

            for result in results:
                if isinstance(result, dict):
                    record, meta = self._event_builder.extract_record(result)
                    if record:
                        yield record, meta

        except Exception as e:
            logger.error(f"Search error: {e}")

    def rehydrate_collection(
        self,
        collection: Optional[str] = None,
        earliest: Optional[str] = None,
        latest: Optional[str] = None,
        write_callback: Optional[callable] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Rehydrate KVStore from indexed events.

        Args:
            collection: Optional collection filter
            earliest: Search earliest time
            latest: Search latest time
            write_callback: Callback to write records (receives record, collection, app, owner)

        Returns:
            Tuple of (records_rehydrated, records_failed, errors)
        """
        rehydrated = 0
        failed = 0
        errors = []
        seen_keys: Dict[str, datetime] = {}  # key -> timestamp for conflict resolution

        for record, meta in self.search_events(collection, earliest, latest):
            try:
                # Get metadata
                target_collection = self.config.target_collection or meta.get("collection")
                key = meta.get("key") or record.get("_key")
                sync_time_str = meta.get("sync_time", "")
                checksum = meta.get("checksum", "")

                if not target_collection or not record:
                    continue

                # Verify checksum if enabled
                if self.config.verify_checksums and checksum:
                    record_json = json.dumps(record, sort_keys=True, separators=(',', ':'))
                    actual = f"sha256:{hashlib.sha256(record_json.encode()).hexdigest()}"
                    if actual != checksum:
                        logger.warning(f"Checksum mismatch for {key}")
                        failed += 1
                        errors.append(f"Checksum mismatch: {key}")
                        continue

                # Handle conflicts
                if key in seen_keys:
                    if self.config.conflict_resolution == "skip":
                        continue
                    elif self.config.conflict_resolution == "newest_wins":
                        try:
                            sync_time = datetime.fromisoformat(sync_time_str.replace("Z", "+00:00"))
                            if sync_time <= seen_keys[key]:
                                continue
                        except ValueError:
                            pass

                # Write record
                if write_callback:
                    success = write_callback(
                        record,
                        target_collection,
                        self.config.target_app,
                        self.config.target_owner
                    )
                    if success:
                        rehydrated += 1
                        if key:
                            try:
                                seen_keys[key] = datetime.fromisoformat(
                                    sync_time_str.replace("Z", "+00:00")
                                )
                            except ValueError:
                                seen_keys[key] = datetime.utcnow()
                    else:
                        failed += 1
                else:
                    rehydrated += 1

            except Exception as e:
                logger.error(f"Rehydration error: {e}")
                failed += 1
                errors.append(str(e))

        logger.info(f"Rehydration complete: {rehydrated} records, {failed} failed")
        return rehydrated, failed, errors

    def get_available_collections(
        self,
        earliest: str = "-30d",
        latest: str = "now"
    ) -> List[Dict[str, Any]]:
        """
        Get list of collections available for rehydration.

        Returns list of dicts with collection info.
        """
        if not self._service:
            return []

        search_query = (
            f'search index="{self.config.index}" '
            f'source="{self.config.source}" '
            f'sourcetype="{self.config.sourcetype}" '
            f'| stats count, min(_time) as first_seen, max(_time) as last_seen '
            f'by "_kvstore_meta.collection", "_kvstore_meta.app"'
        )

        collections = []

        try:
            job = self._service.jobs.create(
                search_query,
                earliest_time=earliest,
                latest_time=latest,
                output_mode="json"
            )

            while not job.is_done():
                time.sleep(0.5)

            results = splunk_results.JSONResultsReader(job.results(output_mode="json"))

            for result in results:
                if isinstance(result, dict):
                    collections.append({
                        "collection": result.get("_kvstore_meta.collection", ""),
                        "app": result.get("_kvstore_meta.app", ""),
                        "event_count": int(result.get("count", 0)),
                        "first_seen": result.get("first_seen", ""),
                        "last_seen": result.get("last_seen", ""),
                    })

        except Exception as e:
            logger.error(f"Error listing collections: {e}")

        return collections

    def get_point_in_time_records(
        self,
        collection: str,
        point_in_time: str
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Get records as they existed at a specific point in time.

        This enables point-in-time recovery by:
        1. Finding the latest event for each key before the specified time
        2. Returning only those records

        Args:
            collection: Collection name
            point_in_time: ISO timestamp or Splunk time format

        Yields:
            Records at point in time
        """
        if not self._service:
            return

        # Search for latest event per key before point in time
        search_query = (
            f'search index="{self.config.index}" '
            f'source="{self.config.source}" '
            f'sourcetype="{self.config.sourcetype}" '
            f'"_kvstore_meta.collection"="{collection}" '
            f'| stats latest(_raw) as event, latest(_time) as event_time '
            f'by "_kvstore_meta.key"'
        )

        try:
            job = self._service.jobs.create(
                search_query,
                earliest_time="0",
                latest_time=point_in_time,
                output_mode="json"
            )

            while not job.is_done():
                time.sleep(0.5)

            results = splunk_results.JSONResultsReader(job.results(output_mode="json"))

            for result in results:
                if isinstance(result, dict):
                    event_str = result.get("event", "")
                    if event_str:
                        try:
                            event_data = json.loads(event_str)
                            record = event_data.get("_kvstore_record", {})
                            if record:
                                yield record
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Point-in-time search error: {e}")


# =============================================================================
# Unified HEC Handler
# =============================================================================

class HECHandler:
    """
    Unified handler for HEC operations.

    Combines sync (export) and rehydration (import) capabilities.
    """

    def __init__(
        self,
        hec_config: HECConfig,
        rehydration_config: Optional[RehydrationConfig] = None
    ):
        self.hec_config = hec_config
        self.rehydration_config = rehydration_config

        self._sync_handler = HECSyncHandler(hec_config)
        self._rehydration_handler = None

        if rehydration_config:
            self._rehydration_handler = RehydrationHandler(rehydration_config)

    def test_hec_connection(self) -> Tuple[bool, str]:
        """Test HEC connection"""
        return self._sync_handler.test_connection()

    def connect_for_rehydration(self) -> bool:
        """Connect for rehydration operations"""
        if self._rehydration_handler:
            return self._rehydration_handler.connect()
        return False

    def disconnect(self) -> None:
        """Disconnect rehydration handler"""
        if self._rehydration_handler:
            self._rehydration_handler.disconnect()

    def sync_to_index(
        self,
        records: Generator[Dict[str, Any], None, None],
        collection: str,
        app: str,
        owner: str,
        source_host: str
    ) -> Tuple[int, int, List[str]]:
        """
        Sync KVStore records to index via HEC.

        This is the "export" phase of Index & Rehydrate.
        """
        return self._sync_handler.sync_collection(
            records, collection, app, owner, source_host
        )

    def rehydrate_from_index(
        self,
        collection: Optional[str] = None,
        earliest: Optional[str] = None,
        latest: Optional[str] = None,
        write_callback: Optional[callable] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Rehydrate KVStore from indexed events.

        This is the "import" phase of Index & Rehydrate.
        """
        if not self._rehydration_handler:
            return 0, 0, ["Rehydration not configured"]

        return self._rehydration_handler.rehydrate_collection(
            collection, earliest, latest, write_callback
        )

    def list_available_collections(self) -> List[Dict[str, Any]]:
        """List collections available for rehydration"""
        if not self._rehydration_handler:
            return []
        return self._rehydration_handler.get_available_collections()

    def point_in_time_recovery(
        self,
        collection: str,
        point_in_time: str,
        write_callback: Optional[callable] = None
    ) -> Tuple[int, List[str]]:
        """
        Recover collection to a specific point in time.

        Args:
            collection: Collection to recover
            point_in_time: Target timestamp
            write_callback: Callback to write records

        Returns:
            Tuple of (records_recovered, errors)
        """
        if not self._rehydration_handler:
            return 0, ["Rehydration not configured"]

        recovered = 0
        errors = []

        try:
            for record in self._rehydration_handler.get_point_in_time_records(
                collection, point_in_time
            ):
                if write_callback:
                    success = write_callback(
                        record,
                        collection,
                        self._rehydration_handler.config.target_app,
                        self._rehydration_handler.config.target_owner
                    )
                    if success:
                        recovered += 1
                    else:
                        errors.append(f"Failed to write: {record.get('_key', 'unknown')}")
                else:
                    recovered += 1

        except Exception as e:
            errors.append(str(e))

        logger.info(f"Point-in-time recovery complete: {recovered} records")
        return recovered, errors
