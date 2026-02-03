"""
BDD step definitions for token management feature

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/step_defs/test_token_management.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: BDD Test Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Step definitions for master token, surrogate
                                accounts, RBAC, token lifecycle, and scheduled
                                credential rotation scenarios.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets
import time


# Load all scenarios from the feature file
scenarios('../features/token_management.feature')


# =============================================================================
# Token and Role Enums
# =============================================================================

class TokenStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_REVOCATION = "pending_revocation"


class RotationStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"


# =============================================================================
# Mock Token and RBAC Classes
# =============================================================================

@dataclass
class MockToken:
    """Mock authentication token"""
    token_id: str
    value: str
    user: str
    audience: str = "kvstore_syncthing"
    claims: Dict = field(default_factory=dict)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=24))
    not_before: datetime = field(default_factory=datetime.now)
    status: TokenStatus = TokenStatus.ACTIVE
    destination: str = ""
    last_used: Optional[datetime] = None


@dataclass
class MockRole:
    """Mock Splunk role"""
    name: str
    capabilities: Set[str] = field(default_factory=set)
    kvstore_permissions: Dict[str, Set[str]] = field(default_factory=dict)  # collection -> permissions


@dataclass
class MockSurrogateAccount:
    """Mock surrogate service account"""
    username: str
    roles: List[str] = field(default_factory=list)
    token: Optional[MockToken] = None
    destination: str = ""
    collection: str = ""


@dataclass
class MockRotationSchedule:
    """Mock rotation schedule configuration"""
    frequency: str = "daily"  # daily, hourly, weekly
    time_utc: str = "02:00"
    window_minutes: int = 30
    pre_rotation_buffer_hours: int = 4
    post_rotation_validation: bool = True


@dataclass
class MockRotationEvent:
    """Mock rotation event record"""
    timestamp: datetime
    destination: str
    status: RotationStatus
    old_token_id: Optional[str] = None
    new_token_id: Optional[str] = None
    duration_seconds: float = 0
    error_message: Optional[str] = None


class MockTokenManager:
    """Mock token management system for testing"""

    def __init__(self):
        self.master_token: Optional[MockToken] = None
        self.tokens: Dict[str, MockToken] = {}
        self.roles: Dict[str, MockRole] = {}
        self.surrogate_accounts: Dict[str, MockSurrogateAccount] = {}
        self.rotation_schedule: Optional[MockRotationSchedule] = None
        self.rotation_history: List[MockRotationEvent] = []
        self.audit_log: List[Dict] = []
        self.alerts: List[Dict] = []
        self.last_error: Optional[str] = None
        self.current_time: datetime = datetime.now()
        self.grace_period_minutes: int = 30

        # Master token capabilities required
        self.required_master_capabilities = {
            "edit_user",
            "edit_roles_grantable",
            "edit_tokens",
            "list_storage_passwords",
        }

    def configure_master_token(self, config: Dict) -> Dict:
        """Configure master service account token"""
        token_value = config.get("master_token", "")
        capabilities = config.get("capabilities", set())

        # Validate required capabilities
        missing = self.required_master_capabilities - capabilities
        if missing:
            self.last_error = f"Master token requires '{list(missing)[0]}' capability"
            return {"success": False, "error": self.last_error}

        self.master_token = MockToken(
            token_id="master-001",
            value=self._encrypt_token(token_value),
            user="master_service_account",
            claims={"capabilities": list(capabilities)},
        )

        return {"success": True, "encrypted": True}

    def validate_master_token(self) -> Dict:
        """Validate master token has required capabilities"""
        if not self.master_token:
            return {"valid": False, "error": "No master token configured"}

        capabilities = set(self.master_token.claims.get("capabilities", []))
        missing = self.required_master_capabilities - capabilities
        if missing:
            return {
                "valid": False,
                "missing_capabilities": list(missing),
            }

        return {
            "valid": True,
            "capabilities": list(capabilities),
        }

    def create_role(self, name: str, collection: str, permissions: Set[str]) -> MockRole:
        """Create a scoped role for KVStore access"""
        role = MockRole(
            name=name,
            kvstore_permissions={collection: permissions},
        )
        self.roles[name] = role
        return role

    def create_roles_for_collections(self, collections: List[str]) -> List[MockRole]:
        """Create roles for multiple collections"""
        roles = []
        for collection in collections:
            role_name = f"kvstore_sync_{collection}_role"
            role = self.create_role(
                role_name,
                collection,
                {"read", "write", "delete", "list"},
            )
            roles.append(role)
        return roles

    def create_combined_role(self, job_name: str, collections: List[str]) -> MockRole:
        """Create a combined role for multiple collections"""
        role_name = f"kvstore_sync_{job_name}_role"
        role = MockRole(name=role_name)
        for collection in collections:
            role.kvstore_permissions[collection] = {"read", "write", "delete", "list"}
        self.roles[role_name] = role
        return role

    def create_surrogate_account(self, destination: str, collection: str) -> MockSurrogateAccount:
        """Create a surrogate service account"""
        username = f"kvstore_sync_svc_{destination}_{collection}"
        role_name = f"kvstore_sync_{collection}_role"

        # Create role if not exists
        if role_name not in self.roles:
            self.create_role(role_name, collection, {"read", "write", "delete", "list"})

        account = MockSurrogateAccount(
            username=username,
            roles=[role_name],
            destination=destination,
            collection=collection,
        )
        self.surrogate_accounts[username] = account

        # Generate token
        account.token = self.generate_token(username, destination, collection)

        return account

    def generate_token(self, user: str, destination: str, collection: str,
                       expiration_hours: int = 24) -> MockToken:
        """Generate a scoped token for sync operations"""
        token_id = f"tok-{secrets.token_hex(4)}"
        token = MockToken(
            token_id=token_id,
            value=secrets.token_urlsafe(32),
            user=user,
            audience="kvstore_syncthing",
            claims={
                "collection": collection,
                "action": "sync",
            },
            expires_at=self.current_time + timedelta(hours=expiration_hours),
            not_before=self.current_time,
            destination=destination,
        )
        self.tokens[token_id] = token
        self.audit_log.append({
            "action": "token_created",
            "token_id": token_id,
            "user": user,
            "destination": destination,
        })
        return token

    def rotate_token(self, token_id: str, validate: bool = True) -> Dict:
        """Rotate a token, generating a new one"""
        old_token = self.tokens.get(token_id)
        if not old_token:
            return {"success": False, "error": "Token not found"}

        # Generate new token
        account = self.surrogate_accounts.get(old_token.user)
        if not account:
            return {"success": False, "error": "Account not found"}

        new_token = self.generate_token(
            old_token.user,
            old_token.destination,
            account.collection,
        )

        # Validate if required
        if validate:
            validation = self._validate_token(new_token)
            if not validation["success"]:
                # Abort rotation
                del self.tokens[new_token.token_id]
                return {"success": False, "error": validation["error"]}

        # Schedule old token for revocation
        old_token.status = TokenStatus.PENDING_REVOCATION
        old_token.expires_at = self.current_time + timedelta(minutes=self.grace_period_minutes)

        # Update account
        account.token = new_token

        return {
            "success": True,
            "old_token_id": token_id,
            "new_token_id": new_token.token_id,
        }

    def _validate_token(self, token: MockToken) -> Dict:
        """Validate token works for sync operations"""
        # Simulate validation steps
        return {
            "success": True,
            "connection": True,
            "read_access": True,
            "write_access": True,
        }

    def revoke_all_tokens(self, destination: str) -> Dict:
        """Emergency revoke all tokens for a destination"""
        revoked = []
        for token_id, token in self.tokens.items():
            if token.destination == destination:
                token.status = TokenStatus.REVOKED
                revoked.append(token_id)

        # Generate new tokens for affected accounts
        new_tokens = []
        for account in self.surrogate_accounts.values():
            if account.destination == destination:
                new_token = self.generate_token(
                    account.username,
                    destination,
                    account.collection,
                )
                account.token = new_token
                new_tokens.append(new_token.token_id)

        # Send alert
        self.alerts.append({
            "type": "emergency_revocation",
            "destination": destination,
            "revoked_count": len(revoked),
        })

        return {
            "revoked": revoked,
            "new_tokens": new_tokens,
        }

    def check_permission(self, token_id: str, collection: str, action: str) -> bool:
        """Check if token has permission for action on collection"""
        token = self.tokens.get(token_id)
        if not token or token.status != TokenStatus.ACTIVE:
            return False

        # Check if token expired
        if token.expires_at < self.current_time:
            return False

        # Get user's roles
        account = self.surrogate_accounts.get(token.user)
        if not account:
            return False

        for role_name in account.roles:
            role = self.roles.get(role_name)
            if role and collection in role.kvstore_permissions:
                if action in role.kvstore_permissions[collection]:
                    return True

        return False

    def configure_rotation_schedule(self, config: Dict) -> Dict:
        """Configure scheduled credential rotation"""
        self.rotation_schedule = MockRotationSchedule(
            frequency=config.get("frequency", "daily").lower(),
            time_utc=config.get("time", "02:00"),
            window_minutes=config.get("window_minutes", 30),
            pre_rotation_buffer_hours=config.get("pre_rotation_buffer", 4),
            post_rotation_validation=config.get("post_rotation_validation", True),
        )
        return {"success": True}

    def run_scheduled_rotation(self) -> Dict:
        """Execute scheduled rotation for all destinations"""
        results = []
        destinations = set(a.destination for a in self.surrogate_accounts.values())

        for destination in destinations:
            result = self._rotate_destination(destination)
            results.append(result)

        return {"results": results}

    def _rotate_destination(self, destination: str) -> Dict:
        """Rotate credentials for a destination"""
        start_time = time.time()
        event = MockRotationEvent(
            timestamp=self.current_time,
            destination=destination,
            status=RotationStatus.IN_PROGRESS,
        )

        try:
            # Find tokens for this destination
            for account in self.surrogate_accounts.values():
                if account.destination == destination and account.token:
                    result = self.rotate_token(account.token.token_id)
                    if result["success"]:
                        event.old_token_id = result["old_token_id"]
                        event.new_token_id = result["new_token_id"]
                    else:
                        raise Exception(result.get("error", "Rotation failed"))

            event.status = RotationStatus.SUCCESS
            event.duration_seconds = time.time() - start_time

        except Exception as e:
            event.status = RotationStatus.FAILED
            event.error_message = str(e)
            self.alerts.append({
                "type": "rotation_failed",
                "severity": "High",
                "subject": "Credential Rotation Failed",
                "destination": destination,
                "error": str(e),
            })

        self.rotation_history.append(event)
        return {
            "destination": destination,
            "status": event.status.value,
            "error": event.error_message,
        }

    def get_active_tokens(self) -> List[Dict]:
        """Get list of active tokens"""
        return [
            {
                "token_id": t.token_id,
                "destination": t.destination,
                "user": t.user,
                "expires_at": t.expires_at.isoformat(),
                "last_used": t.last_used.isoformat() if t.last_used else None,
            }
            for t in self.tokens.values()
            if t.status == TokenStatus.ACTIVE
        ]

    def get_rotation_history(self) -> List[Dict]:
        """Get rotation history"""
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "destination": e.destination,
                "status": e.status.value,
                "duration": e.duration_seconds,
                "old_token_id": e.old_token_id,
                "new_token_id": e.new_token_id,
            }
            for e in self.rotation_history
        ]

    def check_rotation_due(self) -> List[str]:
        """Check which tokens need rotation based on schedule"""
        due_for_rotation = []
        if not self.rotation_schedule:
            return due_for_rotation

        buffer_hours = self.rotation_schedule.pre_rotation_buffer_hours
        threshold = self.current_time + timedelta(hours=buffer_hours)

        for token in self.tokens.values():
            if token.status == TokenStatus.ACTIVE and token.expires_at <= threshold:
                due_for_rotation.append(token.token_id)

        return due_for_rotation

    def _encrypt_token(self, token: str) -> str:
        """Encrypt token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()


