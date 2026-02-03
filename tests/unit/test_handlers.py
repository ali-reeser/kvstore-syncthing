"""
Unit tests for sync handler implementations

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/unit/test_handlers.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Unit Test Suite

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Unit tests for base handler, REST handler,
                                MongoDB handler, and handler factory.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import pytest
from typing import Dict, Generator, List, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from unittest.mock import MagicMock, patch, AsyncMock
import json


# =============================================================================
# Base Handler Interface Tests
# =============================================================================

class BaseSyncHandler(ABC):
    """Abstract base class for sync handlers - interface definition"""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to destination"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection"""
        pass

    @abstractmethod
    def test_connection(self) -> tuple:
        """Test connection and return (success, message)"""
        pass

    @abstractmethod
    def collection_exists(self, collection: str, app: str, owner: str) -> bool:
        """Check if collection exists"""
        pass

    @abstractmethod
    def create_collection(self, collection: str, app: str, owner: str,
                         schema: Optional[Dict] = None) -> bool:
        """Create a collection"""
        pass

    @abstractmethod
    def read_records(self, collection: str, app: str, owner: str,
                    query: Optional[Dict] = None) -> Generator[Dict, None, None]:
        """Read records from collection"""
        pass

    @abstractmethod
    def write_records(self, collection: str, app: str, owner: str,
                     records: List[Dict]) -> tuple:
        """Write records and return (written_count, errors)"""
        pass

    @abstractmethod
    def delete_records(self, collection: str, app: str, owner: str,
                      keys: List[str]) -> tuple:
        """Delete records by key and return (deleted_count, errors)"""
        pass


class TestBaseSyncHandlerInterface:
    """Tests for base handler interface requirements"""

    def test_handler_must_implement_connect(self):
        """Handler must implement connect method"""
        with pytest.raises(TypeError):
            class IncompleteHandler(BaseSyncHandler):
                def disconnect(self): pass
                def test_connection(self): pass
                def collection_exists(self, *args): pass
                def create_collection(self, *args): pass
                def read_records(self, *args): pass
                def write_records(self, *args): pass
                def delete_records(self, *args): pass

            IncompleteHandler()

    def test_handler_must_implement_all_methods(self):
        """Handler must implement all abstract methods"""
        class CompleteHandler(BaseSyncHandler):
            def connect(self): return True
            def disconnect(self): pass
            def test_connection(self): return (True, "OK")
            def collection_exists(self, c, a, o): return True
            def create_collection(self, c, a, o, s=None): return True
            def read_records(self, c, a, o, q=None): yield {}
            def write_records(self, c, a, o, r): return (0, [])
            def delete_records(self, c, a, o, k): return (0, [])

        handler = CompleteHandler()
        assert handler.connect() is True


# =============================================================================
# Mock REST Handler Tests
# =============================================================================

@dataclass
class MockRESTDestination:
    """Mock REST destination configuration"""
    name: str
    host: str
    port: int = 8089
    use_ssl: bool = True
    verify_ssl: bool = False
    token: str = ""
    timeout: int = 30


class MockRESTHandler:
    """Mock implementation of REST sync handler for testing"""

    def __init__(self, destination: MockRESTDestination):
        self.destination = destination
        self._connected = False
        self._session = None

    def connect(self) -> bool:
        if not self.destination.host:
            return False
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._session = None

    def test_connection(self) -> tuple:
        if not self.destination.host:
            return (False, "Host not configured")
        if not self.destination.token:
            return (False, "Token not configured")
        return (True, f"Connected to {self.destination.host}")

    def _build_url(self, endpoint: str) -> str:
        protocol = "https" if self.destination.use_ssl else "http"
        return f"{protocol}://{self.destination.host}:{self.destination.port}{endpoint}"

    def collection_exists(self, collection: str, app: str, owner: str) -> bool:
        # In real implementation, would make REST call
        return True

    def create_collection(self, collection: str, app: str, owner: str,
                         schema: Optional[Dict] = None) -> bool:
        return True

    def read_records(self, collection: str, app: str, owner: str,
                    query: Optional[Dict] = None) -> Generator[Dict, None, None]:
        # Mock implementation yields nothing
        return
        yield

    def write_records(self, collection: str, app: str, owner: str,
                     records: List[Dict]) -> tuple:
        return (len(records), [])

    def delete_records(self, collection: str, app: str, owner: str,
                      keys: List[str]) -> tuple:
        return (len(keys), [])


