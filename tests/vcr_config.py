"""
VCR Configuration for API Test Fixtures

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/vcr_config.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Test Configuration

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  VCR configuration for recording and replaying
                                Splunk API interactions with deidentified data.
-------------------------------------------------------------------------------

License: MIT

SDK REQUIREMENTS (from BDD contracts):
- API tests MUST use VCR cassettes for API mocking
- Cassettes MUST contain deidentified data (PII scrubbed)
- VCR supports "record", "none", and "new_episodes" modes
- NO mock objects for external API simulation
===============================================================================
"""

import os
import re
import vcr
from functools import wraps
from typing import Callable, Dict, List, Optional

# =============================================================================
# VCR Configuration Constants
# =============================================================================

CASSETTE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'cassettes')

# Sensitive patterns to scrub from cassettes
SENSITIVE_PATTERNS = [
    # Splunk tokens
    (r'(Splunk\s+)[A-Za-z0-9_-]{20,}', r'\1REDACTED_TOKEN'),
    (r'(Bearer\s+)[A-Za-z0-9_-]{20,}', r'\1REDACTED_TOKEN'),
    (r'(splunkToken["\']?\s*[:=]\s*["\']?)[^"\'&\s]+', r'\1REDACTED_TOKEN'),

    # Session keys
    (r'(session[Kk]ey["\']?\s*[:=]\s*["\']?)[^"\'&\s]+', r'\1REDACTED_SESSION'),

    # Passwords
    (r'(password["\']?\s*[:=]\s*["\']?)[^"\'&\s]+', r'\1REDACTED_PASSWORD'),

    # IP addresses (anonymize to example ranges)
    (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 'ANONYMIZED_IP'),

    # Hostnames (except localhost)
    (r'(?<!localhost)(splunk-[a-z0-9-]+\.[\w.-]+)', 'anonymized-splunk.example.com'),

    # Email addresses
    (r'[\w.-]+@[\w.-]+\.\w+', 'user@example.com'),

    # UUIDs
    (r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
     'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'),
]

# Headers to scrub entirely
SCRUB_HEADERS = [
    'Authorization',
    'Cookie',
    'Set-Cookie',
    'X-Splunk-Token',
    'X-Auth-Token',
]


# =============================================================================
# Response Scrubbing Functions
# =============================================================================

def scrub_response(response: Dict) -> Dict:
    """
    Scrub sensitive data from VCR response.

    Implements deidentification as required by BDD contracts.

    Args:
        response: VCR response dictionary

    Returns:
        Scrubbed response dictionary
    """
    # Scrub headers
    if 'headers' in response:
        for header in SCRUB_HEADERS:
            if header in response['headers']:
                response['headers'][header] = ['REDACTED']
            if header.lower() in response['headers']:
                response['headers'][header.lower()] = ['REDACTED']

    # Scrub body content
    if 'body' in response and 'string' in response['body']:
        body = response['body']['string']
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='replace')

        for pattern, replacement in SENSITIVE_PATTERNS:
            body = re.sub(pattern, replacement, body, flags=re.IGNORECASE)

        response['body']['string'] = body.encode('utf-8')

    return response


def scrub_request(request):
    """
    Scrub sensitive data from VCR request.

    Args:
        request: VCR request object

    Returns:
        Scrubbed request object
    """
    # Scrub headers
    for header in SCRUB_HEADERS:
        if header in request.headers:
            request.headers[header] = 'REDACTED'

    # Scrub body if present
    if request.body:
        body = request.body
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='replace')

        for pattern, replacement in SENSITIVE_PATTERNS:
            body = re.sub(pattern, replacement, body, flags=re.IGNORECASE)

        request.body = body

    return request


# =============================================================================
# VCR Custom Matchers
# =============================================================================

