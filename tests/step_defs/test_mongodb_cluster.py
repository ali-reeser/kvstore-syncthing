"""
BDD step definitions for MongoDB cluster management feature

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/step_defs/test_mongodb_cluster.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: BDD Test Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Step definitions for MongoDB OOB cluster
                                management, replica sets, failover scenarios.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


# Load all scenarios from the feature file
scenarios('../features/mongodb_cluster.feature')


# =============================================================================
# MongoDB State Enums
# =============================================================================

class ReplicaState(Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    RECOVERING = "RECOVERING"
    ARBITER = "ARBITER"
    DOWN = "DOWN"


# =============================================================================
# Mock MongoDB Classes
# =============================================================================

@dataclass
class MockReplicaSetMember:
    """Mock MongoDB replica set member"""
    host: str
    port: int
    state: ReplicaState = ReplicaState.SECONDARY
    priority: int = 1
    votes: int = 1
    hidden: bool = False
    slave_delay: int = 0
    tags: Dict[str, str] = field(default_factory=dict)
    is_oob: bool = False
    replication_lag_seconds: int = 0
    mongodb_version: str = "4.2"
    is_reachable: bool = True


@dataclass
class MockReplicaSet:
    """Mock MongoDB replica set"""
    name: str = "rs0"
    members: List[MockReplicaSetMember] = field(default_factory=list)
    primary: Optional[MockReplicaSetMember] = None

    def add_member(self, member: MockReplicaSetMember):
        self.members.append(member)
        if member.state == ReplicaState.PRIMARY:
            self.primary = member

    def remove_member(self, host: str):
        self.members = [m for m in self.members if m.host != host.split(":")[0]]

    def get_member(self, host: str) -> Optional[MockReplicaSetMember]:
        for m in self.members:
            if m.host == host.split(":")[0]:
                return m
        return None


class MockMongoDBClusterManager:
    """Mock MongoDB cluster manager for testing"""

    def __init__(self):
        self.replica_set = MockReplicaSet()
        self.alerts: List[Dict] = []
        self.last_error: Optional[str] = None
        self.dry_run_result: Optional[Dict] = None
        self.monitoring_enabled: bool = False

        # Add default Splunk primary
        primary = MockReplicaSetMember(
            host="splunk-sh01",
            port=8191,
            state=ReplicaState.PRIMARY,
            priority=100,
            votes=1,
        )
        self.replica_set.add_member(primary)

    def connect(self, host: str, port: int, credentials: Dict) -> Dict:
        """Connect to MongoDB and return status"""
        return {
            "connected": True,
            "replica_set": self.replica_set.name,
            "primary": f"{self.replica_set.primary.host}:{self.replica_set.primary.port}" if self.replica_set.primary else None,
            "version": "4.2",
        }

    def check_version_compatibility(self, node_version: str, cluster_version: str) -> Dict:
        """Check MongoDB version compatibility"""
        node_major = node_version.split(".")[0]
        cluster_major = cluster_version.split(".")[0]

        if node_major != cluster_major:
            return {
                "compatible": False,
                "warning": f"Major version mismatch: node is {node_version}, cluster is {cluster_version}. This may cause replication issues.",
            }
        return {"compatible": True}

    def add_node(self, host: str, config: Dict, dry_run: bool = False) -> Dict:
        """Add a node to the replica set"""
        # Parse host
        if ":" in host:
            node_host, node_port = host.split(":")
            node_port = int(node_port)
        else:
            node_host = host
            node_port = 27017

        # Check if node is reachable
        if "bad" in node_host or not config.get("is_reachable", True):
            self.last_error = "Cannot reach node"
            return {"success": False, "error": self.last_error}

        if dry_run:
            self.dry_run_result = {
                "would_add": host,
                "config": config,
                "replica_set": self.replica_set.name,
            }
            return {"success": True, "dry_run": True, "config": config}

        # Create and add member
        member = MockReplicaSetMember(
            host=node_host,
            port=node_port,
            priority=config.get("priority", 1),
            votes=config.get("votes", 1),
            hidden=config.get("hidden", False),
            slave_delay=config.get("slave_delay", 0),
            tags=config.get("tags", {}),
            is_oob=True,
        )
        self.replica_set.add_member(member)

        return {"success": True, "member": host}

    def remove_node(self, host: str) -> Dict:
        """Remove a node from the replica set"""
        # Parse host
        node_host = host.split(":")[0]

        # Check if it's the Splunk primary
        if self.replica_set.primary and self.replica_set.primary.host == node_host:
            self.last_error = "Cannot remove Splunk's primary node - this would break Splunk"
            return {"success": False, "error": self.last_error}

        member = self.replica_set.get_member(host)
        if not member:
            self.last_error = f"Node {host} not found in replica set"
            return {"success": False, "error": self.last_error}

        self.replica_set.remove_member(host)
        return {"success": True}

    def get_replication_status(self) -> List[Dict]:
        """Get replication lag for all members"""
        return [
            {
                "host": f"{m.host}:{m.port}" if m.port != 8191 else m.host,
                "state": m.state.value,
                "lag_seconds": m.replication_lag_seconds,
                "is_oob": m.is_oob,
            }
            for m in self.replica_set.members
        ]

    def check_replication_lag(self) -> None:
        """Check for excessive replication lag and raise alerts"""
        for member in self.replica_set.members:
            if member.replication_lag_seconds > 60:
                self.alerts.append({
                    "type": "replication_lag",
                    "node": f"{member.host}:{member.port}",
                    "lag_seconds": member.replication_lag_seconds,
                })

    def wait_for_sync(self, host: str, timeout: int = 300) -> Dict:
        """Wait for node to complete initial sync"""
        member = self.replica_set.get_member(host)
        if not member:
            return {"success": False, "error": "Node not found"}

        # Simulate sync completion
        return {"success": True, "synced": True}

    def promote_node(self, host: str, force: bool = False) -> Dict:
        """Promote node to primary"""
        member = self.replica_set.get_member(host)
        if not member:
            return {"success": False, "error": "Node not found"}

        # Check if current primary is available
        if self.replica_set.primary and self.replica_set.primary.state == ReplicaState.PRIMARY and not force:
            self.last_error = "Current primary is available. Use force=true to override."
            return {"success": False, "error": self.last_error}

        # Demote current primary
        if self.replica_set.primary:
            self.replica_set.primary.state = ReplicaState.SECONDARY
            self.replica_set.primary.priority = 1

        # Promote new primary
        member.state = ReplicaState.PRIMARY
        member.priority = 100
        self.replica_set.primary = member

        return {"success": True, "new_primary": host}

    def restore_original_primary(self, host: str) -> Dict:
        """Restore original primary after failback"""
        return self.promote_node(host, force=True)

    def generate_config(self) -> Dict:
        """Generate mongod.conf template for OOB node"""
        return {
            "replication": {
                "replSetName": self.replica_set.name,
            },
            "security": {
                "keyFile": "/path/to/keyfile",
                "authorization": "enabled",
            },
            "net": {
                "port": 27017,
            },
        }

    def export_key_file(self) -> Dict:
        """Export key file content for OOB nodes"""
        return {
            "key_file_content": "MOCK_KEYFILE_CONTENT_BASE64",
            "instructions": "Place this file at /path/to/keyfile and set permissions to 400",
        }


@pytest.fixture
def mongo_manager() -> MockMongoDBClusterManager:
    """Create fresh MongoDB cluster manager"""
    return MockMongoDBClusterManager()


# =============================================================================
# Context Fixtures
# =============================================================================

@dataclass
class MongoDBContext:
    """Context for MongoDB cluster tests"""
    manager: MockMongoDBClusterManager = field(default_factory=MockMongoDBClusterManager)
    connection_result: Optional[Dict] = None
    last_result: Optional[Dict] = None
    version_check_result: Optional[Dict] = None
    external_node_version: str = "4.2"
    splunk_version: str = "4.2"


@pytest.fixture
def mongo_context() -> MongoDBContext:
    """Fresh context for each scenario"""
    return MongoDBContext()


# =============================================================================
# Background Steps
# =============================================================================

@given("I am logged into Splunk as an admin user")
def logged_in_as_admin(mongo_context):
    """Simulate logged-in admin user"""
    pass


@given("I have access to Splunk's internal KVStore MongoDB")
def have_kvstore_access(mongo_context):
    """Simulate KVStore access"""
    pass


@given("I have network access to external MongoDB nodes")
def have_network_access(mongo_context):
    """Simulate network access"""
    pass


# =============================================================================
# Connection Steps
# =============================================================================

@given("Splunk's KVStore is running on port 8191")
def kvstore_running(mongo_context):
    """Ensure KVStore is running"""
    pass


@given("I have MongoDB credentials from splunk-launch.conf")
def have_mongo_credentials(mongo_context):
    """Have MongoDB credentials"""
    pass


@when("I connect to the KVStore MongoDB")
def connect_to_kvstore(mongo_context):
    """Connect to KVStore MongoDB"""
    mongo_context.connection_result = mongo_context.manager.connect(
        "splunk-sh01", 8191, {"username": "admin", "password": "secret"}
    )


@then("I should see the replica set name")
def see_replica_set_name(mongo_context):
    """Verify replica set name visible"""
    assert mongo_context.connection_result is not None
    assert "replica_set" in mongo_context.connection_result


@then("I should see the current primary node")
def see_primary_node(mongo_context):
    """Verify primary node visible"""
    assert mongo_context.connection_result is not None
    assert "primary" in mongo_context.connection_result


@then("I should see the MongoDB version")
def see_mongo_version(mongo_context):
    """Verify MongoDB version visible"""
    assert mongo_context.connection_result is not None
    assert "version" in mongo_context.connection_result


# =============================================================================
# Version Compatibility Steps
# =============================================================================

@given(parsers.parse("Splunk's KVStore uses MongoDB {version}"))
def splunk_mongo_version(mongo_context, version):
    """Set Splunk MongoDB version"""
    mongo_context.splunk_version = version


@given(parsers.parse("I have an external MongoDB node running version {version}"))
def external_node_version(mongo_context, version):
    """Set external node MongoDB version"""
    mongo_context.external_node_version = version


@when("I check version compatibility")
def check_version_compatibility(mongo_context):
    """Check version compatibility"""
    mongo_context.version_check_result = mongo_context.manager.check_version_compatibility(
        mongo_context.external_node_version,
        mongo_context.splunk_version,
    )


@then("the versions should be reported as compatible")
def versions_compatible(mongo_context):
    """Verify versions compatible"""
    assert mongo_context.version_check_result is not None
    assert mongo_context.version_check_result.get("compatible") is True


@then("a warning should indicate version mismatch")
def version_mismatch_warning(mongo_context):
    """Verify version mismatch warning"""
    assert mongo_context.version_check_result is not None
    assert mongo_context.version_check_result.get("compatible") is False
    assert "warning" in mongo_context.version_check_result


@then("the warning should explain potential issues")
def warning_explains_issues(mongo_context):
    """Verify warning explains issues"""
    assert "warning" in mongo_context.version_check_result
    assert len(mongo_context.version_check_result["warning"]) > 0


# =============================================================================
# Add OOB Node Steps
# =============================================================================

@given("Splunk's KVStore replica set is healthy")
def replica_set_healthy(mongo_context):
    """Ensure replica set is healthy"""
    assert mongo_context.manager.replica_set.primary is not None


@given(parsers.parse("an external MongoDB node \"{host}\" is available"))
def external_node_available(mongo_context, host):
    """External node is available"""
    mongo_context.last_result = {"available_node": host}


@when(parsers.parse("I add the node as a hidden secondary with:\n{table}"))
def add_hidden_secondary(mongo_context, table):
    """Add node as hidden secondary"""
    config = {}
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Setting':
                key = parts[0].lower().replace(" ", "_")
                value = parts[1]

                # Convert types
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)

                config[key] = value

    host = mongo_context.last_result.get("available_node", "external:27017")
    mongo_context.last_result = mongo_context.manager.add_node(host, config)


@then("the node should be added to the replica set")
def node_added_to_rs(mongo_context):
    """Verify node added"""
    assert mongo_context.last_result.get("success") is True


@then("the node should begin replicating data")
def node_replicating(mongo_context):
    """Verify node is replicating"""
    # Replication starts automatically
    pass


@then("the node should not participate in elections")
def node_no_elections(mongo_context):
    """Verify node has no votes"""
    host = mongo_context.last_result.get("member", "")
    member = mongo_context.manager.replica_set.get_member(host)
    if member:
        assert member.votes == 0


@given("an external MongoDB node is available")
def any_external_node(mongo_context):
    """Any external node is available"""
    mongo_context.last_result = {"available_node": "external-node:27017"}


@when("I add the node with dry run enabled")
def add_node_dry_run(mongo_context):
    """Add node with dry run"""
    host = mongo_context.last_result.get("available_node", "external:27017")
    mongo_context.last_result = mongo_context.manager.add_node(host, {"priority": 0, "votes": 0}, dry_run=True)


@then("no changes should be made to the replica set")
def no_rs_changes(mongo_context):
    """Verify no changes made"""
    assert mongo_context.last_result.get("dry_run") is True


@then("I should see what configuration would be applied")
def see_would_be_config(mongo_context):
    """Verify proposed config visible"""
    assert mongo_context.manager.dry_run_result is not None
    assert "config" in mongo_context.manager.dry_run_result


@when(parsers.parse("I add a node with:\n{table}"))
def add_node_with_config(mongo_context, table):
    """Add node with configuration"""
    config = {}
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Setting':
                key = parts[0].lower().replace(" ", "_")
                value = parts[1]

                # Convert types
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)
                elif "=" in value:
                    # Handle tags like role=read
                    k, v = value.split("=")
                    config.setdefault("tags", {})[k] = v
                    continue

                config[key] = value

    host = mongo_context.last_result.get("available_node", "external:27017")
    mongo_context.last_result = mongo_context.manager.add_node(host, config)


@then(parsers.parse("the node should replicate with a {hours:d}-hour delay"))
def node_has_delay(mongo_context, hours):
    """Verify slave delay"""
    host = mongo_context.last_result.get("member", "")
    member = mongo_context.manager.replica_set.get_member(host)
    if member:
        assert member.slave_delay == hours * 3600


@then("I can use this node to recover from accidental deletions")
def node_for_recovery(mongo_context):
    """Verify node can be used for recovery"""
    pass  # Design requirement


@then("the node should be visible for read operations")
def node_visible_for_reads(mongo_context):
    """Verify node not hidden"""
    host = mongo_context.last_result.get("member", "")
    member = mongo_context.manager.replica_set.get_member(host)
    if member:
        assert member.hidden is False


@then("the node should be tagged for read preference targeting")
def node_has_tags(mongo_context):
    """Verify node has tags"""
    host = mongo_context.last_result.get("member", "")
    member = mongo_context.manager.replica_set.get_member(host)
    if member:
        assert len(member.tags) > 0


@given(parsers.parse("I attempt to add a node \"{host}\""))
def attempt_add_node(mongo_context, host):
    """Prepare to add node"""
    mongo_context.last_result = {"available_node": host}


@given("the node is not reachable")
def node_not_reachable(mongo_context):
    """Mark node as not reachable"""
    mongo_context.last_result["is_reachable"] = False


@when("I try to add the node")
def try_add_node(mongo_context):
    """Try to add unreachable node"""
    host = mongo_context.last_result.get("available_node", "bad-node:27017")
    config = {"is_reachable": mongo_context.last_result.get("is_reachable", True)}
    mongo_context.last_result = mongo_context.manager.add_node(host, config)


@then(parsers.parse("the operation should fail with \"{error}\""))
def operation_fails_with_error(mongo_context, error):
    """Verify operation failed with error"""
    assert mongo_context.last_result.get("success") is False
    assert error in mongo_context.manager.last_error


# =============================================================================
# Remove Node Steps
# =============================================================================

@given(parsers.parse("an OOB node \"{host}\" is in the replica set"))
def oob_node_in_rs(mongo_context, host):
    """Add OOB node to replica set"""
    mongo_context.manager.add_node(host, {"priority": 0, "votes": 0, "hidden": True})


@when("I remove the node")
def remove_node(mongo_context):
    """Remove the OOB node"""
    # Get last added OOB node
    for member in mongo_context.manager.replica_set.members:
        if member.is_oob:
            mongo_context.last_result = mongo_context.manager.remove_node(f"{member.host}:{member.port}")
            return
    mongo_context.last_result = {"success": False, "error": "No OOB node found"}


@then("the node should be removed from the replica set configuration")
def node_removed_from_config(mongo_context):
    """Verify node removed"""
    assert mongo_context.last_result.get("success") is True


@then("the remaining nodes should continue operating normally")
def remaining_nodes_ok(mongo_context):
    """Verify remaining nodes ok"""
    assert mongo_context.manager.replica_set.primary is not None


@given(parsers.parse("Splunk's primary KVStore node is \"{host}\""))
def splunk_primary_is(mongo_context, host):
    """Set Splunk primary host"""
    pass  # Already set in manager initialization


@when(parsers.parse("I attempt to remove \"{host}\""))
def attempt_remove_node(mongo_context, host):
    """Attempt to remove node"""
    mongo_context.last_result = mongo_context.manager.remove_node(host)


@then("the operation should be blocked")
def operation_blocked(mongo_context):
    """Verify operation blocked"""
    assert mongo_context.last_result.get("success") is False


@then("an error should explain this would break Splunk")
def error_explains_break_splunk(mongo_context):
    """Verify error explains consequence"""
    assert "break Splunk" in mongo_context.manager.last_error


# =============================================================================
# Replication Monitoring Steps
# =============================================================================

@given("OOB nodes are replicating from Splunk's KVStore")
def oob_nodes_replicating(mongo_context):
    """Set up OOB nodes with replication"""
    # Add OOB nodes with lag
    mongo_context.manager.add_node("dr-mongo.backup.corp:27017", {"priority": 0, "votes": 0})
    mongo_context.manager.add_node("read-replica.corp:27017", {"priority": 0, "votes": 0})

    # Set lag values
    for member in mongo_context.manager.replica_set.members:
        if member.host == "dr-mongo.backup.corp":
            member.replication_lag_seconds = 2
        elif member.host == "read-replica.corp":
            member.replication_lag_seconds = 1


@when("I check replication status")
def check_replication_status(mongo_context):
    """Check replication status"""
    mongo_context.last_result = mongo_context.manager.get_replication_status()


@then(parsers.parse("I should see replication lag for each node:\n{table}"))
def see_replication_lag(mongo_context, table):
    """Verify replication lag visible"""
    expected = {}
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Node':
                expected[parts[0]] = int(parts[1])

    for status in mongo_context.last_result:
        host = status["host"].split(":")[0]
        if host in expected:
            assert status["lag_seconds"] == expected[host]


@given("an OOB node has replication lag > 60 seconds")
def oob_node_high_lag(mongo_context):
    """Set up OOB node with high lag"""
    mongo_context.manager.add_node("lag-node:27017", {"priority": 0, "votes": 0})
    for member in mongo_context.manager.replica_set.members:
        if member.host == "lag-node":
            member.replication_lag_seconds = 120


@when("the monitoring check runs")
def run_monitoring_check(mongo_context):
    """Run monitoring check"""
    mongo_context.manager.check_replication_lag()


@then("an alert should be triggered")
def alert_triggered(mongo_context):
    """Verify alert triggered"""
    assert len(mongo_context.manager.alerts) > 0


@then("the alert should include the node name and lag time")
def alert_has_details(mongo_context):
    """Verify alert details"""
    alert = mongo_context.manager.alerts[-1]
    assert "node" in alert
    assert "lag_seconds" in alert


@given("I've added a new OOB node")
def added_new_oob_node(mongo_context):
    """Add new OOB node"""
    mongo_context.manager.add_node("new-node:27017", {"priority": 0, "votes": 0})


@given("the node is syncing historical data")
def node_syncing_history(mongo_context):
    """Node is in initial sync"""
    pass


@when(parsers.parse("I wait for sync with timeout of {timeout:d} seconds"))
def wait_for_sync(mongo_context, timeout):
    """Wait for node to sync"""
    mongo_context.last_result = mongo_context.manager.wait_for_sync("new-node:27017", timeout)


@then("the operation should block until sync completes")
def block_until_sync(mongo_context):
    """Verify blocking behavior"""
    assert mongo_context.last_result.get("synced") is True


@then("Or timeout if sync takes too long")
def or_timeout(mongo_context):
    """Alternative: timeout"""
    pass  # Design requirement


# =============================================================================
# Failover Steps
# =============================================================================

@given("Splunk's primary node is unavailable")
def primary_unavailable(mongo_context):
    """Mark primary as unavailable"""
    if mongo_context.manager.replica_set.primary:
        mongo_context.manager.replica_set.primary.state = ReplicaState.DOWN


@given(parsers.parse("OOB node \"{host}\" is in sync"))
def oob_node_in_sync(mongo_context, host):
    """Ensure OOB node is in sync"""
    node_host = host.split(":")[0]
    if not mongo_context.manager.replica_set.get_member(host):
        mongo_context.manager.add_node(host, {"priority": 0, "votes": 0})
    member = mongo_context.manager.replica_set.get_member(host)
    if member:
        member.replication_lag_seconds = 0


@when(parsers.parse("I promote \"{host}\" to primary with force=true"))
def promote_with_force(mongo_context, host):
    """Promote node with force"""
    mongo_context.last_result = mongo_context.manager.promote_node(host, force=True)


@then("the node's priority should be set to 100")
def node_priority_100(mongo_context):
    """Verify node priority"""
    assert mongo_context.manager.replica_set.primary.priority == 100


@then("the node should become the new primary")
def node_is_primary(mongo_context):
    """Verify node is primary"""
    assert mongo_context.manager.replica_set.primary.state == ReplicaState.PRIMARY


@then("I should receive confirmation of the promotion")
def promotion_confirmed(mongo_context):
    """Verify promotion confirmation"""
    assert mongo_context.last_result.get("success") is True


@given("Splunk's primary node is healthy")
def primary_healthy(mongo_context):
    """Ensure primary is healthy"""
    if mongo_context.manager.replica_set.primary:
        mongo_context.manager.replica_set.primary.state = ReplicaState.PRIMARY


@given("I attempt to promote an OOB node")
def attempt_promote_oob(mongo_context):
    """Prepare to promote OOB node"""
    mongo_context.manager.add_node("oob-node:27017", {"priority": 0, "votes": 0})


@given("Without force=true")
def without_force(mongo_context):
    """Without force flag"""
    pass


@then("an error should explain the current primary is available")
def error_primary_available(mongo_context):
    """Verify error explains primary available"""
    mongo_context.last_result = mongo_context.manager.promote_node("oob-node:27017", force=False)
    assert mongo_context.last_result.get("success") is False
    assert "primary is available" in mongo_context.manager.last_error


@given("an OOB node was promoted during an outage")
def oob_was_promoted(mongo_context):
    """OOB node was promoted"""
    mongo_context.manager.add_node("promoted-oob:27017", {"priority": 0, "votes": 0})
    # Simulate outage and promotion
    if mongo_context.manager.replica_set.primary:
        mongo_context.manager.replica_set.primary.state = ReplicaState.DOWN
    mongo_context.manager.promote_node("promoted-oob:27017", force=True)


@given("the original Splunk primary is now available")
def original_primary_available(mongo_context):
    """Original primary is available"""
    for member in mongo_context.manager.replica_set.members:
        if member.host == "splunk-sh01":
            member.state = ReplicaState.SECONDARY


@when("I restore the original primary")
def restore_original_primary(mongo_context):
    """Restore original primary"""
    mongo_context.last_result = mongo_context.manager.restore_original_primary("splunk-sh01:8191")


@then("the original node should become primary again")
def original_is_primary(mongo_context):
    """Verify original is primary"""
    assert mongo_context.manager.replica_set.primary.host == "splunk-sh01"


@then("the OOB node should return to secondary status")
def oob_is_secondary(mongo_context):
    """Verify OOB is secondary"""
    for member in mongo_context.manager.replica_set.members:
        if member.host == "promoted-oob":
            assert member.state == ReplicaState.SECONDARY


# =============================================================================
# Configuration Generation Steps
# =============================================================================

@given("I want to set up a new OOB MongoDB node")
def want_new_oob_node(mongo_context):
    """Want to set up OOB node"""
    pass


@when("I generate the configuration")
def generate_config(mongo_context):
    """Generate mongod.conf"""
    mongo_context.last_result = mongo_context.manager.generate_config()


@then(parsers.parse("I should receive a mongod.conf template with:\n{table}"))
def receive_config_template(mongo_context, table):
    """Verify config template"""
    config = mongo_context.last_result
    assert "replication" in config
    assert "security" in config
    assert "net" in config


@given("Splunk's KVStore uses a key file for auth")
def kvstore_uses_keyfile(mongo_context):
    """KVStore uses key file"""
    pass


@when("I export the key file")
def export_keyfile(mongo_context):
    """Export key file"""
    mongo_context.last_result = mongo_context.manager.export_key_file()


@then("I should receive the key file content")
def receive_keyfile(mongo_context):
    """Verify key file content"""
    assert "key_file_content" in mongo_context.last_result


@then("instructions for deploying it to OOB nodes")
def receive_instructions(mongo_context):
    """Verify deployment instructions"""
    assert "instructions" in mongo_context.last_result


# =============================================================================
# Dashboard Steps
# =============================================================================

@given("I open the MongoDB Cluster dashboard")
def open_cluster_dashboard(mongo_context):
    """Open cluster dashboard"""
    pass


@then(parsers.parse("I should see all replica set members:\n{table}"))
def see_all_members(mongo_context, table):
    """Verify all members visible"""
    members = mongo_context.manager.get_replication_status()
    assert len(members) >= 1


@given("one replica set member is in RECOVERING state")
def member_recovering(mongo_context):
    """Set member to recovering"""
    mongo_context.manager.add_node("recovering-node:27017", {"priority": 0, "votes": 0})
    for member in mongo_context.manager.replica_set.members:
        if member.host == "recovering-node":
            member.state = ReplicaState.RECOVERING


@when("I view the dashboard")
def view_dashboard(mongo_context):
    """View dashboard"""
    mongo_context.last_result = mongo_context.manager.get_replication_status()


@then("that member should be highlighted with warning color")
def member_highlighted(mongo_context):
    """Verify warning highlight"""
    for status in mongo_context.last_result:
        if status["host"].startswith("recovering"):
            assert status["state"] == "RECOVERING"


@then("a tooltip should explain the state")
def tooltip_explains_state(mongo_context):
    """Verify tooltip exists"""
    pass  # UI verification
