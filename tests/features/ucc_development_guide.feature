# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: tests/features/ucc_development_guide.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD Contract - UCC Development Quick Reference
#
# PURPOSE:
# This is the MASTER CONTRACT for UCC development.
# It provides a quick reference for DO and DON'T rules.
# Refer to other ucc_*.feature files for detailed contracts.
#
# RELATED CONTRACTS:
# - ucc_structure.feature     - Directory structure requirements
# - ucc_globalconfig.feature  - globalConfig.json schema
# - ucc_modular_inputs.feature- inputHelperModule development
# - ucc_rest_handlers.feature - REST API architecture
# - ucc_kvstore_sync.feature  - KVStore-specific implementation
# ===============================================================================

@ucc @guide @contract
Feature: UCC Development Quick Reference Guide
  As a Splunk add-on developer starting with UCC
  I need a quick reference for what I can and cannot do
  So that I don't violate UCC framework conventions

  # ===========================================================================
  # THE GOLDEN RULES
  # ===========================================================================

  @golden-rules
  Scenario: The three golden rules of UCC development
    """
    These rules MUST be followed at all times.
    Violating these rules breaks UCC compatibility.
    """
    Then I MUST follow:
      | rule | description                                              |
      | 1    | globalConfig.json is the SINGLE SOURCE OF TRUTH          |
      | 2    | NEVER create files that UCC generates                    |
      | 3    | All custom code goes in inputHelperModule or customScript|
    And all other rules derive from these three

  # ===========================================================================
  # WHAT DEVELOPERS CREATE (DO)
  # ===========================================================================

  @do-create
  Scenario: Files developers MUST create
    """
    These files are developer-owned and must be created manually.
    """
    Then developers MUST create:
      | file                           | purpose                              |
      | globalConfig.json              | Defines entire add-on structure      |
      | package/default/app.conf       | Splunk app manifest                  |
      | package/bin/<helper>.py        | inputHelperModule for custom logic   |
      | package/lib/requirements.txt   | Python dependencies (optional)       |
      | additional_packaging.py        | Build customization (optional)       |

  @do-create
  Scenario: Optional files developers MAY create
    """
    These files are optional and enhance functionality.
    """
    Then developers MAY create:
      | file                                | purpose                          |
      | package/bin/<alert_script>.py       | Alert action customScript        |
      | package/appserver/static/js/custom/ | Custom UI hooks                  |
      | custom_dashboard.json               | Custom dashboard definitions     |
      | package/default/<custom>.conf       | Non-UCC-managed conf files       |

  # ===========================================================================
  # WHAT UCC GENERATES (DON'T CREATE)
  # ===========================================================================

  @do-not-create
  Scenario: Files developers MUST NOT create
    """
    UCC generates these files automatically.
    Creating them manually causes conflicts.
    """
    Then developers MUST NOT create:
      | file pattern                        | reason                           |
      | bin/<addon>_rh_*.py                 | REST handlers auto-generated     |
      | bin/<service_name>.py               | Input scripts auto-generated     |
      | default/restmap.conf (UCC sections) | Auto-generated from globalConfig |
      | default/web.conf (UCC sections)     | Auto-generated from globalConfig |
      | default/*_settings.conf             | Auto-generated from tabs         |
      | appserver/                          | Entire directory auto-generated  |
      | lib/solnlib/                        | Auto-installed by UCC            |
      | lib/splunktaucclib/                 | Auto-installed by UCC            |
      | metadata/default.meta (UCC)         | Auto-generated                   |
      | README/*.conf.spec (UCC)            | Auto-generated from globalConfig |

  @do-not-create
  Scenario: Directory structures developers MUST NOT create
    """
    Custom directory structures violate UCC conventions.
    """
    Then developers MUST NOT create:
      | directory pattern                   | reason                           |
      | src/<addon>/handlers/               | Handlers are auto-generated      |
      | src/<addon>/models/                 | No custom model layer needed     |
      | src/<addon>/api/                    | No custom API layer needed       |
      | lib/<addon>/                        | Dependencies go in lib/ root     |

  # ===========================================================================
  # FORBIDDEN PATTERNS
  # ===========================================================================

  @forbidden
  Scenario: Code patterns that are FORBIDDEN
    """
    These coding patterns violate UCC architecture.
    """
    Then code MUST NOT contain:
      | pattern                             | alternative                      |
      | class *Handler(AdminExternalHandler)| Use globalConfig.json tabs       |
      | class *RestHandler                  | Use globalConfig.json tabs       |
      | import splunk.admin                 | Use splunktaucclib via UCC       |
      | requests.get/post (for Splunk)      | Use splunklib.client             |
      | urllib (for Splunk)                 | Use splunklib.client             |
      | Custom conf file parsing            | Use solnlib.conf_manager         |
      | Manual password storage             | Use encrypted: true in entity    |

  @forbidden
  Scenario: Development practices that are FORBIDDEN
    """
    These development practices break UCC compatibility.
    """
    Then developers MUST NOT:
      | practice                            | reason                           |
      | Manually edit UCC-generated files   | Overwritten on next build        |
      | Create custom REST handler classes  | UCC generates these              |
      | Skip globalConfig.json for config   | UCC relies on it                 |
      | Install dependencies in lib/ manually| Use requirements.txt            |
      | Create custom UI without customTab  | Breaks UCC UI generation         |

  # ===========================================================================
  # BUILD AND WORKFLOW
  # ===========================================================================

  @workflow
  Scenario: Correct UCC development workflow
    """
    Follow this workflow for UCC development.
    """
    Then the development workflow is:
      | step | command/action                                    |
      | 1    | Edit globalConfig.json for configuration changes  |
      | 2    | Edit package/bin/<helper>.py for logic changes    |
      | 3    | Run: ucc-gen build --source package               |
      | 4    | Verify output/ directory structure                |
      | 5    | Install output/<addon> to Splunk for testing      |
      | 6    | Run: ucc-gen package --path output/<addon>        |
      | 7    | Deploy .tar.gz to production                      |

  @workflow
  Scenario: Common ucc-gen commands
    """
    These are the primary ucc-gen commands.
    """
    Then the following commands are available:
      | command                         | purpose                           |
      | ucc-gen init                    | Create new add-on scaffold        |
      | ucc-gen build --source package  | Build add-on from globalConfig    |
      | ucc-gen build --ta-version X.Y.Z| Build with specific version       |
      | ucc-gen package --path output/  | Create distributable archive      |
    And version can be set via:
      | method                          | precedence                        |
      | --ta-version flag               | Highest (overrides all)           |
      | globalConfig.json meta.version  | Default if no flag                |
      | Git tag                         | Used if no other version          |

  # ===========================================================================
  # SPLUNK-SDK REQUIREMENTS
  # ===========================================================================

  @splunk-sdk
  Scenario: splunk-sdk is MANDATORY for Splunk APIs
    """
    All Splunk API interactions MUST use splunk-sdk.
    This is a non-negotiable requirement.
    """
    Then for Splunk API operations:
      | operation              | MUST use                          | MUST NOT use      |
      | KVStore CRUD           | splunklib.client.kvstore          | requests, urllib  |
      | Search jobs            | splunklib.client.jobs             | requests, urllib  |
      | Config access          | splunklib.client.service.get()    | requests, urllib  |
      | User/role management   | splunklib.client                  | requests, urllib  |
    And exceptions where external HTTP is acceptable:
      | case                   | reason                            |
      | HEC event submission   | HEC is external-facing HTTP       |
      | External APIs          | Non-Splunk services               |
      | Cloud storage (S3)     | AWS/Azure/GCP APIs                |

  # ===========================================================================
  # TROUBLESHOOTING CHECKLIST
  # ===========================================================================

  @troubleshooting
  Scenario: UCC build failure checklist
    """
    If UCC build fails, check these items.
    """
    Then when build fails, verify:
      | check                           | fix if failed                     |
      | globalConfig.json valid JSON    | Fix JSON syntax errors            |
      | meta section complete           | Add required meta fields          |
      | Entity types are valid          | Use only supported types          |
      | inputHelperModule exists        | Create package/bin/<helper>.py    |
      | No forbidden files exist        | Delete manually created handlers  |
      | requirements.txt valid          | Fix dependency specifications     |

  @troubleshooting
  Scenario: Add-on runtime failure checklist
    """
    If add-on fails at runtime, check these items.
    """
    Then when runtime fails, verify:
      | check                           | fix if failed                     |
      | inputHelperModule imports work  | Check lib/ dependencies           |
      | splunk-sdk client connects      | Verify session_key from helper    |
      | Configuration endpoints work    | Check globalConfig tab names      |
      | Encrypted fields decrypted      | Ensure encrypted: true in entity  |
      | Permissions correct             | Check capabilities in globalConfig|

  # ===========================================================================
  # REFERENCE TO DETAILED CONTRACTS
  # ===========================================================================

  @references
  Scenario: Reference to detailed contract files
    """
    For detailed rules, refer to these contract files.
    """
    Then detailed contracts are in:
      | file                           | contents                          |
      | ucc_structure.feature          | Directory structure rules         |
      | ucc_globalconfig.feature       | globalConfig.json schema          |
      | ucc_modular_inputs.feature     | inputHelperModule development     |
      | ucc_rest_handlers.feature      | REST handler architecture         |
      | ucc_kvstore_sync.feature       | KVStore sync implementation       |
    And official documentation at:
      | resource                        | URL                              |
      | UCC Documentation               | https://splunk.github.io/addonfactory-ucc-generator/ |
      | splunk-sdk Python               | https://dev.splunk.com/enterprise/docs/devtools/python/sdk-python/ |
      | solnlib Documentation           | https://splunk.github.io/addonfactory-solutions-library-python/ |
