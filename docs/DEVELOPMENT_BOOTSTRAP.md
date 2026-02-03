# KVStore Syncthing Development Bootstrap

## How We Built This App: A Methodology Guide for LLM-Assisted Development

This document captures the principles, patterns, and methodology used to develop KVStore Syncthing with Claude Code. Use this as a bootstrap template for future projects.

---

## 1. The Cardinal Rule: BDD First

**Never write code before writing the story.**

```
User Story → Feature File → Step Definitions → Implementation → Tests Pass
```

### Why BDD First?
- Stories force you to think about *what* before *how*
- Feature files become living documentation
- Tests are written before code (TDD embedded in BDD)
- Acceptance criteria are explicit and testable
- Stakeholders can read and validate requirements

### Example Workflow
```gherkin
# 1. First, write the story (features/sync_methods.feature)
@story:rest-sync
Scenario: Sync via Splunk REST API
  Given a source KVStore collection "users" with 1000 records
  And a REST API destination "cloud-prod" is configured
  When I sync using the REST API method
  Then all 1000 records should be transferred via splunk-sdk
  And the destination should have identical data

# 2. Then implement step definitions (tests/step_defs/test_sync.py)
# 3. Then implement the actual code
# 4. Run tests to verify
```

---

## 2. SDK Requirements: No Homebrew

**Use official SDKs. Always.**

### Splunk Development
- `splunk-sdk` for ALL Splunk API interactions
- NO raw `requests` or `urllib` for Splunk endpoints
- NO custom HTTP clients
- UCC framework for configuration
- Splunk-UI components for React dashboards

### Why?
- Security: SDKs handle authentication, SSL, retries properly
- Maintenance: SDK updates fix bugs, you benefit automatically
- Support: Official SDKs are supported by vendors
- Standards: SDKs enforce best practices

### Enforcement Pattern
```python
# Create a BDD contract that enforces SDK usage
# features/sdk_requirements.feature

@story:sdk-enforcement
Scenario: No raw HTTP for Splunk
  Given the codebase
  When I search for "requests.get" or "urllib.request"
  Then no matches should be in Splunk handler files
```

---

## 3. Architecture Patterns

### Handler Pattern
Every sync method is a handler that implements a base interface:

```python
class BaseSyncHandler(ABC):
    @abstractmethod
    def connect(self) -> bool: ...
    @abstractmethod
    def read_records(self, collection, app, owner, **kwargs) -> Generator: ...
    @abstractmethod
    def write_records(self, collection, app, owner, records) -> Tuple[int, List[str]]: ...
```

### Factory Pattern
Use factories to create handlers based on configuration:

```python
def create_handler(destination_type: str) -> BaseSyncHandler:
    handlers = {
        "rest": RESTSyncHandler,
        "mongodb": MongoDBSyncHandler,
        "hec": HECSyncHandler,
        "file": FileExportHandler,
        "cloud_storage": CloudStorageHandler,
    }
    return handlers[destination_type](config)
```

### Configuration via Dataclasses
```python
@dataclass
class DestinationConfig:
    name: str
    destination_type: str
    host: str = ""
    port: int = 8089
    # ... credentials encrypted via UCC
```

---

## 4. Testing Strategy

### Test Pyramid
```
        /\
       /  \     E2E (Live Splunk tests)
      /----\
     /      \   Integration (VCR mocked)
    /--------\
   /          \ Unit (Pure Python)
  /-----------'\
```

### VCR for API Mocking
Record real API responses, then replay them in tests:

```python
@vcr.use_cassette('fixtures/vcr/kvstore_read.yaml')
def test_read_collection():
    handler = RESTSyncHandler(config)
    records = list(handler.read_records("users", "search", "nobody"))
    assert len(records) == 100
```

### Data Deidentification
Scrub sensitive data from VCR cassettes:

```python
SCRUB_PATTERNS = [
    (r'token=[^&]+', 'token=REDACTED'),
    (r'"password":\s*"[^"]+"', '"password": "***"'),
]
```

### Test Matrix
Test across multiple dimensions:
- Splunk versions: 9.0, 9.1, 9.2, 9.3
- Collection sizes: 100, 1K, 10K, 100K, 1M
- Data types: Unicode, special chars, CIDR, wildcards
- Sync modes: full, incremental, append_only

---

## 5. Security Practices

### Never Trust Input
```python
# Validate all external data
def validate_collection_name(name: str) -> bool:
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))
```

### Mask Secrets in Logs
```python
def mask_string(self, text: str) -> str:
    for secret in self._secrets:
        text = text.replace(secret, "***")
    return text
```

### Encrypt at Rest
```python
# Use UCC's encrypted storage for credentials
# Never store plaintext passwords
```

### Scan Continuously
- Bandit for Python SAST
- Semgrep for multi-language analysis
- Safety/pip-audit for dependencies
- detect-secrets for credential leaks

---

## 6. Documentation Strategy

### Provenance Headers
Every file includes:
```python
"""
===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/base.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation
===============================================================================
"""
```