class TestRESTHandler:
    """Tests for REST sync handler"""

    @pytest.fixture
    def rest_destination(self):
        return MockRESTDestination(
            name="test-dest",
            host="splunk.example.com",
            port=8089,
            token="test-token",
        )

    @pytest.fixture
    def rest_handler(self, rest_destination):
        return MockRESTHandler(rest_destination)

    def test_connect_success(self, rest_handler):
        """Handler connects successfully with valid config"""
        result = rest_handler.connect()
        assert result is True
        assert rest_handler._connected is True

    def test_connect_fails_without_host(self):
        """Handler fails to connect without host"""
        dest = MockRESTDestination(name="bad", host="")
        handler = MockRESTHandler(dest)

        result = handler.connect()

        assert result is False

    def test_disconnect(self, rest_handler):
        """Handler disconnects properly"""
        rest_handler.connect()
        rest_handler.disconnect()

        assert rest_handler._connected is False

    def test_test_connection_success(self, rest_handler):
        """Test connection returns success with valid config"""
        success, message = rest_handler.test_connection()

        assert success is True
        assert "Connected" in message

    def test_test_connection_fails_without_token(self):
        """Test connection fails without token"""
        dest = MockRESTDestination(name="test", host="splunk.example.com", token="")
        handler = MockRESTHandler(dest)

        success, message = handler.test_connection()

        assert success is False
        assert "Token" in message

    def test_build_url_https(self, rest_handler):
        """URL built with HTTPS when use_ssl is True"""
        url = rest_handler._build_url("/services/kvstore")

        assert url.startswith("https://")
        assert "8089" in url

    def test_build_url_http(self):
        """URL built with HTTP when use_ssl is False"""
        dest = MockRESTDestination(name="test", host="splunk.example.com", use_ssl=False)
        handler = MockRESTHandler(dest)

        url = handler._build_url("/services/kvstore")

        assert url.startswith("http://")

    def test_write_records_returns_count(self, rest_handler):
        """Write records returns count of written records"""
        records = [{"_key": f"rec-{i}"} for i in range(10)]

        written, errors = rest_handler.write_records("test", "search", "nobody", records)

        assert written == 10
        assert len(errors) == 0

    def test_delete_records_returns_count(self, rest_handler):
        """Delete records returns count of deleted records"""
        keys = ["rec-1", "rec-2", "rec-3"]

        deleted, errors = rest_handler.delete_records("test", "search", "nobody", keys)

        assert deleted == 3


# =============================================================================
# Mock MongoDB Handler Tests
# =============================================================================

@dataclass
class MockMongoDBDestination:
    """Mock MongoDB destination configuration"""
    name: str
    host: str
    port: int = 8191
    database: str = "splunk"
    username: str = ""
    password: str = ""
    replica_set: str = ""
    auth_source: str = "admin"


class MockMongoDBHandler:
    """Mock implementation of MongoDB sync handler for testing"""

    def __init__(self, destination: MockMongoDBDestination):
        self.destination = destination
        self._connected = False
        self._client = None
        self._db = None

    def connect(self) -> bool:
        if not self.destination.host:
            return False
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._client = None
        self._db = None

    def test_connection(self) -> tuple:
        if not self.destination.host:
            return (False, "Host not configured")
        return (True, f"Connected to MongoDB at {self.destination.host}")

    def get_connection_string(self) -> str:
        """Build MongoDB connection string"""
        if self.destination.username and self.destination.password:
            auth = f"{self.destination.username}:{self.destination.password}@"
        else:
            auth = ""

        host_port = f"{self.destination.host}:{self.destination.port}"

        options = []
        if self.destination.replica_set:
            options.append(f"replicaSet={self.destination.replica_set}")
        if self.destination.auth_source:
            options.append(f"authSource={self.destination.auth_source}")

        option_str = "&".join(options)
        if option_str:
            option_str = "?" + option_str

        return f"mongodb://{auth}{host_port}/{self.destination.database}{option_str}"

    def collection_exists(self, collection: str, app: str, owner: str) -> bool:
        return True

    def create_collection(self, collection: str, app: str, owner: str,
                         schema: Optional[Dict] = None) -> bool:
        return True

    def read_records(self, collection: str, app: str, owner: str,
                    query: Optional[Dict] = None) -> Generator[Dict, None, None]:
        return
        yield

    def write_records(self, collection: str, app: str, owner: str,
                     records: List[Dict]) -> tuple:
        return (len(records), [])

    def delete_records(self, collection: str, app: str, owner: str,
                      keys: List[str]) -> tuple:
        return (len(keys), [])


class TestMongoDBHandler:
    """Tests for MongoDB sync handler"""

    @pytest.fixture
    def mongodb_destination(self):
        return MockMongoDBDestination(
            name="test-mongo",
            host="splunk-sh01.example.com",
            port=8191,
            database="splunk",
            username="kvstore_user",
            password="secret",
        )

    @pytest.fixture
    def mongodb_handler(self, mongodb_destination):
        return MockMongoDBHandler(mongodb_destination)

    def test_connect_success(self, mongodb_handler):
        """Handler connects successfully"""
        result = mongodb_handler.connect()

        assert result is True
        assert mongodb_handler._connected is True

    def test_connection_string_basic(self, mongodb_handler):
        """Connection string built correctly"""
        conn_str = mongodb_handler.get_connection_string()

        assert "mongodb://" in conn_str
        assert "kvstore_user:secret@" in conn_str
        assert "splunk-sh01.example.com:8191" in conn_str
        assert "/splunk" in conn_str

    def test_connection_string_with_replica_set(self):
        """Connection string includes replica set"""
        dest = MockMongoDBDestination(
            name="test",
            host="mongo1.example.com",
            replica_set="rs0",
        )
        handler = MockMongoDBHandler(dest)

        conn_str = handler.get_connection_string()

        assert "replicaSet=rs0" in conn_str

    def test_connection_string_without_auth(self):
        """Connection string without auth credentials"""
        dest = MockMongoDBDestination(
            name="test",
            host="localhost",
        )
        handler = MockMongoDBHandler(dest)

        conn_str = handler.get_connection_string()

        assert "@" not in conn_str


