# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/token_management.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:security
@feature:token-management
Feature: Dynamic Token and Role Management
  As a Splunk administrator
  I want the app to use a master token to create scoped sync tokens
  So that each sync operation has minimal required permissions (RBAC)

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed
    And a master service account token is configured

  # -----------------------------------------------------------------------------
  # User Story: Master Token Configuration
  # -----------------------------------------------------------------------------
  @story:master-token
  @priority:high
  Scenario: Configure master service account token
    Given I navigate to Configuration > Advanced Settings
    When I configure the master token settings:
      | Field                    | Value                          |
      | Master Token             | master-admin-token-xyz         |
      | Token Encryption         | AES-256                        |
      | Auto-Rotate Tokens       | Yes                            |
      | Rotation Interval Days   | 30                             |
    And I click "Save"
    Then the master token should be stored encrypted
    And the token should be validated against the target Splunk

  @story:master-token
  @priority:high
  Scenario: Master token must have user creation capability
    Given a master token without user creation capability
    When I try to save the master token configuration
    Then I should see an error "Master token requires 'edit_user' capability"
    And the configuration should not be saved

  @story:master-token
  @priority:medium
  Scenario: Validate master token on configuration
    Given I enter a master token
    When I click "Validate Token"
    Then the system should verify the token has required capabilities:
      | Capability          | Required |
      | edit_user           | Yes      |
      | edit_roles_grantable| Yes      |
      | edit_tokens         | Yes      |
      | list_storage_passwords | Yes   |

  # -----------------------------------------------------------------------------
  # User Story: Dynamic Role Creation
  # -----------------------------------------------------------------------------
  @story:dynamic-roles
  @priority:high
  Scenario: Create scoped role for KVStore sync
    Given a destination "cloud-prod" is configured
    And a collection mapping for "users" collection exists
    When I enable dynamic role creation for this destination
    Then a role "kvstore_sync_users_role" should be created on target with:
      | Permission          | Scope                    |
      | write               | kvstore:users            |
      | read                | kvstore:users            |
      | list                | kvstore:users            |

  @story:dynamic-roles
  @priority:high
  Scenario: Role permissions are collection-specific
    Given collection mappings for:
      | Collection |
      | users      |
      | groups     |
      | assets     |
    When dynamic roles are created
    Then each collection should have its own role:
      | Role Name                   | KVStore Access        |
      | kvstore_sync_users_role     | users only            |
      | kvstore_sync_groups_role    | groups only           |
      | kvstore_sync_assets_role    | assets only           |

  @story:dynamic-roles
  @priority:medium
  Scenario: Create combined role for multiple collections
    Given a sync job syncs collections "users,groups,permissions"
    When I enable "Combined Role" for the job
    Then a single role "kvstore_sync_job_daily_role" should be created
    And the role should have access to all three collections
    And the role should have no access to other collections

  @story:dynamic-roles
  @priority:medium
  Scenario: Role includes read-only access for verification
    Given a dynamic role is created for sync
    Then the role should include:
      | Permission | Purpose                        |
      | write      | Sync records to destination    |
      | read       | Verify synced records          |
      | delete     | Remove orphaned records        |
      | list       | Enumerate records for sync     |
    And the role should NOT include:
      | Permission    | Reason                        |
      | admin         | Not needed for sync           |
      | edit_roles    | Privilege escalation risk     |

  # -----------------------------------------------------------------------------
  # User Story: Surrogate Account Creation
  # -----------------------------------------------------------------------------
  @story:surrogate-accounts
  @priority:high
  Scenario: Create surrogate user account for sync
    Given a destination "cloud-prod" is configured
    When I enable surrogate account for this destination
    Then a user "kvstore_sync_svc_cloud_prod" should be created
    And the user should be assigned the dynamic sync role
    And a token should be generated for the user

  @story:surrogate-accounts
  @priority:high
  Scenario: Surrogate account has minimal permissions
    Given a surrogate account is created for collection "users"
    Then the account should only be able to:
      | Action                        | Allowed |
      | Read from kvstore:users       | Yes     |
      | Write to kvstore:users        | Yes     |
      | Delete from kvstore:users     | Yes     |
      | Read from kvstore:other       | No      |
      | Access Splunk Web             | No      |
      | Run searches                  | No      |
      | Modify system settings        | No      |

  @story:surrogate-accounts
  @priority:medium
  Scenario: Surrogate account naming convention
    Given I create surrogate accounts for multiple destinations:
      | Destination | Collection |
      | cloud-prod  | users      |
      | dr-site     | users      |
      | backup      | assets     |
    Then accounts should be named:
      | Account Name                        |
      | kvstore_sync_svc_cloud_prod_users   |
      | kvstore_sync_svc_dr_site_users      |
      | kvstore_sync_svc_backup_assets      |

  # -----------------------------------------------------------------------------
  # User Story: Token Generation
  # -----------------------------------------------------------------------------
  @story:token-generation
  @priority:high
  Scenario: Generate scoped token for surrogate account
    Given a surrogate account "kvstore_sync_svc_prod" exists
    When I generate a sync token
    Then a token should be created with:
      | Property       | Value                               |
      | Audience       | kvstore_syncthing                   |
      | Claims         | collection:users, action:sync       |
      | Expiration     | 24 hours                            |
      | Not Before     | Now                                 |

  @story:token-generation
  @priority:high
  Scenario: Token is automatically rotated before expiry
    Given a sync token expiring in 2 hours
    And auto-rotation is enabled with 4-hour pre-expiry threshold
    When the rotation check runs
    Then a new token should be generated
    And the old token should be scheduled for revocation
    And sync jobs should use the new token

  @story:token-generation
  @priority:medium
  Scenario: Token per sync job
    Given two sync jobs:
      | Job Name      | Collections       |
      | user-sync     | users             |
      | asset-sync    | assets            |
    When tokens are generated
    Then each job should have its own token
    And tokens should be isolated (user-sync token can't access assets)

  @story:token-generation
  @priority:medium
  Scenario: Emergency token revocation
    Given a sync token may be compromised
    When I click "Revoke All Tokens" for a destination
    Then all tokens for that destination should be immediately revoked
    And new tokens should be generated
    And sync jobs should be updated with new tokens
    And an alert should be sent to administrators

  # -----------------------------------------------------------------------------
  # User Story: RBAC Enforcement
  # -----------------------------------------------------------------------------
  @story:rbac-enforcement
  @priority:high
  Scenario: Sync fails if token lacks permission
    Given a sync token without write permission to "users" collection
    When a sync job tries to write to "users"
    Then the sync should fail with "Permission denied"
    And the error should indicate the missing capability

  @story:rbac-enforcement
  @priority:high
  Scenario: Token cannot escalate privileges
    Given a surrogate account with sync-only permissions
    When the account tries to:
      | Action                        | Expected Result |
      | Create another user           | Denied          |
      | Modify its own role           | Denied          |
      | Access other collections      | Denied          |
      | Run arbitrary searches        | Denied          |
    Then all privilege escalation attempts should fail
    And attempts should be logged to audit

  @story:rbac-enforcement
  @priority:medium
  Scenario: Audit trail for token usage
    Given a sync token is used
    When the sync operation completes
    Then an audit entry should be created with:
      | Field              | Value                          |
      | token_id           | <token identifier>             |
      | surrogate_user     | kvstore_sync_svc_prod          |
      | operation          | kvstore_write                  |
      | collection         | users                          |
      | records_affected   | 150                            |
      | source_ip          | 10.0.1.50                      |

  # -----------------------------------------------------------------------------
  # User Story: Token Lifecycle Management
  # -----------------------------------------------------------------------------
  @story:token-lifecycle
  @priority:medium
  Scenario: View all active sync tokens
    Given multiple sync destinations with tokens
    When I navigate to Configuration > Token Management
    Then I should see a list of all active tokens:
      | Token ID    | Destination  | Surrogate User    | Expires     | Last Used   |
      | tok-001     | cloud-prod   | svc_cloud_prod    | 2026-02-04  | 5 min ago   |
      | tok-002     | dr-site      | svc_dr_site       | 2026-02-04  | 1 hour ago  |

  @story:token-lifecycle
  @priority:medium
  Scenario: Manually rotate a token
    Given a token "tok-001" for destination "cloud-prod"
    When I click "Rotate" for token "tok-001"
    Then a new token should be generated
    And the old token should be invalidated
    And sync jobs should automatically use the new token

  @story:token-lifecycle
  @priority:low
  Scenario: Token expiration warning
    Given a token expiring in less than 24 hours
    And auto-rotation is disabled
    When I view the Token Management page
    Then the token should be highlighted with a warning
    And a notification should be shown

  # -----------------------------------------------------------------------------
  # User Story: Destination-Specific Token Policies
  # -----------------------------------------------------------------------------
  @story:token-policies
  @priority:medium
  Scenario: Configure token policy per destination
    Given I am configuring destination "production-cloud"
    When I configure token policy:
      | Setting                | Value           |
      | Token Lifetime         | 12 hours        |
      | Auto-Rotate            | Yes             |
      | Rotate Before Expiry   | 2 hours         |
      | Require MFA            | No              |
      | IP Allowlist           | 10.0.0.0/8      |
    Then the policy should be saved for this destination
    And all tokens for this destination should follow this policy

  @story:token-policies
  @priority:low
  Scenario: Different policies for different environments
    Given destinations:
      | Destination    | Environment |
      | cloud-prod     | Production  |
      | cloud-dev      | Development |
    When I configure policies:
      | Destination    | Token Lifetime | IP Restriction |
      | cloud-prod     | 4 hours        | Yes            |
      | cloud-dev      | 24 hours       | No             |
    Then production should have stricter token policies

  # -----------------------------------------------------------------------------
  # User Story: Scheduled Credential Rotation
  # -----------------------------------------------------------------------------
  @story:scheduled-rotation
  @priority:high
  Scenario: Configure scheduled credential rotation
    Given I navigate to Configuration > Token Management > Rotation Schedule
    When I configure rotation schedule:
      | Setting                  | Value                          |
      | Rotation Frequency       | Daily                          |
      | Rotation Time            | 02:00 UTC                      |
      | Rotation Window          | 30 minutes                     |
      | Pre-Rotation Buffer      | 4 hours                        |
      | Post-Rotation Validation | Yes                            |
    And I click "Save"
    Then the rotation schedule should be active
    And a scheduled task should run at 02:00 UTC daily

  @story:scheduled-rotation
  @priority:high
  Scenario: Automatic daily credential rotation
    Given rotation is scheduled for 02:00 UTC daily
    And it is now 02:00 UTC
    When the rotation job runs
    Then for each active sync destination:
      | Step | Action                                           |
      | 1    | Generate new token for surrogate account         |
      | 2    | Validate new token works                         |
      | 3    | Update sync job configuration with new token     |
      | 4    | Mark old token for deferred revocation           |
      | 5    | Log rotation event to audit                      |

  @story:scheduled-rotation
  @priority:high
  Scenario: Rotation validates new credentials before switching
    Given a scheduled rotation is running
    When a new token is generated
    Then the system should:
      | Validation Step                     | Fail Action            |
      | Test connection with new token      | Abort rotation         |
      | Verify KVStore read access          | Abort rotation         |
      | Verify KVStore write access         | Abort rotation         |
    And only after all validations pass, switch to new token

  @story:scheduled-rotation
  @priority:high
  Scenario: Rotation failure triggers alert
    Given a scheduled rotation fails
    When the validation step fails
    Then the old token should remain active
    And an alert should be sent:
      | Alert Field     | Value                                    |
      | Severity        | High                                     |
      | Subject         | Credential Rotation Failed               |
      | Details         | Destination, error message, timestamp    |
    And the rotation should be retried in 1 hour

  @story:scheduled-rotation
  @priority:medium
  Scenario: Grace period for old credentials
    Given rotation completed and new token is active
    Then the old token should remain valid for a grace period:
      | Grace Period   | Purpose                                  |
      | 30 minutes     | Allow in-flight operations to complete   |
    And after grace period, old token should be revoked

  @story:scheduled-rotation
  @priority:medium
  Scenario: Staggered rotation for multiple destinations
    Given 10 sync destinations are configured
    And rotation window is 30 minutes
    When scheduled rotation runs
    Then destinations should be rotated sequentially
    And each rotation should complete before starting the next
    And total rotation should complete within the window

  @story:scheduled-rotation
  @priority:medium
  Scenario: Configure rotation schedule per destination
    Given destinations with different security requirements:
      | Destination    | Sensitivity |
      | prod-finance   | High        |
      | prod-hr        | High        |
      | dev-test       | Low         |
    When I configure rotation schedules:
      | Destination    | Frequency   | Time      |
      | prod-finance   | Every 4hrs  | *:00      |
      | prod-hr        | Every 4hrs  | *:15      |
      | dev-test       | Weekly      | Sun 03:00 |
    Then each destination should rotate on its own schedule

  @story:scheduled-rotation
  @priority:medium
  Scenario: Emergency rotation outside schedule
    Given credentials may be compromised
    When I click "Emergency Rotate All"
    Then all credentials should be rotated immediately
    And the scheduled rotation should reset from now
    And an incident should be logged

  @story:scheduled-rotation
  @priority:low
  Scenario: View rotation history
    Given rotations have occurred over the past week
    When I view Rotation History
    Then I should see:
      | Column         | Content                          |
      | Timestamp      | When rotation occurred           |
      | Destination    | Which destination                |
      | Status         | Success/Failed                   |
      | Duration       | How long rotation took           |
      | Old Token ID   | Token that was replaced          |
      | New Token ID   | Token that is now active         |

  @story:scheduled-rotation
  @priority:low
  Scenario: Rotation respects maintenance windows
    Given a maintenance window is configured for "prod-cloud":
      | Window Start | Window End |
      | Sat 22:00    | Sun 06:00  |
    When rotation is scheduled for Sun 02:00
    Then rotation should be deferred until after maintenance window
    Or rotation should occur before maintenance window starts

  # -----------------------------------------------------------------------------
  # User Story: Credential Rotation Notifications
  # -----------------------------------------------------------------------------
  @story:rotation-notifications
  @priority:medium
  Scenario: Notify before scheduled rotation
    Given rotation is scheduled for 02:00 UTC
    And pre-rotation notification is set to 1 hour
    When it is 01:00 UTC
    Then a notification should be sent:
      | Channel        | Message                                  |
      | Slack          | "Credential rotation starting in 1 hour" |
      | Email          | Rotation details and affected systems    |

  @story:rotation-notifications
  @priority:medium
  Scenario: Notify after successful rotation
    Given rotation completed successfully
    Then a notification should be sent:
      | Field          | Content                          |
      | Status         | Success                          |
      | Destinations   | List of rotated destinations     |
      | Duration       | Total rotation time              |
      | Next Rotation  | Scheduled time                   |

  @story:rotation-notifications
  @priority:high
  Scenario: Escalating alerts for rotation failures
    Given rotation has failed
    When failure persists for:
      | Duration    | Alert Action                           |
      | 0 minutes   | Send warning to ops channel            |
      | 30 minutes  | Send alert to on-call                  |
      | 1 hour      | Page security team                     |
      | 4 hours     | Escalate to management                 |

  # -----------------------------------------------------------------------------
  # User Story: Cleanup and Deprovisioning
  # -----------------------------------------------------------------------------
  @story:cleanup
  @priority:medium
  Scenario: Delete destination removes associated tokens and accounts
    Given destination "old-cloud" with:
      | Associated Item          |
      | Surrogate account        |
      | Dynamic role             |
      | Active tokens            |
    When I delete destination "old-cloud"
    Then I should be prompted to clean up associated resources
    And upon confirmation:
      | Resource         | Action    |
      | Tokens           | Revoked   |
      | Surrogate user   | Deleted   |
      | Dynamic role     | Deleted   |

  @story:cleanup
  @priority:low
  Scenario: Orphaned resources detection
    Given a surrogate account exists without a corresponding destination
    When I run "Detect Orphaned Resources"
    Then the orphaned account should be listed
    And I should be able to delete or reassign it
