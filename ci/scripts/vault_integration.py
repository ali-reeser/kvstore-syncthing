#!/usr/bin/env python3
"""
Vault Integration for CI/CD Secrets Management

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: ci/scripts/vault_integration.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: CI/CD Utilities

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Vault integration for secure secrets retrieval
                                in Concourse CI pipelines. Supports token auth,
                                AppRole, and automatic token renewal.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

# Use requests for Vault API (not Splunk, so allowed)
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Vault Configuration
# =============================================================================

@dataclass
class VaultConfig:
    """Vault connection configuration"""
    url: str
    token: Optional[str] = None
    role_id: Optional[str] = None
    secret_id: Optional[str] = None
    namespace: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30

    @classmethod
    def from_environment(cls) -> "VaultConfig":
        """Load configuration from environment variables"""
        return cls(
            url=os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200"),
            token=os.environ.get("VAULT_TOKEN"),
            role_id=os.environ.get("VAULT_ROLE_ID"),
            secret_id=os.environ.get("VAULT_SECRET_ID"),
            namespace=os.environ.get("VAULT_NAMESPACE"),
            verify_ssl=os.environ.get("VAULT_SKIP_VERIFY", "").lower() != "true",
        )


# =============================================================================
# Vault Client
# =============================================================================

class VaultClient:
    """
    Vault client for secrets retrieval.

    Supports:
    - Token authentication
    - AppRole authentication
    - Automatic token renewal
    - KV v1 and v2 secrets engines
    """

    def __init__(self, config: VaultConfig):
        """
        Initialize Vault client.

        Args:
            config: Vault configuration
        """
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify_ssl

        if config.namespace:
            self.session.headers["X-Vault-Namespace"] = config.namespace

        self._token: Optional[str] = config.token
        self._token_ttl: int = 0

    def authenticate(self) -> bool:
        """
        Authenticate to Vault.

        Uses token if provided, otherwise tries AppRole.

        Returns:
            True if authentication successful
        """
        if self._token:
            # Verify token is valid
            return self._verify_token()

        if self.config.role_id and self.config.secret_id:
            return self._approle_login()

        logger.error("No authentication method available")
        return False

    def _verify_token(self) -> bool:
        """Verify current token is valid"""
        try:
            response = self._request("GET", "/v1/auth/token/lookup-self")
            if response.status_code == 200:
                data = response.json()
                self._token_ttl = data.get("data", {}).get("ttl", 0)
                logger.info(f"Token valid, TTL: {self._token_ttl}s")
                return True
            return False
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return False

    def _approle_login(self) -> bool:
        """Authenticate using AppRole"""
        try:
            response = self.session.post(
                urljoin(self.config.url, "/v1/auth/approle/login"),
                json={
                    "role_id": self.config.role_id,
                    "secret_id": self.config.secret_id,
                },
                timeout=self.config.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data["auth"]["client_token"]
                self._token_ttl = data["auth"]["lease_duration"]
                logger.info(f"AppRole login successful, TTL: {self._token_ttl}s")
                return True

            logger.error(f"AppRole login failed: {response.text}")
            return False

        except Exception as e:
            logger.error(f"AppRole login error: {e}")
            return False

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make authenticated request to Vault"""
        headers = kwargs.pop("headers", {})
        if self._token:
            headers["X-Vault-Token"] = self._token

        return self.session.request(
            method,
            urljoin(self.config.url, path),
            headers=headers,
            timeout=self.config.timeout,
            **kwargs,
        )

    def renew_token(self) -> bool:
        """Renew the current token"""
        try:
            response = self._request("POST", "/v1/auth/token/renew-self")
            if response.status_code == 200:
                data = response.json()
                self._token_ttl = data.get("auth", {}).get("lease_duration", 0)
                logger.info(f"Token renewed, new TTL: {self._token_ttl}s")
                return True
            return False
        except Exception as e:
            logger.error(f"Token renewal failed: {e}")
            return False

    def read_secret(self, path: str, version: int = 2) -> Optional[Dict[str, Any]]:
        """
        Read a secret from Vault.

        Args:
            path: Secret path (e.g., "secret/kvstore-syncthing/splunk-dev")
            version: KV secrets engine version (1 or 2)

        Returns:
            Secret data or None
        """
        try:
            if version == 2:
                # KV v2 has /data/ in path
                parts = path.split("/", 1)
                if len(parts) == 2:
                    api_path = f"/v1/{parts[0]}/data/{parts[1]}"
                else:
                    api_path = f"/v1/{path}"
            else:
                api_path = f"/v1/{path}"

            response = self._request("GET", api_path)

            if response.status_code == 200:
                data = response.json()
                if version == 2:
                    return data.get("data", {}).get("data", {})
                return data.get("data", {})

            elif response.status_code == 404:
                logger.warning(f"Secret not found: {path}")
                return None

            else:
                logger.error(f"Failed to read secret: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error reading secret: {e}")
            return None

    def read_secrets_batch(self, paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Read multiple secrets.

        Args:
            paths: List of secret paths

        Returns:
            Dict mapping paths to secret data
        """
        results = {}
        for path in paths:
            secret = self.read_secret(path)
            if secret:
                results[path] = secret
        return results


# =============================================================================
# Secrets Manager for CI/CD
# =============================================================================

class CISecretsManager:
    """
    Manages secrets for CI/CD pipelines.

    Features:
    - Load secrets from Vault
    - Export as environment variables
    - Mask secrets in logs
    - Validate required secrets
    """

    # Paths for KVStore Syncthing secrets
    SECRET_PATHS = {
        "splunk_dev": "secret/kvstore-syncthing/splunk-dev",
        "splunk_staging": "secret/kvstore-syncthing/splunk-staging",
        "splunk_prod": "secret/kvstore-syncthing/splunk-prod",
        "mongodb": "secret/kvstore-syncthing/mongodb",
        "aws": "secret/kvstore-syncthing/aws",
        "github": "secret/kvstore-syncthing/github",
    }

    # Required keys for each secret
    REQUIRED_KEYS = {
        "splunk_dev": ["host", "port", "token"],
        "splunk_staging": ["host", "port", "token"],
        "splunk_prod": ["host", "port", "token"],
        "mongodb": ["host", "port", "username", "password"],
        "aws": ["access_key", "secret_key", "region"],
        "github": ["access_token"],
    }

    def __init__(self, vault_client: VaultClient):
        """
        Initialize secrets manager.

        Args:
            vault_client: Authenticated Vault client
        """
        self.vault = vault_client
        self.secrets: Dict[str, Dict[str, Any]] = {}
        self._masked_values: set = set()

    def load_secrets(self, secret_names: Optional[List[str]] = None) -> bool:
        """
        Load secrets from Vault.

        Args:
            secret_names: Specific secrets to load, or None for all

        Returns:
            True if all secrets loaded successfully
        """
        names = secret_names or list(self.SECRET_PATHS.keys())
        success = True

        for name in names:
            path = self.SECRET_PATHS.get(name)
            if not path:
                logger.warning(f"Unknown secret: {name}")
                continue

            secret = self.vault.read_secret(path)
            if secret:
                self.secrets[name] = secret
                # Track values for masking
                for value in secret.values():
                    if isinstance(value, str) and len(value) > 3:
                        self._masked_values.add(value)
                logger.info(f"Loaded secret: {name}")
            else:
                logger.error(f"Failed to load secret: {name}")
                success = False

        return success

    def validate_secrets(self, secret_names: Optional[List[str]] = None) -> List[str]:
        """
        Validate that required keys are present.

        Args:
            secret_names: Specific secrets to validate, or None for all

        Returns:
            List of validation errors
        """
        names = secret_names or list(self.secrets.keys())
        errors = []

        for name in names:
            if name not in self.secrets:
                errors.append(f"Secret '{name}' not loaded")
                continue

            required = self.REQUIRED_KEYS.get(name, [])
            secret = self.secrets[name]

            for key in required:
                if key not in secret or not secret[key]:
                    errors.append(f"Secret '{name}' missing required key: {key}")

        return errors

    def export_to_environment(self, secret_name: str, prefix: str = "") -> Dict[str, str]:
        """
        Export secret to environment variables.

        Args:
            secret_name: Name of secret to export
            prefix: Prefix for environment variable names

        Returns:
            Dict of exported variables
        """
        if secret_name not in self.secrets:
            logger.error(f"Secret not loaded: {secret_name}")
            return {}

        exported = {}
        secret = self.secrets[secret_name]

        for key, value in secret.items():
            if value is not None:
                env_name = f"{prefix}{key.upper()}" if prefix else key.upper()
                os.environ[env_name] = str(value)
                exported[env_name] = str(value)
                logger.info(f"Exported: {env_name}=***")

        return exported

    def get_value(self, secret_name: str, key: str) -> Optional[str]:
        """
        Get a specific secret value.

        Args:
            secret_name: Name of secret
            key: Key within secret

        Returns:
            Secret value or None
        """
        secret = self.secrets.get(secret_name, {})
        return secret.get(key)

    def mask_string(self, text: str) -> str:
        """
        Mask secret values in a string.

        Args:
            text: Text to mask

        Returns:
            Text with secrets replaced by ***
        """
        result = text
        for value in self._masked_values:
            if value in result:
                result = result.replace(value, "***")
        return result

    def write_env_file(self, filepath: str, secret_names: Optional[List[str]] = None):
        """
        Write secrets to a .env file for local development.

        Args:
            filepath: Path to write .env file
            secret_names: Specific secrets to include
        """
        names = secret_names or list(self.secrets.keys())

        with open(filepath, "w") as f:
            f.write("# Auto-generated secrets - DO NOT COMMIT\n")
            f.write("# Generated by vault_integration.py\n\n")

            for name in names:
                if name not in self.secrets:
                    continue

                f.write(f"# {name}\n")
                secret = self.secrets[name]

                for key, value in secret.items():
                    if value is not None:
                        env_name = f"{name.upper()}_{key.upper()}"
                        f.write(f"{env_name}={value}\n")

                f.write("\n")

        logger.info(f"Wrote env file: {filepath}")


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """CLI entry point for Vault operations"""
    import argparse

    parser = argparse.ArgumentParser(description="Vault secrets management for CI/CD")
    parser.add_argument("action", choices=["load", "export", "validate", "env-file"])
    parser.add_argument("--secrets", nargs="+", help="Specific secrets to process")
    parser.add_argument("--prefix", default="", help="Environment variable prefix")
    parser.add_argument("--env-file", default=".env.secrets", help="Output .env file path")
    parser.add_argument("--output", choices=["json", "env", "masked"], default="masked")

    args = parser.parse_args()

    # Initialize Vault client
    config = VaultConfig.from_environment()
    client = VaultClient(config)

    if not client.authenticate():
        logger.error("Vault authentication failed")
        sys.exit(1)

    # Initialize secrets manager
    manager = CISecretsManager(client)

    # Execute action
    if args.action == "load":
        if manager.load_secrets(args.secrets):
            if args.output == "json":
                # Output JSON (masked)
                masked = {
                    name: {k: "***" for k in secret.keys()}
                    for name, secret in manager.secrets.items()
                }
                print(json.dumps(masked, indent=2))
            else:
                print("Secrets loaded successfully")
        else:
            sys.exit(1)

    elif args.action == "validate":
        if not manager.load_secrets(args.secrets):
            sys.exit(1)

        errors = manager.validate_secrets(args.secrets)
        if errors:
            for error in errors:
                logger.error(error)
            sys.exit(1)
        print("All secrets valid")

    elif args.action == "export":
        if not manager.load_secrets(args.secrets):
            sys.exit(1)

        for name in args.secrets or manager.secrets.keys():
            manager.export_to_environment(name, args.prefix)

        print("Secrets exported to environment")

    elif args.action == "env-file":
        if not manager.load_secrets(args.secrets):
            sys.exit(1)

        manager.write_env_file(args.env_file, args.secrets)


if __name__ == "__main__":
    main()
