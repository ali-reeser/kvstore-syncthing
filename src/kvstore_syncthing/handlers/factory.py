"""
Handler Factory - Creates handlers based on destination type

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/factory.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Handler factory for creating appropriate
                                sync handlers based on destination type.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

from typing import Dict, Type

from .base import BaseSyncHandler, DestinationConfig
from .rest import RESTSyncHandler, RESTDestinationConfig
from .mongodb import MongoDBSyncHandler, MongoDBDestinationConfig


class HandlerFactory:
    """
    Factory for creating sync handlers.

    Maps destination types to handler implementations and
    creates configured handler instances.
    """

    HANDLER_TYPES: Dict[str, Type[BaseSyncHandler]] = {
        "splunk_rest": RESTSyncHandler,
        "mongodb_direct": MongoDBSyncHandler,
    }

    CONFIG_TYPES: Dict[str, Type[DestinationConfig]] = {
        "splunk_rest": RESTDestinationConfig,
        "mongodb_direct": MongoDBDestinationConfig,
    }

    @classmethod
    def create(cls, destination_type: str, config: Dict) -> BaseSyncHandler:
        """
        Create a handler for the given destination type.

        Args:
            destination_type: Type of destination (e.g., "splunk_rest")
            config: Configuration dictionary

        Returns:
            Configured handler instance

        Raises:
            ValueError: If destination type is unknown
        """
        if destination_type not in cls.HANDLER_TYPES:
            raise ValueError(f"Unknown destination type: {destination_type}")

        handler_class = cls.HANDLER_TYPES[destination_type]
        config_class = cls.CONFIG_TYPES[destination_type]

        # Build configuration object
        dest_config = config_class(
            name=config.get("name", ""),
            destination_type=destination_type,
            host=config.get("host", ""),
            port=config.get("port", config_class.port if hasattr(config_class, "port") else 8089),
            use_ssl=config.get("use_ssl", True),
            verify_ssl=config.get("verify_ssl", False),
            auth_type=config.get("auth_type", "token"),
            username=config.get("username"),
            password=config.get("password"),
            connection_timeout=config.get("connection_timeout", 30),
            read_timeout=config.get("read_timeout", 60),
            max_retries=config.get("max_retries", 3),
            target_app=config.get("target_app", "search"),
            target_owner=config.get("target_owner", "nobody"),
        )

        # Add type-specific configuration
        if destination_type == "mongodb_direct":
            dest_config.database = config.get("database", "splunk")
            dest_config.auth_source = config.get("auth_source", "admin")
            dest_config.replica_set = config.get("replica_set")

        return handler_class(dest_config)

    @classmethod
    def get_supported_types(cls) -> list:
        """Get list of supported destination types"""
        return list(cls.HANDLER_TYPES.keys())

    @classmethod
    def register_handler(cls, destination_type: str,
                        handler_class: Type[BaseSyncHandler],
                        config_class: Type[DestinationConfig]):
        """
        Register a new handler type.

        Args:
            destination_type: Type identifier
            handler_class: Handler implementation class
            config_class: Configuration class
        """
        cls.HANDLER_TYPES[destination_type] = handler_class
        cls.CONFIG_TYPES[destination_type] = config_class
