# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: tests/features/ucc_modular_inputs.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD Contract - UCC Modular Input Development
#
# PURPOSE:
# This contract defines how to properly develop modular inputs in UCC.
# Modular inputs are the data collection mechanism in Splunk add-ons.
# UCC generates the scaffolding - developers implement inputHelperModule.
#
# UCC DOCUMENTATION:
# https://splunk.github.io/addonfactory-ucc-generator/inputs/
# ===============================================================================

@ucc @modular-inputs @contract
Feature: UCC Modular Input Development
  As a Splunk add-on developer
  I need to understand how UCC modular inputs work
  So that I can properly implement data collection functionality

  Background:
    Given I am developing a UCC-based Splunk add-on
    And the add-on uses modular inputs for data collection

  # ===========================================================================
  # UCC GENERATED INPUT STRUCTURE
  # ===========================================================================

  @generated @structure
  Scenario: UCC generates modular input scaffolding
    """
    UCC generates the modular input script from service definitions.
    Developers MUST NOT manually create these scripts.
    """
    Given globalConfig.json contains a service "kvstore_sync_job"
    When UCC builds the add-on
    Then UCC generates "output/<addon>/bin/kvstore_sync_job.py"
    And the generated script contains:
      | component              | purpose                                  |
      | ModInputWrapper import | Base class from splunktaucclib           |
      | SingleInstance class   | Ensures single input instance running    |
      | stream_events method   | Entry point for data collection          |
    And developers MUST NOT modify this generated file directly

  @generated @wrapper
  Scenario: ModInputWrapper provides input infrastructure
    """
    The generated input script uses ModInputWrapper from splunktaucclib.
    This wrapper handles all Splunk integration automatically.
    """
    Given a UCC-generated modular input script
    Then the script inherits from "ModInputWrapper" which provides:
      | capability              | description                             |
      | Argument parsing        | Parses inputs.conf stanza values        |
      | Checkpoint management   | Persistent state between runs           |
      | Event writing           | Splunk-compliant event streaming        |
      | Logging integration     | Structured logging via solnlib.log      |
      | Service account         | Authenticated Splunk service client     |
    And developers access these via the "helper" object
    And developers MUST NOT replace or override the wrapper

  # ===========================================================================
  # INPUT HELPER MODULE (Developer Code)
  # ===========================================================================

  @inputhelper @required
  Scenario: inputHelperModule is the developer extension point
    """
    All custom input logic MUST go in inputHelperModule.
    This is the ONLY place developers should write input code.
    """
    Given a service requiring custom data collection
    Then globalConfig.json service MUST specify "inputHelperModule":
      """json
      {
        "name": "kvstore_sync_job",
        "title": "KVStore Sync Job",
        "inputHelperModule": "kvstore_sync_helper",
        "entity": [...]
      }
      """
    And the helper module MUST be placed at "package/bin/kvstore_sync_helper.py"
    And UCC automatically imports and invokes the helper

  @inputhelper @interface
  Scenario: inputHelperModule required interface
    """
    The helper module must implement specific methods.
    stream_events is required - validate_input is optional.
    """
    Given an inputHelperModule named "kvstore_sync_helper"
    Then the module MUST implement "stream_events" method:
      """python
      def stream_events(helper, ew):
          """
          Stream events to Splunk.

          Args:
              helper: Input helper object from splunktaucclib
              ew: EventWriter for streaming events to Splunk
          """
          # Get input configuration
          destination = helper.get_arg('destination')
          sync_profile = helper.get_arg('sync_profile')

          # Perform data collection using splunk-sdk
          # ...

          # Write events
          event = helper.new_event(
              data="event data",
              source="kvstore_sync",
              sourcetype="kvstore:sync:status"
          )
          ew.write_event(event)
      """
    And the module MAY implement "validate_input" method:
      """python
      def validate_input(helper, definition):
          """
          Validate input configuration before saving.

          Args:
              helper: Input helper object
              definition: Input definition being validated

          Returns:
              None if valid, raises ValueError if invalid
          """
          pass
      """

  @inputhelper @helper-object
  Scenario: Helper object provides input context
    """
    The helper object provides access to input configuration and utilities.
    """
    Given a stream_events method implementation
    Then the "helper" object provides:
      | method/property    | description                              |
      | get_arg(name)      | Get input argument value                 |
      | get_input_type()   | Get the input type name                  |
      | get_input_stanza() | Get full input stanza name               |
      | get_output_index() | Get configured output index              |
      | get_sourcetype()   | Get configured sourcetype                |
      | context_meta       | Splunk context (session_key, etc.)       |
      | new_event()        | Create new Event object                  |
      | get_check_point()  | Get checkpoint value                     |
      | save_check_point() | Save checkpoint value                    |
      | log_debug/info/error| Logging methods                         |

  @inputhelper @eventwriter
  Scenario: EventWriter for streaming data to Splunk
    """
    The ew (EventWriter) object streams data to Splunk.
    All collected data must go through EventWriter.
    """
    Given a stream_events method implementation
    Then the "ew" (EventWriter) object provides:
      | method           | description                               |
      | write_event()    | Write a single event to Splunk            |
      | write_events()   | Write multiple events (batch)             |
    And events are created via helper.new_event():
      | parameter  | required | description                          |
      | data       | yes      | Event payload (string or dict)       |
      | time       | no       | Event timestamp (epoch float)        |
      | source     | no       | Event source override                |
      | sourcetype | no       | Event sourcetype override            |
      | index      | no       | Event index override                 |
      | host       | no       | Event host override                  |
      | done       | no       | Mark as final event (boolean)        |

  # ===========================================================================
  # SPLUNK-SDK INTEGRATION (Required)
  # ===========================================================================

  @splunk-sdk @required
  Scenario: Input helper MUST use splunk-sdk for Splunk APIs
    """
    All Splunk API interactions in inputHelperModule MUST use splunk-sdk.
    Raw HTTP clients (requests, urllib) are FORBIDDEN for Splunk APIs.
    """
    Given an inputHelperModule that needs to access Splunk APIs
    Then the module MUST import from splunklib:
      """python
      import splunklib.client as client
      import splunklib.results as results
      """
    And the module MUST create service from helper context:
      """python
      def stream_events(helper, ew):
          # Get session key from helper context
          session_key = helper.context_meta['session_key']
          server_uri = helper.context_meta['server_uri']

          # Create splunk-sdk service
          service = client.connect(
              token=session_key,
              host=server_uri.split(':')[0],
              port=server_uri.split(':')[1],
              app=helper.context_meta['app']
          )

          # Use splunk-sdk for all Splunk operations
          kvstore = service.kvstore
          # ...
      """
    And the module MUST NOT use requests/urllib for Splunk APIs

  @splunk-sdk @kvstore
  Scenario: KVStore operations via splunk-sdk
    """
    This add-on synchronizes KVStore collections.
    All KVStore operations MUST use splunk-sdk's kvstore module.
    """
    Given inputHelperModule performs KVStore operations
    Then KVStore access MUST use splunk-sdk:
      """python
      # Access KVStore collection
      collection = service.kvstore['my_collection']

      # Read data
      data = collection.data.query()

      # Insert/Update data
      collection.data.insert({'field': 'value'})
      collection.data.update('record_id', {'field': 'new_value'})

      # Delete data
      collection.data.delete('record_id')

      # Batch operations
      collection.data.batch_save([{'_key': '1', 'field': 'value'}, ...])
      """
    And FORBIDDEN patterns include:
      | pattern                    | reason                              |
      | requests.get('/kvstore/')  | Use splunklib.client.kvstore        |
      | urllib for /storage/       | Use splunklib.client.kvstore        |
      | custom REST client         | Use splunklib.client                |

  # ===========================================================================
  # CHECKPOINTING
  # ===========================================================================

  @checkpoint
  Scenario: Checkpoint management for incremental collection
    """
    Checkpoints persist state between input runs.
    Use checkpoints for incremental data collection.
    """
    Given inputHelperModule performs incremental data collection
    Then the module SHOULD use checkpointing:
      """python
      def stream_events(helper, ew):
          # Get last checkpoint
          checkpoint_key = f"last_sync_{helper.get_input_stanza()}"
          last_checkpoint = helper.get_check_point(checkpoint_key)

          if last_checkpoint:
              last_timestamp = last_checkpoint.get('timestamp', 0)
          else:
              last_timestamp = 0

          # Collect data since last checkpoint
          new_data = collect_data_since(last_timestamp)

          # Process and write events
          for item in new_data:
              event = helper.new_event(data=json.dumps(item))
              ew.write_event(event)

          # Save new checkpoint
          helper.save_check_point(checkpoint_key, {
              'timestamp': time.time(),
              'records_processed': len(new_data)
          })
      """
    And checkpoints are stored in:
      | location                        | description                       |
      | var/lib/splunk/modinputs/       | Splunk's checkpoint directory     |
    And checkpoints persist across restarts

  # ===========================================================================
  # LOGGING
  # ===========================================================================

  @logging
  Scenario: Structured logging via solnlib
    """
    inputHelperModule should use helper logging methods.
    Logs integrate with Splunk's internal log system.
    """
    Given inputHelperModule needs to log information
    Then the module SHOULD use helper logging:
      """python
      def stream_events(helper, ew):
          helper.log_info("Starting sync job")

          try:
              # ... operation ...
              helper.log_debug(f"Processed {count} records")
          except Exception as e:
              helper.log_error(f"Sync failed: {str(e)}")
      """
    And logs appear in:
      | log file                              | description              |
      | $SPLUNK_HOME/var/log/splunk/*ta*.log | Add-on specific log      |
    And helper logging methods:
      | method          | level    | use case                        |
      | log_debug()     | DEBUG    | Detailed troubleshooting        |
      | log_info()      | INFO     | Normal operation status         |
      | log_warning()   | WARNING  | Non-critical issues             |
      | log_error()     | ERROR    | Errors requiring attention      |
      | log_critical()  | CRITICAL | Severe failures                 |

  # ===========================================================================
  # ERROR HANDLING
  # ===========================================================================

  @errors
  Scenario: Proper error handling in inputHelperModule
    """
    inputHelperModule must handle errors gracefully.
    Uncaught exceptions cause input to fail and restart.
    """
    Given inputHelperModule may encounter errors
    Then the module MUST implement error handling:
      """python
      def stream_events(helper, ew):
          try:
              # Main logic
              perform_sync(helper, ew)
          except splunklib.binding.AuthenticationError as e:
              helper.log_error(f"Authentication failed: {e}")
              # Re-raise to signal retry
              raise
          except splunklib.binding.HTTPError as e:
              helper.log_error(f"Splunk API error: {e.status} - {e.message}")
              if e.status >= 500:
                  raise  # Retry on server errors
              # Don't retry on client errors
          except Exception as e:
              helper.log_error(f"Unexpected error: {e}")
              helper.log_error(traceback.format_exc())
              raise
      """
    And error handling best practices:
      | practice                    | description                         |
      | Log before re-raising       | Ensure errors are recorded          |
      | Distinguish retry-able      | Re-raise for transient failures     |
      | Include traceback           | Log full traceback for debugging    |
      | Never silently swallow      | Always log errors, even if handled  |

  # ===========================================================================
  # TESTING INPUT HELPERS
  # ===========================================================================

  @testing
  Scenario: Unit testing inputHelperModule
    """
    inputHelperModule should have comprehensive unit tests.
    Tests use mocks for helper and EventWriter objects.
    """
    Given inputHelperModule named "kvstore_sync_helper"
    Then tests SHOULD be in "tests/unit/test_kvstore_sync_helper.py"
    And tests SHOULD mock the helper and ew objects:
      """python
      import pytest
      from unittest.mock import Mock, MagicMock
      from bin.kvstore_sync_helper import stream_events

      @pytest.fixture
      def mock_helper():
          helper = Mock()
          helper.get_arg.return_value = 'test_value'
          helper.context_meta = {
              'session_key': 'test_session_key',
              'server_uri': 'localhost:8089',
              'app': 'kvstore_syncthing'
          }
          helper.get_check_point.return_value = None
          return helper

      @pytest.fixture
      def mock_ew():
          return Mock()

      def test_stream_events_success(mock_helper, mock_ew):
          # Arrange
          mock_helper.get_arg.side_effect = lambda x: {
              'destination': 'prod_cluster',
              'sync_profile': 'incremental'
          }.get(x)

          # Act
          stream_events(mock_helper, mock_ew)

          # Assert
          mock_ew.write_event.assert_called()
          mock_helper.save_check_point.assert_called()
      """