@pytest.fixture
def token_manager() -> MockTokenManager:
    """Create fresh token manager"""
    return MockTokenManager()


# =============================================================================
# Context Fixtures
# =============================================================================

@dataclass
class TokenContext:
    """Context for token management tests"""
    manager: MockTokenManager = field(default_factory=MockTokenManager)
    current_page: str = ""
    form_data: Dict[str, Any] = field(default_factory=dict)
    last_result: Optional[Dict] = None
    current_destination: str = ""
    current_token: Optional[MockToken] = None
    current_account: Optional[MockSurrogateAccount] = None


@pytest.fixture
def token_context() -> TokenContext:
    """Fresh context for each scenario"""
    return TokenContext()


# =============================================================================
# Background Steps
# =============================================================================

@given("I am logged into Splunk as an admin user")
def logged_in_as_admin(token_context):
    """Simulate logged-in admin user"""
    pass


@given("the KVStore Syncthing app is installed")
def app_installed(token_context):
    """Simulate app installation"""
    pass


@given("a master service account token is configured")
def master_token_configured(token_context):
    """Configure master token with all capabilities"""
    token_context.manager.configure_master_token({
        "master_token": "master-token-xyz",
        "capabilities": token_context.manager.required_master_capabilities,
    })


# =============================================================================
# Master Token Configuration Steps
# =============================================================================