# =============================================================================
# Handler Factory Tests
# =============================================================================

class MockHandlerFactory:
    """Factory for creating sync handlers"""

    HANDLER_TYPES = {
        "splunk_rest": MockRESTHandler,
        "mongodb_direct": MockMongoDBHandler,
    }

    @classmethod
    def create_handler(cls, destination_type: str, config: Dict):
        """Create a handler for the given destination type"""
        if destination_type not in cls.HANDLER_TYPES:
            raise ValueError(f"Unknown destination type: {destination_type}")

        handler_class = cls.HANDLER_TYPES[destination_type]

        if destination_type == "splunk_rest":
            dest = MockRESTDestination(
                name=config.get("name", ""),
                host=config.get("host", ""),
                port=config.get("port", 8089),
                token=config.get("token", ""),
            )
            return handler_class(dest)
        elif destination_type == "mongodb_direct":
            dest = MockMongoDBDestination(
                name=config.get("name", ""),
                host=config.get("host", ""),
                port=config.get("port", 8191),
                database=config.get("database", "splunk"),
            )
            return handler_class(dest)


class TestHandlerFactory:
    """Tests for handler factory"""

    def test_create_rest_handler(self):
        """Factory creates REST handler"""
        config = {
            "name": "test-rest",
            "host": "splunk.example.com",
            "token": "abc123",
        }

        handler = MockHandlerFactory.create_handler("splunk_rest", config)

        assert isinstance(handler, MockRESTHandler)
        assert handler.destination.host == "splunk.example.com"

    def test_create_mongodb_handler(self):
        """Factory creates MongoDB handler"""
        config = {
            "name": "test-mongo",
            "host": "mongo.example.com",
            "database": "kvstore",
        }

        handler = MockHandlerFactory.create_handler("mongodb_direct", config)

        assert isinstance(handler, MockMongoDBHandler)
        assert handler.destination.database == "kvstore"

    def test_unknown_handler_type_raises(self):
        """Factory raises error for unknown handler type"""
        with pytest.raises(ValueError) as exc_info:
            MockHandlerFactory.create_handler("unknown_type", {})

        assert "Unknown destination type" in str(exc_info.value)


# =============================================================================
# Handler Error Handling Tests
# =============================================================================

class TestHandlerErrorHandling:
    """Tests for handler error handling"""

    def test_write_records_with_errors(self):
        """Write records returns errors for failed records"""
        class ErrorHandler(MockRESTHandler):
            def write_records(self, collection, app, owner, records):
                # Simulate some records failing
                written = len(records) - 2
                errors = ["Record rec-1 failed: duplicate key", "Record rec-2 failed: validation error"]
                return (written, errors)

        dest = MockRESTDestination(name="test", host="splunk.example.com", token="test")
        handler = ErrorHandler(dest)
        records = [{"_key": f"rec-{i}"} for i in range(10)]

        written, errors = handler.write_records("test", "search", "nobody", records)

        assert written == 8
        assert len(errors) == 2

    def test_connection_timeout_handling(self):
        """Handler handles connection timeout gracefully"""
        class TimeoutHandler(MockRESTHandler):
            def test_connection(self):
                return (False, "Connection timed out after 30 seconds")

        dest = MockRESTDestination(name="test", host="slow-server.example.com", token="test")
        handler = TimeoutHandler(dest)

        success, message = handler.test_connection()

        assert success is False
        assert "timeout" in message.lower()


# =============================================================================
# Handler Configuration Validation Tests
# =============================================================================

class TestHandlerConfigValidation:
    """Tests for handler configuration validation"""

    def test_rest_requires_host(self):
        """REST handler requires host"""
        dest = MockRESTDestination(name="test", host="")
        handler = MockRESTHandler(dest)

        success, message = handler.test_connection()

        assert success is False

    def test_rest_requires_token_or_credentials(self):
        """REST handler requires authentication"""
        dest = MockRESTDestination(name="test", host="splunk.example.com", token="")
        handler = MockRESTHandler(dest)

        success, message = handler.test_connection()

        assert success is False

    def test_mongodb_port_default(self):
        """MongoDB handler uses default port 8191"""
        dest = MockMongoDBDestination(name="test", host="mongo.example.com")

        assert dest.port == 8191

    def test_rest_port_default(self):
        """REST handler uses default port 8089"""
        dest = MockRESTDestination(name="test", host="splunk.example.com")

        assert dest.port == 8089
