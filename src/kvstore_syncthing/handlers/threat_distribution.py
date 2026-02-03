"""
Threat Intelligence Distribution Handler - URL Export for Security Devices

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/threat_distribution.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  URL-based threat indicator distribution handler.
                                Supports Palo Alto EDL, Cisco IOS, Fortinet,
                                and standard formats (CSV, JSON, STIX, MISP).
-------------------------------------------------------------------------------

License: MIT

PURPOSE:
Serves KVStore threat indicators as downloadable URLs for integration with
security devices like Palo Alto firewalls, Cisco routers, and FortiGate
appliances. Supports various output formats and authentication methods.
===============================================================================
"""

import csv
import hashlib
import io
import ipaddress
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class OutputFormat(Enum):
    """Supported output formats for threat distribution"""
    PLAIN = "plain"          # One value per line
    CSV = "csv"              # CSV with headers
    JSON = "json"            # JSON array
    PALO_ALTO_EDL = "edl"    # Palo Alto External Dynamic List
    CISCO_IOS = "cisco"      # Cisco IOS ACL format
    FORTINET = "fortinet"    # FortiGate format
    STIX = "stix"            # STIX 2.1 bundle
    MISP = "misp"            # MISP format


class IndicatorType(Enum):
    """Types of threat indicators"""
    IP = "ip"
    IPV6 = "ipv6"
    CIDR = "cidr"
    DOMAIN = "domain"
    URL = "url"
    HASH_MD5 = "md5"
    HASH_SHA1 = "sha1"
    HASH_SHA256 = "sha256"
    EMAIL = "email"


class AuthType(Enum):
    """Authentication types for URL access"""
    NONE = "none"
    TOKEN = "token"
    BASIC = "basic"
    IP_ALLOWLIST = "ip_allowlist"


# Palo Alto EDL limits
PALO_ALTO_IP_LIMIT = 150000
PALO_ALTO_URL_LIMIT = 250000
PALO_ALTO_DOMAIN_LIMIT = 250000


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class DistributionConfig:
    """Configuration for a threat distribution endpoint"""
    name: str
    source_collection: str
    source_app: str = "search"
    source_owner: str = "nobody"

    # Field mapping
    indicator_field: str = "indicator"
    type_field: str = "indicator_type"
    confidence_field: str = "confidence"

    # Output settings
    output_format: OutputFormat = OutputFormat.PLAIN
    fields_to_include: List[str] = field(default_factory=list)
    fields_to_exclude: List[str] = field(default_factory=lambda: ["_key", "_user"])

    # Authentication
    auth_type: AuthType = AuthType.TOKEN
    allowed_ips: List[str] = field(default_factory=list)  # CIDR notation

    # Token settings
    token_ttl_hours: int = 24
    tokens: Dict[str, datetime] = field(default_factory=dict)  # token -> expiry

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 500
    burst_limit: int = 10

    # Caching
    cache_ttl_seconds: int = 300
    etag_enabled: bool = True

    # Filtering
    min_confidence: int = 0
    indicator_types: List[IndicatorType] = field(default_factory=list)
    max_records: int = 100000

    # Device-specific
    palo_alto_prefix_removal: bool = False  # Remove http:// from URLs
    cisco_acl_name: str = "THREAT_BLOCK"
    include_comments: bool = True


@dataclass
class AccessLog:
    """Access log entry"""
    timestamp: datetime
    client_ip: str
    distribution_name: str
    record_count: int
    response_code: int
    response_time_ms: int
    format: str
    user_agent: str = ""


# =============================================================================
# Token Manager
# =============================================================================

