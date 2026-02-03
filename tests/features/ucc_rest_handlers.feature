# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: tests/features/ucc_rest_handlers.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD Contract - UCC REST Handler Architecture
#
# PURPOSE:
# This contract defines how UCC handles REST APIs for configuration.
# UCC auto-generates REST handlers from globalConfig.json.
# Developers MUST NOT create custom REST handler classes.
#
# UCC DOCUMENTATION:
# https://splunk.github.io/addonfactory-ucc-generator/configurations/
# ===============================================================================

@ucc @rest-handlers @contract
Feature: UCC REST Handler Architecture
  As a Splunk add-on developer
  I need to understand that UCC generates REST handlers
  So that I don't create custom handlers that conflict with UCC

  Background:
    Given I am developing a UCC-based Splunk add-on
    And the add-on has configuration tabs defined in globalConfig.json

  # ===========================================================================
  # UCC GENERATED REST HANDLERS
  # ===========================================================================

  @generated @do-not-create
  Scenario: UCC generates REST handlers from tabs
    """
    UCC generates a REST handler for each configuration tab.
    Developers MUST NOT create custom REST handlers for configuration.
    """
    Given globalConfig.json contains tabs:
      | tab name              | purpose                               |
      | destinations          | Sync destination configuration        |
      | sync_profiles         | Sync profile settings                 |
      | collection_mappings   | Collection mapping definitions        |
      | token_management      | Token and auth settings               |
      | logging               | Logging configuration                 |
    When UCC builds the add-on
    Then UCC generates REST handlers in "output/<addon>/bin/":
      | generated file                              | source tab          |
      | <addon>_rh_destinations.py                  | destinations        |
      | <addon>_rh_sync_profiles.py                 | sync_profiles       |
      | <addon>_rh_collection_mappings.py           | collection_mappings |
      | <addon>_rh_token_management.py              | token_management    |
      | <addon>_rh_logging.py                       | logging             |
    And these handlers use "splunktaucclib.rest_handler"
    And developers MUST NOT create files named "*_rh_*.py"

  @generated @handler-structure
  Scenario: UCC REST handler uses AdminExternalHandler
    """
    UCC-generated handlers extend AdminExternalHandler from splunktaucclib.
    This provides CRUD operations automatically.
    """
    Given a UCC-generated REST handler file
    Then the handler contains:
      """python
      from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
      from splunktaucclib.rest_handler.endpoint import (
          field,
          validator,
          RestModel,
          DataInputModel,
          SingleModel,
          MultipleModel,
      )

      # Fields auto-generated from globalConfig entity definitions
      fields = [
          field.RestField('name', required=True, encrypted=False, ...),
          # ... more fields from globalConfig ...
      ]

      # Model defines REST endpoint structure
      model = RestModel(fields, name=None)

      # Endpoint handler
      endpoint = SingleModel('kvstore_syncthing_destinations', model)

      class Handler(AdminExternalHandler):
          def __init__(self):
              super().__init__(endpoint, ...)
      """
    And the handler automatically provides:
      | HTTP method | operation                              |
      | GET         | List/retrieve configuration entries    |
      | POST        | Create new configuration entry         |
      | PUT         | Update existing configuration entry    |
      | DELETE      | Remove configuration entry             |

  @generated @restmap
  Scenario: UCC generates restmap.conf for endpoint routing
    """
    UCC generates restmap.conf to route REST API requests.
    This connects URL paths to generated handlers.
    """
    When UCC builds the add-on
    Then UCC generates "output/<addon>/default/restmap.conf" with:
      """
      [admin:kvstore_syncthing]
      match = /
      members = kvstore_syncthing_destinations, kvstore_syncthing_sync_profiles, ...

      [admin_external:kvstore_syncthing_destinations]
      handlertype = python
      handlerfile = kvstore_syncthing_rh_destinations.py
      handleractions = edit, list, remove, create
      """
    And REST endpoints are accessible at:
      | URL pattern                                           | handler           |
      | /servicesNS/{owner}/{app}/kvstore_syncthing_destinations | _rh_destinations |
      | /servicesNS/{owner}/{app}/kvstore_syncthing_sync_profiles | _rh_sync_profiles|

  # ===========================================================================
  # WHAT DEVELOPERS MUST NOT DO
  # ===========================================================================

  @forbidden @anti-pattern
  Scenario: Custom REST handler classes are forbidden
    """
    Developers MUST NOT create custom REST handler classes.
    UCC handles all REST API concerns automatically.
    """
    Then the project MUST NOT contain:
      | forbidden pattern                    | reason                           |
      | class *Handler(AdminExternalHandler) | UCC generates these              |
      | class *Handler(PersistentHandler)    | UCC generates these              |
      | class *RestHandler                   | Use globalConfig.json instead    |
      | import splunk.admin                  | Use splunktaucclib via UCC       |
    And if custom REST logic is needed, use:
      | approved approach                    | when to use                      |
      | globalConfig hook property           | Custom form validation           |
      | globalConfig customTab               | Custom UI components             |
      | Alert action customScript            | Alert response logic             |
      | inputHelperModule                    | Data collection logic            |

  @forbidden @anti-pattern
  Scenario: Manual restmap.conf editing is forbidden
    """
    The restmap.conf file is auto-generated by UCC.
    Manual edits will be overwritten on next build.
    """
    Then developers MUST NOT manually edit:
      | file                    | reason                                |
      | default/restmap.conf    | Auto-generated from globalConfig      |
      | default/web.conf        | Auto-generated for UI routing         |
    And configuration changes MUST be made in globalConfig.json
    And running "ucc-gen build" regenerates these files

  @forbidden @anti-pattern
  Scenario: Custom conf handlers are forbidden
    """
    Developers MUST NOT create custom .conf file handlers.
    UCC generates all conf file management from globalConfig.json.
    """
    Then the project MUST NOT contain:
      | forbidden pattern                    | reason                           |
      | ConfigHandler class                  | UCC manages conf files           |
      | SplunkConfig subclass                | Use globalConfig tabs            |
      | Manual conf file parsing             | UCC handles via REST API         |
    And configuration storage is handled by:
      | mechanism                            | purpose                          |
      | globalConfig tabs                    | Generates *_settings.conf        |
      | globalConfig inputs.services         | Generates inputs.conf            |
      | globalConfig alerts                  | Generates alert_actions.conf     |
      | passwords.conf (automatic)           | Encrypted field storage          |

  # ===========================================================================
  # ACCESSING CONFIGURATION IN CODE
  # ===========================================================================

  @accessing-config
  Scenario: Reading configuration from inputHelperModule
    """
    inputHelperModule can read configuration using helper methods.
    Configuration is available via REST API (splunk-sdk).
    """
    Given inputHelperModule needs to read destination configuration
    Then the module SHOULD use splunk-sdk:
      """python
      def stream_events(helper, ew):
          # Get splunk service
          session_key = helper.context_meta['session_key']
          service = client.connect(token=session_key, ...)

          # Read destination configuration via REST API
          # UCC generates endpoint at: kvstore_syncthing_destinations
          response = service.get(
              'servicesNS/nobody/kvstore_syncthing/kvstore_syncthing_destinations',
              output_mode='json'
          )
          destinations = json.loads(response.body.read())['entry']

          # Get specific destination
          dest_name = helper.get_arg('destination')
          dest_config = next(
              (d for d in destinations if d['name'] == dest_name),
              None
          )

          if dest_config:
              host = dest_config['content']['host']
              port = dest_config['content']['port']
              # ... use configuration
      """
    And this approach:
      | advantage                    | description                          |
      | Uses UCC-generated endpoint  | Consistent with UCC architecture     |
      | Respects access controls     | Uses Splunk's permission system      |
      | Handles encryption           | Encrypted fields auto-decrypted      |

  @accessing-config @solnlib
  Scenario: Using solnlib for configuration access
    """
    solnlib provides helper functions for common configuration tasks.
    UCC includes solnlib in the lib/ directory.
    """
    Given inputHelperModule needs configuration access
    Then the module MAY use solnlib utilities:
      """python
      from solnlib import conf_manager

      def stream_events(helper, ew):
          # Using solnlib conf_manager
          cfm = conf_manager.ConfManager(
              helper.context_meta['session_key'],
              'kvstore_syncthing',
              realm='__REST_CREDENTIAL__#kvstore_syncthing#configs/conf-kvstore_syncthing_settings'
          )

          # Get configuration
          conf = cfm.get_conf('kvstore_syncthing_settings')
          destinations_stanza = conf.get('destinations')
      """
    And solnlib provides:
      | module              | purpose                                 |
      | conf_manager        | Configuration file access               |
      | credentials         | Credential storage access               |
      | log                 | Structured logging                      |
      | net_utils           | Network utilities                       |
      | orphan_process      | Process management                      |

  # ===========================================================================
  # CAPABILITIES AND PERMISSIONS
  # ===========================================================================

  @capabilities
  Scenario: REST endpoint capabilities
    """
    UCC can define required capabilities for REST endpoints.
    This controls who can access configuration.
    """
    Given globalConfig.json contains "capabilities" in a tab
    Then the capabilities are written to restmap.conf:
      """json
      {
        "tabs": [{
          "name": "destinations",
          "capabilities": {
            "read": "admin_all_objects",
            "write": "admin_all_objects"
          },
          ...
        }]
      }
      """
    And generated restmap.conf includes:
      """
      [admin_external:kvstore_syncthing_destinations]
      capability.read = admin_all_objects
      capability.write = admin_all_objects
      """

  # ===========================================================================
  # CUSTOM REST HANDLERS (Only for Non-Configuration)
  # ===========================================================================

  @custom-rest @exception
  Scenario: Custom REST handlers for non-configuration endpoints
    """
    Custom REST handlers MAY be created ONLY for non-configuration purposes.
    Examples: status endpoints, sync triggers, health checks.
    These are NOT managed by globalConfig.json.
    """
    Given the add-on needs a REST endpoint not for configuration
    Then a custom handler MAY be created for:
      | purpose                    | example endpoint                      |
      | Health check               | /kvstore_syncthing/health             |
      | Manual sync trigger        | /kvstore_syncthing/sync/trigger       |
      | Status reporting           | /kvstore_syncthing/status             |
    And the handler MUST:
      | requirement                           | reason                         |
      | Not overlap with UCC endpoints        | Avoid conflicts                |
      | Use splunktaucclib base classes       | Maintain consistency           |
      | Be placed in package/bin/             | Standard location              |
      | Have manual restmap.conf entry        | In package/default/            |
    And this is the EXCEPTION, not the rule
    And most add-ons do NOT need custom REST handlers