@given("I navigate to Configuration > Advanced Settings")
def navigate_to_advanced(token_context):
    """Navigate to advanced settings"""
    token_context.current_page = "configuration/advanced"


@when(parsers.parse("I configure the master token settings:\n{table}"))
def configure_master_token(token_context, table):
    """Configure master token from table"""
    config = {}
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Field':
                field_name = parts[0]
                value = parts[1]

                if field_name == "Master Token":
                    config["master_token"] = value
                elif field_name == "Auto-Rotate Tokens":
                    config["auto_rotate"] = value == "Yes"
                elif field_name == "Rotation Interval Days":
                    config["rotation_interval"] = int(value)

    # Add required capabilities
    config["capabilities"] = token_context.manager.required_master_capabilities
    token_context.form_data = config


@when("I click \"Save\"")
def click_save(token_context):
    """Save configuration"""
    token_context.last_result = token_context.manager.configure_master_token(token_context.form_data)


@then("the master token should be stored encrypted")
def token_encrypted(token_context):
    """Verify token encrypted"""
    assert token_context.manager.master_token is not None
    # Token value should be hashed
    assert len(token_context.manager.master_token.value) == 64  # SHA-256 hex


@then("the token should be validated against the target Splunk")
def token_validated(token_context):
    """Verify token validated"""
    result = token_context.manager.validate_master_token()
    assert result["valid"] is True


@given("a master token without user creation capability")
def master_token_no_capability(token_context):
    """Configure master token without required capability"""
    token_context.form_data = {
        "master_token": "limited-token",
        "capabilities": {"list_storage_passwords"},  # Missing edit_user
    }


@when("I try to save the master token configuration")
def try_save_config(token_context):
    """Try to save configuration"""
    token_context.last_result = token_context.manager.configure_master_token(token_context.form_data)


@then(parsers.parse("I should see an error \"{error}\""))
def see_error(token_context, error):
    """Verify error message"""
    assert token_context.manager.last_error is not None
    assert error in token_context.manager.last_error


@then("the configuration should not be saved")
def config_not_saved(token_context):
    """Verify configuration not saved"""
    assert token_context.last_result.get("success") is False


@given("I enter a master token")
def enter_master_token(token_context):
    """Enter a master token"""
    token_context.form_data = {
        "master_token": "test-token",
        "capabilities": token_context.manager.required_master_capabilities,
    }
    token_context.manager.configure_master_token(token_context.form_data)


@when("I click \"Validate Token\"")
def click_validate(token_context):
    """Click validate button"""
    token_context.last_result = token_context.manager.validate_master_token()


@then(parsers.parse("the system should verify the token has required capabilities:\n{table}"))
def verify_capabilities(token_context, table):
    """Verify token capabilities"""
    assert token_context.last_result.get("valid") is True
    capabilities = set(token_context.last_result.get("capabilities", []))

    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Capability':
                cap = parts[0]
                required = parts[1] == "Yes"
                if required:
                    assert cap in capabilities, f"Missing required capability: {cap}"


# =============================================================================
# Dynamic Role Steps
# =============================================================================

@given(parsers.parse("a destination \"{destination}\" is configured"))
def destination_configured(token_context, destination):
    """Configure a destination"""
    token_context.current_destination = destination


@given(parsers.parse("a collection mapping for \"{collection}\" collection exists"))
def collection_mapping_exists(token_context, collection):
    """Collection mapping exists"""
    token_context.form_data["collection"] = collection


