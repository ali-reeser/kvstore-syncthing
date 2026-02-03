"""
KVStore Test Fixture Generator

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: tests/generators/kvstore_fixtures.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Test Utilities

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Random KVStore fixture generator supporting
                                multiple schemas, case variants, CIDR ranges,
                                wildcards, and edge cases.
-------------------------------------------------------------------------------

License: MIT
===============================================================================
"""

import hashlib
import ipaddress
import json
import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple
import re


# =============================================================================
# Data Generators
# =============================================================================

class DataGenerators:
    """Collection of data generators for different field types"""

    # Character sets
    LOWERCASE = string.ascii_lowercase
    UPPERCASE = string.ascii_uppercase
    DIGITS = string.digits
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;':\",./<>?"

    # Common names for realistic data
    FIRST_NAMES = [
        "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
        "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan",
        "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Wei", "Yuki",
        "Mohammed", "Fatima", "Raj", "Priya", "Carlos", "Maria", "Ahmed", "Aisha"
    ]

    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Chen", "Wang", "Kim", "Patel",
        "Singh", "Kumar", "Ali", "Hassan", "Santos", "Fernandez"
    ]

    DOMAINS = [
        "example.com", "test.org", "corp.local", "company.net", "internal.io"
    ]

    @classmethod
    def uuid(cls) -> str:
        """Generate a random UUID"""
        return str(uuid.uuid4())

    @classmethod
    def username(cls, case_variant: bool = False) -> str:
        """Generate a random username"""
        first = random.choice(cls.FIRST_NAMES)
        last = random.choice(cls.LAST_NAMES)
        num = random.randint(1, 999)

        username = f"{first.lower()}.{last.lower()}{num}"

        if case_variant:
            variant = random.choice(["lower", "upper", "title", "mixed"])
            if variant == "lower":
                return username.lower()
            elif variant == "upper":
                return username.upper()
            elif variant == "title":
                return username.title()
            else:
                return "".join(
                    c.upper() if random.random() > 0.5 else c.lower()
                    for c in username
                )

        return username

    @classmethod
    def email(cls, case_variant: bool = False) -> str:
        """Generate a random email address"""
        username = cls.username(case_variant=False)
        domain = random.choice(cls.DOMAINS)
        email = f"{username}@{domain}"

        if case_variant:
            variant = random.choice(["lower", "upper", "mixed"])
            if variant == "upper":
                return email.upper()
            elif variant == "mixed":
                return "".join(
                    c.upper() if random.random() > 0.5 else c.lower()
                    for c in email
                )

        return email

    @classmethod
    def hostname(cls, case_variant: bool = False) -> str:
        """Generate a random hostname"""
        prefixes = ["srv", "web", "app", "db", "cache", "worker", "api"]
        envs = ["dev", "stg", "prd", "tst"]
        regions = ["us-east", "us-west", "eu-west", "ap-south"]

        hostname = f"{random.choice(prefixes)}-{random.choice(envs)}-{random.choice(regions)}-{random.randint(1, 99):02d}"

        if case_variant:
            variant = random.choice(["lower", "upper"])
            if variant == "upper":
                return hostname.upper()

        return hostname

    @classmethod
    def ipv4(cls) -> str:
        """Generate a random IPv4 address"""
        # Avoid reserved ranges for more realistic data
        while True:
            ip = ipaddress.IPv4Address(random.randint(0, 2**32 - 1))
            if not (ip.is_private or ip.is_loopback or ip.is_multicast):
                return str(ip)

    @classmethod
    def ipv4_private(cls) -> str:
        """Generate a random private IPv4 address"""
        ranges = [
            ("10.0.0.0", "10.255.255.255"),
            ("172.16.0.0", "172.31.255.255"),
            ("192.168.0.0", "192.168.255.255"),
        ]
        start, end = random.choice(ranges)
        start_int = int(ipaddress.IPv4Address(start))
        end_int = int(ipaddress.IPv4Address(end))
        return str(ipaddress.IPv4Address(random.randint(start_int, end_int)))

    @classmethod
    def ipv6(cls) -> str:
        """Generate a random IPv6 address"""
        return str(ipaddress.IPv6Address(random.randint(0, 2**128 - 1)))

    @classmethod
    def cidr_v4(cls, prefix_min: int = 8, prefix_max: int = 30) -> str:
        """Generate a random CIDR range"""
        prefix = random.randint(prefix_min, prefix_max)
        # Generate a network address
        mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
        network = random.randint(0, 2**32 - 1) & mask
        ip = ipaddress.IPv4Address(network)
        return f"{ip}/{prefix}"

    @classmethod
    def cidr_v6(cls, prefix_min: int = 32, prefix_max: int = 64) -> str:
        """Generate a random IPv6 CIDR range"""
        prefix = random.randint(prefix_min, prefix_max)
        mask = (2**128 - 1) << (128 - prefix)
        network = random.randint(0, 2**128 - 1) & mask
        ip = ipaddress.IPv6Address(network)
        return f"{ip}/{prefix}"

    @classmethod
    def mac_address(cls) -> str:
        """Generate a random MAC address"""
        mac = [random.randint(0, 255) for _ in range(6)]
        return ":".join(f"{b:02X}" for b in mac)

    @classmethod
    def timestamp(cls, range_days: int = 30) -> str:
        """Generate a random timestamp within range"""
        now = datetime.utcnow()
        delta = timedelta(days=random.randint(0, range_days))
        dt = now - delta
        # Add random time component
        dt = dt.replace(
            hour=random.randint(0, 23),
            minute=random.randint(0, 59),
            second=random.randint(0, 59),
        )
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    @classmethod
    def wildcard_pattern(cls) -> str:
        """Generate a random wildcard pattern"""
        pattern_types = [
            lambda: f"{cls.random_string(5)}*",  # prefix
            lambda: f"*{cls.random_string(5)}",  # suffix
            lambda: f"*{cls.random_string(3)}*",  # contains
            lambda: f"{cls.random_string(2)}?{cls.random_string(2)}",  # single char
        ]
        return random.choice(pattern_types)()

    @classmethod
    def random_string(cls, length: int, charset: str = None) -> str:
        """Generate a random string"""
        if charset is None:
            charset = cls.LOWERCASE + cls.DIGITS
        return "".join(random.choice(charset) for _ in range(length))

    @classmethod
    def pattern_string(cls, pattern: str) -> str:
        """Generate a string matching a pattern like 'USR-[0-9]{6}'"""
        result = []
        i = 0
        while i < len(pattern):
            if pattern[i] == "[":
                # Find character class
                end = pattern.index("]", i)
                char_class = pattern[i+1:end]

                # Check for repetition
                repeat = 1
                if end + 1 < len(pattern) and pattern[end + 1] == "{":
                    rep_end = pattern.index("}", end + 1)
                    repeat = int(pattern[end + 2:rep_end])
                    i = rep_end + 1
                else:
                    i = end + 1

                # Generate characters
                if char_class == "0-9":
                    result.append("".join(random.choice(cls.DIGITS) for _ in range(repeat)))
                elif char_class == "A-Z":
                    result.append("".join(random.choice(cls.UPPERCASE) for _ in range(repeat)))
                elif char_class == "a-z":
                    result.append("".join(random.choice(cls.LOWERCASE) for _ in range(repeat)))
                elif char_class == "0-9A-F":
                    result.append("".join(random.choice(cls.DIGITS + "ABCDEF") for _ in range(repeat)))
                else:
                    result.append("".join(random.choice(char_class) for _ in range(repeat)))
            else:
                result.append(pattern[i])
                i += 1

        return "".join(result)


