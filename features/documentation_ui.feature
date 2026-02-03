# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/documentation_ui.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:user-experience
@feature:documentation
Feature: Self-Documenting UI
  As a Splunk administrator
  I want contextual help and documentation throughout the UI
  So that I can understand features without leaving the app

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed

  # -----------------------------------------------------------------------------
  # User Story: Field-Level Tooltips
  # -----------------------------------------------------------------------------
  @story:tooltips
  @priority:high
  Scenario: Every configuration field has a tooltip
    Given I am on the Configuration > Destinations page
    When I hover over the help icon next to "Destination Type"
    Then a tooltip should appear with a brief explanation
    And the tooltip should describe what the field does

  @story:tooltips
  @priority:high
  Scenario: Tooltip includes field-specific examples
    Given I am on the Configuration > Destinations page
    When I hover over the help icon next to "Host"
    Then the tooltip should include example values:
      | Example                            |
      | splunk-cloud.splunkcloud.com       |
      | 192.168.1.100                      |
      | mongodb://host1:27017,host2:27017  |

  @story:tooltips
  @priority:medium
  Scenario Outline: All form fields have help text
    Given I am on the "<page>" page
    Then every input field should have an associated help icon
    And each help icon should display a tooltip on hover

    Examples:
      | page                                |
      | Configuration > Destinations        |
      | Configuration > Sync Profiles       |
      | Configuration > Collection Mappings |
      | Inputs > Sync Jobs                  |

  # -----------------------------------------------------------------------------
  # User Story: Detailed Documentation Modals
  # -----------------------------------------------------------------------------
  @story:doc-modals
  @priority:high
  Scenario: Open detailed documentation from tooltip
    Given I see a tooltip for "Sync Mode"
    When I click "Learn More" in the tooltip
    Then a modal should open with comprehensive documentation
    And the modal should include:
      | Section      | Content                              |
      | Title        | Sync Mode                            |
      | Description  | Detailed explanation with markdown   |
      | Examples     | Usage examples                       |
      | Related      | Links to related documentation       |

  @story:doc-modals
  @priority:medium
  Scenario: Documentation modal supports markdown
    Given I open a documentation modal
    Then the content should render markdown properly:
      | Element        | Renders As           |
      | # Heading      | Large heading        |
      | **bold**       | Bold text            |
      | `code`         | Inline code          |
      | ```code block  | Code block           |
      | - list item    | Bulleted list        |

  @story:doc-modals
  @priority:medium
  Scenario: Navigate between related documentation
    Given I am viewing documentation for "Conflict Resolution"
    When I click a link to "Sync Mode" in the related docs section
    Then the modal should update to show "Sync Mode" documentation
    And I should be able to navigate back

  # -----------------------------------------------------------------------------
  # User Story: Conceptual Documentation
  # -----------------------------------------------------------------------------
  @story:concepts
  @priority:high
  Scenario: Access conceptual documentation from help menu
    Given I click the Help menu
    When I select "Documentation"
    Then I should see a list of conceptual topics:
      | Topic                               |
      | Understanding Sync Methods          |
      | MongoDB Replication for KVStore     |
      | Data Integrity and Verification     |
      | On-Prem to Cloud Sync Guide         |

  @story:concepts
  @priority:medium
  Scenario: Conceptual docs include architecture diagrams
    Given I open "MongoDB Replication for KVStore" documentation
    Then I should see ASCII or visual diagrams showing:
      | Diagram          | Shows                              |
      | Cluster topology | Primary, secondaries, OOB nodes    |
      | Data flow        | Replication direction              |

  # -----------------------------------------------------------------------------
  # User Story: How-To Guides
  # -----------------------------------------------------------------------------
  @story:howto
  @priority:high
  Scenario: Step-by-step guide for common tasks
    Given I search for "sync to cloud"
    When I select the "Sync On-Prem KVStore to Splunk Cloud" guide
    Then I should see numbered steps with:
      | Step | Title                        |
      | 1    | Create Splunk Cloud API Token|
      | 2    | Configure Destination        |
      | 3    | Test Connection              |
      | 4    | Configure Sync Job           |

  @story:howto
  @priority:medium
  Scenario: Troubleshooting guide for common issues
    Given I encounter a "Connection Failed" error
    When I click "Troubleshoot this error"
    Then I should see a troubleshooting guide with:
      | Check                          | Resolution                      |
      | Verify network path            | Check firewall rules            |
      | Verify port is open            | telnet host port                |
      | Verify credentials             | Regenerate token                |

  # -----------------------------------------------------------------------------
  # User Story: Search Documentation
  # -----------------------------------------------------------------------------
  @story:search
  @priority:medium
  Scenario: Search across all documentation
    Given I am in the KVStore Syncthing app
    When I type "conflict" in the documentation search
    Then I should see results from:
      | Source          | Result                          |
      | Field docs      | Conflict Resolution field       |
      | Concepts        | Understanding Conflict Handling |
      | How-to          | Resolving Sync Conflicts        |

  @story:search
  @priority:low
  Scenario: Search highlights matching text
    Given I search for "incremental"
    When I view a search result
    Then the matching text should be highlighted

  # -----------------------------------------------------------------------------
  # User Story: Contextual Help in Dashboards
  # -----------------------------------------------------------------------------
  @story:dashboard-help
  @priority:medium
  Scenario: Dashboard panels have help tooltips
    Given I am viewing the Integrity Dashboard
    When I hover over the "Merkle Root" label
    Then a tooltip should explain what a Merkle root is
    And why it's used for integrity verification

  @story:dashboard-help
  @priority:medium
  Scenario: Status indicators have explanatory tooltips
    Given I see a "MISMATCH" status indicator
    When I hover over the indicator
    Then a tooltip should explain what mismatch means
    And what actions I can take

  # -----------------------------------------------------------------------------
  # User Story: Error Messages with Help
  # -----------------------------------------------------------------------------
  @story:error-help
  @priority:high
  Scenario: Error messages include help links
    Given a sync job fails with "Authentication failed"
    Then the error message should include:
      | Element            | Content                          |
      | Error text         | Authentication failed            |
      | Possible causes    | Invalid token, expired password  |
      | Help link          | Link to auth troubleshooting     |

  @story:error-help
  @priority:medium
  Scenario: Validation errors explain requirements
    Given I enter an invalid value in a form field
    Then the validation error should explain:
      | Element            | Content                          |
      | What's wrong       | "Invalid format"                 |
      | What's expected    | "Must be alphanumeric"           |
      | Example            | "my-destination-01"              |

  # -----------------------------------------------------------------------------
  # User Story: Inline Code Examples
  # -----------------------------------------------------------------------------
  @story:code-examples
  @priority:medium
  Scenario: Configuration examples are copyable
    Given I am viewing documentation with code examples
    When I click the "Copy" button on a code block
    Then the code should be copied to my clipboard
    And I should see "Copied!" confirmation

  @story:code-examples
  @priority:low
  Scenario: SPL examples for rehydration searches
    Given I am configuring Index & Rehydrate sync
    When I view the documentation
    Then I should see ready-to-use SPL examples:
      """
      | inputlookup users
      | append [search index=kvstore_sync sourcetype="kvstore:sync"]
      | dedup _key sortby -_time
      | outputlookup users
      """
    And I should be able to copy the SPL directly

  # -----------------------------------------------------------------------------
  # User Story: Documentation API
  # -----------------------------------------------------------------------------
  @story:doc-api
  @priority:medium
  Scenario: Documentation is available via REST API
    Given I make a GET request to /kvstore_syncthing/docs
    Then I should receive JSON with all documentation entries
    And each entry should include:
      | Field       | Type          |
      | doc_id      | string        |
      | title       | string        |
      | description | string        |
      | help_text   | string        |
      | examples    | array         |

  @story:doc-api
  @priority:low
  Scenario: Retrieve documentation for specific field
    Given I make a GET request to /kvstore_syncthing/docs?component=destinations&field=host
    Then I should receive documentation specific to the "host" field
    And the response should include contextual examples