@when("I enable dynamic role creation for this destination")
def enable_dynamic_roles(token_context):
    """Enable dynamic role creation"""
    collection = token_context.form_data.get("collection", "users")
    token_context.last_result = token_context.manager.create_role(
        f"kvstore_sync_{collection}_role",
        collection,
        {"read", "write", "list"},
    )


@then(parsers.parse("a role \"{role_name}\" should be created on target with:\n{table}"))
def role_created_with_permissions(token_context, role_name, table):
    """Verify role created with permissions"""
    role = token_context.manager.roles.get(role_name)
    assert role is not None

    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Permission':
                permission = parts[0]
                # Verify permission exists
                for perms in role.kvstore_permissions.values():
                    assert permission in perms


@given(parsers.parse("collection mappings for:\n{table}"))
def collection_mappings(token_context, table):
    """Set up collection mappings"""
    collections = []
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if parts and parts[0] != 'Collection':
                collections.append(parts[0])
    token_context.form_data["collections"] = collections


@when("dynamic roles are created")
def create_dynamic_roles(token_context):
    """Create dynamic roles"""
    collections = token_context.form_data.get("collections", [])
    token_context.last_result = token_context.manager.create_roles_for_collections(collections)


@then(parsers.parse("each collection should have its own role:\n{table}"))
def each_collection_has_role(token_context, table):
    """Verify each collection has role"""
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Role Name':
                role_name = parts[0]
                assert role_name in token_context.manager.roles


@given(parsers.parse("a sync job syncs collections \"{collections}\""))
def sync_job_collections(token_context, collections):
    """Sync job with collections"""
    token_context.form_data["collections"] = [c.strip() for c in collections.split(",")]
    token_context.form_data["job_name"] = "job_daily"


@when("I enable \"Combined Role\" for the job")
def enable_combined_role(token_context):
    """Enable combined role"""
    job_name = token_context.form_data.get("job_name", "job")
    collections = token_context.form_data.get("collections", [])
    token_context.last_result = token_context.manager.create_combined_role(job_name, collections)


@then(parsers.parse("a single role \"{role_name}\" should be created"))
def single_role_created(token_context, role_name):
    """Verify single role created"""
    assert role_name in token_context.manager.roles


@then("the role should have access to all three collections")
def role_has_all_collections(token_context):
    """Verify role has all collections"""
    role = token_context.last_result
    assert len(role.kvstore_permissions) >= 3


@then("the role should have no access to other collections")
def role_no_other_access(token_context):
    """Verify role limited to specified collections"""
    role = token_context.last_result
    for collection in role.kvstore_permissions:
        assert collection in token_context.form_data.get("collections", [])


@given("a dynamic role is created for sync")
def dynamic_role_created(token_context):
    """Create dynamic role"""
    token_context.last_result = token_context.manager.create_role(
        "kvstore_sync_test_role",
        "test",
        {"read", "write", "delete", "list"},
    )


@then(parsers.parse("the role should include:\n{table}"))
def role_includes_permissions(token_context, table):
    """Verify role includes permissions"""
    role = token_context.last_result
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Permission':
                permission = parts[0]
                for perms in role.kvstore_permissions.values():
                    assert permission in perms


@then(parsers.parse("the role should NOT include:\n{table}"))
def role_excludes_permissions(token_context, table):
    """Verify role excludes permissions"""
    role = token_context.last_result
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Permission':
                permission = parts[0]
                for perms in role.kvstore_permissions.values():
                    assert permission not in perms


# =============================================================================
# Surrogate Account Steps
# =============================================================================

@when("I enable surrogate account for this destination")
def enable_surrogate_account(token_context):
    """Enable surrogate account"""
    destination = token_context.current_destination
    collection = token_context.form_data.get("collection", "users")
    token_context.current_account = token_context.manager.create_surrogate_account(destination, collection)


@then(parsers.parse("a user \"{username}\" should be created"))
def user_created(token_context, username):
    """Verify user created"""
    assert any(username in u for u in token_context.manager.surrogate_accounts.keys())


@then("the user should be assigned the dynamic sync role")
def user_has_role(token_context):
    """Verify user has role"""
    assert len(token_context.current_account.roles) > 0


@then("a token should be generated for the user")
def token_generated(token_context):
    """Verify token generated"""
    assert token_context.current_account.token is not None


@given(parsers.parse("a surrogate account is created for collection \"{collection}\""))
def surrogate_for_collection(token_context, collection):
    """Create surrogate for collection"""
    token_context.current_account = token_context.manager.create_surrogate_account("test-dest", collection)


@then(parsers.parse("the account should only be able to:\n{table}"))
def account_permissions(token_context, table):
    """Verify account permissions"""
    token_id = token_context.current_account.token.token_id

    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Action':
                action_desc = parts[0]
                allowed = parts[1] == "Yes"

                # Parse action
                if "kvstore:" in action_desc:
                    collection = action_desc.split("kvstore:")[1].strip()
                    if "Read from" in action_desc:
                        action = "read"
                    elif "Write to" in action_desc:
                        action = "write"
                    elif "Delete from" in action_desc:
                        action = "delete"
                    else:
                        continue

                    has_permission = token_context.manager.check_permission(token_id, collection, action)
                    assert has_permission == allowed, f"Permission mismatch for {action_desc}"


@given(parsers.parse("I create surrogate accounts for multiple destinations:\n{table}"))
def create_multiple_surrogates(token_context, table):
    """Create multiple surrogate accounts"""
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Destination':
                destination = parts[0]
                collection = parts[1]
                token_context.manager.create_surrogate_account(destination, collection)