# =============================================================================
# Case Transformation
# =============================================================================

@dataclass
class CaseMapping:
    """Stores original case for later restoration"""
    key: str
    field: str
    original_value: str
    normalized_value: str


class CaseTransformer:
    """Handles case conversion and restoration"""

    def __init__(self, normalize_to: str = "lowercase"):
        """
        Initialize transformer.

        Args:
            normalize_to: Target case - "lowercase", "uppercase", "titlecase"
        """
        self.normalize_to = normalize_to
        self.mappings: List[CaseMapping] = []

    def normalize(self, record: Dict, key: str, fields: List[str]) -> Dict:
        """
        Normalize case of specified fields, storing original for restoration.

        Args:
            record: Record to normalize
            key: Record key
            fields: Fields to normalize

        Returns:
            Normalized record
        """
        result = record.copy()

        for field in fields:
            if field in result and isinstance(result[field], str):
                original = result[field]

                if self.normalize_to == "lowercase":
                    normalized = original.lower()
                elif self.normalize_to == "uppercase":
                    normalized = original.upper()
                elif self.normalize_to == "titlecase":
                    normalized = original.title()
                else:
                    normalized = original

                if original != normalized:
                    self.mappings.append(CaseMapping(
                        key=key,
                        field=field,
                        original_value=original,
                        normalized_value=normalized,
                    ))

                result[field] = normalized

        return result

    def restore(self, record: Dict, key: str) -> Dict:
        """
        Restore original case from mappings.

        Args:
            record: Record to restore
            key: Record key

        Returns:
            Record with original case restored
        """
        result = record.copy()

        for mapping in self.mappings:
            if mapping.key == key and mapping.field in result:
                if result[mapping.field] == mapping.normalized_value:
                    result[mapping.field] = mapping.original_value

        return result

    def get_mapping_table(self) -> List[Dict]:
        """Get mappings as list of dicts for storage"""
        return [
            {
                "_key": f"{m.key}_{m.field}",
                "record_key": m.key,
                "field": m.field,
                "original": m.original_value,
                "normalized": m.normalized_value,
            }
            for m in self.mappings
        ]

    def load_mapping_table(self, mappings: List[Dict]):
        """Load mappings from stored format"""
        self.mappings = [
            CaseMapping(
                key=m["record_key"],
                field=m["field"],
                original_value=m["original"],
                normalized_value=m["normalized"],
            )
            for m in mappings
        ]


