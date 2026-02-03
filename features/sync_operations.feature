# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/sync_operations.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:sync-operations
@feature:sync-jobs
Feature: Sync Job Operations
  As a Splunk administrator
  I want to configure and run sync jobs
  So that my KVStore data is synchronized automatically

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed
    And a destination "cloud-dest" is configured and tested
    And a sync profile "standard-profile" exists

  # -----------------------------------------------------------------------------
  # User Story: Create Sync Job
  # -----------------------------------------------------------------------------
  @story:create-job
  @priority:high
  Scenario: Create a scheduled sync job
    Given I navigate to Inputs > Sync Jobs
    When I click "Create New Input"
    And I fill in the following job details:
      | Field        | Value                |
      | Name         | daily-user-sync      |
      | Interval     | 300                  |
      | Destination  | cloud-dest           |
      | Sync Profile | standard-profile     |
      | Collections  | users,groups,roles   |
    And I click "Save"
    Then the job "daily-user-sync" should appear in the inputs list
    And the job should be enabled by default
    And the job should run every 300 seconds

  @story:create-job
  @priority:medium
  Scenario: Create a sync job with cron schedule
    Given I navigate to Inputs > Sync Jobs
    When I create a job with interval "0 2 * * *"
    Then the job should be scheduled to run at 2 AM daily

  @story:create-job
  @priority:high
  Scenario: Create a job that runs on startup
    Given I create a job with "Run on Startup" enabled
    When Splunk restarts
    Then the sync job should execute immediately on startup
    And then follow its normal schedule

  # -----------------------------------------------------------------------------
  # User Story: Run Sync Job
  # -----------------------------------------------------------------------------
  @story:run-job
  @priority:high
  Scenario: Manual sync job execution
    Given a sync job "manual-sync" exists
    When I click "Run Now" for job "manual-sync"
    Then the job should start executing immediately
    And I should see a progress indicator
    And the job status should show "Running"

  @story:run-job
  @priority:high
  Scenario: Sync job completes successfully
    Given a sync job is running
    And the source collection has 1000 records
    And all records sync without errors
    When the job completes
    Then the job status should show "Success"
    And the metrics should show:
      | Metric          | Value |
      | Records Read    | 1000  |
      | Records Written | 1000  |
      | Records Failed  | 0     |
    And an audit log entry should be created

  @story:run-job
  @priority:high
  Scenario: Sync job completes with partial failures
    Given a sync job is running
    And 950 out of 1000 records sync successfully
    And 50 records fail due to validation errors
    When the job completes
    Then the job status should show "Partial Success"
    And the metrics should show:
      | Metric          | Value |
      | Records Written | 950   |
      | Records Failed  | 50    |
    And the errors should be logged with record keys

  @story:run-job
  @priority:medium
  Scenario: Sync job fails completely
    Given a sync job is running
    And the destination becomes unreachable
    When the job encounters the connection error
    Then the job status should show "Failed"
    And a detailed error message should be logged
    And an alert should be triggered if configured

  # -----------------------------------------------------------------------------
  # User Story: Dry Run Mode
  # -----------------------------------------------------------------------------
  @story:dry-run
  @priority:medium
  Scenario: Execute sync in dry run mode
    Given a sync job "test-sync" with dry run enabled
    And a source collection with 500 records
    When I run the job
    Then no records should actually be written to destination
    And the result should show "Dry Run Completed"
    And the metrics should show what would have been synced:
      | Metric              | Value |
      | Would Write Records | 500   |

  @story:dry-run
  @priority:medium
  Scenario: Dry run detects potential conflicts
    Given a sync job in dry run mode
    And source and destination have conflicting records
    When I run the job
    Then the result should list all potential conflicts
    And no changes should be made to destination

  # -----------------------------------------------------------------------------
  # User Story: Job Retry Logic
  # -----------------------------------------------------------------------------
  @story:retry
  @priority:high
  Scenario: Job retries on transient failure
    Given a sync job with "Retry on Failure" enabled
    And max retries set to 3
    And retry delay set to 60 seconds
    When the job fails due to a network timeout
    Then the job should wait 60 seconds
    And retry the sync operation
    And if successful on retry 2, report "Success (after 1 retry)"

  @story:retry
  @priority:medium
  Scenario: Job stops after max retries exceeded
    Given a sync job with max retries set to 3
    When the job fails 4 consecutive times
    Then the job should stop retrying
    And report "Failed after 3 retries"
    And send a failure notification

  @story:retry
  @priority:low
  Scenario: Retry uses exponential backoff
    Given a sync job with exponential backoff enabled
    And base retry delay of 30 seconds
    When the job fails multiple times
    Then retry delays should be approximately:
      | Retry | Delay    |
      | 1     | 30s      |
      | 2     | 60s      |
      | 3     | 120s     |

  # -----------------------------------------------------------------------------
  # User Story: Job Priority and Queuing
  # -----------------------------------------------------------------------------
  @story:priority
  @priority:medium
  Scenario: High priority job preempts lower priority
    Given sync jobs with different priorities:
      | Job Name    | Priority |
      | critical-ad | Critical |
      | normal-sync | Normal   |
      | bg-backup   | Low      |
    When all jobs are scheduled to run at the same time
    Then "critical-ad" should execute first
    And "normal-sync" should execute second
    And "bg-backup" should execute last

  @story:priority
  @priority:low
  Scenario: Parallel job execution respects limits
    Given max parallel jobs is set to 3
    And 5 jobs are triggered simultaneously
    Then only 3 jobs should run in parallel
    And 2 jobs should be queued
    And queued jobs should start as running jobs complete

  # -----------------------------------------------------------------------------
  # User Story: Job Timeout
  # -----------------------------------------------------------------------------
  @story:timeout
  @priority:medium
  Scenario: Job times out after configured duration
    Given a sync job with timeout of 300 seconds
    And the sync operation takes longer than 300 seconds
    When the timeout is reached
    Then the job should be cancelled
    And the status should show "Timed Out"
    And partially synced data should be checkpointed

  # -----------------------------------------------------------------------------
  # User Story: Cancel Running Job
  # -----------------------------------------------------------------------------
  @story:cancel
  @priority:medium
  Scenario: Cancel a running sync job
    Given a sync job "long-sync" is currently running
    When I click "Cancel" for job "long-sync"
    Then the job should stop gracefully
    And the current batch should complete
    And the status should show "Cancelled"
    And a checkpoint should be saved for resume

  # -----------------------------------------------------------------------------
  # User Story: Enable/Disable Jobs
  # -----------------------------------------------------------------------------
  @story:enable-disable
  @priority:high
  Scenario: Disable a sync job
    Given a sync job "daily-sync" is enabled
    When I click "Disable" for job "daily-sync"
    Then the job should stop running on schedule
    And the status should show "Disabled"
    And the job should not run at the next scheduled time

  @story:enable-disable
  @priority:high
  Scenario: Enable a disabled sync job
    Given a sync job "daily-sync" is disabled
    When I click "Enable" for job "daily-sync"
    Then the job should resume its schedule
    And the next run time should be calculated from now

  # -----------------------------------------------------------------------------
  # User Story: Collection Mapping
  # -----------------------------------------------------------------------------
  @story:collection-mapping
  @priority:high
  Scenario: Sync multiple collections in one job
    Given a sync job configured to sync collections:
      | Source Collection | Destination Collection |
      | users             | users                  |
      | groups            | ad_groups              |
      | permissions       | permissions            |
    When the job runs
    Then all three collections should be synced
    And each collection should use the same sync profile
    And metrics should be reported per collection

  @story:collection-mapping
  @priority:medium
  Scenario: Auto-create destination collection
    Given a collection mapping with "Auto-Create" enabled
    And the destination collection does not exist
    When the sync runs
    Then the destination collection should be created
    And the collection schema should be copied from source
    And records should then be synced

  @story:collection-mapping
  @priority:medium
  Scenario: Sync collection schema
    Given a collection mapping with "Sync Schema" enabled
    And the source collection has field accelerations
    When the sync runs
    Then the destination collection should have matching accelerations
    And field definitions should be copied
