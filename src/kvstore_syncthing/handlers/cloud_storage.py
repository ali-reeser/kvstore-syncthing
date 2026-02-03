"""
Multi-Cloud Storage Handler - AWS S3, MinIO, Wasabi, Azure, GCP

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/cloud_storage.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Multi-cloud storage handler supporting:
                                - AWS S3 (native)
                                - MinIO (S3-compatible)
                                - Wasabi (S3-compatible)
                                - Azure Blob Storage
                                - Google Cloud Storage
                                Uses official SDKs: boto3, azure-storage-blob,
                                google-cloud-storage
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import gzip
import hashlib
import io
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, BinaryIO, Dict, Generator, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# =============================================================================
# SDK Imports - Official Cloud Provider SDKs
# =============================================================================

# AWS S3 / S3-Compatible (MinIO, Wasabi)
try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None

# Azure Blob Storage
try:
    from azure.storage.blob import (
        BlobServiceClient,
        ContainerClient,
        BlobClient,
        ContentSettings,
    )
    from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
    from azure.core.exceptions import AzureError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

# Google Cloud Storage
try:
    from google.cloud import storage as gcs
    from google.oauth2 import service_account
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False


# =============================================================================
# Cloud Storage Configuration
# =============================================================================

@dataclass
class CloudStorageConfig:
    """Base configuration for cloud storage destinations"""
    name: str
    provider: str  # aws_s3, minio, wasabi, azure_blob, gcs, s3_compatible
    bucket: str
    prefix: str = "kvstore/"

    # Credentials (encrypted via UCC)
    access_key: Optional[str] = None
    secret_key: Optional[str] = None

    # AWS-specific
    region: str = "us-east-1"
    endpoint_url: Optional[str] = None  # For S3-compatible
    use_path_style: bool = False
    assume_role_arn: Optional[str] = None

    # Azure-specific
    storage_account: Optional[str] = None
    connection_string: Optional[str] = None
    sas_token: Optional[str] = None
    use_managed_identity: bool = False
    access_tier: str = "Hot"  # Hot, Cool, Archive

    # GCS-specific
    project_id: Optional[str] = None
    service_account_json: Optional[str] = None
    use_workload_identity: bool = False
    storage_class: str = "STANDARD"

    # Common settings
    server_side_encryption: Optional[str] = None  # AES256, aws:kms, etc.
    kms_key_id: Optional[str] = None
    custom_ca_bundle: Optional[str] = None
    verify_ssl: bool = True

    # Export settings
    compression: str = "gzip"  # none, gzip
    file_format: str = "json"  # json, csv
    max_file_size_mb: int = 100
    multipart_threshold_mb: int = 50
    multipart_chunksize_mb: int = 10


@dataclass
class ExportManifest:
    """Manifest for exported data"""
    version: str = "1.0"
    export_id: str = ""
    timestamp: str = ""
    source: Dict[str, str] = field(default_factory=dict)
    destination: Dict[str, str] = field(default_factory=dict)
    files: List[Dict[str, Any]] = field(default_factory=list)
    total_records: int = 0
    total_size_bytes: int = 0
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "export_id": self.export_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "destination": self.destination,
            "files": self.files,
            "total_records": self.total_records,
            "total_size_bytes": self.total_size_bytes,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportManifest":
        return cls(**data)


# =============================================================================
# Abstract Cloud Storage Provider
# =============================================================================

class CloudStorageProvider(ABC):
    """Abstract base class for cloud storage providers"""

    def __init__(self, config: CloudStorageConfig):
        self.config = config
        self._client = None

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to cloud storage"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection"""
        pass

    @abstractmethod
    def upload_file(self, local_path: str, remote_key: str,
                    metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload a file to cloud storage"""
        pass

    @abstractmethod
    def upload_bytes(self, data: bytes, remote_key: str,
                     metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload bytes to cloud storage"""
        pass

    @abstractmethod
    def download_file(self, remote_key: str, local_path: str) -> bool:
        """Download a file from cloud storage"""
        pass

    @abstractmethod
    def download_bytes(self, remote_key: str) -> Optional[bytes]:
        """Download bytes from cloud storage"""
        pass

    @abstractmethod
    def list_objects(self, prefix: str) -> Generator[Dict[str, Any], None, None]:
        """List objects with given prefix"""
        pass

    @abstractmethod
    def delete_object(self, remote_key: str) -> bool:
        """Delete an object"""
        pass

    @abstractmethod
    def object_exists(self, remote_key: str) -> bool:
        """Check if object exists"""
        pass

    def get_checksum(self, data: bytes) -> str:
        """Calculate SHA-256 checksum"""
        return f"sha256:{hashlib.sha256(data).hexdigest()}"


# =============================================================================
# AWS S3 / S3-Compatible Provider
# =============================================================================

class S3Provider(CloudStorageProvider):
    """
    Provider for AWS S3 and S3-compatible storage.

    Supports:
    - AWS S3 (native)
    - MinIO
    - Wasabi
    - DigitalOcean Spaces
    - Backblaze B2
    - Cloudflare R2
    - Ceph RadosGW
    """

    # Known S3-compatible endpoints
    PROVIDER_ENDPOINTS = {
        "minio": None,  # User-provided
        "wasabi": "https://s3.{region}.wasabisys.com",
        "digitalocean": "https://{region}.digitaloceanspaces.com",
        "backblaze": "https://s3.{region}.backblazeb2.com",
        "cloudflare_r2": "https://{account_id}.r2.cloudflarestorage.com",
    }

    def __init__(self, config: CloudStorageConfig):
        super().__init__(config)

        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3 storage. Install with: pip install boto3"
            )

        self._s3_client = None
        self._s3_resource = None

    def connect(self) -> bool:
        """Connect to S3 or S3-compatible storage"""
        try:
            # Build boto3 config
            boto_config = BotoConfig(
                signature_version='s3v4',
                s3={'addressing_style': 'path' if self.config.use_path_style else 'auto'},
            )

            # Session kwargs
            session_kwargs = {}
            if self.config.access_key and self.config.secret_key:
                session_kwargs['aws_access_key_id'] = self.config.access_key
                session_kwargs['aws_secret_access_key'] = self.config.secret_key

            # Determine endpoint URL
            endpoint_url = self._get_endpoint_url()

            # Client kwargs
            client_kwargs = {
                'config': boto_config,
                'region_name': self.config.region,
            }

            if endpoint_url:
                client_kwargs['endpoint_url'] = endpoint_url

            if not self.config.verify_ssl:
                client_kwargs['verify'] = False
            elif self.config.custom_ca_bundle:
                client_kwargs['verify'] = self.config.custom_ca_bundle

            # Handle role assumption for cross-account access
            if self.config.assume_role_arn:
                sts_client = boto3.client('sts', **session_kwargs, **client_kwargs)
                assumed_role = sts_client.assume_role(
                    RoleArn=self.config.assume_role_arn,
                    RoleSessionName='kvstore-syncthing'
                )
                credentials = assumed_role['Credentials']
                session_kwargs = {
                    'aws_access_key_id': credentials['AccessKeyId'],
                    'aws_secret_access_key': credentials['SecretAccessKey'],
                    'aws_session_token': credentials['SessionToken'],
                }

            # Create client and resource
            self._s3_client = boto3.client('s3', **session_kwargs, **client_kwargs)
            self._s3_resource = boto3.resource('s3', **session_kwargs, **client_kwargs)

            # Verify connection by listing bucket
            self._s3_client.head_bucket(Bucket=self.config.bucket)

            logger.info(f"Connected to S3: {self.config.bucket} "
                       f"(provider: {self.config.provider})")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to S3: {e}")
            return False

    def _get_endpoint_url(self) -> Optional[str]:
        """Get endpoint URL for provider"""
        if self.config.endpoint_url:
            return self.config.endpoint_url

        provider = self.config.provider.lower()
        if provider in self.PROVIDER_ENDPOINTS:
            template = self.PROVIDER_ENDPOINTS[provider]
            if template:
                return template.format(
                    region=self.config.region,
                    account_id=self.config.access_key,  # For R2
                )

        return None  # Use default AWS endpoint

    def disconnect(self) -> None:
        """Close S3 connection"""
        self._s3_client = None
        self._s3_resource = None

    def upload_file(self, local_path: str, remote_key: str,
                    metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload file to S3"""
        try:
            extra_args = self._build_extra_args(metadata)

            # Use multipart for large files
            file_size = os.path.getsize(local_path)
            threshold = self.config.multipart_threshold_mb * 1024 * 1024

            if file_size > threshold:
                # Multipart upload
                from boto3.s3.transfer import TransferConfig
                transfer_config = TransferConfig(
                    multipart_threshold=threshold,
                    multipart_chunksize=self.config.multipart_chunksize_mb * 1024 * 1024,
                )
                self._s3_client.upload_file(
                    local_path, self.config.bucket, remote_key,
                    ExtraArgs=extra_args,
                    Config=transfer_config
                )
            else:
                self._s3_client.upload_file(
                    local_path, self.config.bucket, remote_key,
                    ExtraArgs=extra_args
                )

            logger.info(f"Uploaded to S3: {remote_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return False

    def upload_bytes(self, data: bytes, remote_key: str,
                     metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload bytes to S3"""
        try:
            extra_args = self._build_extra_args(metadata)

            self._s3_client.put_object(
                Bucket=self.config.bucket,
                Key=remote_key,
                Body=data,
                **extra_args
            )

            logger.info(f"Uploaded bytes to S3: {remote_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload bytes to S3: {e}")
            return False

    def _build_extra_args(self, metadata: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Build extra arguments for S3 operations"""
        extra_args = {}

        if metadata:
            extra_args['Metadata'] = metadata

        if self.config.server_side_encryption:
            if self.config.server_side_encryption.lower() == 'aws:kms':
                extra_args['ServerSideEncryption'] = 'aws:kms'
                if self.config.kms_key_id:
                    extra_args['SSEKMSKeyId'] = self.config.kms_key_id
            else:
                extra_args['ServerSideEncryption'] = 'AES256'

        return extra_args

    def download_file(self, remote_key: str, local_path: str) -> bool:
        """Download file from S3"""
        try:
            self._s3_client.download_file(
                self.config.bucket, remote_key, local_path
            )
            logger.info(f"Downloaded from S3: {remote_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}")
            return False

    def download_bytes(self, remote_key: str) -> Optional[bytes]:
        """Download bytes from S3"""
        try:
            response = self._s3_client.get_object(
                Bucket=self.config.bucket,
                Key=remote_key
            )
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Failed to download bytes from S3: {e}")
            return None

    def list_objects(self, prefix: str) -> Generator[Dict[str, Any], None, None]:
        """List objects with prefix"""
        try:
            paginator = self._s3_client.get_paginator('list_objects_v2')

            for page in paginator.paginate(Bucket=self.config.bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    yield {
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'etag': obj['ETag'].strip('"'),
                    }
        except Exception as e:
            logger.error(f"Failed to list S3 objects: {e}")

    def delete_object(self, remote_key: str) -> bool:
        """Delete object from S3"""
        try:
            self._s3_client.delete_object(Bucket=self.config.bucket, Key=remote_key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete from S3: {e}")
            return False

    def object_exists(self, remote_key: str) -> bool:
        """Check if object exists in S3"""
        try:
            self._s3_client.head_object(Bucket=self.config.bucket, Key=remote_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise


# =============================================================================
# Azure Blob Storage Provider
# =============================================================================

class AzureBlobProvider(CloudStorageProvider):
    """Provider for Azure Blob Storage"""

    def __init__(self, config: CloudStorageConfig):
        super().__init__(config)

        if not AZURE_AVAILABLE:
            raise ImportError(
                "azure-storage-blob is required. Install with: "
                "pip install azure-storage-blob azure-identity"
            )

        self._blob_service: Optional[BlobServiceClient] = None
        self._container_client: Optional[ContainerClient] = None

    def connect(self) -> bool:
        """Connect to Azure Blob Storage"""
        try:
            # Determine authentication method
            if self.config.connection_string:
                self._blob_service = BlobServiceClient.from_connection_string(
                    self.config.connection_string
                )
            elif self.config.use_managed_identity:
                credential = ManagedIdentityCredential()
                account_url = f"https://{self.config.storage_account}.blob.core.windows.net"
                self._blob_service = BlobServiceClient(account_url, credential=credential)
            elif self.config.sas_token:
                account_url = f"https://{self.config.storage_account}.blob.core.windows.net"
                self._blob_service = BlobServiceClient(
                    account_url,
                    credential=self.config.sas_token
                )
            elif self.config.access_key:
                account_url = f"https://{self.config.storage_account}.blob.core.windows.net"
                self._blob_service = BlobServiceClient(
                    account_url,
                    credential=self.config.access_key
                )
            else:
                # Try default Azure credential
                credential = DefaultAzureCredential()
                account_url = f"https://{self.config.storage_account}.blob.core.windows.net"
                self._blob_service = BlobServiceClient(account_url, credential=credential)

            # Get container client
            self._container_client = self._blob_service.get_container_client(
                self.config.bucket
            )

            # Verify access
            self._container_client.get_container_properties()

            logger.info(f"Connected to Azure Blob: {self.config.bucket}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Azure Blob: {e}")
            return False

    def disconnect(self) -> None:
        """Close Azure connection"""
        self._blob_service = None
        self._container_client = None

    def upload_file(self, local_path: str, remote_key: str,
                    metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload file to Azure Blob"""
        try:
            blob_client = self._container_client.get_blob_client(remote_key)

            with open(local_path, 'rb') as f:
                blob_client.upload_blob(
                    f,
                    overwrite=True,
                    metadata=metadata,
                    standard_blob_tier=self.config.access_tier
                )

            logger.info(f"Uploaded to Azure Blob: {remote_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload to Azure Blob: {e}")
            return False

    def upload_bytes(self, data: bytes, remote_key: str,
                     metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload bytes to Azure Blob"""
        try:
            blob_client = self._container_client.get_blob_client(remote_key)

            blob_client.upload_blob(
                data,
                overwrite=True,
                metadata=metadata,
                standard_blob_tier=self.config.access_tier
            )

            logger.info(f"Uploaded bytes to Azure Blob: {remote_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload bytes to Azure Blob: {e}")
            return False

    def download_file(self, remote_key: str, local_path: str) -> bool:
        """Download file from Azure Blob"""
        try:
            blob_client = self._container_client.get_blob_client(remote_key)

            with open(local_path, 'wb') as f:
                download_stream = blob_client.download_blob()
                f.write(download_stream.readall())

            logger.info(f"Downloaded from Azure Blob: {remote_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to download from Azure Blob: {e}")
            return False

    def download_bytes(self, remote_key: str) -> Optional[bytes]:
        """Download bytes from Azure Blob"""
        try:
            blob_client = self._container_client.get_blob_client(remote_key)
            download_stream = blob_client.download_blob()
            return download_stream.readall()
        except Exception as e:
            logger.error(f"Failed to download bytes from Azure Blob: {e}")
            return None

    def list_objects(self, prefix: str) -> Generator[Dict[str, Any], None, None]:
        """List blobs with prefix"""
        try:
            blobs = self._container_client.list_blobs(name_starts_with=prefix)
            for blob in blobs:
                yield {
                    'key': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified.isoformat(),
                    'etag': blob.etag.strip('"') if blob.etag else '',
                }
        except Exception as e:
            logger.error(f"Failed to list Azure blobs: {e}")

    def delete_object(self, remote_key: str) -> bool:
        """Delete blob"""
        try:
            blob_client = self._container_client.get_blob_client(remote_key)
            blob_client.delete_blob()
            return True
        except Exception as e:
            logger.error(f"Failed to delete Azure blob: {e}")
            return False

    def object_exists(self, remote_key: str) -> bool:
        """Check if blob exists"""
        try:
            blob_client = self._container_client.get_blob_client(remote_key)
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False


# =============================================================================
# Google Cloud Storage Provider
# =============================================================================

class GCSProvider(CloudStorageProvider):
    """Provider for Google Cloud Storage"""

    def __init__(self, config: CloudStorageConfig):
        super().__init__(config)

        if not GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage is required. Install with: "
                "pip install google-cloud-storage"
            )

        self._storage_client = None
        self._bucket = None

    def connect(self) -> bool:
        """Connect to Google Cloud Storage"""
        try:
            # Determine authentication method
            if self.config.service_account_json:
                # Service account key provided
                if os.path.isfile(self.config.service_account_json):
                    credentials = service_account.Credentials.from_service_account_file(
                        self.config.service_account_json
                    )
                else:
                    # Assume it's JSON string
                    import json
                    sa_info = json.loads(self.config.service_account_json)
                    credentials = service_account.Credentials.from_service_account_info(
                        sa_info
                    )
                self._storage_client = gcs.Client(
                    credentials=credentials,
                    project=self.config.project_id
                )
            else:
                # Use default credentials (ADC, Workload Identity, etc.)
                self._storage_client = gcs.Client(project=self.config.project_id)

            # Get bucket
            self._bucket = self._storage_client.bucket(self.config.bucket)

            # Verify access
            self._bucket.reload()

            logger.info(f"Connected to GCS: {self.config.bucket}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to GCS: {e}")
            return False

    def disconnect(self) -> None:
        """Close GCS connection"""
        self._storage_client = None
        self._bucket = None

    def upload_file(self, local_path: str, remote_key: str,
                    metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload file to GCS"""
        try:
            blob = self._bucket.blob(remote_key)

            if metadata:
                blob.metadata = metadata

            blob.upload_from_filename(local_path)

            # Set storage class if not default
            if self.config.storage_class != "STANDARD":
                blob.update_storage_class(self.config.storage_class)

            logger.info(f"Uploaded to GCS: {remote_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            return False

    def upload_bytes(self, data: bytes, remote_key: str,
                     metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload bytes to GCS"""
        try:
            blob = self._bucket.blob(remote_key)

            if metadata:
                blob.metadata = metadata

            blob.upload_from_string(data)

            logger.info(f"Uploaded bytes to GCS: {remote_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload bytes to GCS: {e}")
            return False

    def download_file(self, remote_key: str, local_path: str) -> bool:
        """Download file from GCS"""
        try:
            blob = self._bucket.blob(remote_key)
            blob.download_to_filename(local_path)
            logger.info(f"Downloaded from GCS: {remote_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to download from GCS: {e}")
            return False

    def download_bytes(self, remote_key: str) -> Optional[bytes]:
        """Download bytes from GCS"""
        try:
            blob = self._bucket.blob(remote_key)
            return blob.download_as_bytes()
        except Exception as e:
            logger.error(f"Failed to download bytes from GCS: {e}")
            return None

    def list_objects(self, prefix: str) -> Generator[Dict[str, Any], None, None]:
        """List objects with prefix"""
        try:
            blobs = self._storage_client.list_blobs(self._bucket, prefix=prefix)
            for blob in blobs:
                yield {
                    'key': blob.name,
                    'size': blob.size,
                    'last_modified': blob.updated.isoformat() if blob.updated else '',
                    'etag': blob.etag or '',
                }
        except Exception as e:
            logger.error(f"Failed to list GCS objects: {e}")

    def delete_object(self, remote_key: str) -> bool:
        """Delete object from GCS"""
        try:
            blob = self._bucket.blob(remote_key)
            blob.delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete from GCS: {e}")
            return False

    def object_exists(self, remote_key: str) -> bool:
        """Check if object exists in GCS"""
        blob = self._bucket.blob(remote_key)
        return blob.exists()


# =============================================================================
# Cloud Storage Handler (Main Interface)
# =============================================================================

class CloudStorageHandler:
    """
    Main handler for cloud storage operations.

    Provides a unified interface for all supported cloud storage providers.
    """

    PROVIDERS = {
        'aws_s3': S3Provider,
        's3': S3Provider,
        'minio': S3Provider,
        'wasabi': S3Provider,
        'digitalocean': S3Provider,
        'backblaze': S3Provider,
        'cloudflare_r2': S3Provider,
        's3_compatible': S3Provider,
        'azure_blob': AzureBlobProvider,
        'azure': AzureBlobProvider,
        'gcs': GCSProvider,
        'google_cloud_storage': GCSProvider,
    }

    def __init__(self, config: CloudStorageConfig):
        """Initialize handler with configuration"""
        self.config = config
        self._provider: Optional[CloudStorageProvider] = None

        provider_class = self.PROVIDERS.get(config.provider.lower())
        if not provider_class:
            raise ValueError(f"Unknown cloud provider: {config.provider}")

        self._provider = provider_class(config)

    def connect(self) -> bool:
        """Connect to cloud storage"""
        return self._provider.connect()

    def disconnect(self) -> None:
        """Disconnect from cloud storage"""
        self._provider.disconnect()

    def export_collection(
        self,
        records: List[Dict[str, Any]],
        collection: str,
        app: str,
        owner: str,
        host: str = "unknown"
    ) -> Tuple[bool, Optional[ExportManifest]]:
        """
        Export a KVStore collection to cloud storage.

        Args:
            records: Records to export
            collection: Collection name
            app: Splunk app
            owner: Splunk owner
            host: Source host

        Returns:
            Tuple of (success, manifest)
        """
        import uuid

        export_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        date_path = timestamp.strftime("%Y/%m/%d")

        # Build export path
        prefix = f"{self.config.prefix}{collection}/{date_path}/{export_id}/"

        # Initialize manifest
        manifest = ExportManifest(
            export_id=export_id,
            timestamp=timestamp_str,
            source={
                "host": host,
                "collection": collection,
                "app": app,
                "owner": owner,
            },
            destination={
                "type": self.config.provider,
                "bucket": self.config.bucket,
                "prefix": prefix,
            },
        )

        try:
            # Split records into files if needed
            max_records_per_file = 10000
            files_data = []

            for i in range(0, len(records), max_records_per_file):
                chunk = records[i:i + max_records_per_file]
                part_num = (i // max_records_per_file) + 1
                files_data.append((part_num, chunk))

            total_size = 0

            for part_num, chunk in files_data:
                # Serialize data
                if self.config.file_format == 'json':
                    data_str = json.dumps(chunk, indent=None, separators=(',', ':'))
                    content_type = 'application/json'
                else:
                    # CSV format
                    import csv
                    output = io.StringIO()
                    if chunk:
                        writer = csv.DictWriter(output, fieldnames=chunk[0].keys())
                        writer.writeheader()
                        writer.writerows(chunk)
                    data_str = output.getvalue()
                    content_type = 'text/csv'

                data_bytes = data_str.encode('utf-8')

                # Compress if configured
                if self.config.compression == 'gzip':
                    data_bytes = gzip.compress(data_bytes)
                    ext = f'.{self.config.file_format}.gz'
                else:
                    ext = f'.{self.config.file_format}'

                # Build filename
                filename = f"part-{part_num:05d}{ext}"
                remote_key = f"{prefix}{filename}"

                # Calculate checksum
                checksum = self._provider.get_checksum(data_bytes)

                # Upload
                if not self._provider.upload_bytes(data_bytes, remote_key):
                    return False, None

                # Record in manifest
                manifest.files.append({
                    "name": filename,
                    "size_bytes": len(data_bytes),
                    "record_count": len(chunk),
                    "checksum": checksum,
                })

                total_size += len(data_bytes)

            # Update manifest totals
            manifest.total_records = len(records)
            manifest.total_size_bytes = total_size

            # Calculate manifest checksum
            manifest_data = json.dumps(manifest.to_dict(), sort_keys=True)
            manifest.checksum = self._provider.get_checksum(manifest_data.encode())

            # Upload manifest
            manifest_json = json.dumps(manifest.to_dict(), indent=2)
            manifest_key = f"{prefix}manifest.json"

            if not self._provider.upload_bytes(manifest_json.encode(), manifest_key):
                return False, None

            logger.info(f"Exported {len(records)} records to {self.config.provider}://"
                       f"{self.config.bucket}/{prefix}")

            return True, manifest

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False, None

    def import_collection(
        self,
        prefix: str
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[ExportManifest]]:
        """
        Import a collection from cloud storage.

        Args:
            prefix: Path prefix to import from

        Returns:
            Tuple of (success, records, manifest)
        """
        try:
            # Download manifest
            manifest_key = f"{prefix}manifest.json"
            manifest_bytes = self._provider.download_bytes(manifest_key)

            if not manifest_bytes:
                logger.error("Manifest not found")
                return False, [], None

            manifest_data = json.loads(manifest_bytes.decode('utf-8'))
            manifest = ExportManifest.from_dict(manifest_data)

            # Download and verify each file
            all_records = []

            for file_info in manifest.files:
                file_key = f"{prefix}{file_info['name']}"

                # Download
                file_bytes = self._provider.download_bytes(file_key)
                if not file_bytes:
                    logger.error(f"Failed to download: {file_info['name']}")
                    return False, [], manifest

                # Verify checksum
                actual_checksum = self._provider.get_checksum(file_bytes)
                if actual_checksum != file_info['checksum']:
                    logger.error(f"Checksum mismatch for {file_info['name']}")
                    return False, [], manifest

                # Decompress if needed
                if file_info['name'].endswith('.gz'):
                    file_bytes = gzip.decompress(file_bytes)

                # Parse
                data_str = file_bytes.decode('utf-8')

                if file_info['name'].endswith('.json') or file_info['name'].endswith('.json.gz'):
                    records = json.loads(data_str)
                else:
                    # CSV
                    import csv
                    reader = csv.DictReader(io.StringIO(data_str))
                    records = list(reader)

                all_records.extend(records)

            logger.info(f"Imported {len(all_records)} records from {prefix}")
            return True, all_records, manifest

        except Exception as e:
            logger.error(f"Import failed: {e}")
            return False, [], None


# =============================================================================
# Factory Function
# =============================================================================

def create_cloud_storage_handler(config: CloudStorageConfig) -> CloudStorageHandler:
    """
    Factory function to create cloud storage handler.

    Args:
        config: Cloud storage configuration

    Returns:
        Configured CloudStorageHandler
    """
    return CloudStorageHandler(config)
