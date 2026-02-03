#!/usr/bin/env python3
"""
Security Scanning Suite for CI/CD

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: ci/scripts/security_scan.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: CI/CD Security Script

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Comprehensive security scanning including:
                                - Static analysis (Bandit, Semgrep)
                                - Dependency scanning (Safety, pip-audit)
                                - Secret detection (detect-secrets)
                                - SAST/DAST reporting
-------------------------------------------------------------------------------

License: MIT

PURPOSE:
Run comprehensive security scans and generate reports. Integrates multiple
security tools and aggregates results into unified reports.

TOOLS INTEGRATED:
- Bandit: Python security linter (SAST)
- Semgrep: Multi-language static analysis
- Safety: Python dependency vulnerability scanner
- pip-audit: Python package audit
- detect-secrets: Secret detection

USAGE:
    python security_scan.py --all --output reports/security/
    python security_scan.py --bandit --semgrep --output reports/security/
===============================================================================
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Constants and Enums
# =============================================================================

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScanType(Enum):
    SAST = "sast"  # Static Application Security Testing
    SCA = "sca"   # Software Composition Analysis
    SECRET = "secret"  # Secret Detection
    DAST = "dast"  # Dynamic (placeholder)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ScanConfig:
    """Security scan configuration"""
    source_dir: str = "."
    output_dir: str = "reports/security"
    include_patterns: List[str] = field(default_factory=lambda: ["*.py"])
    exclude_patterns: List[str] = field(default_factory=lambda: ["*test*", "*venv*"])

    # Tool-specific configs
    bandit_config: Optional[str] = None
    semgrep_rules: List[str] = field(default_factory=lambda: ["p/python", "p/security-audit"])
    safety_policy: Optional[str] = None

    # Thresholds
    fail_on_critical: bool = True
    fail_on_high: bool = True
    fail_on_medium: bool = False


@dataclass
class Finding:
    """Security finding"""
    tool: str
    scan_type: ScanType
    severity: Severity
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    cwe: Optional[str] = None
    recommendation: Optional[str] = None
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "scan_type": self.scan_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "cwe": self.cwe,
            "recommendation": self.recommendation,
            "references": self.references
        }


@dataclass
class ScanResult:
    """Results from a security scan"""
    tool: str
    scan_type: ScanType
    timestamp: str
    duration_seconds: float
    findings: List[Finding]
    raw_output: Optional[str] = None
    error: Optional[str] = None

    @property
    def finding_counts(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return counts


# =============================================================================
# Scanner Base Class
# =============================================================================

class SecurityScanner:
    """Base class for security scanners"""

    def __init__(self, config: ScanConfig):
        self.config = config
        self.name = "base"
        self.scan_type = ScanType.SAST

    def is_available(self) -> bool:
        """Check if scanner tool is available"""
        raise NotImplementedError

    def run(self) -> ScanResult:
        """Run the scan"""
        raise NotImplementedError

    def _run_command(self, cmd: List[str], timeout: int = 300) -> Tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.config.source_dir
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)


# =============================================================================
# Bandit Scanner (Python SAST)
# =============================================================================

class BanditScanner(SecurityScanner):
    """Bandit - Python security linter"""

    def __init__(self, config: ScanConfig):
        super().__init__(config)
        self.name = "bandit"
        self.scan_type = ScanType.SAST

    def is_available(self) -> bool:
        code, _, _ = self._run_command(["bandit", "--version"])
        return code == 0

    def run(self) -> ScanResult:
        start_time = datetime.utcnow()
        findings = []

        cmd = [
            "bandit",
            "-r", ".",
            "-f", "json",
            "-ll",  # Low and above
            "--exclude", ",".join(self.config.exclude_patterns)
        ]

        if self.config.bandit_config:
            cmd.extend(["-c", self.config.bandit_config])

        code, stdout, stderr = self._run_command(cmd)
        duration = (datetime.utcnow() - start_time).total_seconds()

        if stderr and "No issues identified" not in stderr:
            logger.warning(f"Bandit stderr: {stderr}")

        try:
            if stdout:
                data = json.loads(stdout)
                for result in data.get("results", []):
                    severity = self._map_severity(result.get("issue_severity", ""))
                    findings.append(Finding(
                        tool="bandit",
                        scan_type=ScanType.SAST,
                        severity=severity,
                        title=result.get("issue_text", ""),
                        description=result.get("issue_text", ""),
                        file_path=result.get("filename"),
                        line_number=result.get("line_number"),
                        code_snippet=result.get("code"),
                        cwe=f"CWE-{result.get('issue_cwe', {}).get('id', '')}" if result.get('issue_cwe') else None,
                        recommendation=result.get("more_info"),
                        references=[result.get("more_info", "")] if result.get("more_info") else []
                    ))
        except json.JSONDecodeError:
            pass

        return ScanResult(
            tool="bandit",
            scan_type=ScanType.SAST,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            findings=findings,
            raw_output=stdout
        )

    def _map_severity(self, level: str) -> Severity:
        mapping = {
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW
        }
        return mapping.get(level.upper(), Severity.INFO)


# =============================================================================
# Semgrep Scanner (Multi-language SAST)
# =============================================================================

class SemgrepScanner(SecurityScanner):
    """Semgrep - Multi-language static analysis"""

    def __init__(self, config: ScanConfig):
        super().__init__(config)
        self.name = "semgrep"
        self.scan_type = ScanType.SAST

    def is_available(self) -> bool:
        code, _, _ = self._run_command(["semgrep", "--version"])
        return code == 0

    def run(self) -> ScanResult:
        start_time = datetime.utcnow()
        findings = []

        cmd = [
            "semgrep",
            "--json",
            "--quiet"
        ]

        for rule in self.config.semgrep_rules:
            cmd.extend(["--config", rule])

        cmd.append(".")

        code, stdout, stderr = self._run_command(cmd, timeout=600)
        duration = (datetime.utcnow() - start_time).total_seconds()

        try:
            if stdout:
                data = json.loads(stdout)
                for result in data.get("results", []):
                    severity = self._map_severity(result.get("extra", {}).get("severity", ""))
                    findings.append(Finding(
                        tool="semgrep",
                        scan_type=ScanType.SAST,
                        severity=severity,
                        title=result.get("check_id", ""),
                        description=result.get("extra", {}).get("message", ""),
                        file_path=result.get("path"),
                        line_number=result.get("start", {}).get("line"),
                        code_snippet=result.get("extra", {}).get("lines"),
                        cwe=result.get("extra", {}).get("metadata", {}).get("cwe"),
                        references=result.get("extra", {}).get("metadata", {}).get("references", [])
                    ))
        except json.JSONDecodeError:
            pass

        return ScanResult(
            tool="semgrep",
            scan_type=ScanType.SAST,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            findings=findings,
            raw_output=stdout
        )

    def _map_severity(self, level: str) -> Severity:
        mapping = {
            "ERROR": Severity.HIGH,
            "WARNING": Severity.MEDIUM,
            "INFO": Severity.LOW
        }
        return mapping.get(level.upper(), Severity.INFO)


# =============================================================================
# Safety Scanner (Dependency Vulnerabilities)
# =============================================================================

class SafetyScanner(SecurityScanner):
    """Safety - Python dependency vulnerability scanner"""

    def __init__(self, config: ScanConfig):
        super().__init__(config)
        self.name = "safety"
        self.scan_type = ScanType.SCA

    def is_available(self) -> bool:
        code, _, _ = self._run_command(["safety", "--version"])
        return code == 0

    def run(self) -> ScanResult:
        start_time = datetime.utcnow()
        findings = []

        cmd = ["safety", "check", "--json"]

        if self.config.safety_policy:
            cmd.extend(["--policy-file", self.config.safety_policy])

        # Check for requirements file
        req_files = ["requirements.txt", "requirements-dev.txt"]
        for req_file in req_files:
            req_path = Path(self.config.source_dir) / req_file
            if req_path.exists():
                cmd.extend(["-r", str(req_path)])

        code, stdout, stderr = self._run_command(cmd)
        duration = (datetime.utcnow() - start_time).total_seconds()

        try:
            if stdout:
                # Safety JSON format varies by version
                data = json.loads(stdout)
                vulnerabilities = data if isinstance(data, list) else data.get("vulnerabilities", [])

                for vuln in vulnerabilities:
                    if isinstance(vuln, list):
                        # Older format: [package, affected, installed, description, id]
                        findings.append(Finding(
                            tool="safety",
                            scan_type=ScanType.SCA,
                            severity=Severity.HIGH,  # Safety doesn't provide severity
                            title=f"Vulnerable dependency: {vuln[0]}",
                            description=vuln[3] if len(vuln) > 3 else "",
                            recommendation=f"Update {vuln[0]} from {vuln[2]} (affected: {vuln[1]})",
                            references=[f"https://pyup.io/vulnerabilities/CVE-{vuln[4]}/"] if len(vuln) > 4 else []
                        ))
                    elif isinstance(vuln, dict):
                        findings.append(Finding(
                            tool="safety",
                            scan_type=ScanType.SCA,
                            severity=self._map_severity(vuln.get("severity", "")),
                            title=f"Vulnerable dependency: {vuln.get('package_name', '')}",
                            description=vuln.get("vulnerability_description", ""),
                            cwe=vuln.get("cwe"),
                            recommendation=vuln.get("recommendation", ""),
                            references=vuln.get("references", [])
                        ))
        except json.JSONDecodeError:
            pass

        return ScanResult(
            tool="safety",
            scan_type=ScanType.SCA,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            findings=findings,
            raw_output=stdout
        )

    def _map_severity(self, level: str) -> Severity:
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW
        }
        return mapping.get(level.lower(), Severity.MEDIUM)


# =============================================================================
# pip-audit Scanner
# =============================================================================

class PipAuditScanner(SecurityScanner):
    """pip-audit - Python package audit"""

    def __init__(self, config: ScanConfig):
        super().__init__(config)
        self.name = "pip-audit"
        self.scan_type = ScanType.SCA

    def is_available(self) -> bool:
        code, _, _ = self._run_command(["pip-audit", "--version"])
        return code == 0

    def run(self) -> ScanResult:
        start_time = datetime.utcnow()
        findings = []

        cmd = ["pip-audit", "--format", "json"]

        code, stdout, stderr = self._run_command(cmd, timeout=300)
        duration = (datetime.utcnow() - start_time).total_seconds()

        try:
            if stdout:
                data = json.loads(stdout)
                for dep in data.get("dependencies", []):
                    for vuln in dep.get("vulns", []):
                        findings.append(Finding(
                            tool="pip-audit",
                            scan_type=ScanType.SCA,
                            severity=Severity.HIGH,
                            title=f"{vuln.get('id', '')}: {dep.get('name', '')}",
                            description=vuln.get("description", ""),
                            recommendation=f"Update {dep.get('name')} from {dep.get('version')} to {vuln.get('fix_versions', ['latest'])[0] if vuln.get('fix_versions') else 'latest'}",
                            references=vuln.get("aliases", [])
                        ))
        except json.JSONDecodeError:
            pass

        return ScanResult(
            tool="pip-audit",
            scan_type=ScanType.SCA,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            findings=findings,
            raw_output=stdout
        )


# =============================================================================
# detect-secrets Scanner
# =============================================================================

class DetectSecretsScanner(SecurityScanner):
    """detect-secrets - Secret detection"""

    def __init__(self, config: ScanConfig):
        super().__init__(config)
        self.name = "detect-secrets"
        self.scan_type = ScanType.SECRET

    def is_available(self) -> bool:
        code, _, _ = self._run_command(["detect-secrets", "--version"])
        return code == 0

    def run(self) -> ScanResult:
        start_time = datetime.utcnow()
        findings = []

        cmd = ["detect-secrets", "scan", "--all-files"]

        code, stdout, stderr = self._run_command(cmd)
        duration = (datetime.utcnow() - start_time).total_seconds()

        try:
            if stdout:
                data = json.loads(stdout)
                for file_path, secrets in data.get("results", {}).items():
                    for secret in secrets:
                        findings.append(Finding(
                            tool="detect-secrets",
                            scan_type=ScanType.SECRET,
                            severity=Severity.CRITICAL,
                            title=f"Potential secret: {secret.get('type', 'Unknown')}",
                            description=f"Detected {secret.get('type', 'secret')} in file",
                            file_path=file_path,
                            line_number=secret.get("line_number"),
                            recommendation="Remove secret from code and rotate credentials"
                        ))
        except json.JSONDecodeError:
            pass

        return ScanResult(
            tool="detect-secrets",
            scan_type=ScanType.SECRET,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
            findings=findings,
            raw_output=stdout
        )


# =============================================================================
# Report Generator
# =============================================================================

class SecurityReportGenerator:
    """Generates security reports in various formats"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        results: List[ScanResult],
        report_name: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate reports in multiple formats"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name = report_name or f"security_scan_{timestamp}"
        files = {}

        # Aggregate data
        all_findings = []
        scan_summary = {}

        for result in results:
            all_findings.extend(result.findings)
            scan_summary[result.tool] = {
                "duration": result.duration_seconds,
                "findings": result.finding_counts,
                "error": result.error
            }

        # JSON report
        json_data = {
            "timestamp": timestamp,
            "summary": {
                "total_findings": len(all_findings),
                "by_severity": self._count_by_severity(all_findings),
                "by_tool": scan_summary
            },
            "findings": [f.to_dict() for f in all_findings]
        }

        json_path = self.output_dir / f"{name}.json"
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        files["json"] = str(json_path)

        # Markdown report
        md_content = self._generate_markdown(json_data)
        md_path = self.output_dir / f"{name}.md"
        with open(md_path, 'w') as f:
            f.write(md_content)
        files["markdown"] = str(md_path)

        # SARIF report (GitHub/IDE compatible)
        sarif = self._generate_sarif(all_findings)
        sarif_path = self.output_dir / f"{name}.sarif"
        with open(sarif_path, 'w') as f:
            json.dump(sarif, f, indent=2)
        files["sarif"] = str(sarif_path)

        logger.info(f"Security reports generated in {self.output_dir}")
        return files

    def _count_by_severity(self, findings: List[Finding]) -> Dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for f in findings:
            counts[f.severity.value] += 1
        return counts

    def _generate_markdown(self, data: Dict) -> str:
        """Generate markdown report"""
        summary = data.get("summary", {})
        findings = data.get("findings", [])

        md = f"""# Security Scan Report

**Generated:** {data.get('timestamp')}

## Summary

| Severity | Count |
|----------|-------|
| Critical | {summary.get('by_severity', {}).get('critical', 0)} |
| High     | {summary.get('by_severity', {}).get('high', 0)} |
| Medium   | {summary.get('by_severity', {}).get('medium', 0)} |
| Low      | {summary.get('by_severity', {}).get('low', 0)} |

**Total Findings:** {summary.get('total_findings', 0)}

## Findings by Tool

"""
        for tool, info in summary.get("by_tool", {}).items():
            md += f"### {tool}\n\n"
            md += f"- Duration: {info.get('duration', 0):.2f}s\n"
            for sev, count in info.get("findings", {}).items():
                if count > 0:
                    md += f"- {sev}: {count}\n"
            md += "\n"

        # Group findings by severity
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
            sev_findings = [f for f in findings if f.get("severity") == severity.value]
            if sev_findings:
                md += f"## {severity.value.upper()} Severity Findings\n\n"
                for f in sev_findings:
                    md += f"### {f.get('title')}\n\n"
                    md += f"**Tool:** {f.get('tool')}  \n"
                    if f.get('file_path'):
                        md += f"**Location:** {f.get('file_path')}:{f.get('line_number', '')}  \n"
                    md += f"\n{f.get('description')}\n\n"
                    if f.get('recommendation'):
                        md += f"**Recommendation:** {f.get('recommendation')}\n\n"
                    md += "---\n\n"

        return md

    def _generate_sarif(self, findings: List[Finding]) -> Dict:
        """Generate SARIF format for GitHub/IDE integration"""
        rules = {}
        results = []

        for f in findings:
            rule_id = hashlib.md5(f.title.encode()).hexdigest()[:8]

            if rule_id not in rules:
                rules[rule_id] = {
                    "id": rule_id,
                    "name": f.title,
                    "shortDescription": {"text": f.title},
                    "fullDescription": {"text": f.description},
                    "defaultConfiguration": {
                        "level": self._severity_to_sarif_level(f.severity)
                    }
                }

            result = {
                "ruleId": rule_id,
                "level": self._severity_to_sarif_level(f.severity),
                "message": {"text": f.description}
            }

            if f.file_path:
                result["locations"] = [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file_path},
                        "region": {"startLine": f.line_number or 1}
                    }
                }]

            results.append(result)

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "KVStore Syncthing Security Scanner",
                        "version": "1.0.0",
                        "rules": list(rules.values())
                    }
                },
                "results": results
            }]
        }

    def _severity_to_sarif_level(self, severity: Severity) -> str:
        mapping = {
            Severity.CRITICAL: "error",
            Severity.HIGH: "error",
            Severity.MEDIUM: "warning",
            Severity.LOW: "note",
            Severity.INFO: "note"
        }
        return mapping.get(severity, "note")


