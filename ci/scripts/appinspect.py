#!/usr/bin/env python3
"""
Splunk AppInspect Integration for CI/CD

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: ci/scripts/appinspect.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: CI/CD Script

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  AppInspect API integration for automated
                                app vetting and Splunkbase publishing.
-------------------------------------------------------------------------------

License: MIT

PURPOSE:
Automate Splunk AppInspect checks and Splunkbase publishing as part of CI/CD.
Validates apps against security, compatibility, and cloud certification
requirements before publishing.

USAGE:
    # Run AppInspect checks
    python appinspect.py check --package app.tar.gz --output reports/

    # Publish to Splunkbase
    python appinspect.py publish --package app.tar.gz --version 1.0.0

REQUIREMENTS:
    - Splunk.com account with AppInspect API access
    - SPLUNK_APPINSPECT_USERNAME and SPLUNK_APPINSPECT_PASSWORD env vars
    - For publishing: Splunkbase developer account
===============================================================================
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

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
# Constants
# =============================================================================

APPINSPECT_API_BASE = "https://appinspect.splunk.com/v1/app"
SPLUNKBASE_API_BASE = "https://splunkbase.splunk.com/api/v1"
AUTH_API_BASE = "https://api.splunk.com/2.0/rest/login/splunk"


class CheckResult(Enum):
    """AppInspect check result types"""
    PASSED = "success"
    FAILED = "failure"
    WARNING = "warning"
    SKIPPED = "skipped"
    MANUAL = "manual_check"
    ERROR = "error"


class InspectTag(Enum):
    """AppInspect tag categories"""
    CLOUD = "cloud"
    PRIVATE_VICTORIA = "private_victoria"
    PRIVATE_CLASSIC = "private_classic"
    SELF_SERVICE = "self_service"
    SECURITY = "security"
    APPINSPECT = "appinspect"


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class AppInspectConfig:
    """AppInspect configuration"""
    username: str
    password: str
    package_path: str
    output_dir: str = "reports/appinspect"

    # Inspection options
    included_tags: List[str] = None  # None = all tags
    excluded_tags: List[str] = None

    # Timeouts
    poll_interval: int = 10
    max_wait_time: int = 600  # 10 minutes

    # Thresholds
    fail_on_error: bool = True
    fail_on_failure: bool = True
    fail_on_warning: bool = False
    fail_on_manual: bool = False


@dataclass
class SplunkbaseConfig:
    """Splunkbase publishing configuration"""
    username: str
    password: str
    package_path: str
    app_id: str  # Splunkbase app ID
    version: str
    release_notes: str = ""
    visibility: str = "public"  # public, private


# =============================================================================
# AppInspect Client
# =============================================================================

class AppInspectClient:
    """
    Client for Splunk AppInspect API.

    Handles:
    - Authentication
    - Package submission
    - Status polling
    - Report retrieval
    """

    def __init__(self, config: AppInspectConfig):
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests is required. Install: pip install requests")

        self.config = config
        self._session = requests.Session()
        self._token: Optional[str] = None

    def authenticate(self) -> bool:
        """Authenticate with Splunk AppInspect API"""
        try:
            response = self._session.post(
                AUTH_API_BASE,
                auth=(self.config.username, self.config.password)
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data.get("data", {}).get("token")
                self._session.headers["Authorization"] = f"Bearer {self._token}"
                logger.info("AppInspect authentication successful")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def submit_package(self) -> Tuple[bool, Optional[str]]:
        """
        Submit app package for inspection.

        Returns:
            Tuple of (success, request_id)
        """
        package_path = Path(self.config.package_path)
        if not package_path.exists():
            return False, None

        try:
            # Build request parameters
            params = {}
            if self.config.included_tags:
                params["included_tags"] = ",".join(self.config.included_tags)
            if self.config.excluded_tags:
                params["excluded_tags"] = ",".join(self.config.excluded_tags)

            with open(package_path, 'rb') as f:
                files = {'app_package': (package_path.name, f, 'application/gzip')}

                response = self._session.post(
                    f"{APPINSPECT_API_BASE}/validate",
                    files=files,
                    data=params,
                    timeout=120
                )

            if response.status_code in [200, 202]:
                data = response.json()
                request_id = data.get("request_id")
                logger.info(f"Package submitted, request_id: {request_id}")
                return True, request_id
            else:
                logger.error(f"Submission failed: {response.status_code} - {response.text}")
                return False, None

        except Exception as e:
            logger.error(f"Submission error: {e}")
            return False, None

    def get_status(self, request_id: str) -> Tuple[str, Optional[Dict]]:
        """
        Get inspection status.

        Returns:
            Tuple of (status, info)
        """
        try:
            response = self._session.get(
                f"{APPINSPECT_API_BASE}/validate/status/{request_id}"
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("status", "UNKNOWN"), data
            else:
                return "ERROR", None

        except Exception as e:
            logger.error(f"Status check error: {e}")
            return "ERROR", None

    def wait_for_completion(self, request_id: str) -> Tuple[bool, Optional[Dict]]:
        """
        Wait for inspection to complete.

        Returns:
            Tuple of (success, final_status)
        """
        start_time = time.time()
        last_status = ""

        while (time.time() - start_time) < self.config.max_wait_time:
            status, info = self.get_status(request_id)

            if status != last_status:
                logger.info(f"Inspection status: {status}")
                last_status = status

            if status == "SUCCESS":
                return True, info
            elif status in ["FAILURE", "ERROR"]:
                return False, info

            time.sleep(self.config.poll_interval)

        logger.error("Inspection timed out")
        return False, None

    def get_report(self, request_id: str) -> Optional[Dict]:
        """Get detailed inspection report"""
        try:
            response = self._session.get(
                f"{APPINSPECT_API_BASE}/report/{request_id}"
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Report retrieval failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Report retrieval error: {e}")
            return None

    def get_html_report(self, request_id: str) -> Optional[str]:
        """Get HTML formatted report"""
        try:
            response = self._session.get(
                f"{APPINSPECT_API_BASE}/report/{request_id}",
                headers={"Accept": "text/html"}
            )

            if response.status_code == 200:
                return response.text
            return None

        except Exception as e:
            logger.error(f"HTML report error: {e}")
            return None


# =============================================================================
# Report Generator
# =============================================================================

class AppInspectReporter:
    """Generates AppInspect reports in various formats"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_reports(
        self,
        report_data: Dict,
        request_id: str,
        html_report: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate reports in multiple formats.

        Returns:
            Dict mapping format to file path
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        files = {}

        # JSON report
        json_path = self.output_dir / f"appinspect_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        files["json"] = str(json_path)

        # HTML report
        if html_report:
            html_path = self.output_dir / f"appinspect_{timestamp}.html"
            with open(html_path, 'w') as f:
                f.write(html_report)
            files["html"] = str(html_path)

        # Summary report (Markdown)
        summary = self._generate_summary(report_data)
        summary_path = self.output_dir / f"appinspect_{timestamp}.md"
        with open(summary_path, 'w') as f:
            f.write(summary)
        files["summary"] = str(summary_path)

        # JUnit XML for CI integration
        junit = self._generate_junit(report_data)
        junit_path = self.output_dir / f"appinspect_{timestamp}.xml"
        with open(junit_path, 'w') as f:
            f.write(junit)
        files["junit"] = str(junit_path)

        logger.info(f"Reports generated in {self.output_dir}")
        return files

    def _generate_summary(self, report_data: Dict) -> str:
        """Generate markdown summary"""
        summary = report_data.get("summary", {})
        reports = report_data.get("reports", [])

        md = f"""# AppInspect Report

## Summary

| Metric | Count |
|--------|-------|
| Passed | {summary.get('success', 0)} |
| Failed | {summary.get('failure', 0)} |
| Warnings | {summary.get('warning', 0)} |
| Skipped | {summary.get('skipped', 0)} |
| Manual Checks | {summary.get('manual_check', 0)} |

## Details

"""
        # Group by result type
        failures = []
        warnings = []
        manual_checks = []

        for report in reports:
            for group in report.get("groups", []):
                for check in group.get("checks", []):
                    result = check.get("result", "")
                    if result == "failure":
                        failures.append({
                            "name": check.get("name"),
                            "description": check.get("description"),
                            "messages": check.get("messages", [])
                        })
                    elif result == "warning":
                        warnings.append({
                            "name": check.get("name"),
                            "description": check.get("description"),
                            "messages": check.get("messages", [])
                        })
                    elif result == "manual_check":
                        manual_checks.append({
                            "name": check.get("name"),
                            "description": check.get("description"),
                        })

        if failures:
            md += "### Failures\n\n"
            for f in failures:
                md += f"#### {f['name']}\n\n"
                md += f"{f['description']}\n\n"
                for msg in f['messages']:
                    md += f"- {msg.get('message', '')}\n"
                md += "\n"

        if warnings:
            md += "### Warnings\n\n"
            for w in warnings:
                md += f"- **{w['name']}**: {w['description']}\n"

        if manual_checks:
            md += "### Manual Checks Required\n\n"
            for m in manual_checks:
                md += f"- **{m['name']}**: {m['description']}\n"

        return md

    def _generate_junit(self, report_data: Dict) -> str:
        """Generate JUnit XML for CI integration"""
        summary = report_data.get("summary", {})
        reports = report_data.get("reports", [])

        total = sum(summary.values())
        failures = summary.get("failure", 0)
        errors = summary.get("error", 0)

        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="AppInspect" tests="{total}" failures="{failures}" errors="{errors}">
