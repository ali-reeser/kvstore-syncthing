# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/onprem_cloud_sync.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:hybrid-sync
@feature:onprem-cloud
Feature: On-Premises to Splunk Cloud Synchronization
  As a Splunk administrator with hybrid infrastructure
  I want to sync KVStore data from on-premises to Splunk Cloud
  So that my cloud searches can use on-prem AD and LDAP data

  Background:
    Given I have an on-premises Splunk deployment
    And I have a Splunk Cloud instance
    And the KVStore Syncthing app is installed on both

  # =============================================================================
  # AD/LDAP Data Sync to Cloud
  # =============================================================================
  @story:ad-ldap-sync
  @priority:critical
  Scenario: Sync AD user data from on-prem to cloud
    Given an on-prem KVStore collection "ad_users" populated via ldapsearch
    And the collection contains Active Directory user data:
      | Field            | Description                    |
      | _key             | sAMAccountName                 |
      | dn               | Distinguished Name             |
      | cn               | Common Name                    |
      | mail             | Email Address                  |
      | memberOf         | Group Memberships (array)      |
      | department       | Department                     |
      | manager          | Manager DN                     |
      | whenCreated      | Account Creation Date          |
      | lastLogonTimestamp | Last Logon Time              |
    When I sync to Splunk Cloud
    Then all AD user records should be available in cloud
    And cloud searches can use the AD data for enrichment

  @story:ad-ldap-sync
  @priority:critical
  Scenario: Incremental AD sync with delta detection
    Given AD data changes frequently
    And I need to minimize sync time
    When I configure incremental sync with:
      | Setting                | Value              |
      | Timestamp Field        | whenChanged        |
      | Sync Interval          | 15 minutes         |
      | Full Sync Schedule     | Daily at 02:00     |
    Then only changed records should be synced
    And full sync should run daily to catch any missed changes

  @story:ad-ldap-sync
  @priority:high
  Scenario: Sync AD group memberships
    Given an on-prem KVStore collection "ad_groups" with group data
    And groups have nested membership
    When I sync to cloud
    Then group hierarchy should be preserved
    And nested group memberships should be flattened optionally

  @story:ad-ldap-sync
  @priority:high
  Scenario: Handle AD data with special characters
    Given AD contains users with special characters in names:
      | sAMAccountName | cn                    |
      | jsmith         | John Smith            |
      | müller         | Hans Müller           |
      | 田中           | 田中太郎              |
      | o'brien        | Patrick O'Brien       |
    When I sync to cloud
    Then all special characters should be preserved
    And lookups should work correctly with these values

  # =============================================================================
  # Splunk Cloud Connectivity
  # =============================================================================
  @story:cloud-connectivity
  @priority:critical
  Scenario: Configure Splunk Cloud destination
    Given I navigate to Configuration > Destinations
    When I create a destination for Splunk Cloud
    Then I should configure:
      | Field              | Value                          |
      | Name               | splunk-cloud-prod              |
      | Type               | Splunk REST API                |
      | Host               | myinstance.splunkcloud.com     |
      | Port               | 8089                           |
      | Use SSL            | true (required)                |
      | Verify SSL         | true                           |
      | Auth Type          | Token                          |
      | Token              | <Splunk Cloud auth token>      |

  @story:cloud-connectivity
  @priority:critical
  Scenario: Handle Splunk Cloud API restrictions
    Given Splunk Cloud has API rate limits
    And certain endpoints may be restricted
    When I sync to cloud
    Then rate limits should be respected
    And restricted operations should fail gracefully
    And alternative methods should be suggested

  @story:cloud-connectivity
  @priority:high
  Scenario: Sync through Splunk Cloud gateway
    Given direct API access is not available
    And I must use the Splunk Cloud gateway
    When I configure the gateway endpoint
    Then sync should route through the gateway
    And authentication should use gateway credentials

  # =============================================================================
  # Heavy Forwarder Deployment (Splunk 10.x)
  # =============================================================================
  @story:hf-deployment
  @priority:critical
  Scenario: Deploy app to Heavy Forwarder via API
    Given a Splunk Heavy Forwarder version 10.x
    And I have admin API credentials
    When I deploy the app using the REST API
    Then the app should be uploaded via /services/apps/local
    And the app should be installed and enabled
    And the HF should not require restart for basic functionality

  @story:hf-deployment
  @priority:high
  Scenario: Configure HF as sync relay
    Given on-prem servers cannot reach Splunk Cloud directly
    And the Heavy Forwarder has cloud connectivity
    When I configure the HF as a relay
    Then on-prem data should sync to HF
    And HF should forward to Splunk Cloud
    And end-to-end integrity should be verified

  @story:hf-deployment
  @priority:high
  Scenario: HF health monitoring
    Given the HF is relaying sync data
    When I check HF health
    Then I should see:
      | Metric                  | Status    |
      | Queue depth             | < 1000    |
      | Sync latency            | < 60s     |
      | Cloud connectivity      | Connected |
      | Last successful sync    | < 5m ago  |

  # =============================================================================
  # Data Sovereignty and Compliance
  # =============================================================================
  @story:compliance
  @priority:high
  Scenario: Filter sensitive data before cloud sync
    Given AD data contains sensitive fields
    And cloud compliance requires data filtering
    When I configure field exclusions:
      | Excluded Field     | Reason                    |
      | userPassword       | Security                  |
      | homeDirectory      | PII                       |
      | telephoneNumber    | PII                       |
      | streetAddress      | PII                       |
    Then excluded fields should not be synced to cloud
    And audit log should record filtered fields

  @story:compliance
  @priority:high
  Scenario: Data residency verification
    Given Splunk Cloud region is "aws-us-east-1"
    When I sync data
    Then the app should verify data goes to correct region
    And alert if data routing appears incorrect

  @story:compliance
  @priority:medium
  Scenario: Audit trail for cross-boundary sync
    Given compliance requires audit of data transfers
    When data syncs from on-prem to cloud
    Then an audit record should be created with:
      | Field              | Value                       |
      | timestamp          | ISO 8601 timestamp          |
      | source             | on-prem-sh01                |
      | destination        | cloud-instance              |
      | collection         | ad_users                    |
      | record_count       | 5000                        |
      | checksum           | sha256 of synced data       |
      | user               | sync_service_account        |

  # =============================================================================
  # Offline/Disconnected Scenarios
  # =============================================================================
  @story:offline-sync
  @priority:high
  Scenario: Queue sync when cloud is unreachable
    Given Splunk Cloud becomes temporarily unreachable
    When sync attempts fail
    Then data should be queued locally
    And queue should persist across restarts
    And sync should resume when connectivity returns

  @story:offline-sync
  @priority:high
  Scenario: Export for manual cloud import
    Given network policy prevents direct on-prem to cloud sync
    When I export for manual transfer
    Then export should create a secure, encrypted package
    And package should include import instructions
    And package should be verifiable on import

  @story:offline-sync
  @priority:medium
  Scenario: Sync via intermediate storage
    Given direct sync is not possible
    And both environments can access shared S3 bucket
    When I configure S3 as intermediate storage
    Then on-prem should export to S3
    And cloud should import from S3
    And sync status should be tracked end-to-end

  # =============================================================================
  # Bidirectional Sync (Cloud to On-Prem)
  # =============================================================================
  @story:bidirectional
  @priority:medium
  Scenario: Sync cloud-only data back to on-prem
    Given some lookups are managed in Splunk Cloud
    And on-prem searches need access to cloud data
    When I configure bidirectional sync
    Then cloud changes should sync to on-prem
    And on-prem changes should sync to cloud
    And conflicts should be resolved based on policy

  @story:bidirectional
  @priority:medium
  Scenario: Conflict resolution for bidirectional sync
    Given the same record is modified in both locations
    When sync runs
    Then conflict should be detected
    And resolution should follow configured policy:
      | Policy           | Behavior                      |
      | cloud_wins       | Cloud version overwrites      |
      | onprem_wins      | On-prem version overwrites    |
      | newest_wins      | Most recent modification wins |
      | manual           | Queue for manual resolution   |