def splunk_request_matcher(r1, r2):
    """
    Custom request matcher for Splunk API calls.

    Matches requests while ignoring dynamic elements like
    session tokens that change between runs.
    """
    # Match on method and path
    if r1.method != r2.method:
        return False

    # Parse URLs, ignoring query parameters that may be dynamic
    from urllib.parse import urlparse, parse_qs

    url1 = urlparse(r1.uri)
    url2 = urlparse(r2.uri)

    if url1.path != url2.path:
        return False

    # Compare query parameters, ignoring output_mode variations
    params1 = parse_qs(url1.query)
    params2 = parse_qs(url2.query)

    # Remove dynamic params from comparison
    dynamic_params = ['output_mode', '_', 'timestamp']
    for param in dynamic_params:
        params1.pop(param, None)
        params2.pop(param, None)

    return params1 == params2


# =============================================================================
# VCR Instance Configuration
# =============================================================================

def get_vcr(record_mode: str = 'none') -> vcr.VCR:
    """
    Get configured VCR instance.

    Args:
        record_mode: VCR record mode
            - 'none': Never record, use cassettes only (for CI/CD)
            - 'new_episodes': Record new requests only
            - 'once': Record once, replay after

    Returns:
        Configured VCR instance
    """
    # Ensure cassette directory exists
    os.makedirs(CASSETTE_DIR, exist_ok=True)

    custom_vcr = vcr.VCR(
        cassette_library_dir=CASSETTE_DIR,
        record_mode=record_mode,
        match_on=['method', 'scheme', 'host', 'port', 'path'],
        filter_headers=SCRUB_HEADERS,
        before_record_request=scrub_request,
        before_record_response=scrub_response,
        decode_compressed_response=True,
    )

    # Register custom matchers
    custom_vcr.register_matcher('splunk', splunk_request_matcher)

    return custom_vcr


# =============================================================================
# Decorator for VCR Tests
# =============================================================================

def use_cassette(cassette_name: str, record_mode: str = None):
    """
    Decorator to use VCR cassette for a test.

    Example:
        @use_cassette('test_sync_records')
        def test_sync_records(self):
            # API calls will be recorded/replayed
            pass

    Args:
        cassette_name: Name of the cassette file
        record_mode: Override default record mode
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            mode = record_mode or os.environ.get('VCR_RECORD_MODE', 'none')
            my_vcr = get_vcr(mode)

            cassette_path = f"{cassette_name}.yaml"
            with my_vcr.use_cassette(cassette_path):
                return func(*args, **kwargs)

        return wrapper
    return decorator


# =============================================================================
# Pytest Fixtures
# =============================================================================

import pytest


@pytest.fixture
def vcr_cassette(request):
    """
    Pytest fixture for VCR cassettes.

    Use with parametrize to specify cassette name:

        @pytest.mark.parametrize('vcr_cassette', ['my_test'], indirect=True)
        def test_something(vcr_cassette):
            with vcr_cassette:
                # API calls recorded/replayed
                pass
    """
    cassette_name = getattr(request, 'param', request.node.name)
    mode = os.environ.get('VCR_RECORD_MODE', 'none')
    my_vcr = get_vcr(mode)

    return my_vcr.use_cassette(f"{cassette_name}.yaml")


@pytest.fixture
def vcr_config():
    """
    Fixture providing VCR configuration for tests.
    """
    return {
        'cassette_library_dir': CASSETTE_DIR,
        'record_mode': os.environ.get('VCR_RECORD_MODE', 'none'),
        'filter_headers': SCRUB_HEADERS,
    }


# =============================================================================
# CLI Utility for Cassette Management
# =============================================================================

def list_cassettes() -> List[str]:
    """List all available cassettes"""
    if not os.path.exists(CASSETTE_DIR):
        return []
    return [f for f in os.listdir(CASSETTE_DIR) if f.endswith('.yaml')]


def delete_cassette(name: str) -> bool:
    """Delete a cassette file"""
    path = os.path.join(CASSETTE_DIR, f"{name}.yaml")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def refresh_cassettes():
    """
    Re-record all cassettes.

    Use with caution - requires live API access.
    """
    import shutil
    backup_dir = f"{CASSETTE_DIR}_backup"

    if os.path.exists(CASSETTE_DIR):
        shutil.move(CASSETTE_DIR, backup_dir)

    os.makedirs(CASSETTE_DIR, exist_ok=True)
    print(f"Cassettes backed up to {backup_dir}")
    print("Run tests with VCR_RECORD_MODE=once to re-record")