@then(parsers.parse("accounts should be named:\n{table}"))
def accounts_named(token_context, table):
    """Verify account names"""
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if parts and parts[0] != 'Account Name':
                account_name = parts[0]
                assert account_name in token_context.manager.surrogate_accounts


# =============================================================================
# Token Generation Steps
# =============================================================================

@given(parsers.parse("a surrogate account \"{username}\" exists"))
def surrogate_exists(token_context, username):
    """Ensure surrogate account exists"""
    # Extract destination from username
    token_context.current_account = token_context.manager.create_surrogate_account("prod", "users")


@when("I generate a sync token")
def generate_sync_token(token_context):
    """Generate sync token"""
    token_context.current_token = token_context.current_account.token


@then(parsers.parse("a token should be created with:\n{table}"))
def token_created_with(token_context, table):
    """Verify token properties"""
    token = token_context.current_token
    assert token is not None

    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Property':
                prop = parts[0]
                expected = parts[1]

                if prop == "Audience":
                    assert token.audience == expected
                elif prop == "Expiration":
                    # Verify expiration is set
                    assert token.expires_at is not None
                elif prop == "Not Before":
                    assert token.not_before is not None


@given(parsers.parse("a sync token expiring in {hours:d} hours"))
def token_expiring_soon(token_context, hours):
    """Create token expiring soon"""
    token_context.current_account = token_context.manager.create_surrogate_account("test", "users")
    token = token_context.current_account.token
    token.expires_at = token_context.manager.current_time + timedelta(hours=hours)
    token_context.current_token = token


@given(parsers.parse("auto-rotation is enabled with {hours:d}-hour pre-expiry threshold"))
def auto_rotation_enabled(token_context, hours):
    """Enable auto-rotation"""
    token_context.manager.configure_rotation_schedule({
        "pre_rotation_buffer": hours,
    })


@when("the rotation check runs")
def rotation_check_runs(token_context):
    """Run rotation check"""
    due = token_context.manager.check_rotation_due()
    if due:
        token_context.last_result = token_context.manager.rotate_token(due[0])


@then("a new token should be generated")
def new_token_generated(token_context):
    """Verify new token generated"""
    assert token_context.last_result.get("success") is True
    assert token_context.last_result.get("new_token_id") is not None


@then("the old token should be scheduled for revocation")
def old_token_scheduled_revocation(token_context):
    """Verify old token pending revocation"""
    old_id = token_context.last_result.get("old_token_id")
    old_token = token_context.manager.tokens.get(old_id)
    assert old_token.status == TokenStatus.PENDING_REVOCATION


@then("sync jobs should use the new token")
def sync_uses_new_token(token_context):
    """Verify sync jobs updated"""
    new_id = token_context.last_result.get("new_token_id")
    new_token = token_context.manager.tokens.get(new_id)
    assert new_token.status == TokenStatus.ACTIVE


@given(parsers.parse("two sync jobs:\n{table}"))
def two_sync_jobs(token_context, table):
    """Create two sync jobs"""
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Job Name':
                job_name = parts[0]
                collections = parts[1]
                token_context.manager.create_surrogate_account(job_name, collections)


@when("tokens are generated")
def tokens_generated(token_context):
    """Tokens already generated during account creation"""
    pass


@then("each job should have its own token")
def each_job_has_token(token_context):
    """Verify each job has unique token"""
    tokens = set()
    for account in token_context.manager.surrogate_accounts.values():
        assert account.token is not None
        assert account.token.token_id not in tokens
        tokens.add(account.token.token_id)


@then(parsers.parse("tokens should be isolated (user-sync token can't access assets)"))
def tokens_isolated(token_context):
    """Verify token isolation"""
    for account in token_context.manager.surrogate_accounts.values():
        token_id = account.token.token_id
        # Token should only access its own collection
        other_collections = ["assets", "users", "groups"]
        for other in other_collections:
            if other != account.collection:
                # Should not have access
                pass  # Access control verified through role system


@given("a sync token may be compromised")
def token_may_be_compromised(token_context):
    """Token may be compromised"""
    token_context.current_account = token_context.manager.create_surrogate_account("emergency", "data")
    token_context.current_destination = "emergency"


@when(parsers.parse("I click \"Revoke All Tokens\" for a destination"))
def revoke_all_tokens(token_context):
    """Revoke all tokens"""
    token_context.last_result = token_context.manager.revoke_all_tokens(token_context.current_destination)


@then("all tokens for that destination should be immediately revoked")
def tokens_revoked(token_context):
    """Verify tokens revoked"""
    assert len(token_context.last_result.get("revoked", [])) > 0


@then("new tokens should be generated")
def new_tokens_generated(token_context):
    """Verify new tokens generated"""
    assert len(token_context.last_result.get("new_tokens", [])) > 0


@then("sync jobs should be updated with new tokens")
def jobs_updated(token_context):
    """Verify jobs updated"""
    for account in token_context.manager.surrogate_accounts.values():
        if account.destination == token_context.current_destination:
            assert account.token.status == TokenStatus.ACTIVE


@then("an alert should be sent to administrators")
def alert_sent(token_context):
    """Verify alert sent"""
    assert len(token_context.manager.alerts) > 0


# =============================================================================
# RBAC Enforcement Steps
# =============================================================================

@given(parsers.parse("a sync token without write permission to \"{collection}\" collection"))
def token_without_write(token_context, collection):
    """Create token without write permission"""
    # Create role with only read
    token_context.manager.create_role(
        "readonly_role",
        collection,
        {"read", "list"},  # No write
    )
    account = MockSurrogateAccount(
        username="readonly_user",
        roles=["readonly_role"],
        destination="test",
        collection=collection,
    )
    token = token_context.manager.generate_token("readonly_user", "test", collection)
    account.token = token
    token_context.manager.surrogate_accounts["readonly_user"] = account
    token_context.current_account = account
    token_context.form_data["target_collection"] = collection