# =============================================================================
# KVStore Fixture Generator
# =============================================================================

@dataclass
class FieldSpec:
    """Specification for a field"""
    name: str
    field_type: str
    generator: Optional[str] = None
    pattern: Optional[str] = None
    choices: Optional[List[Any]] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    precision: Optional[int] = None
    range_days: Optional[int] = None
    nullable: float = 0.0
    case_variants: bool = False
    items: Optional[str] = None
    max_length: Optional[int] = None


class KVStoreFixtureGenerator:
    """
    Generates random KVStore test fixtures based on schema definitions.

    Supports:
    - Multiple field types (string, number, boolean, ip, cidr, timestamp, array)
    - Pattern-based string generation
    - Case variants for testing case sensitivity
    - Nullable fields
    - Edge cases injection
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize generator.

        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

        self.generators = DataGenerators()

    def generate_field(self, spec: FieldSpec) -> Any:
        """
        Generate a value for a field based on its specification.

        Args:
            spec: Field specification

        Returns:
            Generated value
        """
        # Handle nullable fields
        if spec.nullable > 0 and random.random() < spec.nullable:
            return None

        # Generate based on type
        if spec.field_type == "string":
            if spec.pattern:
                return self.generators.pattern_string(spec.pattern)
            elif spec.generator:
                gen_func = getattr(self.generators, spec.generator, None)
                if gen_func:
                    if spec.case_variants:
                        return gen_func(case_variant=True)
                    return gen_func()
            elif spec.choices:
                return random.choice(spec.choices)
            else:
                return self.generators.random_string(10)

        elif spec.field_type == "number":
            min_v = spec.min_val if spec.min_val is not None else 0
            max_v = spec.max_val if spec.max_val is not None else 1000

            if spec.precision is not None:
                value = random.uniform(min_v, max_v)
                return round(value, spec.precision)
            else:
                return random.randint(int(min_v), int(max_v))

        elif spec.field_type == "boolean":
            return random.choice([True, False])

        elif spec.field_type == "ip":
            return self.generators.ipv4()

        elif spec.field_type == "cidr":
            return self.generators.cidr_v4()

        elif spec.field_type == "timestamp":
            days = spec.range_days or 30
            return self.generators.timestamp(days)

        elif spec.field_type == "array":
            length = random.randint(1, spec.max_length or 5)
            item_spec = FieldSpec(
                name="item",
                field_type=spec.items or "string",
                choices=spec.choices,
            )
            return [self.generate_field(item_spec) for _ in range(length)]

        else:
            return self.generators.random_string(10)

    def generate_record(self, schema: Dict[str, FieldSpec]) -> Dict:
        """
        Generate a complete record from schema.

        Args:
            schema: Dict of field name to FieldSpec

        Returns:
            Generated record
        """
        return {
            name: self.generate_field(spec)
            for name, spec in schema.items()
        }

    def generate_collection(
        self,
        schema: Dict[str, FieldSpec],
        count: int,
        include_edge_cases: bool = True,
    ) -> Generator[Dict, None, None]:
        """
        Generate a collection of records.

        Args:
            schema: Schema definition
            count: Number of records to generate
            include_edge_cases: Whether to inject edge case records

        Yields:
            Generated records
        """
        # Calculate edge case injection points
        edge_case_indices = set()
        if include_edge_cases and count >= 10:
            num_edge_cases = min(count // 10, 20)
            edge_case_indices = set(random.sample(range(count), num_edge_cases))

        for i in range(count):
            if i in edge_case_indices:
                yield self._generate_edge_case_record(schema)
            else:
                yield self.generate_record(schema)

    def _generate_edge_case_record(self, schema: Dict[str, FieldSpec]) -> Dict:
        """Generate a record with edge case values"""
        record = self.generate_record(schema)

        # Pick a random string field to inject edge case
        string_fields = [
            name for name, spec in schema.items()
            if spec.field_type == "string" and not spec.pattern
        ]

        if string_fields:
            field = random.choice(string_fields)
            edge_cases = [
                "",  # empty string
                " ",  # single space
                "hello\nworld",  # newline
                "test\ttab",  # tab
                "emoji🎉here",  # emoji
                "日本語",  # unicode
                "Ü̈ñîcödé",  # accented
                "quotes\"here",  # quotes
            ]
            record[field] = random.choice(edge_cases)

        return record

    @classmethod
    def from_yaml_schema(cls, schema_config: Dict) -> Tuple["KVStoreFixtureGenerator", Dict[str, FieldSpec]]:
        """
        Create generator and schema from YAML configuration.

        Args:
            schema_config: Schema configuration from YAML

        Returns:
            Tuple of (generator, schema)
        """
        generator = cls()
        schema = {}

        for field_name, field_config in schema_config.get("fields", {}).items():
            schema[field_name] = FieldSpec(
                name=field_name,
                field_type=field_config.get("type", "string"),
                generator=field_config.get("generator"),
                pattern=field_config.get("pattern"),
                choices=field_config.get("choices"),
                min_val=field_config.get("min"),
                max_val=field_config.get("max"),
                precision=field_config.get("precision"),
                range_days=field_config.get("range_days", 30) if "last_" in str(field_config.get("range", "")) else None,
                nullable=field_config.get("nullable", 0),
                case_variants=field_config.get("case_variants", False),
                items=field_config.get("items"),
                max_length=field_config.get("max_length"),
            )

        return generator, schema
