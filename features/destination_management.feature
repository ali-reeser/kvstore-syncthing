# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/destination_management.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:configuration
@feature:destinations
Feature: Sync Destination Management
  As a Splunk administrator
  I want to configure multiple sync destinations
  So that I can replicate KVStore data across different Splunk deployments

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed

  # -----------------------------------------------------------------------------
  # User Story: Configure Splunk REST API Destination
  # -----------------------------------------------------------------------------
  @story:rest-destination
  @priority:high
  Scenario: Create a new Splunk REST API destination
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I fill in the following destination details:
      | Field            | Value                          |
      | Name             | splunk-cloud-prod              |
      | Destination Type | Splunk REST API                |
      | Host             | my-instance.splunkcloud.com    |
      | Port             | 8089                           |
      | Use SSL          | Yes                            |
      | Auth Type        | Token                          |
      | Password         | my-auth-token-12345            |
    And I click "Save"
    Then the destination "splunk-cloud-prod" should appear in the destinations list
    And the destination should show status "Not Tested"

  @story:rest-destination
  @priority:high
  Scenario: Test connection to Splunk REST API destination
    Given a destination "splunk-cloud-prod" exists with valid credentials
    When I click "Test Connection" for destination "splunk-cloud-prod"
    Then I should see a connection test in progress
    And within 30 seconds I should see "Connection successful"
    And the response should include the Splunk server version

  @story:rest-destination
  @priority:medium
  Scenario: Test connection fails with invalid credentials
    Given a destination "bad-dest" exists with invalid credentials
    When I click "Test Connection" for destination "bad-dest"
    Then within 30 seconds I should see "Authentication failed"
    And the error message should suggest checking credentials

  @story:rest-destination
  @priority:medium
  Scenario: Test connection fails with unreachable host
    Given a destination "unreachable" exists with host "nonexistent.example.com"
    When I click "Test Connection" for destination "unreachable"
    Then within 30 seconds I should see "Connection failed"
    And the error message should indicate network unreachable

  # -----------------------------------------------------------------------------
  # User Story: Configure MongoDB Direct Destination
  # -----------------------------------------------------------------------------
  @story:mongodb-destination
  @priority:high
  Scenario: Create a MongoDB direct destination for master/slave sync
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I fill in the following destination details:
      | Field              | Value                          |
      | Name               | onprem-mongodb-slave           |
      | Destination Type   | MongoDB Direct                 |
      | Host               | splunk-sh01.internal.corp      |
      | Port               | 8191                           |
      | Use SSL            | No                             |
      | Auth Type          | Username/Password              |
      | Username           | splunk_kvstore                 |
      | Password           | mongodb-secret-pass            |
      | MongoDB Database   | splunk                         |
      | MongoDB Auth Source| admin                          |
    And I click "Save"
    Then the destination "onprem-mongodb-slave" should appear in the destinations list

  @story:mongodb-destination
  @priority:medium
  Scenario: Configure MongoDB replica set destination
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I fill in the following destination details:
      | Field               | Value                                           |
      | Name                | mongodb-replicaset                              |
      | Destination Type    | MongoDB Direct                                  |
      | Host                | mongo1.corp:27017,mongo2.corp:27017             |
      | MongoDB Replica Set | rs0                                             |
    And I click "Save"
    Then the destination should be configured for replica set "rs0"

  # -----------------------------------------------------------------------------
  # User Story: Configure Index & Rehydrate (HEC) Destination
  # -----------------------------------------------------------------------------
  @story:hec-destination
  @priority:high
  Scenario: Create an Index & Rehydrate destination for cloud sync
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I fill in the following destination details:
      | Field            | Value                                    |
      | Name             | cloud-hec-sync                           |
      | Destination Type | Index & Rehydrate                        |
      | Host             | input-prd-p-abc123.cloud.splunk.com      |
      | Port             | 443                                      |
      | Use SSL          | Yes                                      |
      | Auth Type        | Token                                    |
      | Password         | hec-token-xyz789                         |
      | HEC Index        | kvstore_sync                             |
      | HEC Sourcetype   | kvstore:sync                             |
    And I click "Save"
    Then the destination "cloud-hec-sync" should appear in the destinations list
    And a help tooltip should explain rehydration search requirements

  # -----------------------------------------------------------------------------
  # User Story: Configure S3 Destination
  # -----------------------------------------------------------------------------
  @story:s3-destination
  @priority:medium
  Scenario: Create an S3 bucket destination with IAM role
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I fill in the following destination details:
      | Field            | Value                          |
      | Name             | aws-s3-backup                  |
      | Destination Type | S3 Bucket                      |
      | Auth Type        | AWS IAM Role                   |
      | AWS Region       | us-east-1                      |
      | S3 Bucket        | company-kvstore-sync           |
      | S3 Prefix        | kvstore/prod/                  |
    And I click "Save"
    Then the destination "aws-s3-backup" should appear in the destinations list

  @story:s3-destination
  @priority:medium
  Scenario: Create an S3 destination with explicit credentials
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I fill in the following destination details:
      | Field            | Value                          |
      | Name             | aws-s3-explicit                |
      | Destination Type | S3 Bucket                      |
      | Auth Type        | Username/Password              |
      | Username         | AKIAIOSFODNN7EXAMPLE           |
      | Password         | wJalrXUtnFEMI/K7MDENG/bPxR     |
      | AWS Region       | eu-west-1                      |
      | S3 Bucket        | eu-kvstore-backup              |
    And I click "Save"
    Then the destination should be configured with explicit AWS credentials

  # -----------------------------------------------------------------------------
  # User Story: Configure File Export Destination
  # -----------------------------------------------------------------------------
  @story:file-destination
  @priority:low
  Scenario: Create a file export destination
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I fill in the following destination details:
      | Field              | Value                               |
      | Name               | local-backup                        |
      | Destination Type   | File Export                         |
      | File Export Path   | /opt/splunk/var/kvstore_exports     |
      | File Export Format | JSON                                |
    And I click "Save"
    Then the destination "local-backup" should appear in the destinations list

  # -----------------------------------------------------------------------------
  # User Story: Edit and Delete Destinations
  # -----------------------------------------------------------------------------
  @story:destination-crud
  @priority:high
  Scenario: Edit an existing destination
    Given a destination "splunk-cloud-prod" exists
    When I click "Edit" for destination "splunk-cloud-prod"
    And I change the "Port" to "8088"
    And I click "Save"
    Then the destination should be updated with port "8088"
    And an audit log entry should be created for the change

  @story:destination-crud
  @priority:high
  Scenario: Delete a destination not in use
    Given a destination "unused-dest" exists
    And the destination is not used by any sync jobs
    When I click "Delete" for destination "unused-dest"
    And I confirm the deletion
    Then the destination "unused-dest" should no longer exist

  @story:destination-crud
  @priority:high
  Scenario: Cannot delete a destination in use
    Given a destination "active-dest" exists
    And the destination is used by sync job "daily-sync"
    When I click "Delete" for destination "active-dest"
    Then I should see an error "Cannot delete destination in use"
    And the error should list the jobs using this destination

  # -----------------------------------------------------------------------------
  # User Story: Destination Validation
  # -----------------------------------------------------------------------------
  @story:validation
  @priority:high
  Scenario Outline: Validate required destination fields
    Given I navigate to the Configuration > Destinations page
    When I click "Add Destination"
    And I leave the "<field>" field empty
    And I click "Save"
    Then I should see a validation error for "<field>"
    And the error message should be "<message>"

    Examples:
      | field            | message                              |
      | Name             | Name is required                     |
      | Destination Type | Destination Type is required         |
      | Host             | Host is required                     |

  @story:validation
  @priority:medium
  Scenario: Validate destination name uniqueness
    Given a destination "existing-dest" exists
    When I try to create a destination with name "existing-dest"
    Then I should see an error "Destination name already exists"

  @story:validation
  @priority:medium
  Scenario: Validate destination name format
    When I try to create a destination with name "invalid name!"
    Then I should see an error "Name can only contain alphanumeric characters, underscores, and hyphens"