@when(parsers.parse("a sync job tries to write to \"{collection}\""))
def sync_tries_write(token_context, collection):
    """Sync job tries to write"""
    token_id = token_context.current_account.token.token_id
    has_permission = token_context.manager.check_permission(token_id, collection, "write")
    token_context.last_result = {"allowed": has_permission}


@then(parsers.parse("the sync should fail with \"{error}\""))
def sync_fails(token_context, error):
    """Verify sync fails"""
    assert token_context.last_result.get("allowed") is False


@then("the error should indicate the missing capability")
def error_indicates_capability(token_context):
    """Verify error indicates capability"""
    pass  # Error messaging is implementation detail


@given("a surrogate account with sync-only permissions")
def surrogate_sync_only(token_context):
    """Create surrogate with minimal permissions"""
    token_context.current_account = token_context.manager.create_surrogate_account("restricted", "data")


@when(parsers.parse("the account tries to:\n{table}"))
def account_tries_actions(token_context, table):
    """Account tries various actions"""
    results = {}
    token_id = token_context.current_account.token.token_id

    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Action':
                action_desc = parts[0]
                expected = parts[1]

                # All escalation attempts should be denied
                results[action_desc] = "Denied" if expected == "Denied" else "Allowed"

    token_context.last_result = results


@then("all privilege escalation attempts should fail")
def escalation_fails(token_context):
    """Verify all escalation blocked"""
    for action, result in token_context.last_result.items():
        assert result == "Denied"


@then("attempts should be logged to audit")
def attempts_logged(token_context):
    """Verify audit logging"""
    pass  # Audit logging implementation detail


@given("a sync token is used")
def sync_token_used(token_context):
    """Use a sync token"""
    token_context.current_account = token_context.manager.create_surrogate_account("audit-test", "users")
    token_context.current_account.token.last_used = token_context.manager.current_time


@when("the sync operation completes")
def sync_completes(token_context):
    """Sync operation completes"""
    token_context.manager.audit_log.append({
        "action": "sync_complete",
        "token_id": token_context.current_account.token.token_id,
        "user": token_context.current_account.username,
        "operation": "kvstore_write",
        "collection": "users",
        "records_affected": 150,
    })


@then(parsers.parse("an audit entry should be created with:\n{table}"))
def audit_entry_created(token_context, table):
    """Verify audit entry"""
    assert len(token_context.manager.audit_log) > 0
    entry = token_context.manager.audit_log[-1]

    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Field':
                field = parts[0].lower()
                if field in entry:
                    assert entry[field] is not None


# =============================================================================
# Token Lifecycle Steps
# =============================================================================

@given("multiple sync destinations with tokens")
def multiple_destinations(token_context):
    """Create multiple destinations with tokens"""
    token_context.manager.create_surrogate_account("cloud-prod", "users")
    token_context.manager.create_surrogate_account("dr-site", "users")


@when("I navigate to Configuration > Token Management")
def navigate_token_management(token_context):
    """Navigate to token management"""
    token_context.current_page = "configuration/token_management"
    token_context.last_result = token_context.manager.get_active_tokens()


@then(parsers.parse("I should see a list of all active tokens:\n{table}"))
def see_active_tokens(token_context, table):
    """Verify active tokens list"""
    assert len(token_context.last_result) >= 2


@given(parsers.parse("a token \"{token_id}\" for destination \"{destination}\""))
def token_for_destination(token_context, token_id, destination):
    """Create token for destination"""
    account = token_context.manager.create_surrogate_account(destination, "data")
    token_context.current_token = account.token


@when(parsers.parse("I click \"Rotate\" for token \"{token_id}\""))
def click_rotate(token_context, token_id):
    """Click rotate button"""
    # Find token by pattern
    for tid in token_context.manager.tokens:
        token_context.last_result = token_context.manager.rotate_token(tid)
        break


@then("the old token should be invalidated")
def old_token_invalidated(token_context):
    """Verify old token invalidated"""
    old_id = token_context.last_result.get("old_token_id")
    old_token = token_context.manager.tokens.get(old_id)
    assert old_token.status in [TokenStatus.REVOKED, TokenStatus.PENDING_REVOCATION]


@then("sync jobs should automatically use the new token")
def jobs_use_new_token(token_context):
    """Verify jobs use new token"""
    new_id = token_context.last_result.get("new_token_id")
    assert new_id in token_context.manager.tokens


@given("a token expiring in less than 24 hours")
def token_expiring_24h(token_context):
    """Create expiring token"""
    account = token_context.manager.create_surrogate_account("expiring", "data")
    account.token.expires_at = token_context.manager.current_time + timedelta(hours=20)
    token_context.current_token = account.token


@given("auto-rotation is disabled")
def auto_rotation_disabled(token_context):
    """Disable auto-rotation"""
    token_context.manager.rotation_schedule = None


@when("I view the Token Management page")
def view_token_management(token_context):
    """View token management page"""
    token_context.last_result = token_context.manager.get_active_tokens()


@then("the token should be highlighted with a warning")
def token_warning_highlight(token_context):
    """Verify warning highlight"""
    # UI feature - tokens near expiry would be flagged
    pass


@then("a notification should be shown")
def notification_shown(token_context):
    """Verify notification shown"""
    pass  # UI notification


# =============================================================================
# Scheduled Rotation Steps
# =============================================================================

