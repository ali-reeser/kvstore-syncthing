# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/mongodb_cluster.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:advanced
@feature:mongodb-cluster
Feature: MongoDB Out-of-Band Cluster Management
  As a Splunk administrator
  I want to manage out-of-band MongoDB nodes
  So that I can create HA/DR replicas of my KVStore data

  Background:
    Given I am logged into Splunk as an admin user
    And I have access to Splunk's internal KVStore MongoDB
    And I have network access to external MongoDB nodes

  # -----------------------------------------------------------------------------
  # User Story: Connect to Splunk KVStore MongoDB
  # -----------------------------------------------------------------------------
  @story:connect-kvstore
  @priority:high
  Scenario: Connect to Splunk's internal KVStore
    Given Splunk's KVStore is running on port 8191
    And I have MongoDB credentials from splunk-launch.conf
    When I connect to the KVStore MongoDB
    Then I should see the replica set name
    And I should see the current primary node
    And I should see the MongoDB version

  @story:connect-kvstore
  @priority:high
  Scenario: Verify MongoDB version compatibility
    Given Splunk's KVStore uses MongoDB 4.2
    And I have an external MongoDB node running version 4.2
    When I check version compatibility
    Then the versions should be reported as compatible

  @story:connect-kvstore
  @priority:high
  Scenario: Detect incompatible MongoDB versions
    Given Splunk's KVStore uses MongoDB 4.2
    And I have an external MongoDB node running version 5.0
    When I check version compatibility
    Then a warning should indicate version mismatch
    And the warning should explain potential issues

  # -----------------------------------------------------------------------------
  # User Story: Add OOB MongoDB Node
  # -----------------------------------------------------------------------------
  @story:add-oob-node
  @priority:high
  Scenario: Add a hidden secondary node for DR
    Given Splunk's KVStore replica set is healthy
    And an external MongoDB node "dr-mongo.backup.corp:27017" is available
    When I add the node as a hidden secondary with:
      | Setting   | Value |
      | Priority  | 0     |
      | Votes     | 0     |
      | Hidden    | true  |
    Then the node should be added to the replica set
    And the node should begin replicating data
    And the node should not participate in elections

  @story:add-oob-node
  @priority:high
  Scenario: Dry run adding an OOB node
    Given an external MongoDB node is available
    When I add the node with dry run enabled
    Then no changes should be made to the replica set
    And I should see what configuration would be applied

  @story:add-oob-node
  @priority:medium
  Scenario: Add a delayed replica for point-in-time recovery
    Given Splunk's KVStore replica set is healthy
    When I add a node with:
      | Setting      | Value |
      | Priority     | 0     |
      | Votes        | 0     |
      | Hidden       | true  |
      | Slave Delay  | 3600  |
    Then the node should replicate with a 1-hour delay
    And I can use this node to recover from accidental deletions

  @story:add-oob-node
  @priority:medium
  Scenario: Add a read replica for query offloading
    Given Splunk's KVStore replica set is healthy
    When I add a node with:
      | Setting   | Value        |
      | Priority  | 0            |
      | Votes     | 0            |
      | Hidden    | false        |
      | Tags      | role=read    |
    Then the node should be visible for read operations
    And the node should be tagged for read preference targeting

  @story:add-oob-node
  @priority:high
  Scenario: Validate node before adding
    Given I attempt to add a node "bad-mongo.corp:27017"
    And the node is not reachable
    When I try to add the node
    Then the operation should fail with "Cannot reach node"
    And no changes should be made to the replica set

  # -----------------------------------------------------------------------------
  # User Story: Remove OOB Node
  # -----------------------------------------------------------------------------
  @story:remove-oob-node
  @priority:high
  Scenario: Remove an OOB node from replica set
    Given an OOB node "dr-mongo.backup.corp:27017" is in the replica set
    When I remove the node
    Then the node should be removed from the replica set configuration
    And the remaining nodes should continue operating normally

  @story:remove-oob-node
  @priority:medium
  Scenario: Cannot remove Splunk's primary node
    Given Splunk's primary KVStore node is "splunk-sh01:8191"
    When I attempt to remove "splunk-sh01:8191"
    Then the operation should be blocked
    And an error should explain this would break Splunk

  # -----------------------------------------------------------------------------
  # User Story: Monitor Replication
  # -----------------------------------------------------------------------------
  @story:replication-monitoring
  @priority:high
  Scenario: View replication lag for OOB nodes
    Given OOB nodes are replicating from Splunk's KVStore
    When I check replication status
    Then I should see replication lag for each node:
      | Node                    | Lag (seconds) |
      | dr-mongo.backup.corp    | 2             |
      | read-replica.corp       | 1             |

  @story:replication-monitoring
  @priority:high
  Scenario: Alert on excessive replication lag
    Given an OOB node has replication lag > 60 seconds
    When the monitoring check runs
    Then an alert should be triggered
    And the alert should include the node name and lag time

  @story:replication-monitoring
  @priority:medium
  Scenario: Wait for node to catch up
    Given I've added a new OOB node
    And the node is syncing historical data
    When I wait for sync with timeout of 300 seconds
    Then the operation should block until sync completes
    Or timeout if sync takes too long

  # -----------------------------------------------------------------------------
  # User Story: Failover to OOB Node
  # -----------------------------------------------------------------------------
  @story:failover
  @priority:high
  Scenario: Promote OOB node to primary (disaster recovery)
    Given Splunk's primary node is unavailable
    And OOB node "dr-mongo.backup.corp" is in sync
    When I promote "dr-mongo.backup.corp" to primary with force=true
    Then the node's priority should be set to 100
    And the node should become the new primary
    And I should receive confirmation of the promotion

  @story:failover
  @priority:high
  Scenario: Cannot promote when primary is available
    Given Splunk's primary node is healthy
    And I attempt to promote an OOB node
    Without force=true
    Then the operation should be blocked
    And an error should explain the current primary is available

  @story:failover
  @priority:medium
  Scenario: Failback to original primary
    Given an OOB node was promoted during an outage
    And the original Splunk primary is now available
    When I restore the original primary
    Then the original node should become primary again
    And the OOB node should return to secondary status

  # -----------------------------------------------------------------------------
  # User Story: Generate OOB Node Configuration
  # -----------------------------------------------------------------------------
  @story:configuration
  @priority:medium
  Scenario: Generate mongod.conf for OOB node
    Given I want to set up a new OOB MongoDB node
    When I generate the configuration
    Then I should receive a mongod.conf template with:
      | Setting              | Value                |
      | replSetName          | <from Splunk>        |
      | keyFile              | <path to key file>   |
      | authorization        | enabled              |
      | port                 | 27017                |

  @story:configuration
  @priority:low
  Scenario: Generate key file from Splunk
    Given Splunk's KVStore uses a key file for auth
    When I export the key file
    Then I should receive the key file content
    And instructions for deploying it to OOB nodes

  # -----------------------------------------------------------------------------
  # User Story: Replica Set Status Dashboard
  # -----------------------------------------------------------------------------
  @story:dashboard
  @priority:medium
  Scenario: View replica set status
    Given I open the MongoDB Cluster dashboard
    Then I should see all replica set members:
      | Node               | Role      | State     | Lag  |
      | splunk-sh01:8191   | Primary   | PRIMARY   | 0    |
      | splunk-sh02:8191   | Secondary | SECONDARY | 1s   |
      | dr-mongo:27017     | OOB       | SECONDARY | 2s   |

  @story:dashboard
  @priority:low
  Scenario: Visual indicator for unhealthy nodes
    Given one replica set member is in RECOVERING state
    When I view the dashboard
    Then that member should be highlighted with warning color
    And a tooltip should explain the state
