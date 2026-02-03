# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/data_integrity.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:data-integrity
@feature:integrity-verification
Feature: Data Integrity and Verification
  As a Splunk administrator
  I want to verify data integrity across all sync targets
  So that I can ensure all records have been correctly replicated

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed
    And multiple sync destinations are configured

  # -----------------------------------------------------------------------------
  # User Story: Finger Probe (Quick Status Check)
  # -----------------------------------------------------------------------------
  @story:finger-probe
  @priority:high
  Scenario: Execute finger probe on a destination
    Given a destination "cloud-prod" with synced collection "users"
    When I run a finger probe on destination "cloud-prod" for collection "users"
    Then I should receive a response within 30 seconds
    And the response should include:
      | Field           | Description                    |
      | status          | ok, mismatch, or error         |
      | response_time   | probe latency in milliseconds  |
      | record_count    | number of records              |
      | checksum        | collection-level hash          |
      | server_info     | destination server details     |

  @story:finger-probe
  @priority:high
  Scenario: Finger probe detects healthy destination
    Given a source collection "assets" with 1000 records
    And destination "backup-site" has matching 1000 records
    When I run a finger probe
    Then the status should be "ok"
    And the record counts should match
    And the checksums should match

  @story:finger-probe
  @priority:high
  Scenario: Finger probe detects record count mismatch
    Given a source collection "assets" with 1000 records
    And destination "backup-site" has only 950 records
    When I run a finger probe
    Then the status should be "mismatch"
    And the response should indicate "Record count differs: source=1000, dest=950"

  @story:finger-probe
  @priority:high
  Scenario: Finger probe detects checksum mismatch
    Given source and destination have same record count
    But some records have different values
    When I run a finger probe
    Then the status should be "mismatch"
    And the response should indicate checksum difference

  @story:finger-probe
  @priority:medium
  Scenario: Finger probe handles unreachable destination
    Given a destination "offline-site" that is not reachable
    When I run a finger probe
    Then the status should be "error"
    And the error message should indicate connection failure
    And the response time should reflect the timeout

  # -----------------------------------------------------------------------------
  # User Story: Record Checksums
  # -----------------------------------------------------------------------------
  @story:checksums
  @priority:high
  Scenario: Compute SHA-256 checksum for a record
    Given a record with data:
      """
      {
        "_key": "user-001",
        "name": "John Doe",
        "email": "john@example.com",
        "department": "Engineering"
      }
      """
    When I compute the checksum
    Then the checksum should be a 64-character hexadecimal string
    And the checksum should be deterministic (same input = same output)
    And the checksum should exclude internal fields (_user, _raw)

  @story:checksums
  @priority:high
  Scenario: Checksum detects any field change
    Given two records that differ only in the "status" field:
      | Record | status   |
      | A      | active   |
      | B      | inactive |
    When I compute checksums for both records
    Then the checksums should be different

  @story:checksums
  @priority:medium
  Scenario: Checksum is order-independent
    Given two records with same fields in different order:
      """
      Record A: {"name": "Test", "value": 123}
      Record B: {"value": 123, "name": "Test"}
      """
    When I compute checksums for both records
    Then the checksums should be identical

  # -----------------------------------------------------------------------------
  # User Story: Merkle Tree for Collections
  # -----------------------------------------------------------------------------
  @story:merkle-tree
  @priority:high
  Scenario: Compute Merkle root for a collection
    Given a collection with records:
      | _key  | name    |
      | rec-1 | Alpha   |
      | rec-2 | Beta    |
      | rec-3 | Gamma   |
      | rec-4 | Delta   |
    When I compute the collection fingerprint
    Then a Merkle tree should be built from record checksums
    And the Merkle root should be a 64-character hash
    And the fingerprint should include:
      | Field        | Value           |
      | record_count | 4               |
      | merkle_root  | <calculated>    |
      | total_bytes  | <calculated>    |

  @story:merkle-tree
  @priority:high
  Scenario: Merkle root changes when any record changes
    Given a collection fingerprint with Merkle root "abc123..."
    When one record in the collection is modified
    And I recompute the fingerprint
    Then the Merkle root should be different from "abc123..."

  @story:merkle-tree
  @priority:medium
  Scenario: Merkle tree enables efficient difference detection
    Given a source Merkle tree with 10,000 records
    And a destination Merkle tree with 10,000 records
    And only 5 records differ
    When I compare the Merkle trees
    Then I should identify the 5 differing records
    # Without comparing all 10,000 record checksums individually

  # -----------------------------------------------------------------------------
  # User Story: Parity Verification
  # -----------------------------------------------------------------------------
  @story:parity
  @priority:high
  Scenario: Generate parity blocks for a collection
    Given a collection with 1000 records
    And parity block size of 100 records
    When I generate parity blocks
    Then 10 parity blocks should be created
    And each block should have an XOR-based checksum
    And the parity data should be stored for later verification

  @story:parity
  @priority:high
  Scenario: Verify parity blocks detect corruption
    Given stored parity blocks for collection "assets"
    And one record in block 5 has been corrupted
    When I run parity verification
    Then blocks 1-4 and 6-10 should pass verification
    And block 5 should fail verification
    And the report should indicate which block failed

  @story:parity
  @priority:medium
  Scenario: Parity verification across all destinations
    Given parity blocks stored for source collection
    And 3 sync destinations
    When I run parity verification on all destinations
    Then each destination should be checked against source parity
    And the report should show per-destination results

  # -----------------------------------------------------------------------------
  # User Story: Full Integrity Report
  # -----------------------------------------------------------------------------
  @story:integrity-report
  @priority:high
  Scenario: Generate comprehensive integrity report
    Given a source collection "users" with 5000 records
    And destinations:
      | Name        | Records | Status    |
      | cloud-prod  | 5000    | in-sync   |
      | backup-site | 4998    | 2 missing |
      | dr-site     | 5000    | 1 mismatch|
    When I generate an integrity report
    Then the report should include:
      | Section              | Content                           |
      | Source Fingerprint   | record_count, merkle_root         |
      | Destination Results  | finger probe for each destination |
      | Missing Keys         | keys missing from each destination|
      | Extra Keys           | keys extra on each destination    |
      | Mismatched Keys      | keys with different values        |
      | Parity Check         | overall parity status             |
      | Overall Status       | ok, mismatch, or error            |

  @story:integrity-report
  @priority:high
  Scenario: Identify specific mismatched records
    Given source record {_key: "user-500", name: "Alice", status: "active"}
    And destination record {_key: "user-500", name: "Alice", status: "inactive"}
    When I generate an integrity report
    Then "user-500" should appear in the mismatched keys list
    And I should be able to view both versions for comparison

  @story:integrity-report
  @priority:medium
  Scenario: Identify missing records
    Given source has record with key "user-999"
    And destination is missing record "user-999"
    When I generate an integrity report
    Then "user-999" should appear in the missing keys list
    And the report should indicate which destination is missing it

  @story:integrity-report
  @priority:medium
  Scenario: Identify extra records (orphans)
    Given destination has record "old-user-001" not in source
    When I generate an integrity report
    Then "old-user-001" should appear in the extra keys list
    And the report should indicate which destination has the extra record

  # -----------------------------------------------------------------------------
  # User Story: Reconciliation
  # -----------------------------------------------------------------------------
  @story:reconciliation
  @priority:high
  Scenario: Reconcile missing records
    Given an integrity report showing 10 missing records on "backup-site"
    When I click "Reconcile" for the missing records
    Then the 10 missing records should be copied to "backup-site"
    And a new integrity check should show 0 missing records

  @story:reconciliation
  @priority:high
  Scenario: Reconcile mismatched records
    Given an integrity report showing 5 mismatched records
    When I select records and click "Reconcile from Source"
    Then the destination records should be updated to match source
    And a new integrity check should show 0 mismatched records

  @story:reconciliation
  @priority:medium
  Scenario: Preview reconciliation before executing
    Given an integrity report with discrepancies
    When I click "Preview Reconciliation"
    Then I should see a list of changes that would be made
    And I should be able to approve or cancel the reconciliation

  @story:reconciliation
  @priority:low
  Scenario: Reconcile with dry run
    Given mismatched records exist
    When I run reconciliation with dry run enabled
    Then no actual changes should be made
    And the result should show what would have been reconciled

  # -----------------------------------------------------------------------------
  # User Story: Data Trail Dashboard
  # -----------------------------------------------------------------------------
  @story:data-trail
  @priority:high
  Scenario: View data trail visualization
    Given a source collection and 3 destinations
    When I open the Integrity Dashboard
    Then I should see a visual flow diagram showing:
      | Element      | Content                              |
      | Source       | Record count, Merkle root preview    |
      | Arrows       | Sync direction indicators            |
      | Destinations | Status icon, record count, checksum  |

  @story:data-trail
  @priority:high
  Scenario: Dashboard shows real-time sync status
    Given the Integrity Dashboard is open
    And auto-refresh is enabled
    When a sync job completes
    Then the dashboard should update automatically
    And destination statuses should reflect new data

  @story:data-trail
  @priority:medium
  Scenario: Dashboard highlights integrity issues
    Given one destination has mismatched records
    When I view the Integrity Dashboard
    Then that destination should be highlighted in red/warning
    And clicking it should show details of the mismatches

  # -----------------------------------------------------------------------------
  # User Story: Drift Detection
  # -----------------------------------------------------------------------------
  @story:drift-detection
  @priority:medium
  Scenario: Detect gradual drift over time
    Given integrity checks are scheduled hourly
    And historical integrity data is stored
    When drift is detected (increasing mismatches over time)
    Then an alert should be generated
    And the dashboard should show drift trend

  @story:drift-detection
  @priority:low
  Scenario: Alert on sudden integrity change
    Given the last integrity check showed 0 issues
    And the current check shows 100+ mismatches
    When the integrity check completes
    Then a critical alert should be sent
    And the change should be flagged for investigation