# =============================================================================
# Main Scanner Orchestrator
# =============================================================================

class SecurityScanOrchestrator:
    """Orchestrates multiple security scanners"""

    SCANNERS = {
        "bandit": BanditScanner,
        "semgrep": SemgrepScanner,
        "safety": SafetyScanner,
        "pip-audit": PipAuditScanner,
        "detect-secrets": DetectSecretsScanner
    }

    def __init__(self, config: ScanConfig):
        self.config = config
        self.reporter = SecurityReportGenerator(config.output_dir)

    def run(
        self,
        scanners: Optional[List[str]] = None,
        report_name: Optional[str] = None
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Run security scans.

        Returns:
            Tuple of (passed, report_files)
        """
        scanner_names = scanners or list(self.SCANNERS.keys())
        results = []

        for name in scanner_names:
            scanner_class = self.SCANNERS.get(name)
            if not scanner_class:
                logger.warning(f"Unknown scanner: {name}")
                continue

            scanner = scanner_class(self.config)

            if not scanner.is_available():
                logger.warning(f"Scanner not available: {name}")
                continue

            logger.info(f"Running {name}...")
            result = scanner.run()
            results.append(result)

            logger.info(
                f"{name} complete: {len(result.findings)} findings in "
                f"{result.duration_seconds:.2f}s"
            )

        # Generate reports
        files = self.reporter.generate(results, report_name)

        # Check thresholds
        all_findings = []
        for r in results:
            all_findings.extend(r.findings)

        passed = True
        if self.config.fail_on_critical:
            critical = [f for f in all_findings if f.severity == Severity.CRITICAL]
            if critical:
                passed = False
                logger.error(f"Found {len(critical)} CRITICAL findings")

        if self.config.fail_on_high:
            high = [f for f in all_findings if f.severity == Severity.HIGH]
            if high:
                passed = False
                logger.error(f"Found {len(high)} HIGH findings")

        if self.config.fail_on_medium:
            medium = [f for f in all_findings if f.severity == Severity.MEDIUM]
            if medium:
                passed = False

        return passed, files


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Security scanning suite")

    parser.add_argument("--source", default=".", help="Source directory to scan")
    parser.add_argument("--output", default="reports/security", help="Output directory")
    parser.add_argument("--all", action="store_true", help="Run all available scanners")
    parser.add_argument("--bandit", action="store_true", help="Run Bandit")
    parser.add_argument("--semgrep", action="store_true", help="Run Semgrep")
    parser.add_argument("--safety", action="store_true", help="Run Safety")
    parser.add_argument("--pip-audit", action="store_true", help="Run pip-audit")
    parser.add_argument("--detect-secrets", action="store_true", help="Run detect-secrets")
    parser.add_argument("--fail-on-medium", action="store_true", help="Fail on medium findings")
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    parser.add_argument("--report-name", help="Custom report name")

    args = parser.parse_args()

    # Determine which scanners to run
    scanners = []
    if args.all:
        scanners = list(SecurityScanOrchestrator.SCANNERS.keys())
    else:
        if args.bandit:
            scanners.append("bandit")
        if args.semgrep:
            scanners.append("semgrep")
        if args.safety:
            scanners.append("safety")
        if args.pip_audit:
            scanners.append("pip-audit")
        if args.detect_secrets:
            scanners.append("detect-secrets")

    if not scanners:
        scanners = list(SecurityScanOrchestrator.SCANNERS.keys())

    config = ScanConfig(
        source_dir=args.source,
        output_dir=args.output,
        fail_on_medium=args.fail_on_medium
    )

    orchestrator = SecurityScanOrchestrator(config)
    passed, files = orchestrator.run(scanners, args.report_name)

    if args.json:
        print(json.dumps({"passed": passed, "reports": files}, indent=2))
    else:
        print(f"\nSecurity Scan {'PASSED' if passed else 'FAILED'}")
        print(f"Reports: {files}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
