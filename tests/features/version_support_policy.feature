# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: tests/features/version_support_policy.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD Contract - Version Support Policy
#
# PURPOSE:
# This contract defines the version support policy for KVStore Syncthing.
# We ONLY support Splunk versions that are currently supported by Splunk Inc.
# This contract MUST be updated when Splunk releases new versions or EOLs old ones.
#
# AUTHORITATIVE SOURCES:
# - https://endoflife.date/splunk
# - https://www.splunk.com/en_us/legal/splunk-software-support-policy.html
# - https://splunk.github.io/addonfactory-ucc-generator/
#
# LAST UPDATED: 2026-02-03
# NEXT REVIEW: When Splunk releases a new major/minor version
# ===============================================================================

@version-policy @contract @mandatory
Feature: Splunk and Python Version Support Policy
  As a KVStore Syncthing maintainer
  I enforce support ONLY for Splunk-supported versions
  So that users receive security updates and we don't maintain legacy code

  # ===========================================================================
  # SPLUNK VERSION SUPPORT POLICY
  # ===========================================================================

  @splunk-versions @authoritative
  Scenario: Splunk Enterprise supported versions (as of 2026-02-03)
    """
    AUTHORITATIVE SOURCE: https://endoflife.date/splunk

    Splunk provides 24 months of support for each major/minor release.
    We ONLY support versions that Splunk Inc. currently supports.
    This list MUST be updated when versions are released or EOL'd.

    CURRENT STATUS (2026-02-03):
    - 10.0: Supported until 2027-07-28 (ACTIVE)
    - 9.4:  Supported until 2026-12-16 (ACTIVE)
    - 9.3:  Supported until 2026-07-24 (ACTIVE)
    - 9.2:  EXPIRED 2026-01-31 (DO NOT SUPPORT)
    - 9.1:  EXPIRED 2025-06-28 (DO NOT SUPPORT)
    - 9.0 and below: EXPIRED (DO NOT SUPPORT)
    """
    Then the add-on MUST support these Splunk Enterprise versions:
      | version | release_date | end_of_support | latest_patch | status |
      | 10.0    | 2025-07-28   | 2027-07-28     | 10.0.2       | active |
      | 9.4     | 2024-12-16   | 2026-12-16     | 9.4.7        | active |
      | 9.3     | 2024-07-24   | 2026-07-24     | 9.3.8        | active |
    And the add-on MUST NOT claim support for expired versions:
      | version | expired_date | reason                              |
      | 9.2     | 2026-01-31   | End of Splunk support               |
      | 9.1     | 2025-06-28   | End of Splunk support               |
      | 9.0     | 2025-01-29   | End of Splunk support               |
      | 8.2     | 2024-04-12   | End of Splunk support               |
      | 8.1     | 2023-04-19   | End of Splunk support               |
    And CI/CD pipelines MUST test against ALL active versions
    And documentation MUST list ONLY active versions as supported

  @splunk-versions @docker-images
  Scenario: Splunk Docker images for testing
    """
    Official Splunk Docker images are used for integration testing.
    Image tags correspond to Splunk versions.
    """
    Then integration tests MUST use these Docker images:
      | image                    | splunk_version | purpose           |
      | splunk/splunk:10.0       | 10.0.x         | Latest stable     |
      | splunk/splunk:9.4        | 9.4.x          | Current LTS       |
      | splunk/splunk:9.3        | 9.3.x          | Previous release  |
    And tests MUST NOT use images for unsupported versions
    And the "latest" tag SHOULD be avoided for reproducibility

  # ===========================================================================
  # PYTHON VERSION SUPPORT POLICY
  # ===========================================================================

  @python-versions @authoritative
  Scenario: Python version requirements
    """
    AUTHORITATIVE SOURCES:
    - https://splunk.github.io/addonfactory-ucc-generator/ (requires Python 3.9+)
    - Splunk Enterprise bundles Python 3.9+ in versions 9.1+

    Python version support is determined by:
    1. UCC framework requirements (Python 3.9+)
    2. Splunk's bundled Python version
    3. Python.org support status
    """
    Then the add-on MUST support these Python versions:
      | version | status      | splunk_bundled | ucc_compatible | eol_date   |
      | 3.11    | active      | 9.3+, 10.0+    | yes            | 2027-10    |
      | 3.10    | active      | 9.1+, 9.2+     | yes            | 2026-10    |
      | 3.9     | active      | 9.0+           | yes            | 2025-10    |
    And the add-on MUST NOT support these Python versions:
      | version | reason                                        |
      | 3.8     | EOL October 2024, not in latest Splunk        |
      | 3.7     | EOL June 2023                                 |
      | 2.7     | EOL January 2020, removed from Splunk 9.0+    |
    And CI/CD pipelines MUST test against Python 3.9, 3.10, and 3.11
    And Python 3.11 SHOULD be the primary development version

  @python-versions @dependencies
  Scenario: Python dependency constraints
    """
    Dependencies must be compatible with all supported Python versions.
    """
    Given the add-on supports Python 3.9, 3.10, and 3.11
    Then all dependencies in requirements.txt MUST support Python 3.9+
    And dependencies MUST NOT require Python 3.12+ features
    And dependency versions SHOULD be pinned for reproducibility
    And the splunk-sdk MUST be installed from GitHub (not PyPI)

  # ===========================================================================
  # UCC FRAMEWORK VERSION POLICY
  # ===========================================================================

  @ucc-versions
  Scenario: UCC framework version requirements
    """
    The UCC framework version determines available features.
    We track the latest stable UCC release.
    """
    Then the add-on MUST use UCC framework version 5.50.0 or later
    And the add-on MUST specify UCC version in CI/CD configuration
    And the add-on SHOULD update UCC within 30 days of new releases
    And UCC version MUST be documented in globalConfig.json schemaVersion

  # ===========================================================================
  # CI/CD MATRIX REQUIREMENTS
  # ===========================================================================

  @cicd-matrix @mandatory
  Scenario: CI/CD test matrix requirements
    """
    CI/CD pipelines MUST test the full matrix of supported versions.
    This ensures compatibility across all supported environments.
    """
    Then the CI/CD test matrix MUST include:
      | dimension        | values                          | required |
      | splunk_version   | 10.0, 9.4, 9.3                  | yes      |
      | python_version   | 3.9, 3.10, 3.11                 | yes      |
      | os               | ubuntu-latest                   | yes      |
    And unit tests MUST pass on ALL Python versions
    And integration tests MUST pass on ALL Splunk versions
    And the matrix MUST be updated when this contract is updated

  @cicd-matrix @github-actions
  Scenario: GitHub Actions workflow matrix configuration
    """
    GitHub Actions workflows must implement the version matrix.
    """
    Then ".github/workflows/ci.yml" MUST contain:
      """yaml
      strategy:
        matrix:
          python-version: ['3.9', '3.10', '3.11']
      """
    And ".github/workflows/integration-tests.yml" MUST contain:
      """yaml
      strategy:
        matrix:
          splunk_version: ['9.3', '9.4', '10.0']
      """
    And matrix values MUST match this contract's supported versions
    And "fail-fast: false" SHOULD be set to test all combinations

  # ===========================================================================
  # VERSION UPDATE PROCEDURES
  # ===========================================================================

  @update-procedures
  Scenario: Procedure for adding new Splunk version support
    """
    When Splunk releases a new version, follow this procedure.
    """
    Given Splunk Inc. releases a new version X.Y
    Then within 30 days of release:
      | step | action                                                |
      | 1    | Update this contract with new version and dates       |
      | 2    | Update CI/CD matrix in GitHub Actions workflows       |
      | 3    | Update Docker image references                        |
      | 4    | Run full test suite against new version               |
      | 5    | Update documentation and README                       |
      | 6    | Create release notes mentioning new version support   |
    And the new version SHOULD be tested before official support announcement

  @update-procedures
  Scenario: Procedure for removing EOL Splunk version support
    """
    When a Splunk version reaches end-of-life, follow this procedure.
    """
    Given Splunk version X.Y reaches end-of-support date
    Then on or before the EOL date:
      | step | action                                                |
      | 1    | Update this contract to move version to unsupported   |
      | 2    | Remove version from CI/CD test matrix                 |
      | 3    | Update documentation to remove version                |
      | 4    | Add deprecation notice in CHANGELOG                   |
    And users SHOULD be warned 30 days before dropping support
    And support removal SHOULD coincide with a minor version bump

  # ===========================================================================
  # COMPATIBILITY VALIDATION
  # ===========================================================================

  @validation
  Scenario: Validate version support claims
    """
    CI/CD must validate that claimed support is actually tested.
    """
    Given the add-on claims to support specific versions
    Then every claimed Splunk version MUST have passing integration tests
    And every claimed Python version MUST have passing unit tests
    And the README MUST accurately reflect tested versions
    And Splunkbase listing MUST match tested versions

  @validation @appinspect
  Scenario: AppInspect version compatibility
    """
    AppInspect validates version compatibility claims.
    """
    Given the add-on is submitted to Splunkbase
    Then app.conf MUST specify accurate version requirements
    And the "python.version" in app.conf MUST be "python3"
    And AppInspect MUST pass for all claimed Splunk versions

  # ===========================================================================
  # DOCUMENTATION REQUIREMENTS
  # ===========================================================================

  @documentation
  Scenario: Version support documentation
    """
    Documentation must clearly state supported versions.
    """
    Then the README MUST include a "Compatibility" section listing:
      | item                     | requirement                          |
      | Splunk Enterprise        | List all supported versions          |
      | Splunk Cloud             | State if supported                   |
      | Python                   | List supported Python versions       |
      | Operating Systems        | List tested OS platforms             |
    And the CHANGELOG MUST note version support changes
    And this contract file serves as the authoritative source

  # ===========================================================================
  # EXCEPTIONS AND EDGE CASES
  # ===========================================================================

  @exceptions
  Scenario: Extended support exceptions
    """
    In rare cases, extended support may be provided.
    """
    Given a customer requires support for an EOL Splunk version
    Then extended support MAY be provided only if:
      | condition                                                   |
      | Customer has formal support agreement                       |
      | Security vulnerabilities are addressed                      |
      | Extended support is time-limited (max 6 months)             |
      | Extended support is documented in separate branch           |
    And extended support MUST NOT delay new version adoption
    And extended support versions MUST NOT be in default CI/CD matrix
