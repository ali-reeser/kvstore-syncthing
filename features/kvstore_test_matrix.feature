# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/kvstore_test_matrix.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:testing
@feature:kvstore-matrix
Feature: KVStore Test Matrix
  As a QA engineer
  I want comprehensive test coverage for all KVStore configurations
  So that I can ensure sync works correctly across all edge cases

  Background:
    Given a test Splunk instance is available
    And the KVStore Syncthing app is installed
    And test fixtures can be generated dynamically

  # -----------------------------------------------------------------------------
  # User Story: Lookup Definition Types
  # -----------------------------------------------------------------------------
  @story:lookup-definitions
  @priority:critical
  Scenario Outline: Sync KVStore with different lookup definitions
    Given a source KVStore collection "<collection>" exists
    And the collection has lookup definition type "<lookup_type>"
    And the collection contains <record_count> records
    When I sync to destination
    Then all records should be synced correctly
    And the lookup definition should be preserved

    Examples:
      | collection     | lookup_type        | record_count |
      | users          | kvstore            | 1000         |
      | assets         | kvstore            | 5000         |
      | ip_intel       | kvstore_external   | 10000        |
      | geo_data       | kvstore_transform  | 50000        |

  @story:lookup-definitions
  @priority:high
  Scenario: Sync collection with field aliases
    Given a KVStore collection with field aliases:
      | Original Field | Alias          |
      | user_name      | username       |
      | ip_address     | src_ip         |
      | dest_address   | dest_ip        |
    When I sync to destination
    Then field aliases should be preserved in transforms.conf
    And lookups using aliases should work correctly

  # -----------------------------------------------------------------------------
  # User Story: Accelerated Lookups
  # -----------------------------------------------------------------------------
  @story:accelerations
  @priority:critical
  Scenario: Sync accelerated KVStore lookup
    Given a KVStore collection with acceleration enabled
    And acceleration is configured on fields:
      | Field      | Acceleration Type |
      | _key       | primary           |
      | user_id    | index             |
      | timestamp  | index             |
    When I sync to destination
    Then acceleration settings should be synced
    And destination should rebuild acceleration after sync

  @story:accelerations
  @priority:high
  Scenario: Large accelerated collection sync
    Given an accelerated collection with 1,000,000 records
    When I sync to destination
    Then sync should complete within acceptable time
    And acceleration should be disabled during bulk load
    And acceleration should be re-enabled after sync completes

  @story:accelerations
  @priority:medium
  Scenario: Sync during acceleration rebuild
    Given destination is rebuilding acceleration
    When a sync operation starts
    Then sync should wait for rebuild to complete
    Or sync should proceed with warning about degraded performance

  # -----------------------------------------------------------------------------
  # User Story: Wildcard Matching
  # -----------------------------------------------------------------------------
  @story:wildcard-matching
  @priority:critical
  Scenario: KVStore with wildcard field matching
    Given a KVStore collection configured for wildcard matching
    And the collection contains patterns:
      | Pattern         | Match Type |
      | 192.168.*       | prefix     |
      | *.example.com   | suffix     |
      | *admin*         | contains   |
    When I sync to destination
    Then wildcard patterns should be preserved
    And wildcard matching should work identically at destination

  @story:wildcard-matching
  @priority:high
  Scenario: Sync collection with MATCH_TYPE=WILDCARD
    Given a transforms.conf with:
      """
      [my_lookup]
      collection = my_collection
      external_type = kvstore
      fields_list = _key, pattern, value
      match_type = WILDCARD(pattern)
      """
    When I sync to destination
    Then the match_type configuration should be preserved
    And wildcard lookups should return correct results

  @story:wildcard-matching
  @priority:medium
  Scenario: Test wildcard edge cases
    Given wildcard patterns with special characters:
      | Pattern           | Should Match        | Should Not Match  |
      | test*             | testing, test123    | atest, 1test      |
      | *test             | mytest, 123test     | testing, tester   |
      | *test*            | mytesting, atestb   | tes, tst          |
      | te?t              | test, text          | tet, testt        |
    When synced and queried
    Then matching behavior should be identical to source

  # -----------------------------------------------------------------------------
  # User Story: CIDR Matching
  # -----------------------------------------------------------------------------
  @story:cidr-matching
  @priority:critical
  Scenario: KVStore with CIDR field matching
    Given a KVStore collection with CIDR ranges:
      | CIDR            | Label           |
      | 10.0.0.0/8      | private_a       |
      | 172.16.0.0/12   | private_b       |
      | 192.168.0.0/16  | private_c       |
      | 0.0.0.0/0       | default         |
    And MATCH_TYPE=CIDR is configured
    When I sync to destination
    Then CIDR matching should work correctly
    And IP 10.1.2.3 should match "private_a"
    And IP 8.8.8.8 should match "default"

  @story:cidr-matching
  @priority:high
  Scenario: CIDR matching with overlapping ranges
    Given CIDR ranges that overlap:
      | CIDR              | Priority | Label      |
      | 192.168.1.0/24    | 1        | specific   |
      | 192.168.0.0/16    | 2        | general    |
    When synced and queried with IP 192.168.1.100
    Then the most specific match should be returned
    And match order should be preserved after sync

  @story:cidr-matching
  @priority:high
  Scenario: IPv6 CIDR matching
    Given a KVStore collection with IPv6 CIDR ranges:
      | CIDR                  | Label       |
      | 2001:db8::/32         | documentation |
      | fe80::/10             | link_local  |
      | ::1/128               | loopback    |
    When I sync to destination
    Then IPv6 CIDR matching should work correctly

  # -----------------------------------------------------------------------------
  # User Story: Case Sensitivity
  # -----------------------------------------------------------------------------
  @story:case-sensitivity
  @priority:critical
  Scenario: Sync case-insensitive KVStore
    Given a KVStore collection with case_sensitive_match=false
    And records with mixed case keys:
      | _key        | value |
      | UserAdmin   | 1     |
      | useradmin   | 2     |
      | USERADMIN   | 3     |
    When I sync to destination
    Then case-insensitive matching should be preserved
    And query for "useradmin" should return all variations

  @story:case-sensitivity
  @priority:critical
  Scenario: Convert case and restore original
    Given a KVStore collection with mixed case data:
      | _key  | username    | department |
      | 001   | JohnSmith   | IT         |
      | 002   | janesmith   | HR         |
      | 003   | BOBWILSON   | SALES      |
    When I convert all text fields to lowercase for sync
    Then a case mapping table should be created
    And original case should be restorable from mapping

  @story:case-sensitivity
  @priority:high
  Scenario: Case conversion strategies
    Given data that needs case normalization
    When I configure case conversion
    Then I should be able to choose:
      | Strategy      | Description                        |
      | lowercase     | Convert all to lowercase           |
      | uppercase     | Convert all to uppercase           |
      | titlecase     | Convert to Title Case              |
      | preserve      | Keep original case with mapping    |
      | normalize     | Lowercase with original in _case   |

  @story:case-sensitivity
  @priority:high
  Scenario: Restore case after round-trip sync
    Given original data with specific casing
    And case was normalized during sync
    When I restore from the case mapping
    Then all original casing should be restored exactly
    And no data loss should occur

  # -----------------------------------------------------------------------------
  # User Story: Random KVStore Generation
  # -----------------------------------------------------------------------------
  @story:random-generation
  @priority:critical
  Scenario: Generate random KVStore for testing
    Given I need test data for sync validation
    When I generate a random KVStore with:
      | Parameter        | Value              |
      | record_count     | 10000              |
      | field_count      | 15                 |
      | field_types      | string,int,ip,date |
      | null_percentage  | 5                  |
      | unicode_enabled  | true               |
    Then a KVStore collection should be created
    And all specified parameters should be applied
    And data should be suitable for sync testing

  @story:random-generation
  @priority:high
  Scenario: Generate KVStore matching schema
    Given a schema definition:
      """
      {
        "fields": {
          "user_id": {"type": "string", "pattern": "USR-[0-9]{6}"},
          "ip_address": {"type": "cidr", "version": "ipv4"},
          "created_at": {"type": "timestamp", "range": "last_30_days"},
          "score": {"type": "number", "min": 0, "max": 100},
          "tags": {"type": "array", "items": "string", "max_length": 5}
        }
      }
      """
    When I generate test data
    Then all records should conform to the schema

  @story:random-generation
  @priority:medium
  Scenario: Generate edge case data
    Given I need to test edge cases
    When I generate data with:
      | Edge Case              | Description                    |
      | empty_strings          | Fields with ""                 |
      | null_values            | Fields with null               |
      | special_chars          | Unicode, emoji, newlines       |
      | max_length             | Fields at max length limit     |
      | numeric_strings        | "12345" vs 12345               |
      | boolean_variants       | true, "true", 1, "1"           |
    Then edge cases should be properly represented

  # -----------------------------------------------------------------------------
  # User Story: Test Matrix Execution
  # -----------------------------------------------------------------------------
  @story:test-matrix
  @priority:critical
  Scenario: Full test matrix execution
    Given test matrix dimensions:
      | Dimension          | Values                              |
      | splunk_version     | 9.0, 9.1, 9.2, 9.3                 |
      | collection_size    | 100, 10000, 100000, 1000000        |
      | sync_mode          | full, incremental, append          |
      | lookup_type        | kvstore, external, transform       |
      | case_sensitivity   | sensitive, insensitive             |
    When the test matrix runs
    Then all combinations should be tested
    And results should be aggregated into a report
    And failures should identify the specific matrix cell

  @story:test-matrix
  @priority:high
  Scenario: Matrix test parallelization
    Given a test matrix with 100+ combinations
    When tests execute
    Then tests should run in parallel where possible
    And resource contention should be managed
    And total execution time should be minimized

  @story:test-matrix
  @priority:high
  Scenario: Matrix test result reporting
    Given test matrix execution completes
    Then results should show:
      | Metric                  | Format           |
      | pass/fail per cell      | matrix grid      |
      | execution time per cell | heatmap          |
      | record throughput       | records/second   |
      | error messages          | grouped by type  |

  # -----------------------------------------------------------------------------
  # User Story: Data Integrity Verification
  # -----------------------------------------------------------------------------
  @story:integrity-verification
  @priority:critical
  Scenario: Verify sync integrity across matrix
    Given a sync operation completed
    When I verify integrity
    Then source and destination record counts should match
    And checksums should match for all records
    And no data corruption should be detected

  @story:integrity-verification
  @priority:high
  Scenario: Detect and report sync discrepancies
    Given a sync with potential issues
    When verification runs
    Then discrepancies should be reported:
      | Discrepancy Type     | Details                    |
      | missing_records      | Keys in source not in dest |
      | extra_records        | Keys in dest not in source |
      | modified_records     | Checksum mismatch          |
      | schema_mismatch      | Field type differences     |