'''

        for report in reports:
            for group in report.get("groups", []):
                for check in group.get("checks", []):
                    name = check.get("name", "unknown")
                    result = check.get("result", "")
                    description = check.get("description", "")

                    xml += f'  <testcase name="{name}" classname="appinspect.{group.get("name", "default")}">\n'

                    if result == "failure":
                        messages = " ".join(m.get("message", "") for m in check.get("messages", []))
                        xml += f'    <failure message="{description}">{messages}</failure>\n'
                    elif result == "error":
                        xml += f'    <error message="{description}"/>\n'
                    elif result == "skipped":
                        xml += '    <skipped/>\n'

                    xml += '  </testcase>\n'

        xml += '</testsuite>'
        return xml


# =============================================================================
# Splunkbase Publisher
# =============================================================================

class SplunkbasePublisher:
    """
    Client for publishing to Splunkbase.

    Note: Requires approved AppInspect report and Splunkbase developer account.
    """

    def __init__(self, config: SplunkbaseConfig):
        self.config = config
        self._session = requests.Session()
        self._token: Optional[str] = None

    def authenticate(self) -> bool:
        """Authenticate with Splunk.com"""
        try:
            response = self._session.post(
                AUTH_API_BASE,
                auth=(self.config.username, self.config.password)
            )

            if response.status_code == 200:
                data = response.json()
                self._token = data.get("data", {}).get("token")
                self._session.headers["Authorization"] = f"Bearer {self._token}"
                logger.info("Splunkbase authentication successful")
                return True
            else:
                logger.error(f"Authentication failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def publish(self) -> Tuple[bool, str]:
        """
        Publish app to Splunkbase.

        Returns:
            Tuple of (success, message)
        """
        package_path = Path(self.config.package_path)
        if not package_path.exists():
            return False, f"Package not found: {package_path}"

        try:
            # Build request
            url = f"{SPLUNKBASE_API_BASE}/apps/{self.config.app_id}/releases"

            with open(package_path, 'rb') as f:
                files = {'filename': (package_path.name, f, 'application/gzip')}
                data = {
                    'version': self.config.version,
                    'visibility': self.config.visibility,
                }
                if self.config.release_notes:
                    data['release_notes'] = self.config.release_notes

                response = self._session.post(
                    url,
                    files=files,
                    data=data,
                    timeout=300
                )

            if response.status_code in [200, 201]:
                logger.info(f"Published to Splunkbase: v{self.config.version}")
                return True, "Published successfully"
            else:
                return False, f"Publish failed: {response.status_code} - {response.text}"

        except Exception as e:
            return False, str(e)

    def get_app_info(self) -> Optional[Dict]:
        """Get app information from Splunkbase"""
        try:
            response = self._session.get(
                f"{SPLUNKBASE_API_BASE}/apps/{self.config.app_id}"
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            logger.error(f"Error getting app info: {e}")
            return None


# =============================================================================
# Workflow
# =============================================================================

def run_appinspect(
    package_path: str,
    username: str,
    password: str,
    output_dir: str = "reports/appinspect",
    tags: Optional[List[str]] = None,
    fail_on_failure: bool = True,
    fail_on_warning: bool = False
) -> Tuple[bool, Dict]:
    """
    Run complete AppInspect workflow.

    Returns:
        Tuple of (passed, results)
    """
    config = AppInspectConfig(
        username=username,
        password=password,
        package_path=package_path,
        output_dir=output_dir,
        included_tags=tags,
        fail_on_failure=fail_on_failure,
        fail_on_warning=fail_on_warning
    )

    client = AppInspectClient(config)
    reporter = AppInspectReporter(output_dir)

    # Authenticate
    if not client.authenticate():
        return False, {"error": "Authentication failed"}

    # Submit package
    success, request_id = client.submit_package()
    if not success:
        return False, {"error": "Package submission failed"}

    # Wait for completion
    success, status = client.wait_for_completion(request_id)
    if not success:
        return False, {"error": "Inspection failed", "status": status}

    # Get reports
    report = client.get_report(request_id)
    html_report = client.get_html_report(request_id)

    if not report:
        return False, {"error": "Failed to retrieve report"}

    # Generate output reports
    files = reporter.generate_reports(report, request_id, html_report)

    # Check results
    summary = report.get("summary", {})
    passed = True

    if config.fail_on_failure and summary.get("failure", 0) > 0:
        passed = False
    if config.fail_on_warning and summary.get("warning", 0) > 0:
        passed = False

    return passed, {
        "request_id": request_id,
        "summary": summary,
        "files": files,
        "passed": passed
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Splunk AppInspect and Splunkbase CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Check command
    check_parser = subparsers.add_parser("check", help="Run AppInspect checks")
    check_parser.add_argument("--package", required=True, help="Path to app package")
    check_parser.add_argument("--output", default="reports/appinspect", help="Output directory")
    check_parser.add_argument("--tags", nargs="+", help="AppInspect tags to include")
    check_parser.add_argument("--fail-on-warning", action="store_true")
    check_parser.add_argument("--json", action="store_true", help="Output JSON")

    # Publish command
    publish_parser = subparsers.add_parser("publish", help="Publish to Splunkbase")
    publish_parser.add_argument("--package", required=True, help="Path to app package")
    publish_parser.add_argument("--app-id", required=True, help="Splunkbase app ID")
    publish_parser.add_argument("--version", required=True, help="Version to publish")
    publish_parser.add_argument("--release-notes", help="Release notes")

    args = parser.parse_args()

    # Get credentials from environment
    username = os.environ.get("SPLUNK_APPINSPECT_USERNAME")
    password = os.environ.get("SPLUNK_APPINSPECT_PASSWORD")

    if not username or not password:
        logger.error("SPLUNK_APPINSPECT_USERNAME and SPLUNK_APPINSPECT_PASSWORD required")
        sys.exit(1)

    if args.command == "check":
        passed, results = run_appinspect(
            args.package,
            username,
            password,
            args.output,
            args.tags,
            fail_on_warning=args.fail_on_warning
        )

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            summary = results.get("summary", {})
            print(f"\nAppInspect Results:")
            print(f"  Passed: {summary.get('success', 0)}")
            print(f"  Failed: {summary.get('failure', 0)}")
            print(f"  Warnings: {summary.get('warning', 0)}")
            print(f"\nReports: {results.get('files', {})}")
            print(f"\nOverall: {'PASSED' if passed else 'FAILED'}")

        sys.exit(0 if passed else 1)

    elif args.command == "publish":
        config = SplunkbaseConfig(
            username=username,
            password=password,
            package_path=args.package,
            app_id=args.app_id,
            version=args.version,
            release_notes=args.release_notes or ""
        )

        publisher = SplunkbasePublisher(config)

        if not publisher.authenticate():
            logger.error("Authentication failed")
            sys.exit(1)

        success, message = publisher.publish()
        print(message)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
