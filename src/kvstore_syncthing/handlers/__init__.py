"""
Sync Handlers Package

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/__init__.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Package Initialization

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Initial package structure
2026-02-03  Claude/AI   UPDATE  Added cloud storage, HEC, file export,
                                and threat distribution handlers
-------------------------------------------------------------------------------
===============================================================================
"""

# Core handlers
from .base import BaseSyncHandler, DestinationConfig
from .rest import RESTSyncHandler
from .mongodb import MongoDBSyncHandler
from .factory import HandlerFactory

# HEC handler for Index & Rehydrate pattern
from .hec import (
    HECConfig,
    HECHandler,
    HECSyncHandler,
    RehydrationConfig,
    RehydrationHandler,
)

# File export for offline sync
from .file_export import (
    FileExportConfig,
    FileExportHandler,
    ExportPackage,
)

# Multi-cloud storage
from .cloud_storage import (
    CloudStorageConfig,
    CloudStorageHandler,
    S3Provider,
    AzureBlobProvider,
    GCSProvider,
    ExportManifest,
)

# Threat intelligence distribution
from .threat_distribution import (
    DistributionConfig,
    ThreatDistributionHandler,
    ThreatFeedIngester,
    FeedConfig,
    OutputFormat,
    IndicatorType,
    AuthType,
)

__all__ = [
    # Core
    "BaseSyncHandler",
    "DestinationConfig",
    "RESTSyncHandler",
    "MongoDBSyncHandler",
    "HandlerFactory",
    # HEC
    "HECConfig",
    "HECHandler",
    "HECSyncHandler",
    "RehydrationConfig",
    "RehydrationHandler",
    # File Export
    "FileExportConfig",
    "FileExportHandler",
    "ExportPackage",
    # Cloud Storage
    "CloudStorageConfig",
    "CloudStorageHandler",
    "S3Provider",
    "AzureBlobProvider",
    "GCSProvider",
    "ExportManifest",
    # Threat Distribution
    "DistributionConfig",
    "ThreatDistributionHandler",
    "ThreatFeedIngester",
    "FeedConfig",
    "OutputFormat",
    "IndicatorType",
    "AuthType",
]
