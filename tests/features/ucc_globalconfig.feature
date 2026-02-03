# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: tests/features/ucc_globalconfig.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD Contract - globalConfig.json Schema Definition
#
# PURPOSE:
# This contract defines the schema and rules for globalConfig.json.
# globalConfig.json is the SINGLE SOURCE OF TRUTH for UCC add-ons.
# All UI, REST handlers, and modular inputs are generated from this file.
#
# UCC DOCUMENTATION:
# https://splunk.github.io/addonfactory-ucc-generator/
# ===============================================================================

@ucc @globalconfig @contract
Feature: globalConfig.json Schema and Validation
  As a Splunk add-on developer using UCC framework
  I need globalConfig.json to be correctly structured
  So that UCC can generate a working Splunk add-on

  Background:
    Given I have a globalConfig.json file
    And UCC schema version is "0.0.3"

  # ===========================================================================
  # META SECTION (Required)
  # ===========================================================================

  @meta @required
  Scenario: Meta section defines add-on identity
    """
    The meta section is REQUIRED and defines the add-on's identity.
    UCC uses this to generate app.conf and REST endpoints.
    """
    Then globalConfig.json MUST contain "meta" object with:
      | field         | type   | required | constraints                        |
      | name          | string | yes      | Alphanumeric + underscore only     |
      | displayName   | string | yes      | Human-readable name                |
      | version       | string | yes      | Semantic version (X.Y.Z)           |
      | restRoot      | string | yes      | REST API namespace                 |
      | schemaVersion | string | yes      | Must be "0.0.3" or compatible      |
    And "name" MUST match pattern "^[a-zA-Z0-9_]+$"
    And "name" MUST NOT contain spaces or special characters
    And "restRoot" typically matches "name"

  @meta
  Scenario: Meta section optional fields
    Then globalConfig.json MAY contain in "meta":
      | field             | type   | description                            |
      | apiVersion        | string | API compatibility version              |
      | checkForUpdates   | bool   | Enable update checking                 |
      | defaultView       | string | Default view to display                |
      | os_dependentLibs  | array  | OS-specific library dependencies       |

  # ===========================================================================
  # PAGES SECTION (Required)
  # ===========================================================================

  @pages @required
  Scenario: Pages section defines UI structure
    """
    The pages section defines what users see in the add-on UI.
    It must contain at least configuration or inputs.
    """
    Then globalConfig.json MUST contain "pages" object
    And "pages" MUST contain at least one of:
      | page          | purpose                                    |
      | configuration | Settings and credential management         |
      | inputs        | Data collection input definitions          |
    And "pages" MAY contain:
      | page      | purpose                                      |
      | dashboard | Monitoring dashboard (UCC 5.42.0+)           |

  # ===========================================================================
  # CONFIGURATION PAGE
  # ===========================================================================

  @configuration @tabs
  Scenario: Configuration page with tabs
    """
    The configuration page contains tabs for different setting groups.
    Each tab generates a REST handler and conf file section.
    """
    Given globalConfig.json contains "pages.configuration"
    Then "configuration" MUST contain:
      | field       | type   | required | description                      |
      | title       | string | yes      | Page title shown in UI           |
      | description | string | no       | Page description                 |
      | tabs        | array  | yes      | Array of tab definitions         |
    And each tab generates a REST endpoint at "/servicesNS/{owner}/{app}/{restRoot}_{tab.name}"
    And each tab generates config stanza in "{restRoot}_settings.conf"

  @tabs @entity
  Scenario: Tab entity field definitions
    """
    Each tab contains entity fields that define form inputs.
    Entity fields map directly to .conf file attributes.
    """
    Given a tab definition in globalConfig.json
    Then each tab MUST contain:
      | field  | type   | required | description                      |
      | name   | string | yes      | Tab identifier (alphanumeric)    |
      | title  | string | yes      | Tab display title                |
      | entity | array  | yes      | Field definitions                |
    And each entity field MUST contain:
      | field | type   | required | description                      |
      | field | string | yes      | Attribute name in .conf          |
      | label | string | yes      | Form label shown to user         |
      | type  | string | yes      | Input type (see entity types)    |

  @entity @types
  Scenario: Supported entity field types
    """
    UCC supports specific field types that map to UI components.
    Developers MUST use these types - custom types are not supported.
    """
    Then valid entity types are:
      | type                    | description                              |
      | text                    | Single-line text input                   |
      | textarea                | Multi-line text input                    |
      | checkbox                | Boolean toggle                           |
      | singleSelect            | Dropdown with single selection           |
      | multipleSelect          | Multi-select dropdown                    |
      | radio                   | Radio button group                       |
      | file                    | File upload input                        |
      | oauth                   | OAuth authentication flow                |
      | custom                  | Custom React component                   |
      | helpLink                | Help documentation link                  |
      | interval                | Time interval selector                   |
      | index                   | Splunk index selector                    |
      | singleSelectSplunkSearch| Dynamic dropdown via SPL                 |
    And using an invalid type causes UCC build failure
    And custom components require "customTab" configuration

  @entity @options
  Scenario: Entity field options for select types
    """
    Select-type fields require options configuration.
    Options can be static or dynamic (endpoint-based).
    """
    Given an entity field with type "singleSelect" or "multipleSelect"
    Then the field MUST contain "options" object with either:
      | option              | description                               |
      | autoCompleteFields  | Static array of {value, label} objects    |
      | endpointUrl         | REST endpoint for dynamic options         |
    And when using "endpointUrl":
      | field       | required | description                          |
      | endpointUrl | yes      | REST endpoint path                   |
      | labelField  | yes      | Field to display as label            |
      | valueField  | yes      | Field to use as value                |

  @entity @validators
  Scenario: Field validation via validators array
    """
    Validators enforce input constraints in the UI.
    UCC provides built-in validators for common cases.
    """
    Given an entity field definition
    Then the field MAY contain "validators" array with:
      | validator type | properties                               |
      | string         | minLength, maxLength, errorMsg           |
      | number         | range [min, max], errorMsg               |
      | regex          | pattern, errorMsg                        |
      | url            | errorMsg                                 |
      | email          | errorMsg                                 |
      | ipv4           | errorMsg                                 |
      | date           | errorMsg                                 |
    And validators are evaluated in array order
    And all validators must pass for form submission

  @entity @encrypted
  Scenario: Encrypted fields for credentials
    """
    Sensitive data must use encrypted: true.
    UCC automatically handles encryption via Splunk's password storage.
    """
    Given an entity field storing sensitive data
    Then the field MUST have "encrypted": true
    And encrypted fields are stored in passwords.conf
    And encrypted fields never appear in cleartext logs
    And the UI masks encrypted field values

  @tabs @table
  Scenario: Tab table configuration for account management
    """
    Tabs can display a table of configured items (accounts, destinations).
    The table property enables list view with CRUD actions.
    """
    Given a tab that manages multiple items
    Then the tab MAY contain "table" object with:
      | field   | type   | required | description                      |
      | header  | array  | yes      | Column definitions               |
      | actions | array  | yes      | Available actions (edit, delete) |
      | moreInfo| array  | no       | Expandable detail fields         |
    And header items contain:
      | field | description                                     |
      | field | Attribute name to display                       |
      | label | Column header text                              |
    And valid actions are: "edit", "delete", "clone"

  # ===========================================================================
  # INPUTS PAGE (Services)
  # ===========================================================================

  @inputs @services
  Scenario: Inputs page defines modular inputs
    """
    The inputs page defines data collection inputs (modular inputs).
    Each service generates a modular input script.
    """
    Given globalConfig.json contains "pages.inputs"
    Then "inputs" MUST contain:
      | field    | type   | required | description                      |
      | title    | string | yes      | Page title                       |
      | services | array  | yes      | Modular input definitions        |
    And "inputs" MAY contain:
      | field       | type   | description                         |
      | description | string | Page description                    |
      | table       | object | Table display configuration         |

  @services @definition
  Scenario: Service definition structure
    """
    Each service defines a modular input type.
    UCC generates the input script and inputs.conf stanza.
    """
    Given a service in "pages.inputs.services"
    Then the service MUST contain:
      | field  | type   | required | description                      |
      | name   | string | yes      | Input type identifier            |
      | title  | string | yes      | Display title                    |
      | entity | array  | yes      | Input configuration fields       |
    And the service generates:
      | generated file                 | purpose                         |
      | bin/{service.name}.py          | Modular input script            |
      | default/inputs.conf            | Input stanza template           |
      | README/inputs.conf.spec        | Input specification             |

  @services @inputhelper
  Scenario: inputHelperModule for custom input logic
    """
    Custom input logic is implemented via inputHelperModule.
    This is the ONLY approved way to add custom code to inputs.
    """
    Given a service requiring custom data collection logic
    Then the service MUST define "inputHelperModule" property
    And the helper module MUST be placed in "package/bin/"
    And the helper module MUST implement:
      | method          | required | signature                         |
      | stream_events   | yes      | (helper, ew)                      |
      | validate_input  | no       | (definition, item) -> bool        |
    And "helper" provides access to:
      | property        | description                              |
      | get_arg()       | Get input argument value                 |
      | get_input_type()| Get the input type name                  |
      | context_meta    | Splunk context metadata                  |
    And "ew" is the EventWriter for streaming events

  # ===========================================================================
  # DASHBOARD PAGE
  # ===========================================================================

  @dashboard
  Scenario: Dashboard page for monitoring
    """
    The dashboard page provides pre-built monitoring panels.
    Available in UCC 5.42.0 and later.
    """
    Given UCC version is 5.42.0 or higher
    Then globalConfig.json MAY contain "pages.dashboard" with:
      | field  | type   | required | description                      |
      | panels | array  | yes      | Dashboard panel definitions      |
    And default panels include:
      | panel name     | description                             |
      | default        | Overview, ingestion, errors, resources  |
    And custom dashboards via "custom_dashboard.json" file

  # ===========================================================================
  # ALERT ACTIONS
  # ===========================================================================

  @alerts
  Scenario: Alert actions definition
    """
    Alert actions enable responding to triggered alerts.
    Each alert action generates a script in bin/.
    """
    Given globalConfig.json contains "alerts"
    Then "alerts" is an array of alert action definitions
    And each alert MUST contain:
      | field       | type   | required | description                   |
      | name        | string | yes      | Alert identifier              |
      | label       | string | yes      | Display label                 |
      | description | string | yes      | Alert description             |
      | entity      | array  | yes      | Alert parameter fields        |
    And each alert generates:
      | generated file                      | purpose                      |
      | bin/{alert.name}_modalert.py        | Alert action script          |
      | default/alert_actions.conf          | Alert configuration          |
      | README/alert_actions.conf.spec      | Alert specification          |

  @alerts @customscript
  Scenario: customScript for alert action implementation
    """
    Alert logic is implemented via customScript.
    This is the ONLY approved way to add custom alert code.
    """
    Given an alert action requiring custom logic
    Then the alert MAY define "customScript" property
    And the script MUST be placed in "package/bin/"
    And the script receives parameters via stdin (JSON)
    And the script MUST use splunk-sdk for Splunk interactions

  # ===========================================================================
  # HOOKS AND CUSTOM BEHAVIOR
  # ===========================================================================

  @hooks
  Scenario: Form behavior hooks
    """
    Hooks allow custom JavaScript for form behavior.
    Use sparingly - prefer built-in validators.
    """
    Given a tab or service requiring custom form behavior
    Then the definition MAY contain "hook" property with:
      | field   | type   | required | description                    |
      | src     | string | yes      | Path to JavaScript module      |
      | type    | string | no       | Hook type (default: "external")|
    And hook modules are placed in "package/appserver/static/js/build/custom/"
    And hooks can implement:
      | method         | description                              |
      | onCreate       | Called when creating new item            |
      | onEdit         | Called when editing existing item        |
      | onSave         | Called before saving                     |
      | onSaveSuccess  | Called after successful save             |
      | onSaveFail     | Called after failed save                 |
      | onRender       | Called when form renders                 |

  @modifyfields
  Scenario: Dynamic field behavior with modifyFieldsOnValue
    """
    modifyFieldsOnValue enables conditional field visibility.
    Use this for dependent field relationships.
    """
    Given an entity field that controls other fields' visibility
    Then the controlling field MAY have "modifyFieldsOnValue" array
    And each modifier contains:
      | field       | type   | required | description                    |
      | fieldValue  | any    | yes      | Value that triggers change     |
      | fieldsToModify| object| yes      | Fields and their new state     |
    And fieldsToModify can set:
      | property    | description                                |
      | display     | Show/hide field                            |
      | required    | Make field required/optional               |
      | value       | Set field value                            |
