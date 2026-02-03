"""
KVStore Syncthing - Enterprise KVStore Synchronization for Splunk

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/__init__.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Package Initialization

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Main package initialization with version
                                and public API exports.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

__version__ = "1.0.0"
__author__ = "KVStore Syncthing Contributors"
__license__ = "MIT"

from .sync_engine import SyncEngine, SyncResult, SyncMode
from .handlers.base import BaseSyncHandler

__all__ = [
    "SyncEngine",
    "SyncResult",
    "SyncMode",
    "BaseSyncHandler",
    "__version__",
]
