# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/sync_profiles.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:configuration
@feature:sync-profiles
Feature: Sync Profile Management
  As a Splunk administrator
  I want to configure different sync profiles
  So that I can control how data is synchronized for different use cases

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed

  # -----------------------------------------------------------------------------
  # User Story: Full Sync Profile
  # -----------------------------------------------------------------------------
  @story:full-sync
  @priority:high
  Scenario: Create a full sync profile
    Given I navigate to Configuration > Sync Profiles
    When I click "Add Sync Profile"
    And I fill in the following profile details:
      | Field               | Value                          |
      | Name                | full-replace-profile           |
      | Sync Mode           | Full Sync (Replace All)        |
      | Conflict Resolution | Source Wins                    |
      | Batch Size          | 1000                           |
      | Delete Orphans      | Yes                            |
    And I click "Save"
    Then the profile "full-replace-profile" should appear in the profiles list
    And a help tooltip should explain that full sync replaces all destination records

  @story:full-sync
  @priority:high
  Scenario: Full sync replaces all records in destination
    Given a sync profile "full-replace" with mode "Full Sync"
    And a source collection "users" with 100 records
    And a destination collection "users" with 50 different records
    When I run a sync using profile "full-replace"
    Then the destination should have exactly 100 records
    And all destination records should match the source records
    And the sync result should show 100 records written

  # -----------------------------------------------------------------------------
  # User Story: Incremental Sync Profile
  # -----------------------------------------------------------------------------
  @story:incremental-sync
  @priority:high
  Scenario: Create an incremental sync profile
    Given I navigate to Configuration > Sync Profiles
    When I click "Add Sync Profile"
    And I fill in the following profile details:
      | Field               | Value                          |
      | Name                | incremental-profile            |
      | Sync Mode           | Incremental                    |
      | Conflict Resolution | Newest Wins                    |
      | Timestamp Field     | _updated                       |
      | Batch Size          | 500                            |
    And I click "Save"
    Then the profile "incremental-profile" should appear in the profiles list

  @story:incremental-sync
  @priority:high
  Scenario: Incremental sync only transfers changed records
    Given a sync profile "incremental" with mode "Incremental"
    And a source collection "assets" with 1000 records
    And a destination collection "assets" with 1000 matching records
    And 10 records in the source have been modified since last sync
    When I run a sync using profile "incremental"
    Then only 10 records should be transferred
    And the sync result should show 10 records written
    And the sync result should show 990 records skipped

  @story:incremental-sync
  @priority:medium
  Scenario: Incremental sync detects changes by checksum
    Given a sync profile "incremental-checksum" with mode "Incremental"
    And a source record with key "asset-001" and data {"name": "Server A", "status": "active"}
    And a destination record with key "asset-001" and data {"name": "Server A", "status": "inactive"}
    When I run a sync using profile "incremental-checksum"
    Then the destination record should be updated to {"name": "Server A", "status": "active"}

  # -----------------------------------------------------------------------------
  # User Story: Append Only Sync Profile
  # -----------------------------------------------------------------------------
  @story:append-sync
  @priority:medium
  Scenario: Create an append-only sync profile
    Given I navigate to Configuration > Sync Profiles
    When I click "Add Sync Profile"
    And I fill in the following profile details:
      | Field               | Value                          |
      | Name                | audit-log-profile              |
      | Sync Mode           | Append Only                    |
      | Preserve Key        | Yes                            |
    And I click "Save"
    Then the profile "audit-log-profile" should appear in the profiles list

  @story:append-sync
  @priority:medium
  Scenario: Append only sync never updates existing records
    Given a sync profile "append-only" with mode "Append Only"
    And a source collection "audit_events" with records:
      | _key  | event_type | timestamp  |
      | evt-1 | login      | 1000000001 |
      | evt-2 | logout     | 1000000002 |
      | evt-3 | access     | 1000000003 |
    And a destination collection "audit_events" with records:
      | _key  | event_type | timestamp  |
      | evt-1 | login-old  | 1000000000 |
    When I run a sync using profile "append-only"
    Then the destination should have 3 records
    And record "evt-1" should still have event_type "login-old"
    And records "evt-2" and "evt-3" should be added

  @story:append-sync
  @priority:medium
  Scenario: Append only sync never deletes records
    Given a sync profile "append-only" with mode "Append Only" and "Delete Orphans" disabled
    And a source collection with 5 records
    And a destination collection with 10 records including 5 not in source
    When I run a sync using profile "append-only"
    Then the destination should still have all 10 records

  # -----------------------------------------------------------------------------
  # User Story: Master/Slave Sync Profile
  # -----------------------------------------------------------------------------
  @story:master-slave
  @priority:high
  Scenario: Create a master/slave sync profile
    Given I navigate to Configuration > Sync Profiles
    When I click "Add Sync Profile"
    And I fill in the following profile details:
      | Field               | Value                          |
      | Name                | ldap-master-slave              |
      | Sync Mode           | Master/Slave                   |
      | Conflict Resolution | Source Wins                    |
      | Delete Orphans      | Yes                            |
    And I click "Save"
    Then the profile should enforce source as authoritative
    And the help text should warn about destination data being overwritten

  @story:master-slave
  @priority:high
  Scenario: Master/slave sync makes destination match source exactly
    Given a sync profile "master-slave" with mode "Master/Slave"
    And a source collection "ad_users" with 500 records from LDAP
    And a destination collection "ad_users" with 600 records including local additions
    When I run a sync using profile "master-slave"
    Then the destination should have exactly 500 records
    And the destination records should exactly match the source
    And 100 orphaned records should be deleted

  # -----------------------------------------------------------------------------
  # User Story: Conflict Resolution
  # -----------------------------------------------------------------------------
  @story:conflict-resolution
  @priority:high
  Scenario Outline: Configure conflict resolution strategy
    Given I create a sync profile with conflict resolution "<strategy>"
    And a source record {key: "rec-1", value: "source-value", _updated: <source_time>}
    And a destination record {key: "rec-1", value: "dest-value", _updated: <dest_time>}
    When I run the sync
    Then the destination record value should be "<expected_value>"

    Examples:
      | strategy         | source_time | dest_time | expected_value |
      | Source Wins      | 1000        | 2000      | source-value   |
      | Destination Wins | 1000        | 2000      | dest-value     |
      | Newest Wins      | 2000        | 1000      | source-value   |
      | Newest Wins      | 1000        | 2000      | dest-value     |

  @story:conflict-resolution
  @priority:medium
  Scenario: Merge conflict resolution combines fields
    Given a sync profile with conflict resolution "Merge"
    And a source record {key: "rec-1", name: "Source Name", status: "active"}
    And a destination record {key: "rec-1", name: "Dest Name", location: "NYC"}
    When I run the sync
    Then the destination record should be {key: "rec-1", name: "Source Name", status: "active", location: "NYC"}

  @story:conflict-resolution
  @priority:medium
  Scenario: Manual conflict resolution queues conflicts for review
    Given a sync profile with conflict resolution "Manual Review"
    And a source record that conflicts with a destination record
    When I run the sync
    Then the record should not be synced
    And a conflict should be queued for manual review
    And the conflict should appear in the Sync Status dashboard

  # -----------------------------------------------------------------------------
  # User Story: Field Transformations
  # -----------------------------------------------------------------------------
  @story:field-mapping
  @priority:medium
  Scenario: Configure field mappings
    Given I create a sync profile with field mappings:
      | Source Field | Destination Field |
      | user_name    | username          |
      | mail         | email             |
      | dept         | department        |
    And a source record {user_name: "jdoe", mail: "jdoe@example.com", dept: "IT"}
    When I run the sync
    Then the destination record should have fields {username: "jdoe", email: "jdoe@example.com", department: "IT"}

  @story:field-mapping
  @priority:medium
  Scenario: Exclude fields from sync
    Given I create a sync profile with excluded fields "_user,_raw,internal_id"
    And a source record {_key: "rec-1", name: "Test", _user: "admin", internal_id: "12345"}
    When I run the sync
    Then the destination record should not have fields "_user" or "internal_id"
    And the destination record should have fields "_key" and "name"

  @story:field-mapping
  @priority:low
  Scenario: Filter records with query
    Given I create a sync profile with filter query {"status": "active"}
    And source records:
      | _key  | name    | status   |
      | rec-1 | Active1 | active   |
      | rec-2 | Inactive| inactive |
      | rec-3 | Active2 | active   |
    When I run the sync
    Then only records "rec-1" and "rec-3" should be synced
    And record "rec-2" should be skipped

  # -----------------------------------------------------------------------------
  # User Story: Batch Configuration
  # -----------------------------------------------------------------------------
  @story:batching
  @priority:medium
  Scenario Outline: Configure batch size for performance
    Given I create a sync profile with batch size <batch_size>
    And a source collection with 10000 records
    When I run the sync
    Then records should be processed in batches of <batch_size>
    And approximately <expected_batches> batches should be processed

    Examples:
      | batch_size | expected_batches |
      | 100        | 100              |
      | 1000       | 10               |
      | 5000       | 2                |

  @story:batching
  @priority:low
  Scenario: Checkpoint saved after each batch
    Given I create a sync profile with batch size 100
    And a source collection with 500 records
    When I run the sync
    Then a checkpoint should be saved after each batch
    And if the sync fails at batch 3, it should resume from batch 3
