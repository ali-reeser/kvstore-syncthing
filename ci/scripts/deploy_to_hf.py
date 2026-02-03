#!/usr/bin/env python3
"""
Splunk Heavy Forwarder Deployment Script - REST API Based

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: ci/scripts/deploy_to_hf.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: CI/CD Deployment Script

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  REST API-based deployment script for Splunk
                                Heavy Forwarder 10.x. Uses splunk-sdk and
                                REST APIs exclusively (no SSH, no CLI).
-------------------------------------------------------------------------------

License: MIT

PURPOSE:
Deploy KVStore Syncthing app to Splunk Heavy Forwarders using REST APIs.
Supports Splunk 10.x and later. All operations performed via API - no
direct filesystem access or SSH required.

USAGE:
    python deploy_to_hf.py --host hf01.example.com --token <auth_token> \\
                           --package kvstore_syncthing.tar.gz

REQUIREMENTS:
    - splunk-sdk (pip install splunk-sdk)
    - requests (pip install requests)
    - Target HF must have REST API enabled (port 8089)
    - Valid authentication token with admin capabilities
===============================================================================
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# SDK Imports
try:
    import splunklib.client as splunk_client
    SPLUNK_SDK_AVAILABLE = True
except ImportError:
    SPLUNK_SDK_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class DeploymentConfig:
    """Configuration for HF deployment"""
    host: str
    port: int = 8089
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: bool = True
    verify_ssl: bool = False

    # App settings
    app_name: str = "kvstore_syncthing"
    app_package: str = ""

    # Deployment options
    update_if_exists: bool = True
    restart_required: bool = False
    check_for_updates: bool = True

    # Timeouts
    upload_timeout: int = 300
    restart_timeout: int = 120


# =============================================================================
# Splunk API Client for Deployment
# =============================================================================

class SplunkDeploymentClient:
    """
    Client for deploying apps to Splunk via REST API.

    Uses splunk-sdk for standard operations and requests for
    file uploads (splunk-sdk doesn't support multipart uploads).
    """

    def __init__(self, config: DeploymentConfig):
        if not SPLUNK_SDK_AVAILABLE:
            raise ImportError(
                "splunk-sdk is required. Install with: pip install splunk-sdk"
            )
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests is required. Install with: pip install requests"
            )

        self.config = config
        self._service: Optional[splunk_client.Service] = None
        self._session: Optional[requests.Session] = None

    def connect(self) -> bool:
        """Connect to Splunk using splunk-sdk"""
        try:
            connect_kwargs = {
                "host": self.config.host,
                "port": self.config.port,
                "scheme": "https" if self.config.use_ssl else "http",
            }

            if self.config.token:
                connect_kwargs["splunkToken"] = self.config.token
            elif self.config.username and self.config.password:
                connect_kwargs["username"] = self.config.username
                connect_kwargs["password"] = self.config.password
            else:
                raise ValueError("Token or username/password required")

            self._service = splunk_client.connect(**connect_kwargs)

            # Create requests session for file uploads
            self._session = requests.Session()
            self._session.verify = self.config.verify_ssl
            if self.config.token:
                self._session.headers["Authorization"] = f"Bearer {self.config.token}"

            # Verify connection
            info = self._service.info
            version = info.get("version", "unknown")
            server_name = info.get("serverName", "unknown")

            logger.info(f"Connected to {server_name} running Splunk {version}")

            # Verify it's a Heavy Forwarder or full Splunk
            instance_type = info.get("instance_type", "")
            if "forwarder" in instance_type.lower():
                logger.info(f"Instance type: {instance_type}")

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Splunk"""
        if self._service:
            try:
                self._service.logout()
            except Exception:
                pass
        self._service = None
        self._session = None

    def get_server_info(self) -> Dict[str, Any]:
        """Get detailed server information"""
        if not self._service:
            return {}

        info = self._service.info
        return {
            "version": info.get("version"),
            "build": info.get("build"),
            "server_name": info.get("serverName"),
            "instance_type": info.get("instance_type"),
            "os_name": info.get("os_name"),
            "os_version": info.get("os_version"),
            "cpu_arch": info.get("cpu_arch"),
            "guid": info.get("guid"),
            "license_state": info.get("license_state"),
        }

    def check_app_installed(self, app_name: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if an app is installed.

        Returns:
            Tuple of (is_installed, app_info)
        """
        if not self._service:
            return False, None

        try:
            apps = self._service.apps
            if app_name in apps:
                app = apps[app_name]
                return True, {
                    "name": app.name,
                    "version": app.content.get("version", "unknown"),
                    "label": app.content.get("label", ""),
                    "visible": app.content.get("visible", True),
                    "disabled": app.content.get("disabled", False),
                }
            return False, None
        except Exception as e:
            logger.error(f"Error checking app: {e}")
            return False, None

    def upload_app(
        self,
        package_path: str,
        update: bool = True
    ) -> Tuple[bool, str]:
        """
        Upload and install an app package via REST API.

        Uses /services/apps/local endpoint for installation.

        Args:
            package_path: Path to .tar.gz or .spl package
            update: Update if app already exists

        Returns:
            Tuple of (success, message)
        """
        if not self._service or not self._session:
            return False, "Not connected"

        package_path = Path(package_path)
        if not package_path.exists():
            return False, f"Package not found: {package_path}"

        try:
            # Calculate checksum for verification
            with open(package_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            logger.info(f"Package checksum: sha256:{file_hash}")

            # Build upload URL
            base_url = f"{'https' if self.config.use_ssl else 'http'}://{self.config.host}:{self.config.port}"
            upload_url = f"{base_url}/services/apps/local"

            # Prepare multipart upload
            with open(package_path, 'rb') as f:
                files = {
                    'appfile': (package_path.name, f, 'application/gzip')
                }
                data = {
                    'name': package_path.stem.replace('.tar', ''),
                    'filename': 'true',
                    'update': 'true' if update else 'false',
                }

                logger.info(f"Uploading {package_path.name} to {self.config.host}...")

                response = self._session.post(
                    upload_url,
                    files=files,
                    data=data,
                    timeout=self.config.upload_timeout
                )

            if response.status_code in [200, 201]:
                logger.info("App uploaded successfully")
                return True, "App installed successfully"

            elif response.status_code == 409:
                # App already exists
                if update:
                    logger.info("App exists, attempting update...")
                    return self._update_app(package_path)
                else:
                    return False, "App already exists and update=False"

            else:
                return False, f"Upload failed: {response.status_code} - {response.text}"

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False, str(e)

    def _update_app(self, package_path: Path) -> Tuple[bool, str]:
        """Update an existing app"""
        # Get app name from package
        app_name = package_path.stem.replace('.tar', '').replace('.spl', '')

        base_url = f"{'https' if self.config.use_ssl else 'http'}://{self.config.host}:{self.config.port}"
        update_url = f"{base_url}/services/apps/local/{app_name}"

        try:
            with open(package_path, 'rb') as f:
                files = {'appfile': (package_path.name, f, 'application/gzip')}

                response = self._session.post(
                    update_url,
                    files=files,
                    timeout=self.config.upload_timeout
                )

            if response.status_code in [200, 201]:
                return True, "App updated successfully"
            else:
                return False, f"Update failed: {response.status_code} - {response.text}"

        except Exception as e:
            return False, str(e)

    def enable_app(self, app_name: str) -> Tuple[bool, str]:
        """Enable an app"""
        if not self._service:
            return False, "Not connected"

        try:
            apps = self._service.apps
            if app_name not in apps:
                return False, f"App not found: {app_name}"

            app = apps[app_name]
            app.enable()
            logger.info(f"App {app_name} enabled")
            return True, "App enabled"

        except Exception as e:
            return False, str(e)

    def disable_app(self, app_name: str) -> Tuple[bool, str]:
        """Disable an app"""
        if not self._service:
            return False, "Not connected"

        try:
            apps = self._service.apps
            if app_name not in apps:
                return False, f"App not found: {app_name}"

            app = apps[app_name]
            app.disable()
            logger.info(f"App {app_name} disabled")
            return True, "App disabled"

        except Exception as e:
            return False, str(e)

    def restart_splunk(self, wait: bool = True) -> Tuple[bool, str]:
        """
        Restart Splunk via REST API.

        Args:
            wait: Wait for restart to complete

        Returns:
            Tuple of (success, message)
        """
        if not self._service:
            return False, "Not connected"

        try:
            logger.info("Initiating Splunk restart...")
            self._service.restart(timeout=self.config.restart_timeout)

            if wait:
                logger.info("Waiting for Splunk to restart...")
                time.sleep(30)  # Initial wait

                # Reconnect
                for attempt in range(10):
                    try:
                        if self.connect():
                            logger.info("Splunk restarted successfully")
                            return True, "Restart complete"
                    except Exception:
                        pass
                    time.sleep(10)

                return False, "Restart timeout - Splunk may still be starting"

            return True, "Restart initiated"

        except Exception as e:
            return False, str(e)

    def check_restart_required(self) -> bool:
        """Check if a restart is required"""
        if not self._service:
            return False

        try:
            messages = self._service.messages
            for msg in messages:
                if "restart" in msg.name.lower():
                    return True
            return False
        except Exception:
            return False

    def get_app_config(self, app_name: str, conf_file: str) -> Dict[str, Any]:
        """Get app configuration"""
        if not self._service:
            return {}

        try:
            # Use the confs endpoint
            confs = self._service.confs
            if conf_file in confs:
                conf = confs[conf_file]
                return {
                    stanza.name: dict(stanza.content)
                    for stanza in conf
                }
            return {}
        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return {}

    def update_app_config(
        self,
        app_name: str,
        conf_file: str,
        stanza: str,
        settings: Dict[str, str]
    ) -> Tuple[bool, str]:
        """Update app configuration"""
        if not self._service:
            return False, "Not connected"

        try:
            confs = self._service.confs
            if conf_file not in confs:
                return False, f"Config file not found: {conf_file}"

            conf = confs[conf_file]

            if stanza in conf:
                # Update existing stanza
                conf[stanza].update(**settings)
            else:
                # Create new stanza
                conf.create(stanza, **settings)

            logger.info(f"Updated {conf_file}/{stanza}")
            return True, "Configuration updated"

        except Exception as e:
            return False, str(e)

    def validate_deployment(self, app_name: str) -> Tuple[bool, List[str]]:
        """
        Validate that app is properly deployed.

        Returns:
            Tuple of (valid, issues)
        """
        issues = []

        if not self._service:
            return False, ["Not connected"]

        # Check app installed
        installed, app_info = self.check_app_installed(app_name)
        if not installed:
            issues.append("App is not installed")
            return False, issues

        # Check app enabled
        if app_info and app_info.get("disabled"):
            issues.append("App is disabled")

        # Check for required configurations
        # This is specific to kvstore_syncthing
        if app_name == "kvstore_syncthing":
            # Check if app.conf exists
            app_conf = self.get_app_config(app_name, "app")
            if not app_conf:
                issues.append("app.conf not found or empty")

        # Check for error messages
        try:
            messages = self._service.messages
            for msg in messages:
                if app_name.lower() in msg.name.lower():
                    if "error" in msg.content.get("severity", "").lower():
                        issues.append(f"Error message: {msg.content.get('value', '')}")
        except Exception:
            pass

        return len(issues) == 0, issues


# =============================================================================
# Deployment Workflow
# =============================================================================

class HFDeploymentWorkflow:
    """
    Complete workflow for deploying to Heavy Forwarder.

    Steps:
    1. Connect and verify HF is accessible
    2. Check if app is already installed
    3. Upload and install app package
    4. Configure app settings
    5. Validate deployment
    6. Restart if required
    """

    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.client = SplunkDeploymentClient(config)

    def deploy(
        self,
        package_path: str,
        initial_config: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Execute full deployment workflow.

        Args:
            package_path: Path to app package
            initial_config: Optional initial configuration to apply

        Returns:
            Tuple of (success, deployment_report)
        """
        report = {
            "host": self.config.host,
            "app": self.config.app_name,
            "package": package_path,
            "steps": [],
            "success": False,
        }

        try:
            # Step 1: Connect
            logger.info(f"Step 1: Connecting to {self.config.host}...")
            if not self.client.connect():
                report["steps"].append({"step": "connect", "success": False, "error": "Connection failed"})
                return False, report

            report["steps"].append({"step": "connect", "success": True})
            report["server_info"] = self.client.get_server_info()

            # Step 2: Check existing installation
            logger.info("Step 2: Checking existing installation...")
            installed, existing_info = self.client.check_app_installed(self.config.app_name)

            if installed:
                report["existing_app"] = existing_info
                if not self.config.update_if_exists:
                    report["steps"].append({
                        "step": "check_existing",
                        "success": False,
                        "error": "App exists and update_if_exists=False"
                    })
                    return False, report
                logger.info(f"Existing version: {existing_info.get('version')}")

            report["steps"].append({"step": "check_existing", "success": True, "was_installed": installed})

            # Step 3: Upload and install
            logger.info("Step 3: Uploading app package...")
            success, message = self.client.upload_app(
                package_path,
                update=self.config.update_if_exists
            )

            if not success:
                report["steps"].append({"step": "upload", "success": False, "error": message})
                return False, report

            report["steps"].append({"step": "upload", "success": True, "message": message})

            # Step 4: Enable app
            logger.info("Step 4: Enabling app...")
            success, message = self.client.enable_app(self.config.app_name)
            report["steps"].append({"step": "enable", "success": success, "message": message})

            # Step 5: Apply initial configuration
            if initial_config:
                logger.info("Step 5: Applying initial configuration...")
                config_success = True

                for conf_file, stanzas in initial_config.items():
                    for stanza, settings in stanzas.items():
                        success, message = self.client.update_app_config(
                            self.config.app_name,
                            conf_file,
                            stanza,
                            settings
                        )
                        if not success:
                            config_success = False
                            logger.warning(f"Config failed: {message}")

                report["steps"].append({"step": "configure", "success": config_success})
            else:
                report["steps"].append({"step": "configure", "success": True, "skipped": True})

            # Step 6: Check if restart required
            restart_required = self.client.check_restart_required()
            if restart_required and self.config.restart_required:
                logger.info("Step 6: Restarting Splunk...")
                success, message = self.client.restart_splunk(wait=True)
                report["steps"].append({
                    "step": "restart",
                    "success": success,
                    "message": message
                })
            else:
                report["steps"].append({
                    "step": "restart",
                    "success": True,
                    "skipped": not restart_required,
                    "note": "Restart recommended" if restart_required else "No restart required"
                })

            # Step 7: Validate deployment
            logger.info("Step 7: Validating deployment...")
            valid, issues = self.client.validate_deployment(self.config.app_name)
            report["steps"].append({
                "step": "validate",
                "success": valid,
                "issues": issues
            })

            # Final status
            report["success"] = valid
            if valid:
                logger.info("Deployment completed successfully!")
            else:
                logger.warning(f"Deployment completed with issues: {issues}")

            # Get final app info
            _, final_info = self.client.check_app_installed(self.config.app_name)
            report["deployed_app"] = final_info

            return valid, report

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            report["steps"].append({"step": "unknown", "success": False, "error": str(e)})
            return False, report

        finally:
            self.client.disconnect()


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """CLI entry point for HF deployment"""
    parser = argparse.ArgumentParser(
        description="Deploy KVStore Syncthing to Splunk Heavy Forwarder via REST API"
    )

    # Connection arguments
    parser.add_argument("--host", required=True, help="HF hostname or IP")
    parser.add_argument("--port", type=int, default=8089, help="Management port (default: 8089)")
    parser.add_argument("--token", help="Splunk auth token")
    parser.add_argument("--username", help="Splunk username (alternative to token)")
    parser.add_argument("--password", help="Splunk password (alternative to token)")
    parser.add_argument("--no-ssl", action="store_true", help="Disable SSL")
    parser.add_argument("--verify-ssl", action="store_true", help="Verify SSL certificates")

    # Deployment arguments
    parser.add_argument("--package", required=True, help="Path to app package (.tar.gz or .spl)")
    parser.add_argument("--app-name", default="kvstore_syncthing", help="App name")
    parser.add_argument("--no-update", action="store_true", help="Don't update if app exists")
    parser.add_argument("--restart", action="store_true", help="Restart Splunk after deployment")

    # Output arguments
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    parser.add_argument("--output", help="Write report to file")

    args = parser.parse_args()

    # Validate authentication
    if not args.token and not (args.username and args.password):
        parser.error("Either --token or --username/--password required")

    # Build configuration
    config = DeploymentConfig(
        host=args.host,
        port=args.port,
        token=args.token,
        username=args.username,
        password=args.password,
        use_ssl=not args.no_ssl,
        verify_ssl=args.verify_ssl,
        app_name=args.app_name,
        app_package=args.package,
        update_if_exists=not args.no_update,
        restart_required=args.restart,
    )

    # Execute deployment
    workflow = HFDeploymentWorkflow(config)
    success, report = workflow.deploy(args.package)

    # Output report
    if args.json or args.output:
        report_json = json.dumps(report, indent=2, default=str)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(report_json)
            logger.info(f"Report written to: {args.output}")

        if args.json:
            print(report_json)
    else:
        # Human-readable output
        print("\n" + "=" * 60)
        print("DEPLOYMENT REPORT")
        print("=" * 60)
        print(f"Host: {report['host']}")
        print(f"App: {report['app']}")
        print(f"Success: {report['success']}")
        print("\nSteps:")
        for step in report.get('steps', []):
            status = "OK" if step.get('success') else "FAILED"
            if step.get('skipped'):
                status = "SKIPPED"
            print(f"  - {step['step']}: {status}")
            if step.get('error'):
                print(f"    Error: {step['error']}")
            if step.get('issues'):
                for issue in step['issues']:
                    print(f"    Issue: {issue}")
        print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