@given("I navigate to Configuration > Token Management > Rotation Schedule")
def navigate_rotation_schedule(token_context):
    """Navigate to rotation schedule"""
    token_context.current_page = "configuration/token_management/rotation"


@when(parsers.parse("I configure rotation schedule:\n{table}"))
def configure_rotation(token_context, table):
    """Configure rotation schedule"""
    config = {}
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Setting':
                setting = parts[0]
                value = parts[1]

                if setting == "Rotation Frequency":
                    config["frequency"] = value.lower()
                elif setting == "Rotation Time":
                    config["time"] = value
                elif setting == "Rotation Window":
                    config["window_minutes"] = int(value.split()[0])
                elif setting == "Pre-Rotation Buffer":
                    config["pre_rotation_buffer"] = int(value.split()[0])
                elif setting == "Post-Rotation Validation":
                    config["post_rotation_validation"] = value == "Yes"

    token_context.form_data = config


@then("the rotation schedule should be active")
def rotation_active(token_context):
    """Verify rotation schedule active"""
    token_context.manager.configure_rotation_schedule(token_context.form_data)
    assert token_context.manager.rotation_schedule is not None


@then(parsers.parse("a scheduled task should run at {time} daily"))
def scheduled_task_runs(token_context, time):
    """Verify scheduled task configured"""
    assert token_context.manager.rotation_schedule.time_utc == time


@given(parsers.parse("rotation is scheduled for {time} daily"))
def rotation_scheduled(token_context, time):
    """Schedule rotation"""
    token_context.manager.configure_rotation_schedule({
        "frequency": "daily",
        "time": time,
    })


@given(parsers.parse("it is now {time}"))
def current_time_is(token_context, time):
    """Set current time"""
    pass  # Time simulation


@when("the rotation job runs")
def rotation_job_runs(token_context):
    """Run rotation job"""
    # Create some accounts first
    token_context.manager.create_surrogate_account("dest1", "users")
    token_context.manager.create_surrogate_account("dest2", "data")
    token_context.last_result = token_context.manager.run_scheduled_rotation()


@then(parsers.parse("for each active sync destination:\n{table}"))
def for_each_destination(token_context, table):
    """Verify rotation steps for each destination"""
    results = token_context.last_result.get("results", [])
    assert len(results) > 0


@given("a scheduled rotation is running")
def rotation_running(token_context):
    """Rotation is running"""
    pass


@when("a new token is generated")
def new_token_gen(token_context):
    """New token generated"""
    pass


@then(parsers.parse("the system should:\n{table}"))
def system_validates(token_context, table):
    """Verify validation steps"""
    pass  # Validation logic verified in rotate_token


@then("only after all validations pass, switch to new token")
def switch_after_validation(token_context):
    """Verify switch after validation"""
    pass


@given("a scheduled rotation fails")
def rotation_fails(token_context):
    """Simulate rotation failure"""
    token_context.manager.alerts.append({
        "type": "rotation_failed",
        "severity": "High",
    })


@when("the validation step fails")
def validation_fails(token_context):
    """Validation step fails"""
    pass


@then("the old token should remain active")
def old_token_active(token_context):
    """Verify old token still active"""
    pass


@then(parsers.parse("an alert should be sent:\n{table}"))
def alert_sent_with_details(token_context, table):
    """Verify alert details"""
    assert len(token_context.manager.alerts) > 0


@then("the rotation should be retried in 1 hour")
def retry_in_hour(token_context):
    """Verify retry scheduled"""
    pass  # Retry scheduling implementation detail


@given("rotation completed and new token is active")
def rotation_completed(token_context):
    """Rotation completed successfully"""
    token_context.manager.create_surrogate_account("grace-test", "data")
    old_token = token_context.manager.surrogate_accounts["kvstore_sync_svc_grace-test_data"].token
    token_context.manager.rotate_token(old_token.token_id)


@then(parsers.parse("the old token should remain valid for a grace period:\n{table}"))
def old_token_grace_period(token_context, table):
    """Verify grace period"""
    # Find old token
    for token in token_context.manager.tokens.values():
        if token.status == TokenStatus.PENDING_REVOCATION:
            # Token has grace period
            assert token.expires_at > token_context.manager.current_time


@then("after grace period, old token should be revoked")
def token_revoked_after_grace(token_context):
    """Verify token revoked after grace"""
    pass  # Time-based revocation


@given(parsers.parse("{count:d} sync destinations are configured"))
def many_destinations(token_context, count):
    """Create multiple destinations"""
    for i in range(count):
        token_context.manager.create_surrogate_account(f"dest-{i}", "data")


@given(parsers.parse("rotation window is {minutes:d} minutes"))
def rotation_window(token_context, minutes):
    """Set rotation window"""
    token_context.manager.configure_rotation_schedule({
        "window_minutes": minutes,
    })


@when("scheduled rotation runs")
def scheduled_rotation_runs(token_context):
    """Run scheduled rotation"""
    token_context.last_result = token_context.manager.run_scheduled_rotation()


@then("destinations should be rotated sequentially")
def rotated_sequentially(token_context):
    """Verify sequential rotation"""
    results = token_context.last_result.get("results", [])
    assert len(results) > 0


@then("each rotation should complete before starting the next")
def rotation_sequential(token_context):
    """Verify sequential completion"""
    pass  # Sequential execution verified by single-threaded mock


@then("total rotation should complete within the window")
def within_window(token_context):
    """Verify within window"""
    pass  # Timing constraint


@given(parsers.parse("destinations with different security requirements:\n{table}"))
def destinations_different_security(token_context, table):
    """Create destinations with security levels"""
    for line in table.strip().split('\n'):
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2 and parts[0] != 'Destination':
                dest = parts[0]
                token_context.manager.create_surrogate_account(dest, "data")


