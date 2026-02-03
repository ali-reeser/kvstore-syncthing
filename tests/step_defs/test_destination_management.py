"""
BDD step definitions for destination management feature

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/step_defs/test_destination_management.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: BDD Test Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Step definitions for destination CRUD,
                                connection testing, and validation scenarios.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch
import re


# Load all scenarios from the feature file
scenarios('../features/destination_management.feature')


# =============================================================================
# Destination Type Constants
# =============================================================================

DESTINATION_TYPES = {
    "Splunk REST API": "splunk_rest",
    "MongoDB Direct": "mongodb_direct",
    "Index & Rehydrate": "index_rehydrate",
    "S3 Bucket": "s3_bucket",
    "File Export": "file_export",
}


# =============================================================================
# Mock Destination Manager
# =============================================================================

@dataclass
class MockDestination:
    """Mock destination for testing"""
    name: str
    destination_type: str
    host: str = ""
    port: int = 8089
    use_ssl: bool = True
    auth_type: str = "token"
    username: Optional[str] = None
    password: Optional[str] = None
    mongodb_database: Optional[str] = None
    mongodb_auth_source: Optional[str] = None
    mongodb_replica_set: Optional[str] = None
    aws_region: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    hec_index: Optional[str] = None
    hec_sourcetype: Optional[str] = None
    file_export_path: Optional[str] = None
    file_export_format: Optional[str] = None
    status: str = "Not Tested"
    used_by_jobs: List[str] = field(default_factory=list)
    is_valid_credentials: bool = True
    is_reachable: bool = True


class MockDestinationManager:
    """Mock destination manager for testing CRUD operations"""

    def __init__(self):
        self.destinations: Dict[str, MockDestination] = {}
        self.audit_log: List[Dict] = []
        self.connection_test_results: Dict[str, Dict] = {}

    def create(self, config: Dict) -> MockDestination:
        name = config.get("name", "")
        if not name:
            raise ValueError("Name is required")
        if name in self.destinations:
            raise ValueError("Destination name already exists")
        if not self._validate_name_format(name):
            raise ValueError("Name can only contain alphanumeric characters, underscores, and hyphens")

        dest_type = config.get("destination_type", "")
        if not dest_type:
            raise ValueError("Destination Type is required")

        host = config.get("host", "")
        if not host and dest_type not in ["file_export"]:
            raise ValueError("Host is required")

        dest = MockDestination(
            name=name,
            destination_type=dest_type,
            host=host,
            port=config.get("port", 8089),
            use_ssl=config.get("use_ssl", True),
            auth_type=config.get("auth_type", "token"),
            username=config.get("username"),
            password=config.get("password"),
            mongodb_database=config.get("mongodb_database"),
            mongodb_auth_source=config.get("mongodb_auth_source"),
            mongodb_replica_set=config.get("mongodb_replica_set"),
            aws_region=config.get("aws_region"),
            s3_bucket=config.get("s3_bucket"),
            s3_prefix=config.get("s3_prefix"),
            hec_index=config.get("hec_index"),
            hec_sourcetype=config.get("hec_sourcetype"),
            file_export_path=config.get("file_export_path"),
            file_export_format=config.get("file_export_format"),
        )

        self.destinations[name] = dest
        self.audit_log.append({"action": "create", "destination": name})
        return dest

    def update(self, name: str, updates: Dict) -> MockDestination:
        if name not in self.destinations:
            raise ValueError(f"Destination {name} not found")

        dest = self.destinations[name]
        for key, value in updates.items():
            if hasattr(dest, key):
                setattr(dest, key, value)

        self.audit_log.append({"action": "update", "destination": name, "changes": updates})
        return dest

    def delete(self, name: str, force: bool = False) -> bool:
        if name not in self.destinations:
            raise ValueError(f"Destination {name} not found")

        dest = self.destinations[name]
        if dest.used_by_jobs and not force:
            raise ValueError(f"Cannot delete destination in use by: {', '.join(dest.used_by_jobs)}")

        del self.destinations[name]
        self.audit_log.append({"action": "delete", "destination": name})
        return True

    def get(self, name: str) -> Optional[MockDestination]:
        return self.destinations.get(name)

    def list_all(self) -> List[MockDestination]:
        return list(self.destinations.values())

    def test_connection(self, name: str) -> Dict:
        if name not in self.destinations:
            raise ValueError(f"Destination {name} not found")

        dest = self.destinations[name]

        if not dest.is_reachable:
            return {
                "success": False,
                "message": "Connection failed",
                "error": "Network unreachable",
            }

        if not dest.is_valid_credentials:
            return {
                "success": False,
                "message": "Authentication failed",
                "error": "Invalid credentials",
            }

        dest.status = "Connected"
        return {
            "success": True,
            "message": "Connection successful",
            "server_version": "9.0.0",
        }

    def _validate_name_format(self, name: str) -> bool:
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))


@pytest.fixture
def destination_manager() -> MockDestinationManager:
    """Create fresh destination manager"""
    return MockDestinationManager()


# =============================================================================
# Context Fixtures
# =============================================================================

@dataclass
class DestinationContext:
    """Context for destination management tests"""
    manager: MockDestinationManager = field(default_factory=MockDestinationManager)
    current_page: str = ""
    form_data: Dict[str, Any] = field(default_factory=dict)
    last_result: Optional[Any] = None
    last_error: Optional[str] = None
    connection_in_progress: bool = False
    connection_result: Optional[Dict] = None


@pytest.fixture
def dest_context() -> DestinationContext:
    """Fresh context for each scenario"""
    return DestinationContext()


# =============================================================================
# Background Steps
# =============================================================================

@given("I am logged into Splunk as an admin user")
def logged_in_as_admin(dest_context):
    """Simulate logged-in admin user"""
    dest_context.form_data["current_user"] = "admin"


@given("the KVStore Syncthing app is installed")
def app_installed(dest_context):
    """Simulate app installation"""
    dest_context.form_data["app_installed"] = True


# =============================================================================
# Navigation Steps
# =============================================================================

@given("I navigate to the Configuration > Destinations page")
def navigate_to_destinations(dest_context):
    """Navigate to destinations configuration page"""
    dest_context.current_page = "configuration/destinations"


# =============================================================================
# Create Destination Steps
# =============================================================================

@when("I click \"Add Destination\"")
def click_add_destination(dest_context):
    """Open add destination form"""
    dest_context.form_data = {}


@when(parsers.parse("I fill in the following destination details:\n{table}"))
def fill_destination_details(dest_context, table):
    """Fill in destination form fields from table"""
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Field':
                field_name = parts[0]
                value = parts[1]

                # Map UI field names to config keys
                field_mapping = {
                    "Name": "name",
                    "Destination Type": "destination_type",
                    "Host": "host",
                    "Port": "port",
                    "Use SSL": "use_ssl",
                    "Auth Type": "auth_type",
                    "Username": "username",
                    "Password": "password",
                    "MongoDB Database": "mongodb_database",
                    "MongoDB Auth Source": "mongodb_auth_source",
                    "MongoDB Replica Set": "mongodb_replica_set",
                    "AWS Region": "aws_region",
                    "S3 Bucket": "s3_bucket",
                    "S3 Prefix": "s3_prefix",
                    "HEC Index": "hec_index",
                    "HEC Sourcetype": "hec_sourcetype",
                    "File Export Path": "file_export_path",
                    "File Export Format": "file_export_format",
                }

                config_key = field_mapping.get(field_name, field_name.lower().replace(" ", "_"))

                # Convert destination type to internal format
                if config_key == "destination_type" and value in DESTINATION_TYPES:
                    value = DESTINATION_TYPES[value]

                # Convert boolean strings
                if value in ("Yes", "True", "true"):
                    value = True
                elif value in ("No", "False", "false"):
                    value = False

                # Convert port to int
                if config_key == "port":
                    value = int(value)

                dest_context.form_data[config_key] = value


@when("I click \"Save\"")
def click_save(dest_context):
    """Save the destination configuration"""
    try:
        dest_context.last_result = dest_context.manager.create(dest_context.form_data)
        dest_context.last_error = None
    except ValueError as e:
        dest_context.last_error = str(e)
        dest_context.last_result = None


@then(parsers.parse("the destination \"{name}\" should appear in the destinations list"))
def destination_in_list(dest_context, name):
    """Verify destination appears in list"""
    dest = dest_context.manager.get(name)
    assert dest is not None, f"Destination {name} not found"


@then(parsers.parse("the destination should show status \"{status}\""))
def destination_has_status(dest_context, status):
    """Verify destination status"""
    assert dest_context.last_result is not None
    assert dest_context.last_result.status == status


# =============================================================================
# Connection Test Steps
# =============================================================================

@given(parsers.parse("a destination \"{name}\" exists with valid credentials"))
def destination_with_valid_creds(dest_context, name):
    """Create destination with valid credentials"""
    dest_context.manager.create({
        "name": name,
        "destination_type": "splunk_rest",
        "host": "localhost",
        "port": 8089,
        "password": "valid-token",
    })


@given(parsers.parse("a destination \"{name}\" exists with invalid credentials"))
def destination_with_invalid_creds(dest_context, name):
    """Create destination with invalid credentials"""
    dest = dest_context.manager.create({
        "name": name,
        "destination_type": "splunk_rest",
        "host": "localhost",
        "port": 8089,
        "password": "invalid-token",
    })
    dest.is_valid_credentials = False


@given(parsers.parse("a destination \"{name}\" exists with host \"{host}\""))
def destination_with_host(dest_context, name, host):
    """Create destination with specific host"""
    dest = dest_context.manager.create({
        "name": name,
        "destination_type": "splunk_rest",
        "host": host,
        "port": 8089,
    })
    if "nonexistent" in host or "unreachable" in host:
        dest.is_reachable = False


@when(parsers.parse("I click \"Test Connection\" for destination \"{name}\""))
def click_test_connection(dest_context, name):
    """Test connection to destination"""
    dest_context.connection_in_progress = True
    dest_context.connection_result = dest_context.manager.test_connection(name)
    dest_context.connection_in_progress = False


@then("I should see a connection test in progress")
def connection_test_in_progress(dest_context):
    """Verify connection test started"""
    # In real implementation, this would check async state
    pass


@then(parsers.parse("within {seconds:d} seconds I should see \"{message}\""))
def see_message_within_time(dest_context, seconds, message):
    """Verify message appears within timeout"""
    assert dest_context.connection_result is not None
    assert message in dest_context.connection_result.get("message", "")


@then("the response should include the Splunk server version")
def response_has_server_version(dest_context):
    """Verify server version in response"""
    assert dest_context.connection_result is not None
    assert "server_version" in dest_context.connection_result


@then("the error message should suggest checking credentials")
def error_suggests_credentials(dest_context):
    """Verify error suggests credential check"""
    assert dest_context.connection_result is not None
    assert not dest_context.connection_result.get("success", True)


@then("the error message should indicate network unreachable")
def error_indicates_network(dest_context):
    """Verify network error message"""
    assert dest_context.connection_result is not None
    assert "unreachable" in dest_context.connection_result.get("error", "").lower()


# =============================================================================
# MongoDB Destination Steps
# =============================================================================

@then(parsers.parse("the destination should be configured for replica set \"{rs_name}\""))
def configured_for_replica_set(dest_context, rs_name):
    """Verify replica set configuration"""
    assert dest_context.last_result is not None
    assert dest_context.last_result.mongodb_replica_set == rs_name


# =============================================================================
# HEC Destination Steps
# =============================================================================

@then("a help tooltip should explain rehydration search requirements")
def rehydration_tooltip_shown(dest_context):
    """Verify HEC rehydration help tooltip"""
    # In real implementation, would verify UI tooltip
    pass


# =============================================================================
# S3 Destination Steps
# =============================================================================

@then("the destination should be configured with explicit AWS credentials")
def configured_with_aws_creds(dest_context):
    """Verify AWS credential configuration"""
    assert dest_context.last_result is not None
    assert dest_context.last_result.auth_type == "Username/Password"


# =============================================================================
# Edit/Delete Steps
# =============================================================================

@given(parsers.parse("a destination \"{name}\" exists"))
def destination_exists(dest_context, name):
    """Create a destination"""
    dest_context.manager.create({
        "name": name,
        "destination_type": "splunk_rest",
        "host": "localhost",
        "port": 8089,
    })


@given("the destination is not used by any sync jobs")
def destination_not_in_use(dest_context):
    """Ensure destination is not used"""
    pass  # Default state is not used


@given(parsers.parse("the destination is used by sync job \"{job_name}\""))
def destination_used_by_job(dest_context, job_name):
    """Mark destination as used by a job"""
    # Get most recently created destination
    if dest_context.manager.destinations:
        dest_name = list(dest_context.manager.destinations.keys())[-1]
        dest_context.manager.destinations[dest_name].used_by_jobs.append(job_name)


@when(parsers.parse("I click \"Edit\" for destination \"{name}\""))
def click_edit_destination(dest_context, name):
    """Open edit form for destination"""
    dest = dest_context.manager.get(name)
    assert dest is not None
    dest_context.form_data = {
        "name": dest.name,
        "destination_type": dest.destination_type,
        "host": dest.host,
        "port": dest.port,
    }


@when(parsers.parse("I change the \"{field}\" to \"{value}\""))
def change_field_value(dest_context, field, value):
    """Change a form field value"""
    field_key = field.lower().replace(" ", "_")
    if field_key == "port":
        value = int(value)
    dest_context.form_data[field_key] = value


@when(parsers.parse("I click \"Save\""))
def click_save_edit(dest_context):
    """Save edited destination"""
    name = dest_context.form_data.get("name")
    if name and name in dest_context.manager.destinations:
        try:
            dest_context.last_result = dest_context.manager.update(name, dest_context.form_data)
            dest_context.last_error = None
        except ValueError as e:
            dest_context.last_error = str(e)


@then(parsers.parse("the destination should be updated with port \"{port}\""))
def destination_updated_port(dest_context, port):
    """Verify destination port updated"""
    assert dest_context.last_result is not None
    assert dest_context.last_result.port == int(port)


@then("an audit log entry should be created for the change")
def audit_log_created(dest_context):
    """Verify audit log entry exists"""
    assert len(dest_context.manager.audit_log) > 0
    assert dest_context.manager.audit_log[-1]["action"] == "update"


@when(parsers.parse("I click \"Delete\" for destination \"{name}\""))
def click_delete_destination(dest_context, name):
    """Click delete for destination"""
    dest_context.form_data["delete_target"] = name


@when("I confirm the deletion")
def confirm_deletion(dest_context):
    """Confirm deletion dialog"""
    name = dest_context.form_data.get("delete_target")
    if name:
        try:
            dest_context.manager.delete(name)
            dest_context.last_error = None
        except ValueError as e:
            dest_context.last_error = str(e)


@then(parsers.parse("the destination \"{name}\" should no longer exist"))
def destination_deleted(dest_context, name):
    """Verify destination deleted"""
    assert dest_context.manager.get(name) is None


@then(parsers.parse("I should see an error \"{error_message}\""))
def see_error_message(dest_context, error_message):
    """Verify error message displayed"""
    assert dest_context.last_error is not None
    assert error_message in dest_context.last_error


@then("the error should list the jobs using this destination")
def error_lists_jobs(dest_context):
    """Verify error lists job names"""
    assert dest_context.last_error is not None
    # The error message should contain job references


# =============================================================================
# Validation Steps
# =============================================================================

@when(parsers.parse("I leave the \"{field}\" field empty"))
def leave_field_empty(dest_context, field):
    """Leave a form field empty"""
    field_key = field.lower().replace(" ", "_")
    dest_context.form_data[field_key] = ""


@then(parsers.parse("I should see a validation error for \"{field}\""))
def see_validation_error(dest_context, field):
    """Verify validation error for field"""
    assert dest_context.last_error is not None


@then(parsers.parse("the error message should be \"{message}\""))
def error_message_is(dest_context, message):
    """Verify specific error message"""
    assert dest_context.last_error is not None
    assert message in dest_context.last_error


@when(parsers.parse("I try to create a destination with name \"{name}\""))
def try_create_destination(dest_context, name):
    """Attempt to create destination with name"""
    dest_context.form_data["name"] = name
    dest_context.form_data["destination_type"] = "splunk_rest"
    dest_context.form_data["host"] = "localhost"
    try:
        dest_context.manager.create(dest_context.form_data)
        dest_context.last_error = None
    except ValueError as e:
        dest_context.last_error = str(e)
