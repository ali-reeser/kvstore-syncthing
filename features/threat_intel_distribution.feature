# ===============================================================================
# PROVENANCE TRACKING
# ===============================================================================
# File: features/threat_intel_distribution.feature
# Created: 2026-02-03
# Author: Claude (AI Assistant - claude-opus-4-5-20251101)
# Session: claude/kvstore-sync-solution-vPJQI
# Type: BDD User Stories / Acceptance Criteria
# ===============================================================================

@epic:threat-intel
@feature:url-distribution
Feature: Threat Intelligence Distribution via URL
  As a security operations engineer
  I want to export KVStore threat indicators as downloadable URLs
  So that I can distribute threat intel to network devices like Palo Alto firewalls

  Background:
    Given I am logged into Splunk as an admin user
    And the KVStore Syncthing app is installed
    And I have a KVStore collection with threat indicators

  # =============================================================================
  # URL-Based Distribution
  # =============================================================================
  @story:url-export
  @priority:critical
  Scenario: Configure URL Export endpoint
    Given I navigate to Configuration > Distributions
    When I create a new distribution with type "URL Export"
    Then I should see configuration fields:
      | Field                | Required | Default        |
      | Distribution Name    | Yes      |                |
      | Source Collection    | Yes      |                |
      | Output Format        | Yes      | csv            |
      | URL Path             | Yes      | /export/       |
      | Authentication       | No       | token          |
      | Token TTL (hours)    | No       | 24             |
      | Cache TTL (seconds)  | No       | 300            |
      | Max Records          | No       | 100000         |
      | CORS Enabled         | No       | false          |

  @story:url-export
  @priority:critical
  Scenario: Generate downloadable threat indicator URL
    Given a KVStore collection "blocked_ips" with threat indicators:
      | ip_address     | threat_type    | confidence | source      |
      | 192.168.1.100  | malware_c2     | 95         | internal    |
      | 10.0.0.50      | ransomware     | 90         | threat_feed |
      | 203.0.113.42   | phishing       | 85         | community   |
    When I configure a URL Export for "blocked_ips"
    Then a URL should be generated:
      """
      https://splunk.example.com:8089/servicesNS/nobody/kvstore_syncthing/export/blocked_ips?token=<auth_token>&format=csv
      """
    And the URL should return threat indicators in requested format

  @story:url-export
  @priority:critical
  Scenario: CSV format for Palo Alto External Dynamic Lists
    Given a URL Export is configured for "blocked_ips"
    And output format is "palo_alto_edl"
    When a client requests the URL
    Then response should be plain text with one IP per line:
      """
      192.168.1.100
      10.0.0.50
      203.0.113.42
      """
    And response should include header: Content-Type: text/plain
    And response should be compatible with Palo Alto EDL format

  @story:url-export
  @priority:high
  Scenario: Multiple output formats
    Given a URL Export is configured
    When I request different formats via query parameter:
      | Format        | Query Parameter | Use Case                    |
      | csv           | format=csv      | General spreadsheet import  |
      | json          | format=json     | API integrations            |
      | plain         | format=plain    | One value per line          |
      | palo_alto_edl | format=edl      | Palo Alto firewalls         |
      | cisco_ios     | format=cisco    | Cisco IOS ACLs              |
      | stix          | format=stix     | STIX/TAXII compatible       |
      | misp          | format=misp     | MISP threat sharing         |
    Then each format should be correctly rendered

  @story:url-export
  @priority:high
  Scenario: Field selection for export
    Given a collection with multiple fields:
      | Field          | Include in Export |
      | ip_address     | Yes               |
      | threat_type    | Optional          |
      | confidence     | Optional          |
      | source         | No (internal)     |
      | _key           | No                |
    When I configure field selection
    Then only selected fields should appear in export
    And sensitive fields can be excluded

  # =============================================================================
  # Authentication and Security
  # =============================================================================
  @story:url-auth
  @priority:critical
  Scenario: Token-based URL authentication
    Given a URL Export is configured with token authentication
    When I generate an access token
    Then the token should have configurable TTL
    And the token should be revocable
    And expired tokens should be rejected with 401

  @story:url-auth
  @priority:high
  Scenario: IP-based access control
    Given a URL Export is configured
    When I configure IP allowlist:
      | Allowed CIDR       | Description          |
      | 10.0.0.0/8         | Internal network     |
      | 192.168.1.0/24     | Security zone        |
      | 203.0.113.10/32    | Palo Alto firewall   |
    Then requests from allowed IPs should succeed
    And requests from other IPs should be rejected with 403

  @story:url-auth
  @priority:high
  Scenario: Rate limiting
    Given a URL Export is configured
    When I configure rate limits:
      | Setting              | Value    |
      | Requests per minute  | 60       |
      | Requests per hour    | 500      |
      | Burst limit          | 10       |
    Then requests exceeding limits should receive 429
    And Retry-After header should be included

  @story:url-auth
  @priority:medium
  Scenario: Basic authentication support
    Given a URL Export is configured with basic authentication
    When a client provides valid credentials
    Then the export should be returned
    And credentials should be validated against Splunk users

  # =============================================================================
  # Palo Alto Firewall Integration
  # =============================================================================
  @story:palo-alto
  @priority:critical
  Scenario: External Dynamic List (EDL) for IP blocking
    Given I have a collection "malicious_ips" with IP addresses
    When I configure an EDL export
    Then the URL should be usable as Palo Alto External Dynamic List
    And Palo Alto should be able to poll the URL
    And format should be one IP per line
    And maximum should be 150,000 entries (Palo Alto limit)

  @story:palo-alto
  @priority:high
  Scenario: EDL for URL blocking
    Given I have a collection "malicious_urls" with URLs
    When I configure an EDL export for URLs
    Then format should be one URL per line
    And URLs should be normalized (no protocol prefix option)
    And wildcard URLs should be supported: *.malicious.com

  @story:palo-alto
  @priority:high
  Scenario: EDL for domain blocking
    Given I have a collection "malicious_domains"
    When I configure an EDL export for domains
    Then format should be one domain per line
    And subdomains should be optionally included
    And IDN domains should be converted to punycode

  @story:palo-alto
  @priority:medium
  Scenario: EDL refresh configuration
    Given Palo Alto polls the EDL URL
    When I configure cache settings:
      | Setting           | Value   |
      | Cache TTL         | 300     |
      | ETag support      | true    |
      | Last-Modified     | true    |
    Then Palo Alto should receive 304 Not Modified when data unchanged
    And bandwidth should be conserved

  # =============================================================================
  # Other Security Device Integrations
  # =============================================================================
  @story:cisco-integration
  @priority:medium
  Scenario: Cisco IOS ACL format
    Given I have a collection of blocked IPs
    When I export in Cisco IOS format
    Then output should be valid IOS ACL entries:
      """
      ip access-list extended THREAT_BLOCK
       deny ip host 192.168.1.100 any log
       deny ip host 10.0.0.50 any log
       deny ip host 203.0.113.42 any log
       permit ip any any
      """

  @story:cisco-integration
  @priority:medium
  Scenario: Cisco Firepower format
    Given I have a collection of threat indicators
    When I export in Firepower format
    Then output should be compatible with Firepower Intelligence Director

  @story:fortinet-integration
  @priority:medium
  Scenario: Fortinet threat feed format
    Given I have a collection of blocked IPs
    When I export in Fortinet format
    Then output should be compatible with FortiGate External Connectors
    And format should be one entry per line

  @story:checkpoint-integration
  @priority:low
  Scenario: Check Point IoC feed format
    Given I have threat indicators
    When I export in Check Point format
    Then output should be compatible with Check Point ThreatCloud

  # =============================================================================
  # Threat Feed Ingestion
  # =============================================================================
  @story:feed-ingestion
  @priority:high
  Scenario: Configure threat feed source
    Given I navigate to Configuration > Threat Feeds
    When I create a new threat feed source
    Then I should see configuration fields:
      | Field                | Required | Default        |
      | Feed Name            | Yes      |                |
      | Feed URL             | Yes      |                |
      | Feed Type            | Yes      | csv            |
      | Poll Interval        | Yes      | 3600           |
      | Authentication       | No       | none           |
      | API Key              | Cond     |                |
      | Target Collection    | Yes      |                |
      | Field Mapping        | No       |                |
      | Deduplication        | No       | true           |

  @story:feed-ingestion
  @priority:high
  Scenario: Ingest from common threat feeds
    Given the following threat feed sources:
      | Feed Name           | URL                                  | Format |
      | AlienVault OTX      | https://otx.alienvault.com/api/...   | json   |
      | Abuse.ch URLhaus    | https://urlhaus.abuse.ch/downloads/csv/ | csv |
      | Emerging Threats    | https://rules.emergingthreats.net/... | plain |
      | MISP Community      | https://misp.example.org/...         | misp   |
      | Feodo Tracker       | https://feodotracker.abuse.ch/...    | csv    |
    When I configure and enable a feed
    Then indicators should be polled at the configured interval
    And new indicators should be added to the target collection
    And duplicates should be handled per configuration

  @story:feed-ingestion
  @priority:high
  Scenario: Feed normalization
    Given feeds have different field names:
      | Feed         | IP Field       | Type Field      |
      | OTX          | indicator      | type            |
      | URLhaus      | url            | threat          |
      | Custom       | ip_address     | threat_category |
    When I configure field mapping
    Then all feeds should normalize to standard schema:
      | Standard Field | Description              |
      | indicator      | The IOC value            |
      | indicator_type | ip, domain, url, hash    |
      | threat_type    | malware, phishing, etc.  |
      | confidence     | 0-100 score              |
      | source         | Feed name                |
      | first_seen     | Timestamp                |
      | last_seen      | Timestamp                |

  @story:feed-ingestion
  @priority:medium
  Scenario: STIX/TAXII feed ingestion
    Given a TAXII server is available
    When I configure STIX/TAXII feed:
      | Setting          | Value                          |
      | TAXII URL        | https://taxii.example.org      |
      | Collection       | default                        |
      | API Root         | /taxii2/                       |
      | Version          | 2.1                            |
    Then STIX bundles should be polled
    And indicators should be extracted and normalized
    And relationships should be optionally preserved

  # =============================================================================
  # Distribution to Multiple Destinations
  # =============================================================================
  @story:multi-destination
  @priority:high
  Scenario: Distribute to multiple security devices
    Given I have aggregated threat indicators
    When I configure distribution to multiple destinations:
      | Destination          | Format         | Delivery     |
      | Palo Alto FW-1       | edl            | URL poll     |
      | Palo Alto FW-2       | edl            | URL poll     |
      | Cisco ASA            | cisco          | Push via API |
      | FortiGate            | plain          | URL poll     |
      | SIEM                  | stix           | Push via API |
    Then each destination should receive properly formatted data
    And distribution status should be tracked

  @story:multi-destination
  @priority:medium
  Scenario: Destination-specific filtering
    Given I have indicators of varying confidence
    When I configure per-destination filters:
      | Destination    | Min Confidence | Indicator Types       |
      | Production FW  | 90             | ip, domain            |
      | Test FW        | 50             | ip, domain, url, hash |
    Then each destination should receive filtered indicators

  # =============================================================================
  # Monitoring and Auditing
  # =============================================================================
  @story:distribution-monitoring
  @priority:high
  Scenario: Track distribution access
    Given URL Exports are configured
    When clients access the URLs
    Then access logs should record:
      | Field           | Value                    |
      | timestamp       | ISO 8601                 |
      | client_ip       | Requester IP             |
      | export_name     | Distribution name        |
      | record_count    | Number of records        |
      | response_code   | HTTP status              |
      | response_time   | Milliseconds             |

  @story:distribution-monitoring
  @priority:medium
  Scenario: Alert on distribution failures
    Given a security device relies on threat feed
    When the device fails to retrieve the feed
    Then an alert should be generated
    And the alert should include last successful access time
    And remediation steps should be suggested

  @story:distribution-monitoring
  @priority:medium
  Scenario: Distribution health dashboard
    Given multiple distributions are configured
    When I view the health dashboard
    Then I should see for each distribution:
      | Metric                 | Description                |
      | Last Access            | Time of last request       |
      | Access Count (24h)     | Requests in last 24 hours  |
      | Unique Clients         | Number of unique requesters|
      | Average Response Time  | Mean response time         |
      | Error Rate             | Percentage of errors       |
      | Record Count           | Current indicator count    |