### BDD as Documentation
Feature files ARE the documentation:
- Written in plain English (Gherkin)
- Executable (tests prove they work)
- Always current (tests fail if wrong)

### Inline Comments
```python
# CRITICAL: Using official splunk-sdk - NO homebrew HTTP clients
# This is a REQUIRED enterprise SDK per BDD contracts
```

---

## 7. Working with Claude Code

### Be Explicit About Constraints
```
"Use splunk-sdk for ALL Splunk interactions. NO raw requests."
"Follow BDD methodology: stories → tests → code."
"Write security reports to reports/security/"
```

### Request Parallel Work
```
"Create the feature file, step definitions, and implementation
in parallel to maximize efficiency."
```

### Use Todo Lists
Claude Code maintains todo lists. Check progress:
```
"Mark the HEC handler as complete and start on File Export."
```

### Provide Context
```
"We're building a Splunk app that syncs KVStore data.
It must work with:
- On-prem Splunk 9.x and 10.x
- Splunk Cloud
- Heavy Forwarders as relay points"
```

### Iterate on Stories
```
"The S3 handler should also support MinIO, Wasabi, Azure, and GCP.
Update the feature file to include these cloud providers."
```

---

## 8. CI/CD Best Practices

### Pipeline Stages
```yaml
1. lint          # Code quality
2. unit-tests    # Fast, no external deps
3. security-scan # SAST, SCA, secrets
4. integration   # VCR mocked APIs
5. appinspect    # Splunk validation
6. live-tests    # Real Splunk instances
7. build         # Package app
8. publish       # Splunkbase
```

### Secrets Management
- Never commit secrets
- Use Vault or similar
- Rotate credentials
- Audit access

### Fail Fast
```yaml
fail_on_critical: true
fail_on_high: true
fail_on_warning: false  # Configurable
```

---

## 9. Project Structure

```
kvstore-syncthing/
├── features/                    # BDD feature files
│   ├── sync_methods.feature
│   ├── cloud_storage.feature
│   ├── threat_intel_distribution.feature
│   └── workflow_templates.feature
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── live/                    # Live Splunk tests
│   ├── step_defs/               # BDD step definitions
│   ├── fixtures/                # Test data
│   └── vcr_cassettes/           # VCR recordings
├── src/kvstore_syncthing/
│   ├── handlers/                # Sync handlers
│   │   ├── base.py
│   │   ├── rest.py
│   │   ├── mongodb.py
│   │   ├── hec.py
│   │   ├── file_export.py
│   │   ├── cloud_storage.py
│   │   └── threat_distribution.py
│   ├── engine/                  # Core sync engine
│   └── utils/                   # Utilities
├── packages/                    # UCC package structure
├── ci/
│   ├── concourse/               # Pipeline definitions
│   ├── scripts/                 # CI scripts
│   └── tasks/                   # Task definitions
├── reports/
│   ├── security/                # Security scan reports
│   └── appinspect/              # AppInspect reports
├── docs/
│   ├── DEVELOPMENT_BOOTSTRAP.md # This file
│   └── API.md                   # API documentation
├── CHANGELOG.md                 # Version history
├── globalConfig.json            # UCC configuration
└── requirements.txt             # Python dependencies
```

---

## 10. Quick Start for New Sessions

When starting a new Claude Code session on this project:

```
1. "Continue from where we left off on kvstore-syncthing"

2. "Review the todo list and show me current progress"

3. "The next feature we need is [X].
    Write the BDD feature file first, then implement."

4. "Run the security scans and fix any critical findings"

5. "Commit all changes with a descriptive message"
```

### Key Commands
```bash
# Run tests
pytest tests/unit/ -v

# Run BDD tests
pytest tests/step_defs/ -v

# Security scan
python ci/scripts/security_scan.py --all --output reports/security/

# AppInspect
python ci/scripts/appinspect.py check --package dist/kvstore_syncthing.tar.gz

# Deploy to HF
python ci/scripts/deploy_to_hf.py --host hf01 --token $TOKEN --package dist/kvstore_syncthing.tar.gz
```

---

## 11. Principles Summary

| Principle | Implementation |
|-----------|---------------|
| BDD First | Feature files before code |
| SDK Only | splunk-sdk, UCC, Splunk-UI |
| Test Everything | Unit, Integration, Live, Security |
| Document Inline | Provenance headers, comments |
| Secure by Default | Encrypt, mask, scan |
| Automate CI/CD | Concourse, Vault, AppInspect |
| Iterate | Stories → Tests → Code → Refine |

---

## 12. Mrs. Reddington's Parting Wisdom

*adjusts silk scarf thoughtfully*

"My dear, remember: In our business, trust is earned through verification.
Every line of code, every feature, every deployment - verify it works,
secure it properly, document it completely. The devil is in the details,
and the details are what separate the amateurs from the professionals.

Now go build something magnificent."

---

**Document Version:** 1.0.0
**Last Updated:** 2026-02-03
**Author:** Claude (claude-opus-4-5-20251101)
**Session:** claude/kvstore-sync-solution-vPJQI
