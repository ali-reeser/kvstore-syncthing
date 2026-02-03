# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: tests/features/ucc_kvstore_sync.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD Contract - KVStore Sync Implementation within UCC Framework
#
# PURPOSE:
# This contract defines how KVStore sync functionality should be implemented
# within the UCC framework constraints. All sync logic goes in inputHelperModule.
#
# ARCHITECTURE:
# - globalConfig.json defines UI and configuration
# - inputHelperModule implements sync logic using splunk-sdk
# - NO custom handlers - UCC generates all handlers
# ===============================================================================

@ucc @kvstore-sync @contract
Feature: KVStore Sync Implementation in UCC Framework
  As a KVStore synchronization add-on developer
  I need to implement sync functionality within UCC constraints
  So that the add-on follows Splunk best practices and is maintainable

  Background:
    Given I am developing the KVStore Syncthing add-on
    And the add-on uses UCC framework
    And all sync logic is in inputHelperModule

  # ===========================================================================
  # ARCHITECTURE OVERVIEW
  # ===========================================================================

  @architecture
  Scenario: KVStore Syncthing UCC-compliant architecture
    """
    The add-on architecture follows UCC conventions.
    All business logic is in inputHelperModule, not custom handlers.
    """
    Then the add-on architecture is:
      | component                    | location                        | purpose                        |
      | globalConfig.json            | project root                    | UI and configuration schema    |
      | package/default/app.conf     | package/default/                | Splunk app manifest            |
      | package/bin/kvstore_sync_helper.py | package/bin/             | Sync logic (inputHelperModule) |
      | package/lib/requirements.txt | package/lib/                    | Python dependencies            |
    And UCC generates during build:
      | generated                    | source                          |
      | bin/kvstore_sync_job.py      | globalConfig services           |
      | bin/*_rh_*.py                | globalConfig tabs               |
      | appserver/                   | globalConfig UI                 |
      | lib/solnlib, splunktaucclib  | UCC requirements                |

  # ===========================================================================
  # GLOBAL CONFIG STRUCTURE
  # ===========================================================================

  @globalconfig
  Scenario: globalConfig.json for KVStore Syncthing
    """
    globalConfig.json defines all configuration and inputs.
    This is the ONLY place to define add-on structure.
    """
    Given globalConfig.json exists at project root
    Then it MUST contain:
      """json
      {
        "meta": {
          "name": "kvstore_syncthing",
          "displayName": "KVStore Syncthing",
          "version": "X.Y.Z",
          "restRoot": "kvstore_syncthing",
          "schemaVersion": "0.0.3"
        },
        "pages": {
          "configuration": {
            "title": "Configuration",
            "tabs": [
              /* destinations tab - sync target configuration */
              /* sync_profiles tab - sync behavior settings */
              /* collection_mappings tab - what to sync */
              /* token_management tab - auth credentials */
              /* logging tab - log level settings */
            ]
          },
          "inputs": {
            "title": "Sync Jobs",
            "services": [
              {
                "name": "kvstore_sync_job",
                "title": "KVStore Sync Job",
                "inputHelperModule": "kvstore_sync_helper",
                "entity": [
                  /* job configuration fields */
                ]
              }
            ]
          }
        }
      }
      """

  @globalconfig @destinations
  Scenario: Destinations tab configuration
    """
    The destinations tab defines sync target configuration.
    Supports REST API, HEC, File Export, Cloud Storage destinations.
    """
    Given globalConfig.json contains destinations tab
    Then the tab entity MUST include:
      | field             | type          | required | purpose                      |
      | name              | text          | yes      | Destination identifier       |
      | destination_type  | singleSelect  | yes      | Type: rest/hec/file/cloud    |
      | host              | text          | yes      | Target hostname              |
      | port              | text          | yes      | Target port                  |
      | use_ssl           | checkbox      | no       | Enable SSL                   |
      | verify_ssl        | checkbox      | no       | Verify certificates          |
      | auth_type         | singleSelect  | yes      | Authentication method        |
      | password          | text          | yes      | Credentials (encrypted=true) |
    And destination_type options include:
      | value        | label                           |
      | splunk_rest  | Splunk REST API                 |
      | splunk_hec   | Splunk HEC (Index & Rehydrate)  |
      | s3_export    | AWS S3 Export                   |
      | file_export  | File Export                     |

  @globalconfig @services
  Scenario: Sync job service definition
    """
    The sync job service creates the modular input.
    inputHelperModule contains all sync logic.
    """
    Given globalConfig.json contains kvstore_sync_job service
    Then the service MUST specify:
      """json
      {
        "name": "kvstore_sync_job",
        "title": "KVStore Sync Job",
        "inputHelperModule": "kvstore_sync_helper",
        "entity": [
          {"field": "name", "label": "Job Name", "type": "text", "required": true},
          {"field": "destination", "label": "Destination", "type": "singleSelect",
           "options": {"endpointUrl": "kvstore_syncthing_destinations"}},
          {"field": "sync_profile", "label": "Sync Profile", "type": "singleSelect",
           "options": {"endpointUrl": "kvstore_syncthing_sync_profiles"}},
          {"field": "collection_mappings", "label": "Collections", "type": "multipleSelect",
           "options": {"endpointUrl": "kvstore_syncthing_collection_mappings"}},
          {"field": "interval", "label": "Interval", "type": "interval"}
        ]
      }
      """
    And "inputHelperModule": "kvstore_sync_helper" points to package/bin/kvstore_sync_helper.py

  # ===========================================================================
  # INPUT HELPER MODULE IMPLEMENTATION
  # ===========================================================================

  @inputhelper @sync-logic
  Scenario: kvstore_sync_helper.py implements all sync logic
    """
    All KVStore synchronization logic lives in the inputHelperModule.
    This is the ONLY place for custom business logic.
    """
    Given package/bin/kvstore_sync_helper.py exists
    Then the module MUST implement stream_events:
      """python
      # =========================================================================
      # File: package/bin/kvstore_sync_helper.py
      # Type: UCC inputHelperModule - KVStore Sync Logic
      #
      # ARCHITECTURE:
      # This is the ONLY file containing custom sync logic.
      # All Splunk API calls use splunk-sdk (splunklib).
      # NO raw HTTP clients (requests, urllib) for Splunk APIs.
      # =========================================================================

      import json
      import time
      import traceback
      import splunklib.client as client
      from splunklib import binding

      def validate_input(helper, definition):
          """
          Validate input configuration before saving.
          Called by UCC when user creates/edits sync job.
          """
          destination = definition.parameters.get('destination')
          if not destination:
              raise ValueError("Destination is required")
          # Additional validation...
          return

      def stream_events(helper, ew):
          """
          Main entry point - performs KVStore synchronization.

          Args:
              helper: UCC input helper (provides config access, logging, checkpoints)
              ew: EventWriter for streaming events to Splunk
          """
          helper.log_info("Starting KVStore sync job")

          try:
              # Get job configuration
              destination_name = helper.get_arg('destination')
              sync_profile_name = helper.get_arg('sync_profile')
              collection_mappings = helper.get_arg('collection_mappings')

              # Get Splunk service using session key from helper
              source_service = _get_splunk_service(helper)

              # Load destination configuration via REST API
              dest_config = _get_destination_config(source_service, destination_name)

              # Load sync profile via REST API
              sync_profile = _get_sync_profile(source_service, sync_profile_name)

              # Connect to destination
              dest_service = _connect_to_destination(dest_config)

              # Perform sync for each collection mapping
              for mapping_name in collection_mappings.split(','):
                  mapping = _get_collection_mapping(source_service, mapping_name)
                  _sync_collection(helper, ew, source_service, dest_service,
                                   mapping, sync_profile)

              helper.log_info("KVStore sync job completed successfully")

          except Exception as e:
              helper.log_error(f"Sync job failed: {str(e)}")
              helper.log_error(traceback.format_exc())
              _write_error_event(helper, ew, str(e))
              raise

      def _get_splunk_service(helper):
          """Create splunk-sdk service from helper context."""
          session_key = helper.context_meta['session_key']
          server_uri = helper.context_meta['server_uri']
          # Parse server URI and create service
          return client.connect(token=session_key, ...)

      # ... additional helper functions ...
      """

  @inputhelper @splunk-sdk
  Scenario: Sync logic uses splunk-sdk exclusively
    """
    All Splunk API interactions MUST use splunk-sdk.
    Raw HTTP clients are FORBIDDEN for Splunk APIs.
    """
    Given kvstore_sync_helper.py performs Splunk operations
    Then it MUST use splunk-sdk for:
      | operation                    | splunk-sdk approach                   |
      | KVStore read                 | service.kvstore['coll'].data.query()  |
      | KVStore write                | service.kvstore['coll'].data.insert() |
      | KVStore batch                | service.kvstore['coll'].data.batch_save()|
      | Config read                  | service.get('endpoint', ...)          |
      | Search execution             | service.jobs.create(query, ...)       |
    And it MUST NOT use:
      | forbidden                    | reason                                |
      | requests.get/post            | Use splunklib.client                  |
      | urllib.request               | Use splunklib.client                  |
      | http.client                  | Use splunklib.client                  |
      | Custom REST wrapper          | Use splunklib.client                  |

  @inputhelper @sync-modes
  Scenario: Sync modes implemented in helper
    """
    Different sync modes are implemented within the helper module.
    Mode selection is based on sync_profile configuration.
    """
    Given kvstore_sync_helper.py implements sync modes
    Then the following modes MUST be supported:
      | mode          | behavior                                      |
      | full_sync     | Replace all destination records               |
      | incremental   | Only sync changed records (by timestamp)      |
      | append_only   | Only add new records, never update            |
      | master_slave  | Exact replica with orphan deletion            |
    And mode implementation:
      """python
      def _sync_collection(helper, ew, src_svc, dest_svc, mapping, profile):
          sync_mode = profile['sync_mode']

          if sync_mode == 'full_sync':
              _full_sync(helper, ew, src_svc, dest_svc, mapping)
          elif sync_mode == 'incremental':
              _incremental_sync(helper, ew, src_svc, dest_svc, mapping, profile)
          elif sync_mode == 'append_only':
              _append_only_sync(helper, ew, src_svc, dest_svc, mapping)
          elif sync_mode == 'master_slave':
              _master_slave_sync(helper, ew, src_svc, dest_svc, mapping)
          else:
              raise ValueError(f"Unknown sync mode: {sync_mode}")
      ```

  # ===========================================================================
  # DESTINATION TYPES
  # ===========================================================================

  @destinations @rest
  Scenario: Splunk REST API destination
    """
    REST API destination syncs to another Splunk instance via KVStore API.
    Uses splunk-sdk for both source and destination.
    """
    Given a destination with type "splunk_rest"
    Then sync logic MUST:
      """python
      def _connect_to_destination(dest_config):
          """Connect to destination Splunk instance."""
          if dest_config['destination_type'] == 'splunk_rest':
              return client.connect(
                  host=dest_config['host'],
                  port=int(dest_config['port']),
                  token=dest_config['password'],  # Decrypted by UCC
                  scheme='https' if dest_config['use_ssl'] else 'http',
                  autologin=True
              )
      ```
    And use splunk-sdk KVStore operations on destination service

  @destinations @hec
  Scenario: HEC destination with Index & Rehydrate
    """
    HEC destination indexes data, then rehydrates to KVStore.
    This enables sync across network boundaries.
    """
    Given a destination with type "splunk_hec"
    Then sync logic MUST:
      | step | operation                                      |
      | 1    | Read source KVStore data via splunk-sdk        |
      | 2    | Format as HEC events with metadata             |
      | 3    | Send to HEC endpoint (may use requests)        |
      | 4    | Destination runs saved search to rehydrate     |
    And HEC is an EXCEPTION where external HTTP is acceptable
    And the rehydration search on destination:
      """spl
      index=kvstore_sync sourcetype=kvstore:sync:data
      | eval _key=kvstore_key
      | outputlookup append=true kvstore_collection
      ```

  @destinations @file
  Scenario: File export destination
    """
    File export writes KVStore data to local filesystem.
    Used for air-gapped environments.
    """
    Given a destination with type "file_export"
    Then sync logic MUST:
      | step | operation                                      |
      | 1    | Read source KVStore via splunk-sdk             |
      | 2    | Serialize to JSON/CSV format                   |
      | 3    | Write to configured file path                  |
      | 4    | Generate checksums for integrity               |
      | 5    | Write manifest file                            |
    And file operations use Python standard library (not Splunk SDK)

  @destinations @s3
  Scenario: S3 cloud storage destination
    """
    S3 destination uploads KVStore exports to cloud storage.
    Uses boto3 for S3 operations.
    """
    Given a destination with type "s3_export"
    Then sync logic MUST:
      | step | operation                                      |
      | 1    | Read source KVStore via splunk-sdk             |
      | 2    | Serialize to export format                     |
      | 3    | Upload to S3 using boto3                       |
      | 4    | Store manifest with checksums                  |
    And boto3 is acceptable for AWS S3 operations (not Splunk API)

  # ===========================================================================
  # EVENT OUTPUT
  # ===========================================================================

  @events
  Scenario: Sync status events
    """
    The sync job writes status events to Splunk.
    These enable monitoring and dashboards.
    """
    Given kvstore_sync_helper.py completes sync operations
    Then it MUST write events via EventWriter:
      """python
      def _write_sync_status_event(helper, ew, status_data):
          event = helper.new_event(
              data=json.dumps({
                  'action': 'sync_completed',
                  'destination': status_data['destination'],
                  'collection': status_data['collection'],
                  'records_synced': status_data['count'],
                  'duration_seconds': status_data['duration'],
                  'timestamp': time.time()
              }),
              sourcetype='kvstore:sync:status',
              source='kvstore_syncthing'
          )
          ew.write_event(event)
      ```
    And events enable the UCC dashboard to show sync status

  # ===========================================================================
  # TESTING
  # ===========================================================================

  @testing
  Scenario: Unit tests for kvstore_sync_helper
    """
    The inputHelperModule MUST have comprehensive unit tests.
    Tests mock splunk-sdk and helper objects.
    """
    Given tests/unit/test_kvstore_sync_helper.py exists
    Then tests MUST cover:
      | test case                           | purpose                        |
      | test_validate_input_valid           | Valid config accepted          |
      | test_validate_input_missing_dest    | Missing destination rejected   |
      | test_stream_events_full_sync        | Full sync mode works           |
      | test_stream_events_incremental      | Incremental sync works         |
      | test_connection_failure             | Handle connection errors       |
      | test_kvstore_read_error             | Handle KVStore read errors     |
    And tests use pytest with mocking:
      ```python
      @pytest.fixture
      def mock_helper():
          helper = Mock()
          helper.get_arg.side_effect = lambda x: {
              'destination': 'test_dest',
              'sync_profile': 'test_profile',
              'collection_mappings': 'test_mapping'
          }.get(x)
          helper.context_meta = {'session_key': 'test_key', ...}
          return helper

      @patch('kvstore_sync_helper.client.connect')
      def test_stream_events_full_sync(mock_connect, mock_helper, mock_ew):
          # Setup mock service
          mock_service = Mock()
          mock_connect.return_value = mock_service
          mock_service.kvstore = {...}

          # Execute
          stream_events(mock_helper, mock_ew)

          # Verify
          mock_ew.write_event.assert_called()
      ```