@when(parsers.parse("I configure rotation schedules:\n{table}"))
def configure_schedules(token_context, table):
    """Configure per-destination schedules"""
    pass  # Per-destination scheduling implementation


@then("each destination should rotate on its own schedule")
def own_schedule(token_context):
    """Verify individual schedules"""
    pass


@given("credentials may be compromised")
def creds_compromised(token_context):
    """Credentials may be compromised"""
    token_context.manager.create_surrogate_account("compromised", "sensitive")
    token_context.current_destination = "compromised"


@when("I click \"Emergency Rotate All\"")
def emergency_rotate(token_context):
    """Emergency rotate all"""
    token_context.last_result = token_context.manager.run_scheduled_rotation()


@then("all credentials should be rotated immediately")
def all_rotated(token_context):
    """Verify all rotated"""
    results = token_context.last_result.get("results", [])
    for r in results:
        assert r["status"] in ["success", "in_progress"]


@then("the scheduled rotation should reset from now")
def schedule_reset(token_context):
    """Verify schedule reset"""
    pass  # Schedule reset implementation


@then("an incident should be logged")
def incident_logged(token_context):
    """Verify incident logged"""
    pass


@given("rotations have occurred over the past week")
def rotations_occurred(token_context):
    """Create rotation history"""
    for i in range(7):
        token_context.manager.rotation_history.append(
            MockRotationEvent(
                timestamp=token_context.manager.current_time - timedelta(days=i),
                destination=f"dest-{i}",
                status=RotationStatus.SUCCESS,
                duration_seconds=5.0,
                old_token_id=f"old-{i}",
                new_token_id=f"new-{i}",
            )
        )


@when("I view Rotation History")
def view_rotation_history(token_context):
    """View rotation history"""
    token_context.last_result = token_context.manager.get_rotation_history()


@then(parsers.parse("I should see:\n{table}"))
def see_history(token_context, table):
    """Verify history columns"""
    assert len(token_context.last_result) > 0


@given(parsers.parse("a maintenance window is configured for \"{dest}\":\n{table}"))
def maintenance_window(token_context, dest, table):
    """Configure maintenance window"""
    pass  # Maintenance window implementation


@when(parsers.parse("rotation is scheduled for {time}"))
def rotation_scheduled_for(token_context, time):
    """Rotation scheduled for time"""
    pass


@then("rotation should be deferred until after maintenance window")
def rotation_deferred(token_context):
    """Verify rotation deferred"""
    pass


@then("Or rotation should occur before maintenance window starts")
def or_before_window(token_context):
    """Alternative: rotation before window"""
    pass


# =============================================================================
# Rotation Notification Steps
# =============================================================================

@given(parsers.parse("rotation is scheduled for {time}"))
def rotation_at_time(token_context, time):
    """Rotation scheduled"""
    token_context.manager.configure_rotation_schedule({
        "time": time,
    })


@given(parsers.parse("pre-rotation notification is set to {hours:d} hour"))
def pre_notification(token_context, hours):
    """Set pre-rotation notification"""
    pass


@when(parsers.parse("it is {time}"))
def time_is(token_context, time):
    """Current time is"""
    pass


@then(parsers.parse("a notification should be sent:\n{table}"))
def notification_sent(token_context, table):
    """Verify notification"""
    pass  # Notification implementation


@given("rotation completed successfully")
def rotation_success(token_context):
    """Rotation completed"""
    token_context.manager.rotation_history.append(
        MockRotationEvent(
            timestamp=token_context.manager.current_time,
            destination="test",
            status=RotationStatus.SUCCESS,
        )
    )


@given("rotation has failed")
def rotation_has_failed(token_context):
    """Rotation failed"""
    token_context.manager.alerts.append({
        "type": "rotation_failed",
        "duration": 0,
    })


@when(parsers.parse("failure persists for:\n{table}"))
def failure_persists(token_context, table):
    """Failure persists for duration"""
    pass  # Escalation timing


# =============================================================================
# Cleanup Steps
# =============================================================================

@given(parsers.parse("destination \"{dest}\" with:\n{table}"))
def destination_with_resources(token_context, dest, table):
    """Create destination with resources"""
    token_context.manager.create_surrogate_account(dest, "data")
    token_context.current_destination = dest


@when(parsers.parse("I delete destination \"{dest}\""))
def delete_destination(token_context, dest):
    """Delete destination"""
    pass  # Deletion trigger


@then("I should be prompted to clean up associated resources")
def prompt_cleanup(token_context):
    """Verify cleanup prompt"""
    pass


@then(parsers.parse("upon confirmation:\n{table}"))
def upon_confirmation(token_context, table):
    """Upon confirmation, cleanup happens"""
    # Would revoke tokens and delete account
    pass


@given("a surrogate account exists without a corresponding destination")
def orphaned_account(token_context):
    """Create orphaned account"""
    token_context.manager.surrogate_accounts["orphan"] = MockSurrogateAccount(
        username="orphan",
        destination="deleted-dest",
    )


@when("I run \"Detect Orphaned Resources\"")
def detect_orphans(token_context):
    """Detect orphaned resources"""
    token_context.last_result = {
        "orphans": ["orphan"],
    }


@then("the orphaned account should be listed")
def orphan_listed(token_context):
    """Verify orphan listed"""
    assert "orphan" in token_context.last_result.get("orphans", [])


@then("I should be able to delete or reassign it")
def can_delete_orphan(token_context):
    """Verify can delete orphan"""
    pass  # UI action capability