class TokenManager:
    """Manages authentication tokens for distribution endpoints"""

    def __init__(self):
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def generate_token(
        self,
        distribution_name: str,
        ttl_hours: int = 24,
        description: str = ""
    ) -> str:
        """Generate a new access token"""
        token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(hours=ttl_hours)

        self._tokens[token] = {
            "distribution": distribution_name,
            "created": datetime.utcnow(),
            "expiry": expiry,
            "description": description,
            "revoked": False,
        }

        logger.info(f"Generated token for {distribution_name}, expires {expiry}")
        return token

    def validate_token(self, token: str, distribution_name: str) -> Tuple[bool, str]:
        """
        Validate an access token.

        Returns:
            Tuple of (valid, error_message)
        """
        if token not in self._tokens:
            return False, "Invalid token"

        token_info = self._tokens[token]

        if token_info["revoked"]:
            return False, "Token has been revoked"

        if token_info["expiry"] < datetime.utcnow():
            return False, "Token has expired"

        if token_info["distribution"] != distribution_name:
            return False, "Token not valid for this distribution"

        return True, ""

    def revoke_token(self, token: str) -> bool:
        """Revoke a token"""
        if token in self._tokens:
            self._tokens[token]["revoked"] = True
            logger.info(f"Revoked token {token[:8]}...")
            return True
        return False

    def list_tokens(self, distribution_name: str) -> List[Dict[str, Any]]:
        """List all tokens for a distribution"""
        return [
            {
                "token_prefix": token[:8] + "...",
                **info
            }
            for token, info in self._tokens.items()
            if info["distribution"] == distribution_name
        ]

    def cleanup_expired(self) -> int:
        """Remove expired tokens"""
        now = datetime.utcnow()
        expired = [
            token for token, info in self._tokens.items()
            if info["expiry"] < now
        ]
        for token in expired:
            del self._tokens[token]
        return len(expired)


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate_per_minute: int, rate_per_hour: int, burst: int):
        self.rate_per_minute = rate_per_minute
        self.rate_per_hour = rate_per_hour
        self.burst = burst
        self._minute_buckets: Dict[str, List[float]] = {}
        self._hour_buckets: Dict[str, List[float]] = {}

    def check_limit(self, client_id: str) -> Tuple[bool, int]:
        """
        Check if request is within rate limits.

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600

        # Initialize buckets if needed
        if client_id not in self._minute_buckets:
            self._minute_buckets[client_id] = []
            self._hour_buckets[client_id] = []

        # Cleanup old entries
        self._minute_buckets[client_id] = [
            t for t in self._minute_buckets[client_id] if t > minute_ago
        ]
        self._hour_buckets[client_id] = [
            t for t in self._hour_buckets[client_id] if t > hour_ago
        ]

        # Check limits
        minute_count = len(self._minute_buckets[client_id])
        hour_count = len(self._hour_buckets[client_id])

        if minute_count >= self.rate_per_minute:
            oldest = min(self._minute_buckets[client_id])
            retry_after = int(60 - (now - oldest)) + 1
            return False, retry_after

        if hour_count >= self.rate_per_hour:
            oldest = min(self._hour_buckets[client_id])
            retry_after = int(3600 - (now - oldest)) + 1
            return False, retry_after

        # Record this request
        self._minute_buckets[client_id].append(now)
        self._hour_buckets[client_id].append(now)

        return True, 0


# =============================================================================
# Output Formatters
# =============================================================================

class OutputFormatter:
    """Format indicators for various security devices"""

    @staticmethod
    def format_plain(
        indicators: List[Dict[str, Any]],
        indicator_field: str,
        include_header: bool = False
    ) -> str:
        """One indicator per line"""
        lines = []
        if include_header:
            lines.append(f"# Generated: {datetime.utcnow().isoformat()}")
            lines.append(f"# Count: {len(indicators)}")
            lines.append("")

        for ind in indicators:
            value = ind.get(indicator_field, "")
            if value:
                lines.append(str(value))

        return "\n".join(lines)

    @staticmethod
    def format_csv(
        indicators: List[Dict[str, Any]],
        fields: List[str]
    ) -> str:
        """CSV format with headers"""
        if not indicators:
            return ""

        if not fields:
            fields = list(indicators[0].keys())

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()

        for ind in indicators:
            writer.writerow(ind)

        return output.getvalue()

    @staticmethod
    def format_json(
        indicators: List[Dict[str, Any]],
        fields: Optional[List[str]] = None
    ) -> str:
        """JSON array format"""
        if fields:
            filtered = [
                {k: v for k, v in ind.items() if k in fields}
                for ind in indicators
            ]
        else:
            filtered = indicators

        return json.dumps(filtered, indent=2)

    @staticmethod
    def format_palo_alto_edl(
        indicators: List[Dict[str, Any]],
        indicator_field: str,
        indicator_type: IndicatorType,
        remove_prefix: bool = False
    ) -> str:
        """
        Palo Alto External Dynamic List format.

        Format: One indicator per line, no headers.
        Supports: IP, URL, Domain
        """
        lines = []

        for ind in indicators:
            value = ind.get(indicator_field, "")
            if not value:
                continue

            # Process based on type
            if indicator_type == IndicatorType.URL and remove_prefix:
                # Remove protocol prefix for URL EDLs
                for prefix in ["http://", "https://", "ftp://"]:
                    if value.lower().startswith(prefix):
                        value = value[len(prefix):]
                        break

            lines.append(str(value))

        # Apply limits
        if indicator_type == IndicatorType.IP:
            lines = lines[:PALO_ALTO_IP_LIMIT]
        elif indicator_type == IndicatorType.URL:
            lines = lines[:PALO_ALTO_URL_LIMIT]
        elif indicator_type == IndicatorType.DOMAIN:
            lines = lines[:PALO_ALTO_DOMAIN_LIMIT]

        return "\n".join(lines)

    @staticmethod
    def format_cisco_ios(
        indicators: List[Dict[str, Any]],
        indicator_field: str,
        acl_name: str = "THREAT_BLOCK"
    ) -> str:
        """
        Cisco IOS extended ACL format.

        Example:
        ip access-list extended THREAT_BLOCK
         deny ip host 192.168.1.100 any log
         permit ip any any
        """
        lines = [f"ip access-list extended {acl_name}"]

        for ind in indicators:
            value = ind.get(indicator_field, "")
            if not value:
                continue

            try:
                # Try to parse as IP or CIDR
                network = ipaddress.ip_network(value, strict=False)

                if network.prefixlen == 32:
                    # Single host
                    lines.append(f" deny ip host {network.network_address} any log")
                else:
                    # Network with wildcard mask
                    wildcard = ipaddress.ip_address(
                        int(network.hostmask)
                    )
                    lines.append(
                        f" deny ip {network.network_address} {wildcard} any log"
                    )
            except ValueError:
                # Not a valid IP, skip
                continue

        lines.append(" permit ip any any")
        return "\n".join(lines)

    @staticmethod
    def format_fortinet(
        indicators: List[Dict[str, Any]],
        indicator_field: str
    ) -> str:
        """
        FortiGate external threat feed format.

        One indicator per line, plain text.
        """
        lines = []

        for ind in indicators:
            value = ind.get(indicator_field, "")
            if value:
                lines.append(str(value))

        return "\n".join(lines)

    @staticmethod
    def format_stix(
        indicators: List[Dict[str, Any]],
        indicator_field: str,
        type_field: str,
        source_name: str = "kvstore-syncthing"
    ) -> str:
        """
        STIX 2.1 Bundle format.

        Creates indicator SDOs for each threat indicator.
        """
        import uuid

        bundle_id = f"bundle--{uuid.uuid4()}"

        stix_objects = []

        # Create identity for source
        identity_id = f"identity--{uuid.uuid5(uuid.NAMESPACE_DNS, source_name)}"
        stix_objects.append({
            "type": "identity",
            "spec_version": "2.1",
            "id": identity_id,
            "created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "modified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "name": source_name,
            "identity_class": "system",
        })

        # Create indicators
        for ind in indicators:
            value = ind.get(indicator_field, "")
            ind_type = ind.get(type_field, "unknown")

            if not value:
                continue

            # Map to STIX pattern
            if ind_type in ["ip", "ipv4"]:
                pattern = f"[ipv4-addr:value = '{value}']"
            elif ind_type == "ipv6":
                pattern = f"[ipv6-addr:value = '{value}']"
            elif ind_type == "domain":
                pattern = f"[domain-name:value = '{value}']"
            elif ind_type == "url":
                pattern = f"[url:value = '{value}']"
            elif ind_type in ["md5", "sha1", "sha256"]:
                pattern = f"[file:hashes.'{ind_type.upper()}' = '{value}']"
            else:
                pattern = f"[x-custom:value = '{value}']"

            indicator_id = f"indicator--{uuid.uuid5(uuid.NAMESPACE_DNS, value)}"

            stix_objects.append({
                "type": "indicator",
                "spec_version": "2.1",
                "id": indicator_id,
                "created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "modified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "name": f"Indicator: {value}",
                "pattern": pattern,
                "pattern_type": "stix",
                "valid_from": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "created_by_ref": identity_id,
                "confidence": ind.get("confidence", 50),
            })

        bundle = {
            "type": "bundle",
            "id": bundle_id,
            "objects": stix_objects,
        }

        return json.dumps(bundle, indent=2)

    @staticmethod
    def format_misp(
        indicators: List[Dict[str, Any]],
        indicator_field: str,
        type_field: str,
        event_info: str = "KVStore Threat Indicators"
    ) -> str:
        """
        MISP event format.

        Creates a MISP event with attributes.
        """
        import uuid

        # Map indicator types to MISP types
        type_mapping = {
            "ip": "ip-dst",
            "ipv4": "ip-dst",
            "ipv6": "ip-dst",
            "domain": "domain",
            "url": "url",
            "md5": "md5",
            "sha1": "sha1",
            "sha256": "sha256",
            "email": "email-dst",
        }

        attributes = []

        for ind in indicators:
            value = ind.get(indicator_field, "")
            ind_type = ind.get(type_field, "ip")

            if not value:
                continue

            misp_type = type_mapping.get(ind_type, "text")

            attributes.append({
                "type": misp_type,
                "value": value,
                "to_ids": True,
                "category": "Network activity" if misp_type in ["ip-dst", "domain", "url"] else "Payload delivery",
                "comment": ind.get("description", ""),
            })

        event = {
            "Event": {
                "uuid": str(uuid.uuid4()),
                "info": event_info,
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "threat_level_id": "2",  # Medium
                "analysis": "2",  # Completed
                "distribution": "0",  # Your organization only
                "Attribute": attributes,
            }
        }

        return json.dumps(event, indent=2)


# =============================================================================
# Distribution Handler
# =============================================================================

class ThreatDistributionHandler:
    """
    Main handler for threat intelligence distribution.

    Serves KVStore data as downloadable URLs for security devices.
    """

    def __init__(self):
        self._configs: Dict[str, DistributionConfig] = {}
        self._token_manager = TokenManager()
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._cache: Dict[str, Tuple[str, datetime, str]] = {}  # name -> (data, time, etag)
        self._access_logs: List[AccessLog] = []

    def register_distribution(self, config: DistributionConfig) -> None:
        """Register a new distribution endpoint"""
        self._configs[config.name] = config
        self._rate_limiters[config.name] = RateLimiter(
            config.rate_limit_per_minute,
            config.rate_limit_per_hour,
            config.burst_limit
        )
        logger.info(f"Registered distribution: {config.name}")

    def get_distribution(self, name: str) -> Optional[DistributionConfig]:
        """Get distribution configuration"""
        return self._configs.get(name)

    def generate_token(self, distribution_name: str, ttl_hours: int = 24) -> str:
        """Generate access token for distribution"""
        config = self._configs.get(distribution_name)
        if not config:
            raise ValueError(f"Unknown distribution: {distribution_name}")
        return self._token_manager.generate_token(distribution_name, ttl_hours)

    def revoke_token(self, token: str) -> bool:
        """Revoke an access token"""
        return self._token_manager.revoke_token(token)

    def validate_request(
        self,
        distribution_name: str,
        client_ip: str,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Tuple[bool, int, str]:
        """
        Validate an incoming request.

        Returns:
            Tuple of (allowed, http_status_code, error_message)
        """
        config = self._configs.get(distribution_name)
        if not config:
            return False, 404, "Distribution not found"

        # Check rate limit
        rate_limiter = self._rate_limiters.get(distribution_name)
        if rate_limiter:
            allowed, retry_after = rate_limiter.check_limit(client_ip)
            if not allowed:
                return False, 429, f"Rate limit exceeded. Retry after {retry_after}s"

        # Check authentication
        if config.auth_type == AuthType.NONE:
            pass  # No auth required

        elif config.auth_type == AuthType.TOKEN:
            if not token:
                return False, 401, "Authentication required"
            valid, error = self._token_manager.validate_token(token, distribution_name)
            if not valid:
                return False, 401, error

        elif config.auth_type == AuthType.IP_ALLOWLIST:
            if not self._check_ip_allowed(client_ip, config.allowed_ips):
                return False, 403, "IP not in allowlist"

        elif config.auth_type == AuthType.BASIC:
            if not username or not password:
                return False, 401, "Basic authentication required"
            # Note: Actual validation should use Splunk's auth system
            # This is a placeholder

        return True, 200, ""

    def _check_ip_allowed(self, client_ip: str, allowed_cidrs: List[str]) -> bool:
        """Check if client IP is in allowed CIDR ranges"""
        try:
            client = ipaddress.ip_address(client_ip)
            for cidr in allowed_cidrs:
                network = ipaddress.ip_network(cidr, strict=False)
                if client in network:
                    return True
            return False
        except ValueError:
            return False

    def get_indicators(
        self,
        distribution_name: str,
        indicators: List[Dict[str, Any]],
        output_format: Optional[OutputFormat] = None,
        client_ip: str = "unknown",
        user_agent: str = ""
    ) -> Tuple[str, str, str, int]:
        """
        Get formatted indicators for distribution.

        Args:
            distribution_name: Name of distribution
            indicators: Raw indicators from KVStore
            output_format: Override output format
            client_ip: Client IP for logging
            user_agent: Client user agent

        Returns:
            Tuple of (content, content_type, etag, record_count)
        """
        start_time = time.time()

        config = self._configs.get(distribution_name)
        if not config:
            return "", "text/plain", "", 0

        format_to_use = output_format or config.output_format

        # Apply filters
        filtered = self._filter_indicators(indicators, config)

        # Check cache
        cache_key = f"{distribution_name}:{format_to_use.value}"
        if config.cache_ttl_seconds > 0:
            cached = self._cache.get(cache_key)
            if cached:
                data, cache_time, etag = cached
                if (datetime.utcnow() - cache_time).total_seconds() < config.cache_ttl_seconds:
                    self._log_access(
                        distribution_name, client_ip, len(filtered),
                        200, int((time.time() - start_time) * 1000),
                        format_to_use.value, user_agent
                    )
                    return data, self._get_content_type(format_to_use), etag, len(filtered)

        # Format output
        content = self._format_output(filtered, config, format_to_use)

        # Calculate ETag
        etag = hashlib.md5(content.encode()).hexdigest()

        # Update cache
        if config.cache_ttl_seconds > 0:
            self._cache[cache_key] = (content, datetime.utcnow(), etag)

        # Log access
        response_time = int((time.time() - start_time) * 1000)
        self._log_access(
            distribution_name, client_ip, len(filtered),
            200, response_time, format_to_use.value, user_agent
        )

        return content, self._get_content_type(format_to_use), etag, len(filtered)

    def _filter_indicators(
        self,
        indicators: List[Dict[str, Any]],
        config: DistributionConfig
    ) -> List[Dict[str, Any]]:
        """Apply configured filters to indicators"""
        filtered = []

        for ind in indicators:
            # Confidence filter
            confidence = ind.get(config.confidence_field, 100)
            if isinstance(confidence, (int, float)) and confidence < config.min_confidence:
                continue

            # Type filter
            if config.indicator_types:
                ind_type = ind.get(config.type_field, "")
                try:
                    if IndicatorType(ind_type) not in config.indicator_types:
                        continue
                except ValueError:
                    pass  # Unknown type, include by default

            # Field exclusion
            filtered_ind = {
                k: v for k, v in ind.items()
                if k not in config.fields_to_exclude
            }

            # Field inclusion (if specified)
            if config.fields_to_include:
                filtered_ind = {
                    k: v for k, v in filtered_ind.items()
                    if k in config.fields_to_include or k == config.indicator_field
                }

            filtered.append(filtered_ind)

        # Apply max records limit
        return filtered[:config.max_records]

    def _format_output(
        self,
        indicators: List[Dict[str, Any]],
        config: DistributionConfig,
        format_type: OutputFormat
    ) -> str:
        """Format indicators for output"""
        formatter = OutputFormatter()

        if format_type == OutputFormat.PLAIN:
            return formatter.format_plain(
                indicators,
                config.indicator_field,
                config.include_comments
            )

        elif format_type == OutputFormat.CSV:
            fields = config.fields_to_include or None
            return formatter.format_csv(indicators, fields)

        elif format_type == OutputFormat.JSON:
            fields = config.fields_to_include or None
            return formatter.format_json(indicators, fields)

        elif format_type == OutputFormat.PALO_ALTO_EDL:
            # Determine indicator type
            ind_type = IndicatorType.IP
            if config.indicator_types:
                ind_type = config.indicator_types[0]

            return formatter.format_palo_alto_edl(
                indicators,
                config.indicator_field,
                ind_type,
                config.palo_alto_prefix_removal
            )

        elif format_type == OutputFormat.CISCO_IOS:
            return formatter.format_cisco_ios(
                indicators,
                config.indicator_field,
                config.cisco_acl_name
            )

        elif format_type == OutputFormat.FORTINET:
            return formatter.format_fortinet(
                indicators,
                config.indicator_field
            )

        elif format_type == OutputFormat.STIX:
            return formatter.format_stix(
                indicators,
                config.indicator_field,
                config.type_field
            )

        elif format_type == OutputFormat.MISP:
            return formatter.format_misp(
                indicators,
                config.indicator_field,
                config.type_field
            )

        return ""

    def _get_content_type(self, format_type: OutputFormat) -> str:
        """Get HTTP Content-Type for format"""
        content_types = {
            OutputFormat.PLAIN: "text/plain; charset=utf-8",
            OutputFormat.CSV: "text/csv; charset=utf-8",
            OutputFormat.JSON: "application/json; charset=utf-8",
            OutputFormat.PALO_ALTO_EDL: "text/plain; charset=utf-8",
            OutputFormat.CISCO_IOS: "text/plain; charset=utf-8",
            OutputFormat.FORTINET: "text/plain; charset=utf-8",
            OutputFormat.STIX: "application/stix+json; charset=utf-8",
            OutputFormat.MISP: "application/json; charset=utf-8",
        }
        return content_types.get(format_type, "text/plain")

    def _log_access(
        self,
        distribution_name: str,
        client_ip: str,
        record_count: int,
        response_code: int,
        response_time_ms: int,
        format_str: str,
        user_agent: str
    ) -> None:
        """Log access for monitoring"""
        log_entry = AccessLog(
            timestamp=datetime.utcnow(),
            client_ip=client_ip,
            distribution_name=distribution_name,
            record_count=record_count,
            response_code=response_code,
            response_time_ms=response_time_ms,
            format=format_str,
            user_agent=user_agent
        )
        self._access_logs.append(log_entry)

        # Keep only last 10000 entries
        if len(self._access_logs) > 10000:
            self._access_logs = self._access_logs[-10000:]

    def get_access_stats(self, distribution_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get access statistics for a distribution"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        relevant_logs = [
            log for log in self._access_logs
            if log.distribution_name == distribution_name and log.timestamp > cutoff
        ]

        if not relevant_logs:
            return {
                "access_count": 0,
                "unique_clients": 0,
                "avg_response_time_ms": 0,
                "error_rate": 0,
            }

        unique_clients = len(set(log.client_ip for log in relevant_logs))
        total_time = sum(log.response_time_ms for log in relevant_logs)
        errors = sum(1 for log in relevant_logs if log.response_code >= 400)

        return {
            "access_count": len(relevant_logs),
            "unique_clients": unique_clients,
            "avg_response_time_ms": total_time // len(relevant_logs),
            "error_rate": errors / len(relevant_logs) if relevant_logs else 0,
            "last_access": max(log.timestamp for log in relevant_logs).isoformat(),
        }

    def invalidate_cache(self, distribution_name: str) -> None:
        """Invalidate cache for a distribution"""
        keys_to_remove = [
            k for k in self._cache.keys()
            if k.startswith(f"{distribution_name}:")
        ]
        for key in keys_to_remove:
            del self._cache[key]
        logger.info(f"Invalidated cache for {distribution_name}")


# =============================================================================
# Feed Ingestion Handler
# =============================================================================

@dataclass
class FeedConfig:
    """Configuration for a threat feed source"""
    name: str
    url: str
    feed_format: str = "csv"  # csv, json, plain, stix
    poll_interval_seconds: int = 3600
    target_collection: str = ""

    # Authentication
    auth_type: str = "none"  # none, basic, api_key, bearer
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

    # Field mapping
    field_mapping: Dict[str, str] = field(default_factory=dict)
    default_indicator_type: str = "ip"

    # Processing
    deduplicate: bool = True
    dedup_field: str = "indicator"
    expiration_days: int = 30

    # Request settings
    timeout_seconds: int = 30
    verify_ssl: bool = True
    custom_headers: Dict[str, str] = field(default_factory=dict)


class ThreatFeedIngester:
    """
    Ingests threat indicators from external feeds.

    Supports various feed formats and sources like:
    - Abuse.ch (URLhaus, Feodo Tracker)
    - Emerging Threats
    - Spamhaus (DROP, EDROP)
    - FireHOL
    - AlienVault OTX
    - Custom CSV/JSON feeds
    """

    # Pre-configured feed templates
    FEED_TEMPLATES = {
        "urlhaus": FeedConfig(
            name="URLhaus",
            url="https://urlhaus.abuse.ch/downloads/csv_online/",
            feed_format="csv",
            poll_interval_seconds=3600,
            field_mapping={
                "url": "indicator",
                "url_status": "status",
                "threat": "threat_type",
            },
            default_indicator_type="url",
        ),
        "feodo_tracker": FeedConfig(
            name="Feodo Tracker",
            url="https://feodotracker.abuse.ch/downloads/ipblocklist.csv",
            feed_format="csv",
            poll_interval_seconds=3600,
            field_mapping={
                "ip_address": "indicator",
            },
            default_indicator_type="ip",
        ),
        "spamhaus_drop": FeedConfig(
            name="Spamhaus DROP",
            url="https://www.spamhaus.org/drop/drop.txt",
            feed_format="plain",
            poll_interval_seconds=86400,
            default_indicator_type="cidr",
        ),
        "spamhaus_edrop": FeedConfig(
            name="Spamhaus EDROP",
            url="https://www.spamhaus.org/drop/edrop.txt",
            feed_format="plain",
            poll_interval_seconds=86400,
            default_indicator_type="cidr",
        ),
        "firehol_level1": FeedConfig(
            name="FireHOL Level 1",
            url="https://iplists.firehol.org/files/firehol_level1.netset",
            feed_format="plain",
            poll_interval_seconds=86400,
            default_indicator_type="cidr",
        ),
        "emerging_threats": FeedConfig(
            name="Emerging Threats",
            url="https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
            feed_format="plain",
            poll_interval_seconds=3600,
            default_indicator_type="ip",
        ),
    }

    def __init__(self):
        self._feeds: Dict[str, FeedConfig] = {}
        self._last_poll: Dict[str, datetime] = {}

    def register_feed(self, config: FeedConfig) -> None:
        """Register a threat feed"""
        self._feeds[config.name] = config
        logger.info(f"Registered threat feed: {config.name}")

    def get_feed_template(self, template_name: str) -> Optional[FeedConfig]:
        """Get a pre-configured feed template"""
        return self.FEED_TEMPLATES.get(template_name)

    def list_templates(self) -> List[str]:
        """List available feed templates"""
        return list(self.FEED_TEMPLATES.keys())

    def poll_feed(self, feed_name: str) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Poll a feed for new indicators.

        Returns:
            Tuple of (success, indicators, error_message)
        """
        import requests

        config = self._feeds.get(feed_name)
        if not config:
            return False, [], f"Unknown feed: {feed_name}"

        try:
            # Build request
            headers = dict(config.custom_headers)

            if config.auth_type == "api_key":
                headers["X-API-Key"] = config.api_key
            elif config.auth_type == "bearer":
                headers["Authorization"] = f"Bearer {config.api_key}"

            auth = None
            if config.auth_type == "basic":
                auth = (config.username, config.password)

            # Make request
            response = requests.get(
                config.url,
                headers=headers,
                auth=auth,
                timeout=config.timeout_seconds,
                verify=config.verify_ssl
            )
            response.raise_for_status()

            # Parse response
            indicators = self._parse_feed(
                response.text,
                config.feed_format,
                config.field_mapping,
                config.default_indicator_type
            )

            # Deduplicate if enabled
            if config.deduplicate:
                seen = set()
                unique = []
                for ind in indicators:
                    key = ind.get(config.dedup_field, "")
                    if key and key not in seen:
                        seen.add(key)
                        unique.append(ind)
                indicators = unique

            # Update poll time
            self._last_poll[feed_name] = datetime.utcnow()

            logger.info(f"Polled {feed_name}: {len(indicators)} indicators")
            return True, indicators, ""

        except Exception as e:
            logger.error(f"Failed to poll {feed_name}: {e}")
            return False, [], str(e)

    def _parse_feed(
        self,
        content: str,
        feed_format: str,
        field_mapping: Dict[str, str],
        default_type: str
    ) -> List[Dict[str, Any]]:
        """Parse feed content into indicators"""
        indicators = []
        now = datetime.utcnow().isoformat()

        if feed_format == "plain":
            # One indicator per line
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue

                # Some feeds have comments after the value
                if ";" in line:
                    line = line.split(";")[0].strip()

                indicators.append({
                    "indicator": line,
                    "indicator_type": default_type,
                    "source": "feed",
                    "first_seen": now,
                })

        elif feed_format == "csv":
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                indicator = {"first_seen": now, "source": "feed"}

                # Apply field mapping
                for src_field, dst_field in field_mapping.items():
                    if src_field in row:
                        indicator[dst_field] = row[src_field]

                # Copy unmapped fields
                for key, value in row.items():
                    if key not in field_mapping:
                        indicator[key] = value

                # Set default type if not mapped
                if "indicator_type" not in indicator:
                    indicator["indicator_type"] = default_type

                if indicator.get("indicator"):
                    indicators.append(indicator)

        elif feed_format == "json":
            data = json.loads(content)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Try common keys
                items = data.get("data", data.get("results", data.get("indicators", [data])))
            else:
                items = []

            for item in items:
                if isinstance(item, dict):
                    indicator = {"first_seen": now, "source": "feed"}

                    # Apply field mapping
                    for src_field, dst_field in field_mapping.items():
                        if src_field in item:
                            indicator[dst_field] = item[src_field]

                    # Copy unmapped fields
                    for key, value in item.items():
                        if key not in field_mapping:
                            indicator[key] = value

                    if "indicator_type" not in indicator:
                        indicator["indicator_type"] = default_type

                    if indicator.get("indicator"):
                        indicators.append(indicator)

        return indicators

    def get_poll_status(self, feed_name: str) -> Optional[Dict[str, Any]]:
        """Get poll status for a feed"""
        config = self._feeds.get(feed_name)
        if not config:
            return None

        last_poll = self._last_poll.get(feed_name)

        return {
            "name": feed_name,
            "url": config.url,
            "last_poll": last_poll.isoformat() if last_poll else None,
            "poll_interval_seconds": config.poll_interval_seconds,
            "next_poll": (
                (last_poll + timedelta(seconds=config.poll_interval_seconds)).isoformat()
                if last_poll else "pending"
            ),
        }
