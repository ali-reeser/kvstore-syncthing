# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/sync_methods.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:sync-methods
@feature:multi-method-sync
Feature: Multiple Synchronization Methods
  As a Splunk administrator
  I want multiple ways to sync KVStore data
  So that I can choose the best method for my environment and constraints

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed

  # =============================================================================
  # REST API Sync (Primary Method - uses splunk-sdk)
  # =============================================================================
  @story:rest-sync
  @priority:critical
  Scenario: Sync via Splunk REST API
    Given a source KVStore collection "users" with 1000 records
    And a REST API destination "cloud-prod" is configured
    When I sync using the REST API method
    Then all 1000 records should be transferred via splunk-sdk
    And the destination should have identical data

  @story:rest-sync
  @priority:high
  Scenario: REST sync with authentication token
    Given a destination with token-based authentication
    When I test the connection
    Then the connection should succeed via splunk-sdk
    And I should see the Splunk version in the response

  @story:rest-sync
  @priority:high
  Scenario: REST sync handles rate limiting
    Given the destination has rate limiting enabled
    When I sync a large collection
    Then the sync should respect rate limits
    And retry with exponential backoff on 429 responses

  # =============================================================================
  # MongoDB Direct Sync
  # =============================================================================
  @story:mongodb-direct
  @priority:high
  Scenario: Configure MongoDB direct connection
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "MongoDB Direct"
    Then I should see configuration fields:
      | Field              | Required | Default    |
      | Host               | Yes      |            |
      | Port               | Yes      | 27017      |
      | Database           | Yes      | splunk     |
      | Username           | No       |            |
      | Password           | No       |            |
      | Auth Source        | No       | admin      |
      | Replica Set        | No       |            |
      | SSL Enabled        | No       | true       |
      | SSL CA Certificate | No       |            |

  @story:mongodb-direct
  @priority:high
  Scenario: Sync via MongoDB direct connection
    Given a source KVStore collection "assets" with 5000 records
    And a MongoDB destination "mongo-replica" is configured
    When I sync using the MongoDB Direct method
    Then records should be written directly to MongoDB
    And no REST API calls should be made
    And sync should be faster than REST for large collections

  @story:mongodb-direct
  @priority:high
  Scenario: MongoDB direct sync for master/slave replication
    Given Splunk KVStore as the master on port 8191
    And an external MongoDB as the slave
    When I configure master/slave replication
    Then the slave should receive all changes from master
    And replication lag should be monitored
    And alerts should fire if lag exceeds threshold

  @story:mongodb-direct
  @priority:medium
  Scenario: MongoDB direct connection to Splunk's internal KVStore
    Given I need to connect to Splunk's internal MongoDB
    And I have the credentials from server.conf
    When I connect to localhost:8191
    Then I should be able to read KVStore collections directly
    And I should see the internal replica set configuration

  @story:mongodb-direct
  @priority:medium
  Scenario: MongoDB sync with SSL/TLS
    Given a MongoDB destination with SSL enabled
    And a CA certificate is provided
    When I test the connection
    Then the connection should use TLS
    And certificate validation should pass

  # =============================================================================
  # HTTP Event Collector (HEC) - Index & Rehydrate
  # =============================================================================
  @story:hec-sync
  @priority:high
  Scenario: Configure HEC destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "Splunk HEC"
    Then I should see configuration fields:
      | Field              | Required | Default    |
      | HEC URL            | Yes      |            |
      | HEC Token          | Yes      |            |
      | Index              | Yes      |            |
      | Source             | No       | kvstore    |
      | Sourcetype         | No       | kvstore_sync |
      | SSL Enabled        | No       | true       |
      | Batch Size         | No       | 100        |
      | Acknowledgment     | No       | true       |

  @story:hec-sync
  @priority:high
  Scenario: Sync KVStore to index via HEC
    Given a source KVStore collection "audit_logs" with 10000 records
    And a HEC destination "cloud-hec" is configured
    When I sync using the HEC method
    Then records should be sent to the HEC endpoint
    And each record should be a separate event
    And events should include metadata for rehydration:
      | Field              | Value                |
      | _kvstore_collection| audit_logs           |
      | _kvstore_key       | <record _key>        |
      | _kvstore_app       | search               |
      | _kvstore_owner     | nobody               |
      | _kvstore_checksum  | <record checksum>    |

  @story:hec-sync
  @priority:high
  Scenario: Rehydrate KVStore from indexed events
    Given events were previously synced to index "kvstore_archive"
    And I need to restore the KVStore collection
    When I run the rehydration process
    Then events should be read from the index
    And records should be written back to KVStore
    And checksums should be verified after rehydration

  @story:hec-sync
  @priority:medium
  Scenario: HEC sync with acknowledgment
    Given HEC acknowledgment is enabled
    When records are sent to HEC
    Then the app should wait for acknowledgment
    And only mark records as synced after ack
    And retry failed batches

  @story:hec-sync
  @priority:medium
  Scenario: Point-in-time recovery from index
    Given KVStore data was synced to index over time
    And I need to recover data from a specific point
    When I specify earliest="2026-01-15T00:00:00" latest="2026-01-15T23:59:59"
    Then only events from that time range should be rehydrated
    And I should be able to restore the KVStore to that state

  # =============================================================================
  # File Export Sync
  # =============================================================================
  @story:file-export
  @priority:high
  Scenario: Configure File Export destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "File Export"
    Then I should see configuration fields:
      | Field              | Required | Default           |
      | Export Path        | Yes      |                   |
      | File Format        | Yes      | json              |
      | Compression        | No       | gzip              |
      | File Naming        | No       | {collection}_{timestamp} |
      | Max File Size MB   | No       | 100               |
      | Include Schema     | No       | true              |
      | Include Checksums  | No       | true              |

  @story:file-export
  @priority:high
  Scenario: Export KVStore to JSON files
    Given a source KVStore collection "users" with 5000 records
    And a File Export destination to "/opt/splunk/var/kvstore_export"
    When I sync using the File Export method
    Then files should be created at the export path
    And file format should be:
      """
      {
        "metadata": {
          "collection": "users",
          "app": "search",
          "owner": "nobody",
          "exported_at": "2026-02-03T10:00:00Z",
          "record_count": 5000,
          "checksum": "sha256:..."
        },
        "schema": { ... },
        "records": [ ... ]
      }
      """

  @story:file-export
  @priority:high
  Scenario: Import KVStore from exported files
    Given exported files exist at "/opt/splunk/var/kvstore_export"
    When I import from the File Export
    Then records should be read from the files
    And records should be written to the destination KVStore
    And checksums should be verified

  @story:file-export
  @priority:medium
  Scenario: Export with compression
    Given compression is set to "gzip"
    When I export a collection
    Then files should be compressed
    And file extension should be .json.gz
    And import should automatically detect and decompress

  @story:file-export
  @priority:medium
  Scenario: Split large exports into multiple files
    Given a collection with 1,000,000 records
    And max file size is 100MB
    When I export the collection
    Then multiple files should be created
    And each file should be under 100MB
    And files should be named with sequence numbers

  @story:file-export
  @priority:low
  Scenario: Export to CSV format
    Given file format is set to "csv"
    When I export a collection
    Then a CSV file should be created
    And the header row should contain field names
    And a separate schema.json file should be created

  # =============================================================================
  # AWS S3 Export Sync
  # =============================================================================
  @story:s3-export
  @priority:high
  Scenario: Configure S3 Export destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "AWS S3"
    Then I should see configuration fields:
      | Field              | Required | Default    |
      | Bucket Name        | Yes      |            |
      | Region             | Yes      | us-east-1  |
      | Access Key ID      | Yes      |            |
      | Secret Access Key  | Yes      |            |
      | Prefix             | No       | kvstore/   |
      | Storage Class      | No       | STANDARD   |
      | Server-Side Encrypt| No       | AES256     |
      | KMS Key ID         | No       |            |

  @story:s3-export
  @priority:high
  Scenario: Export KVStore to S3
    Given a source KVStore collection "logs" with 50000 records
    And an S3 destination "backup-bucket" is configured
    When I sync using the S3 Export method
    Then files should be uploaded to S3
    And S3 path should be: s3://backup-bucket/kvstore/logs/2026/02/03/
    And manifest file should be created listing all parts

  @story:s3-export
  @priority:high
  Scenario: Import KVStore from S3
    Given exported data exists in S3 bucket "backup-bucket"
    When I import from S3 path "kvstore/logs/2026/02/03/"
    Then manifest should be read first
    And all data files should be downloaded
    And records should be written to destination KVStore

  @story:s3-export
  @priority:medium
  Scenario: S3 export with server-side encryption
    Given server-side encryption is enabled with KMS
    And KMS Key ID is specified
    When I export to S3
    Then files should be encrypted at rest
    And encryption should use the specified KMS key

  @story:s3-export
  @priority:medium
  Scenario: S3 multipart upload for large exports
    Given a collection that exports to >100MB
    When I export to S3
    Then multipart upload should be used
    And upload should be resumable on failure
    And progress should be tracked

  @story:s3-export
  @priority:medium
  Scenario: S3 lifecycle for retention
    Given I configure retention policy of 90 days
    When exports are created
    Then S3 lifecycle rules should be applied
    And objects should transition to Glacier after 30 days
    And objects should be deleted after 90 days

  @story:s3-export
  @priority:low
  Scenario: Cross-account S3 export
    Given I need to export to an S3 bucket in another AWS account
    And I have cross-account IAM role ARN
    When I configure the destination with assume role
    Then the app should assume the cross-account role
    And export should succeed to the external bucket

  # =============================================================================
  # Sync Method Selection Logic
  # =============================================================================
  @story:method-selection
  @priority:high
  Scenario: Automatic method selection based on destination
    Given multiple sync methods are available
    When I create a sync job
    Then the method should be selected based on destination type:
      | Destination Type | Selected Method    |
      | splunk_rest      | REST API           |
      | mongodb_direct   | MongoDB Direct     |
      | splunk_hec       | HEC Index/Rehydrate|
      | file_export      | File Export        |
      | s3_export        | S3 Export          |

  @story:method-selection
  @priority:medium
  Scenario: Fallback method on failure
    Given primary method is "REST API"
    And fallback method is "File Export"
    When the REST API sync fails
    Then the app should attempt File Export as fallback
    And the failure should be logged
    And an alert should be sent

  @story:method-selection
  @priority:medium
  Scenario: Method comparison report
    Given I want to evaluate sync methods
    When I run a benchmark sync
    Then I should see comparison metrics:
      | Metric              | REST    | MongoDB | HEC     | File    |
      | Records/Second      | 500     | 2000    | 1000    | 5000    |
      | Network Overhead    | High    | Low     | Medium  | N/A     |
      | Resumability        | Yes     | Yes     | Yes     | Yes     |
      | Requires Splunk     | Yes     | No      | Yes     | No      |
