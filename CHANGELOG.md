# Changelog

All notable changes to KVStore Syncthing will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Core Sync Engine
- Multi-method synchronization support:
  - REST API sync using splunk-sdk exclusively
  - MongoDB Direct sync for master/slave replication
  - HEC (HTTP Event Collector) with Index & Rehydrate pattern
  - File Export for offline/air-gapped environments
  - Multi-cloud storage (AWS S3, MinIO, Wasabi, Azure Blob, Google Cloud Storage)

#### Threat Intelligence Distribution
- URL-based threat indicator export for security devices
- Palo Alto External Dynamic List (EDL) format support
- Cisco IOS ACL format generation
- FortiGate threat feed format
- STIX 2.1 and MISP format support
- Token-based authentication for secure access
- IP allowlist support
- Rate limiting with configurable thresholds
- Threat feed ingestion from external sources:
  - Abuse.ch (URLhaus, Feodo Tracker)
  - Spamhaus (DROP, EDROP)
  - FireHOL, Emerging Threats
  - Custom CSV/JSON/STIX feeds

#### Workflow Templates
- ServiceNow CMDB integration via SA-ldapsearch and TA-SNOW
- Database integration via Splunk DB Connect
- Active Directory / LDAP synchronization
- Web threat feed aggregation

#### Data Integrity
- SHA-256 checksums for all sync operations
- Merkle tree verification for collection-level integrity
- Export manifest with complete metadata
- Checksum verification on import

#### Cloud Storage Integration
- AWS S3 with IAM role assumption support
- MinIO (S3-compatible) with custom CA certificate support
- Wasabi with automatic endpoint selection
- Azure Blob Storage with Managed Identity support
- Google Cloud Storage with Workload Identity support
- Server-side encryption support for all providers
- Multipart upload for large exports
- Export manifest with file checksums

#### CI/CD Infrastructure
- Concourse CI pipeline with multi-stage validation
- HashiCorp Vault integration for secrets management
- Live testing matrix for Splunk 9.0, 9.1, 9.2, 9.3
- Splunk AppInspect integration for app vetting
- Splunkbase publishing automation
- Security scanning suite:
  - Bandit (Python SAST)
  - Semgrep (Multi-language SAST)
  - Safety (Dependency vulnerabilities)
  - pip-audit (Package audit)
  - detect-secrets (Secret detection)
- SARIF report generation for GitHub integration

#### Deployment
- REST API-based deployment to Splunk Heavy Forwarder 10.x
- No SSH required - all operations via API
- Automatic app enable/disable
- Configuration via REST API
- Deployment validation and health checks

#### Testing
- BDD test framework with pytest-bdd
- VCR fixtures for API mocking with data deidentification
- KVStore fixture generator with:
  - Unicode and special character support
  - CIDR and wildcard pattern generation
  - Case transformation with restoration mappings
- Test matrix covering:
  - Lookup definitions and accelerations
  - Wildcard matching
  - CIDR (IPv4/IPv6) matching
  - Case-insensitive operations

#### Configuration
- UCC (Universal Configuration Console) framework
- globalConfig.json for all configuration
- Encrypted credential storage via UCC
- Splunk-UI React components for dashboard

### Security
- splunk-sdk required for all Splunk API interactions
- No homebrew HTTP clients
- Automatic secret masking in logs
- Encrypted export packages with password-based key derivation
- Rate limiting on distribution endpoints
- IP allowlist support

### Documentation
- BDD feature files as living documentation
- Import instructions included in export packages
- Comprehensive inline documentation with provenance tracking

## [0.1.0] - 2026-02-03

### Added
- Initial project structure
- BDD test framework setup
- Core sync engine architecture
- SDK requirements enforcement

---

## Version History Format

### Version Numbering
- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality, backwards compatible
- **PATCH**: Bug fixes, backwards compatible

### Change Categories
- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Vulnerability fixes
