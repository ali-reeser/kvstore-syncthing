# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: tests/features/ucc_structure.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD Contract - UCC Framework Structure Compliance
#
# PURPOSE:
# This contract defines the required directory structure for a UCC-compliant
# Splunk add-on. UCC (Universal Configuration Console) generates specific
# files and directories that MUST NOT be manually created or modified.
#
# UCC DOCUMENTATION:
# https://splunk.github.io/addonfactory-ucc-generator/
# ===============================================================================

@ucc @structure @contract
Feature: UCC Framework Directory Structure Compliance
  As a Splunk add-on developer using UCC framework
  I need to follow the UCC-generated directory structure
  So that my add-on works correctly with Splunk and can be maintained via UCC

  Background:
    Given I am developing a UCC-based Splunk add-on
    And the add-on name is "kvstore_syncthing"
    And the UCC version is "6.x" or higher

  # ===========================================================================
  # REQUIRED FILES (Developer Must Create)
  # ===========================================================================

  @required-files
  Scenario: globalConfig.json is the single source of truth
    """
    UCC Contract: globalConfig.json defines ALL UI components, REST handlers,
    modular inputs, and configuration. UCC generates everything from this file.
    """
    Then the file "globalConfig.json" MUST exist at the project root
    And "globalConfig.json" MUST contain the "meta" section with:
      | field         | required | description                          |
      | name          | yes      | Add-on internal name (no spaces)     |
      | displayName   | yes      | Human-readable add-on name           |
      | version       | yes      | Semantic version string              |
      | restRoot      | yes      | REST API root path                   |
      | schemaVersion | yes      | UCC schema version (currently 0.0.3) |
    And "globalConfig.json" MUST be valid JSON
    And "globalConfig.json" MUST pass UCC schema validation

  @required-files
  Scenario: Package directory structure
    """
    UCC Contract: Source code lives in package/ directory structure.
    UCC reads from package/ and generates output/ during build.
    """
    Then the directory "package/" MUST exist
    And the directory "package/default/" MUST exist
    And the file "package/default/app.conf" MUST exist
    And "package/default/app.conf" MUST contain [launcher] section
    And "package/default/app.conf" MUST contain version matching globalConfig.json

  # ===========================================================================
  # AUTO-GENERATED FILES (Developer MUST NOT Create)
  # ===========================================================================

  @auto-generated @do-not-create
  Scenario: UCC generates REST handlers from globalConfig tabs
    """
    UCC Contract: REST handlers for configuration tabs are AUTO-GENERATED.
    Developers MUST NOT create custom REST handler classes for configuration.
    UCC uses splunktaucclib.rest_handler for all CRUD operations.
    """
    When UCC processes globalConfig.json "pages.configuration.tabs"
    Then UCC generates REST handlers in "output/<addon>/bin/"
    And each tab generates a handler named "<addon>_rh_<tab_name>.py"
    And these handlers use "splunktaucclib.rest_handler.admin_external.AdminExternalHandler"
    And developers MUST NOT manually create files matching "*_rh_*.py"
    And developers MUST NOT create custom classes extending "AdminExternalHandler"

  @auto-generated @do-not-create
  Scenario: UCC generates modular input stubs from services
    """
    UCC Contract: Modular input scripts are AUTO-GENERATED from services.
    Developers extend functionality via inputHelperModule, not custom scripts.
    """
    When UCC processes globalConfig.json "pages.inputs.services"
    Then UCC generates input script "output/<addon>/bin/<service_name>.py"
    And the script imports from "splunktaucclib.modinput_wrapper"
    And the script uses "ModInputWrapper" base class
    And developers MUST NOT manually create modular input scripts
    And developers MUST use "inputHelperModule" to add custom logic

  @auto-generated @do-not-create
  Scenario: UCC generates conf files from globalConfig
    """
    UCC Contract: Configuration files are AUTO-GENERATED.
    Each tab in globalConfig creates a corresponding .conf file.
    """
    When UCC processes globalConfig.json
    Then UCC generates "output/<addon>/default/<addon>_settings.conf"
    And UCC generates "output/<addon>/default/inputs.conf" for services
    And UCC generates "output/<addon>/README/<addon>_settings.conf.spec"
    And developers MUST NOT manually create these .conf files
    And developers MAY create additional .conf files not defined in globalConfig

  @auto-generated @do-not-create
  Scenario: UCC generates UI components in appserver
    """
    UCC Contract: All UI components are AUTO-GENERATED from globalConfig.
    The entire appserver/ directory is generated by UCC.
    """
    When UCC builds the add-on
    Then UCC generates "output/<addon>/appserver/static/js/build/"
    And UCC generates "output/<addon>/appserver/templates/"
    And UCC generates "output/<addon>/appserver/static/openapi.json"
    And developers MUST NOT manually create files in "appserver/"
    And developers MAY use "customTab" in globalConfig for custom UI

  @auto-generated @do-not-create
  Scenario: UCC installs Python dependencies in lib
    """
    UCC Contract: Python dependencies are installed in lib/ during build.
    UCC always includes solnlib and splunktaucclib.
    """
    When UCC builds the add-on
    Then UCC creates "output/<addon>/lib/"
    And "lib/" contains "solnlib" package
    And "lib/" contains "splunktaucclib" package
    And developers MUST NOT manually install packages in "lib/"
    And developers MUST declare dependencies in "package/lib/requirements.txt"

  # ===========================================================================
  # EXTENSION POINTS (Developer MAY Create)
  # ===========================================================================

  @extension-points
  Scenario: inputHelperModule for custom modular input logic
    """
    UCC Contract: Custom input logic goes in inputHelperModule.
    This is the ONLY approved way to add custom code to modular inputs.
    """
    Given a service definition in globalConfig with "inputHelperModule"
    Then the helper module MUST be placed in "package/bin/<helper_name>.py"
    And the helper module MUST implement the required interface:
      | method                | required | description                     |
      | validate_input        | no       | Custom validation logic         |
      | stream_events         | yes      | Event streaming implementation  |
    And the helper MUST use splunk-sdk for all Splunk API calls
    And the helper MUST NOT use raw HTTP clients (requests, urllib)

  @extension-points
  Scenario: customScript for alert action logic
    """
    UCC Contract: Alert action logic goes in customScript.
    This is the ONLY approved way to add custom code to alert actions.
    """
    Given an alert action definition in globalConfig with "customScript"
    Then the script MUST be placed in "package/bin/<script_name>.py"
    And the script receives alert parameters via "sys.stdin"
    And the script MUST use splunk-sdk for Splunk API interactions
    And the script MUST NOT use raw HTTP clients

  @extension-points
  Scenario: additional_packaging.py for build customization
    """
    UCC Contract: Build customization via additional_packaging.py.
    This hook runs during ucc-gen build for custom packaging needs.
    """
    Then developers MAY create "additional_packaging.py" at project root
    And this file is executed during "ucc-gen build"
    And it can modify the output directory contents
    And it MUST NOT modify auto-generated UCC files

  @extension-points
  Scenario: Custom validation hooks in globalConfig
    """
    UCC Contract: Field validation via validators in globalConfig.
    For complex validation, use hook property with custom JavaScript.
    """
    Given an entity field in globalConfig requiring custom validation
    Then developers SHOULD use built-in validators when possible:
      | validator | description                              |
      | string    | Min/max length validation                |
      | number    | Numeric range validation                 |
      | regex     | Pattern matching validation              |
      | url       | URL format validation                    |
      | email     | Email format validation                  |
      | ipv4      | IPv4 address validation                  |
      | date      | Date format validation                   |
    And for complex validation, use "hook" property with JavaScript module
    And hook modules MUST be placed in "package/appserver/static/js/build/custom/"

  # ===========================================================================
  # FORBIDDEN PATTERNS (Developer MUST NOT Do)
  # ===========================================================================

  @forbidden @anti-pattern
  Scenario: No custom handler directories
    """
    UCC Contract: Custom handler directory structures are FORBIDDEN.
    UCC generates all handlers - no src/handlers/ or similar.
    """
    Then the project MUST NOT contain "src/<addon>/handlers/"
    And the project MUST NOT contain custom Python modules for:
      | forbidden pattern           | reason                              |
      | *Handler.py (custom)        | UCC generates handlers              |
      | *_handler.py (custom)       | UCC generates handlers              |
      | rest_handler.py (custom)    | Use splunktaucclib                  |
      | admin_handler.py (custom)   | Use splunktaucclib                  |
    And developers MUST delete any existing custom handler code
    And all handler logic MUST be defined in globalConfig.json

  @forbidden @anti-pattern
  Scenario: No homebrew HTTP clients
    """
    UCC Contract: Raw HTTP clients are FORBIDDEN for Splunk APIs.
    All Splunk interactions MUST use splunk-sdk.
    """
    Then custom code MUST NOT import "requests" for Splunk APIs
    And custom code MUST NOT import "urllib" for Splunk APIs
    And custom code MUST NOT import "http.client" for Splunk APIs
    And custom code MUST NOT import "aiohttp" for Splunk APIs
    And all Splunk API calls MUST use "splunklib" from splunk-sdk
    And external API calls (non-Splunk) MAY use appropriate clients

  @forbidden @anti-pattern
  Scenario: No manual conf file editing for UCC-managed configs
    """
    UCC Contract: UCC-managed conf files are FORBIDDEN from manual editing.
    All configuration changes MUST go through globalConfig.json.
    """
    Then developers MUST NOT manually edit:
      | file pattern                | reason                              |
      | *_settings.conf             | Generated from globalConfig tabs    |
      | restmap.conf (UCC section)  | Generated from globalConfig         |
      | web.conf (UCC section)      | Generated from globalConfig         |
      | inputs.conf (UCC services)  | Generated from globalConfig services|
    And changes to these files MUST be made in globalConfig.json
    And "ucc-gen build" regenerates these files

  # ===========================================================================
  # BUILD AND DEPLOYMENT
  # ===========================================================================

  @build
  Scenario: UCC build command generates complete add-on
    """
    UCC Contract: ucc-gen build is the ONLY way to build the add-on.
    Manual assembly of add-on packages is FORBIDDEN.
    """
    Given globalConfig.json is valid
    And package/ directory contains source files
    When I run "ucc-gen build --source package"
    Then UCC creates "output/<addon>/" with complete add-on structure
    And the output is ready for Splunk installation
    And developers MUST NOT manually assemble add-on packages

  @build
  Scenario: UCC package command creates distributable archive
    """
    UCC Contract: ucc-gen package creates the .tar.gz/.spl for distribution.
    """
    Given UCC build has completed successfully
    When I run "ucc-gen package --path output/<addon>"
    Then UCC creates "<addon>-<version>.tar.gz"
    And the archive passes Splunk AppInspect validation
    And the archive can be uploaded to Splunkbase

  @versioning
  Scenario: Version management via globalConfig.json
    """
    UCC Contract: Version is defined in globalConfig.json meta section.
    Build can override with --ta-version flag.
    """
    Given globalConfig.json contains "meta.version"
    When I run "ucc-gen build --ta-version 1.0.0"
    Then the built add-on has version "1.0.0"
    And app.conf is updated with the version
    And package metadata reflects the version
