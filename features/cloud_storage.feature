# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/cloud_storage.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:sync-methods
@feature:cloud-storage
Feature: Multi-Cloud Object Storage Synchronization
  As a Splunk administrator
  I want to sync KVStore data to multiple cloud storage providers
  So that I can choose the best storage option for my infrastructure and compliance requirements

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed

  # =============================================================================
  # AWS S3 Storage
  # =============================================================================
  @story:s3-storage
  @priority:critical
  Scenario: Configure AWS S3 destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "AWS S3"
    Then I should see configuration fields:
      | Field                | Required | Default        |
      | Bucket Name          | Yes      |                |
      | Region               | Yes      | us-east-1      |
      | Access Key ID        | Yes      |                |
      | Secret Access Key    | Yes      |                |
      | Prefix               | No       | kvstore/       |
      | Storage Class        | No       | STANDARD       |
      | Server-Side Encrypt  | No       | AES256         |
      | KMS Key ID           | No       |                |
      | Endpoint URL         | No       |                |
      | Use Path Style       | No       | false          |

  @story:s3-storage
  @priority:critical
  Scenario: Export KVStore to AWS S3
    Given a source KVStore collection "threat_indicators" with 50000 records
    And an AWS S3 destination "aws-prod-bucket" is configured
    When I sync using the AWS S3 method
    Then files should be uploaded to S3
    And S3 path should be: s3://aws-prod-bucket/kvstore/threat_indicators/2026/02/03/
    And manifest file should be created with metadata

  @story:s3-storage
  @priority:high
  Scenario: AWS S3 with IAM role assumption
    Given I need to export to an S3 bucket in another AWS account
    And I have a cross-account IAM role ARN
    When I configure the destination with role assumption
    Then the app should assume the cross-account role
    And export should succeed to the external bucket

  # =============================================================================
  # MinIO (S3-Compatible) Storage
  # =============================================================================
  @story:minio-storage
  @priority:high
  Scenario: Configure MinIO destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "MinIO"
    Then I should see configuration fields:
      | Field                | Required | Default        |
      | Endpoint URL         | Yes      |                |
      | Bucket Name          | Yes      |                |
      | Access Key           | Yes      |                |
      | Secret Key           | Yes      |                |
      | Prefix               | No       | kvstore/       |
      | Use SSL              | No       | true           |
      | Verify SSL           | No       | true           |
      | Region               | No       | us-east-1      |

  @story:minio-storage
  @priority:high
  Scenario: Export KVStore to MinIO
    Given a source KVStore collection "assets" with 10000 records
    And a MinIO destination "minio-local" is configured with:
      | Setting       | Value                         |
      | Endpoint URL  | https://minio.internal:9000   |
      | Bucket Name   | splunk-kvstore                |
      | Access Key    | minio_access                  |
      | Secret Key    | <encrypted via UCC>           |
    When I sync using the MinIO method
    Then files should be uploaded to MinIO
    And S3-compatible API should be used
    And path style addressing should be used

  @story:minio-storage
  @priority:medium
  Scenario: MinIO with custom CA certificate
    Given MinIO uses a self-signed certificate
    And I have the CA certificate file
    When I configure the destination with custom CA
    Then SSL verification should use the custom CA
    And the connection should succeed

  # =============================================================================
  # Wasabi Storage
  # =============================================================================
  @story:wasabi-storage
  @priority:high
  Scenario: Configure Wasabi destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "Wasabi"
    Then I should see configuration fields:
      | Field                | Required | Default              |
      | Bucket Name          | Yes      |                      |
      | Region               | Yes      | us-east-1            |
      | Access Key           | Yes      |                      |
      | Secret Key           | Yes      |                      |
      | Prefix               | No       | kvstore/             |
      | Endpoint Override    | No       | s3.wasabisys.com     |

  @story:wasabi-storage
  @priority:high
  Scenario: Export KVStore to Wasabi
    Given a source KVStore collection "logs_archive" with 100000 records
    And a Wasabi destination "wasabi-archive" is configured
    When I sync using the Wasabi method
    Then files should be uploaded to Wasabi
    And Wasabi's S3-compatible endpoint should be used
    And no egress fees should apply for download

  @story:wasabi-storage
  @priority:medium
  Scenario: Wasabi region selection
    Given Wasabi has multiple regions available:
      | Region          | Endpoint                    |
      | us-east-1       | s3.us-east-1.wasabisys.com |
      | us-east-2       | s3.us-east-2.wasabisys.com |
      | us-west-1       | s3.us-west-1.wasabisys.com |
      | eu-central-1    | s3.eu-central-1.wasabisys.com |
      | ap-northeast-1  | s3.ap-northeast-1.wasabisys.com |
    When I select a region
    Then the correct endpoint should be automatically configured

  # =============================================================================
  # Azure Blob Storage
  # =============================================================================
  @story:azure-storage
  @priority:high
  Scenario: Configure Azure Blob Storage destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "Azure Blob"
    Then I should see configuration fields:
      | Field                | Required | Default        |
      | Storage Account      | Yes      |                |
      | Container Name       | Yes      |                |
      | Auth Type            | Yes      | connection_string |
      | Connection String    | Cond     |                |
      | Account Key          | Cond     |                |
      | SAS Token            | Cond     |                |
      | Prefix               | No       | kvstore/       |
      | Access Tier          | No       | Hot            |

  @story:azure-storage
  @priority:high
  Scenario: Export KVStore to Azure Blob
    Given a source KVStore collection "compliance_data" with 25000 records
    And an Azure Blob destination "azure-compliance" is configured with:
      | Setting          | Value                              |
      | Storage Account  | splunkkvstore                      |
      | Container Name   | kvstore-sync                       |
      | Auth Type        | connection_string                  |
    When I sync using the Azure Blob method
    Then blobs should be uploaded to Azure
    And path should be: https://splunkkvstore.blob.core.windows.net/kvstore-sync/compliance_data/

  @story:azure-storage
  @priority:high
  Scenario: Azure Blob with Managed Identity
    Given Splunk is running on Azure VM
    And Managed Identity is configured
    When I configure Azure Blob with "managed_identity" auth type
    Then no credentials should be needed
    And authentication should use VM's managed identity

  @story:azure-storage
  @priority:medium
  Scenario: Azure Blob access tiers
    Given I want to optimize storage costs
    When I configure access tier:
      | Tier    | Use Case                           |
      | Hot     | Frequently accessed data           |
      | Cool    | Infrequently accessed (30+ days)   |
      | Archive | Rarely accessed (180+ days)        |
    Then data should be stored in the specified tier
    And tier can be changed post-upload

  # =============================================================================
  # Google Cloud Storage (GCS)
  # =============================================================================
  @story:gcs-storage
  @priority:high
  Scenario: Configure Google Cloud Storage destination
    Given I navigate to Configuration > Destinations
    When I create a new destination with type "Google Cloud Storage"
    Then I should see configuration fields:
      | Field                | Required | Default        |
      | Project ID           | Yes      |                |
      | Bucket Name          | Yes      |                |
      | Auth Type            | Yes      | service_account |
      | Service Account JSON | Cond     |                |
      | Prefix               | No       | kvstore/       |
      | Storage Class        | No       | STANDARD       |
      | Location             | No       | US             |

  @story:gcs-storage
  @priority:high
  Scenario: Export KVStore to Google Cloud Storage
    Given a source KVStore collection "user_analytics" with 75000 records
    And a GCS destination "gcs-analytics" is configured with:
      | Setting              | Value                    |
      | Project ID           | my-splunk-project        |
      | Bucket Name          | splunk-kvstore-sync      |
      | Auth Type            | service_account          |
    When I sync using the GCS method
    Then objects should be uploaded to GCS
    And path should be: gs://splunk-kvstore-sync/kvstore/user_analytics/

  @story:gcs-storage
  @priority:medium
  Scenario: GCS with Workload Identity
    Given Splunk is running on GKE
    And Workload Identity is configured
    When I configure GCS with "workload_identity" auth type
    Then no service account key should be needed
    And authentication should use Kubernetes service account

  @story:gcs-storage
  @priority:medium
  Scenario: GCS storage classes
    Given I want to optimize for access patterns
    When I configure storage class:
      | Class               | Use Case                           |
      | STANDARD            | Frequently accessed                |
      | NEARLINE            | Once per month access              |
      | COLDLINE            | Once per quarter access            |
      | ARCHIVE             | Once per year access               |
    Then data should be stored in the specified class

  # =============================================================================
  # Generic S3-Compatible Storage
  # =============================================================================
  @story:s3-compatible
  @priority:medium
  Scenario: Configure generic S3-compatible destination
    Given I have an S3-compatible storage service
    When I create a new destination with type "S3 Compatible"
    Then I should see configuration fields:
      | Field                | Required | Default        |
      | Endpoint URL         | Yes      |                |
      | Bucket Name          | Yes      |                |
      | Access Key           | Yes      |                |
      | Secret Key           | Yes      |                |
      | Region               | No       | us-east-1      |
      | Path Style           | No       | true           |
      | Signature Version    | No       | v4             |
      | Prefix               | No       | kvstore/       |

  @story:s3-compatible
  @priority:medium
  Scenario: S3-compatible with various providers
    Given the following S3-compatible providers:
      | Provider         | Endpoint Example                    |
      | MinIO            | https://minio.local:9000           |
      | Wasabi           | https://s3.wasabisys.com           |
      | DigitalOcean     | https://nyc3.digitaloceanspaces.com |
      | Backblaze B2     | https://s3.us-west-001.backblazeb2.com |
      | Ceph RadosGW     | https://ceph.local:7480            |
      | Cloudflare R2    | https://account.r2.cloudflarestorage.com |
    When I configure any S3-compatible endpoint
    Then the sync should work with standard S3 API calls

  # =============================================================================
  # Common Cloud Storage Features
  # =============================================================================
  @story:cloud-common
  @priority:high
  Scenario: Multipart upload for large exports
    Given a collection that exports to >100MB
    When I export to any cloud storage
    Then multipart upload should be used
    And parts should be uploaded in parallel
    And failed parts should be retried
    And upload should be resumable

  @story:cloud-common
  @priority:high
  Scenario: Server-side encryption
    Given encryption is required for compliance
    When I configure server-side encryption:
      | Provider | Encryption Options              |
      | AWS S3   | SSE-S3, SSE-KMS, SSE-C          |
      | Azure    | Microsoft-managed, Customer-managed |
      | GCS      | Google-managed, Customer-managed |
      | MinIO    | SSE-S3, SSE-KMS                 |
    Then data should be encrypted at rest
    And encryption key should be managed per policy

  @story:cloud-common
  @priority:high
  Scenario: Import from cloud storage
    Given data was previously exported to cloud storage
    When I run import from any cloud provider
    Then manifest file should be read first
    And all data files should be downloaded
    And records should be written to destination KVStore
    And checksums should be verified

  @story:cloud-common
  @priority:medium
  Scenario: Lifecycle policies
    Given I want to manage data retention
    When I configure lifecycle policy:
      | Stage                | Days | Action                    |
      | Current              | 0    | Standard/Hot storage      |
      | Archive              | 30   | Move to cold storage      |
      | Expire               | 365  | Delete permanently        |
    Then cloud provider lifecycle rules should be applied

  @story:cloud-common
  @priority:medium
  Scenario: Cross-region replication
    Given I need disaster recovery across regions
    When I configure cross-region replication
    Then data should be replicated to secondary region
    And replication status should be monitored
    And failover should be possible

  # =============================================================================
  # Export Manifest and Metadata
  # =============================================================================
  @story:cloud-manifest
  @priority:high
  Scenario: Generate export manifest
    When data is exported to any cloud storage
    Then a manifest file should be created with:
      """json
      {
        "version": "1.0",
        "export_id": "uuid",
        "timestamp": "2026-02-03T10:00:00Z",
        "source": {
          "host": "splunk-sh01.example.com",
          "collection": "threat_indicators",
          "app": "search",
          "owner": "nobody"
        },
        "destination": {
          "type": "aws_s3",
          "bucket": "splunk-backup",
          "prefix": "kvstore/threat_indicators/2026/02/03/"
        },
        "files": [
          {
            "name": "part-00001.json.gz",
            "size_bytes": 10485760,
            "record_count": 10000,
            "checksum": "sha256:abc123..."
          }
        ],
        "total_records": 50000,
        "total_size_bytes": 52428800,
        "checksum": "sha256:manifest-hash..."
      }
      """

  @story:cloud-manifest
  @priority:medium
  Scenario: Validate manifest on import
    Given I am importing from cloud storage
    When the manifest is read
    Then all file checksums should be verified
    And missing files should be reported
    And corrupted files should be flagged
    And import should fail gracefully on errors
