# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/workflow_templates.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:workflows
@feature:templates
Feature: Pre-Built Workflow Templates
  As a Splunk administrator
  I want pre-built workflow templates for common data sync scenarios
  So that I can quickly set up CMDB, database, and threat intel synchronization

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed

  # =============================================================================
  # ServiceNow CMDB Integration
  # =============================================================================
  @story:cmdb-snow
  @priority:critical
  Scenario: Configure ServiceNow CMDB workflow using existing TA
    Given the Splunk Add-on for ServiceNow (TA-snow) is installed
    When I create a workflow from template "ServiceNow CMDB"
    Then I should see configuration options:
      | Field                | Required | Default          |
      | ServiceNow Instance  | Yes      |                  |
      | TA-SNOW Input        | Yes      |                  |
      | Target Collection    | Yes      | snow_cmdb_ci     |
      | CI Types to Sync     | No       | cmdb_ci_server,cmdb_ci_computer |
      | Sync Interval        | Yes      | 3600             |
      | Field Mapping        | No       | <default mapping>|

  @story:cmdb-snow
  @priority:critical
  Scenario: Sync CMDB Configuration Items to KVStore
    Given TA-SNOW is configured with ServiceNow credentials
    And the CMDB workflow is configured for "cmdb_ci_server"
    When the scheduled sync runs
    Then CIs should be fetched via TA-SNOW's API
    And CIs should be written to KVStore collection
    And the following fields should be mapped:
      | ServiceNow Field | KVStore Field | Description            |
      | sys_id           | _key          | Unique identifier      |
      | name             | name          | CI Name                |
      | ip_address       | ip_address    | Primary IP             |
      | os               | os            | Operating System       |
      | sys_class_name   | ci_type       | CI Class               |
      | operational_status | status      | Operational status     |
      | sys_updated_on   | updated_at    | Last modification      |

  @story:cmdb-snow
  @priority:high
  Scenario: Incremental CMDB sync
    Given CMDB data changes frequently
    When I configure incremental sync based on sys_updated_on
    Then only records modified since last sync should be fetched
    And sync time should be recorded in checkpoint
    And full sync should run weekly to catch deletions

  @story:cmdb-snow
  @priority:high
  Scenario: CMDB relationship sync
    Given CIs have relationships (hosted_on, connected_to, etc.)
    When I enable relationship sync
    Then relationships should be synced to separate collection "snow_cmdb_rel"
    And relationship types should be preserved
    And lookups can join CIs with relationships

  @story:cmdb-snow
  @priority:medium
  Scenario: CMDB to multiple Splunk instances
    Given I have on-prem and cloud Splunk deployments
    When I configure CMDB sync to both
    Then same CMDB data should be available in both environments
    And sync status should be tracked per destination

  # =============================================================================
  # Database Integration via DBConnect
  # =============================================================================
  @story:dbconnect
  @priority:critical
  Scenario: Configure DBConnect SQL workflow
    Given Splunk DB Connect is installed
    When I create a workflow from template "DBConnect SQL"
    Then I should see configuration options:
      | Field                | Required | Default          |
      | DBConnect Connection | Yes      |                  |
      | SQL Query            | Yes      |                  |
      | Target Collection    | Yes      |                  |
      | Key Field            | Yes      | id               |
      | Sync Interval        | Yes      | 3600             |
      | Sync Mode            | No       | full_replace     |

  @story:dbconnect
  @priority:critical
  Scenario: Sync SQL query results to KVStore
    Given DBConnect connection "oracle_hr" is configured
    And I have a SQL query for employee data:
      """sql
      SELECT
        employee_id,
        first_name,
        last_name,
        email,
        department_name,
        manager_id
      FROM employees e
      JOIN departments d ON e.department_id = d.department_id
      WHERE e.status = 'ACTIVE'
      """
    When the scheduled sync runs
    Then query should be executed via DBConnect
    And results should be written to KVStore
    And employee_id should become _key

  @story:dbconnect
  @priority:high
  Scenario: Incremental SQL sync with timestamp
    Given the source table has a modified_date column
    When I configure incremental sync:
      """sql
      SELECT * FROM employees
      WHERE modified_date > :last_sync_time
      """
    Then only changed records should be fetched
    And :last_sync_time should be populated from checkpoint

  @story:dbconnect
  @priority:high
  Scenario: SQL sync with soft deletes
    Given records are soft-deleted (status = 'DELETED')
    When I configure deletion handling:
      | Setting              | Value                          |
      | Detect Deletions     | true                           |
      | Deletion Query       | SELECT id FROM employees WHERE status = 'DELETED' |
      | Action               | remove                         |
    Then deleted records should be removed from KVStore

  @story:dbconnect
  @priority:medium
  Scenario: Multiple database sources
    Given I have multiple databases with related data:
      | Database    | Table         | Collection        |
      | Oracle HR   | employees     | hr_employees      |
      | MySQL Asset | servers       | asset_servers     |
      | MSSQL CMDB  | config_items  | cmdb_items        |
    When I configure workflows for each
    Then all should sync on independent schedules
    And cross-database lookups should be possible

  @story:dbconnect
  @priority:medium
  Scenario: Stored procedure support
    Given I need to call a stored procedure
    When I configure the workflow with:
      """sql
      CALL get_active_users(:start_date, :end_date)
      """
    Then stored procedure should be called via DBConnect
    And output parameters should be handled
    And result sets should be captured

  # =============================================================================
  # Web Threat Intelligence Feeds
  # =============================================================================
  @story:web-threat-feeds
  @priority:critical
  Scenario: Configure web threat feed workflow
    Given I want to ingest threat indicators from the web
    When I create a workflow from template "Web Threat Feed"
    Then I should see configuration options:
      | Field                | Required | Default          |
      | Feed Name            | Yes      |                  |
      | Feed URL             | Yes      |                  |
      | Feed Format          | Yes      | csv              |
      | Authentication       | No       | none             |
      | Target Collection    | Yes      |                  |
      | Deduplication Key    | No       | indicator        |
      | Poll Interval        | Yes      | 3600             |
      | Field Mapping        | No       |                  |
      | Expiration Days      | No       | 30               |

  @story:web-threat-feeds
  @priority:critical
  Scenario: Built-in threat feed templates
    Given I select from pre-configured feeds:
      | Feed Template        | URL                                          | Format  |
      | Abuse.ch URLhaus     | https://urlhaus.abuse.ch/downloads/csv_online/ | csv    |
      | Abuse.ch Feodo       | https://feodotracker.abuse.ch/downloads/ipblocklist.csv | csv |
      | Emerging Threats     | https://rules.emergingthreats.net/blockrules/compromised-ips.txt | plain |
      | Spamhaus DROP        | https://www.spamhaus.org/drop/drop.txt       | plain   |
      | Spamhaus EDROP       | https://www.spamhaus.org/drop/edrop.txt      | plain   |
      | FireHOL Level 1      | https://iplists.firehol.org/files/firehol_level1.netset | plain |
      | AlienVault Reputation| https://reputation.alienvault.com/reputation.generic | plain |
      | Talos IP Blacklist   | https://www.talosintelligence.com/documents/ip-blacklist | plain |
    When I select a template
    Then URL, format, and field mapping should be pre-configured

  @story:web-threat-feeds
  @priority:high
  Scenario: Aggregate multiple threat feeds
    Given I have configured multiple threat feeds:
      | Feed               | Indicator Type | Collection         |
      | URLhaus            | url            | threat_urls        |
      | Feodo Tracker      | ip             | threat_ips_c2      |
      | Spamhaus DROP      | cidr           | threat_ips_spam    |
    When feeds are ingested
    Then each should populate its target collection
    And a master collection "threat_indicators_all" should aggregate all
    And source attribution should be preserved

  @story:web-threat-feeds
  @priority:high
  Scenario: Threat indicator enrichment
    Given raw indicators are ingested
    When enrichment is enabled
    Then indicators should be enriched with:
      | Enrichment        | Source           | Field Added        |
      | GeoIP             | MaxMind/GeoLite  | country, city      |
      | ASN               | MaxMind          | asn, org           |
      | WHOIS             | RDAP             | registrar, created |
      | Reputation        | Multiple         | reputation_score   |

  @story:web-threat-feeds
  @priority:medium
  Scenario: Feed health monitoring
    Given threat feeds are configured
    When a feed fails to update
    Then an alert should be generated after 2 consecutive failures
    And last successful update time should be tracked
    And stale indicator warnings should appear after 7 days

  @story:web-threat-feeds
  @priority:medium
  Scenario: Indicator aging and expiration
    Given indicators have varying ages
    When I configure expiration policy:
      | Age (days) | Action            |
      | 30         | Mark as stale     |
      | 90         | Lower confidence  |
      | 180        | Remove            |
    Then old indicators should be handled per policy
    And re-observed indicators should refresh timestamp

  # =============================================================================
  # Active Directory / LDAP Integration
  # =============================================================================
  @story:ad-ldap
  @priority:critical
  Scenario: Configure AD/LDAP workflow using SA-ldapsearch
    Given SA-ldapsearch is installed and configured
    When I create a workflow from template "Active Directory"
    Then I should see configuration options:
      | Field                | Required | Default                    |
      | LDAP Domain          | Yes      |                            |
      | SA-ldapsearch Input  | Yes      |                            |
      | Target Collection    | Yes      | ad_users                   |
      | Object Classes       | No       | user,computer,group        |
      | Attributes           | No       | <common AD attributes>     |
      | Sync Interval        | Yes      | 900                        |

  @story:ad-ldap
  @priority:critical
  Scenario: Sync AD users to KVStore
    Given SA-ldapsearch is configured for "corp.example.com"
    And the AD workflow is configured
    When the scheduled sync runs
    Then users should be fetched via ldapsearch
    And mapped to KVStore:
      | AD Attribute        | KVStore Field    |
      | sAMAccountName      | _key             |
      | distinguishedName   | dn               |
      | cn                  | display_name     |
      | mail                | email            |
      | department          | department       |
      | manager             | manager_dn       |
      | memberOf            | groups           |
      | userAccountControl  | uac_flags        |
      | whenChanged         | modified_at      |

  @story:ad-ldap
  @priority:high
  Scenario: Sync AD groups with nested membership
    Given AD has nested group memberships
    When I enable group sync with nesting:
      | Setting               | Value  |
      | Flatten Nested Groups | true   |
      | Max Nesting Depth     | 5      |
    Then groups should be synced to "ad_groups" collection
    And nested memberships should be flattened
    And users should have all effective groups listed

  @story:ad-ldap
  @priority:high
  Scenario: AD sync to Splunk Cloud
    Given on-prem AD data needs to sync to Splunk Cloud
    When I configure the AD workflow with cloud destination
    Then sensitive fields should be excluded:
      | Excluded Attribute  | Reason           |
      | userPassword        | Security         |
      | homeDirectory       | PII              |
      | telephoneNumber     | PII              |
    And sync should go through Heavy Forwarder if required

  # =============================================================================
  # Workflow Template Management
  # =============================================================================
  @story:template-management
  @priority:high
  Scenario: Create custom workflow template
    Given I have configured a complex workflow
    When I save it as a template
    Then the template should capture:
      | Element             | Captured               |
      | Source configuration | Yes (without secrets)  |
      | Field mappings       | Yes                    |
      | Transformation rules | Yes                    |
      | Schedule             | Yes                    |
      | Destination type     | Yes                    |
    And template should be exportable as JSON

  @story:template-management
  @priority:medium
  Scenario: Import workflow template
    Given I have a workflow template JSON file
    When I import the template
    Then a new workflow should be created
    And I should be prompted for missing values (secrets, endpoints)
    And validation should ensure all references exist

  @story:template-management
  @priority:medium
  Scenario: Share workflow templates
    Given I have custom workflow templates
    When I export for sharing
    Then templates should be sanitized:
      | Removed             | Reason                |
      | Credentials         | Security              |
      | Internal IPs        | Privacy               |
      | User-specific paths | Portability           |
    And documentation should be included

  # =============================================================================
  # Workflow Orchestration
  # =============================================================================
  @story:orchestration
  @priority:high
  Scenario: Chain workflows in sequence
    Given I have related workflows:
      | Order | Workflow          | Description                    |
      | 1     | snow_cmdb_sync    | Sync CMDB from ServiceNow      |
      | 2     | ad_user_sync      | Sync users from AD             |
      | 3     | enrich_assets     | Join CMDB with AD data         |
    When I configure workflow chain
    Then workflows should run in order
    And each should wait for previous to complete
    And failure in one should optionally stop chain

  @story:orchestration
  @priority:medium
  Scenario: Parallel workflow execution
    Given I have independent workflows that can run concurrently
    When I configure parallel execution
    Then workflows should run simultaneously
    And resource limits should be respected
    And completion should be tracked individually

  @story:orchestration
  @priority:medium
  Scenario: Workflow dependencies
    Given workflow B depends on workflow A's data
    When workflow A completes
    Then workflow B should be triggered automatically
    And dependency graph should prevent cycles
    And missing dependencies should raise errors
