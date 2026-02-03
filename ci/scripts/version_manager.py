#!/usr/bin/env python3
"""
Semantic Version Manager for CI/CD

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: ci/scripts/version_manager.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: CI/CD Tooling

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  Semantic version manager supporting:
                                - Major/Minor/Patch bumps
                                - Pre-release tags (alpha, beta, rc)
                                - Build metadata
                                - Multi-file version sync
-------------------------------------------------------------------------------

License: MIT

USAGE:
    # Bump patch version (1.0.0 -> 1.0.1)
    python version_manager.py bump patch

    # Bump minor version (1.0.0 -> 1.1.0)
    python version_manager.py bump minor

    # Bump major version (1.0.0 -> 2.0.0)
    python version_manager.py bump major

    # Set pre-release (1.0.0 -> 1.0.0-rc1)
    python version_manager.py prerelease rc 1

    # Bump pre-release (1.0.0-rc1 -> 1.0.0-rc2)
    python version_manager.py bump prerelease

    # Promote to release (1.0.0-rc2 -> 1.0.0)
    python version_manager.py promote

    # Set specific version
    python version_manager.py set 2.0.0-beta1

    # Show current version
    python version_manager.py show
===============================================================================
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Semantic Version Class
# =============================================================================

@dataclass
class SemanticVersion:
    """
    Semantic version following SemVer 2.0.0 specification.

    Format: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]

    Examples:
        1.0.0
        1.0.0-alpha
        1.0.0-alpha.1
        1.0.0-rc1
        1.0.0-rc1+build.123
    """
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: Optional[str] = None
    prerelease_num: Optional[int] = None
    build: Optional[str] = None

    VERSION_PATTERN = re.compile(
        r'^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)'
        r'(?:-(?P<prerelease>[a-zA-Z]+)(?:\.?(?P<prerelease_num>\d+))?)?'
        r'(?:\+(?P<build>.+))?$'
    )

    @classmethod
    def parse(cls, version_string: str) -> "SemanticVersion":
        """Parse a version string into SemanticVersion"""
        match = cls.VERSION_PATTERN.match(version_string.strip())
        if not match:
            raise ValueError(f"Invalid version format: {version_string}")

        groups = match.groupdict()
        return cls(
            major=int(groups['major']),
            minor=int(groups['minor']),
            patch=int(groups['patch']),
            prerelease=groups.get('prerelease'),
            prerelease_num=int(groups['prerelease_num']) if groups.get('prerelease_num') else None,
            build=groups.get('build')
        )

    def __str__(self) -> str:
        """Format version as string"""
        version = f"{self.major}.{self.minor}.{self.patch}"

        if self.prerelease:
            version += f"-{self.prerelease}"
            if self.prerelease_num is not None:
                version += f"{self.prerelease_num}"

        if self.build:
            version += f"+{self.build}"

        return version

    def bump_major(self) -> "SemanticVersion":
        """Bump major version, reset minor and patch"""
        return SemanticVersion(
            major=self.major + 1,
            minor=0,
            patch=0
        )

    def bump_minor(self) -> "SemanticVersion":
        """Bump minor version, reset patch"""
        return SemanticVersion(
            major=self.major,
            minor=self.minor + 1,
            patch=0
        )

    def bump_patch(self) -> "SemanticVersion":
        """Bump patch version"""
        return SemanticVersion(
            major=self.major,
            minor=self.minor,
            patch=self.patch + 1
        )

    def bump_prerelease(self) -> "SemanticVersion":
        """Bump pre-release number"""
        if not self.prerelease:
            raise ValueError("No pre-release tag to bump")

        new_num = (self.prerelease_num or 0) + 1
        return SemanticVersion(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            prerelease=self.prerelease,
            prerelease_num=new_num
        )

    def set_prerelease(self, tag: str, num: Optional[int] = None) -> "SemanticVersion":
        """Set pre-release tag"""
        valid_tags = ['alpha', 'beta', 'rc', 'dev', 'preview']
        if tag.lower() not in valid_tags:
            print(f"Warning: '{tag}' is not a standard pre-release tag. "
                  f"Standard tags: {valid_tags}")

        return SemanticVersion(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            prerelease=tag.lower(),
            prerelease_num=num
        )

    def promote(self) -> "SemanticVersion":
        """Remove pre-release tag (promote to release)"""
        return SemanticVersion(
            major=self.major,
            minor=self.minor,
            patch=self.patch
        )

    def with_build(self, build: str) -> "SemanticVersion":
        """Add build metadata"""
        return SemanticVersion(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            prerelease=self.prerelease,
            prerelease_num=self.prerelease_num,
            build=build
        )

    @property
    def is_prerelease(self) -> bool:
        """Check if this is a pre-release version"""
        return self.prerelease is not None

    @property
    def core_version(self) -> str:
        """Get core version without pre-release or build"""
        return f"{self.major}.{self.minor}.{self.patch}"


# =============================================================================
# Version File Handlers
# =============================================================================

class VersionFileHandler:
    """Base class for version file handlers"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def read_version(self) -> Optional[str]:
        """Read version from file"""
        raise NotImplementedError

    def write_version(self, version: str) -> bool:
        """Write version to file"""
        raise NotImplementedError


class JSONVersionHandler(VersionFileHandler):
    """Handler for JSON files (globalConfig.json, package.json)"""

    def __init__(self, file_path: str, version_key: str = "version"):
        super().__init__(file_path)
        self.version_key = version_key

    def read_version(self) -> Optional[str]:
        if not self.file_path.exists():
            return None

        with open(self.file_path, 'r') as f:
            data = json.load(f)

        # Handle nested keys like "meta.version"
        keys = self.version_key.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return str(value)

    def write_version(self, version: str) -> bool:
        if not self.file_path.exists():
            return False

        with open(self.file_path, 'r') as f:
            data = json.load(f)

        # Handle nested keys
        keys = self.version_key.split('.')
        target = data
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = version

        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=4)

        return True


class AppConfHandler(VersionFileHandler):
    """Handler for Splunk app.conf files"""

    def read_version(self) -> Optional[str]:
        if not self.file_path.exists():
            return None

        with open(self.file_path, 'r') as f:
            content = f.read()

        match = re.search(r'^version\s*=\s*(.+)$', content, re.MULTILINE)
        return match.group(1).strip() if match else None

    def write_version(self, version: str) -> bool:
        if not self.file_path.exists():
            # Create new app.conf
            content = f"""[install]
is_configured = false

[ui]
is_visible = true
label = KVStore Syncthing

[launcher]
author = KVStore Syncthing Team
description = Comprehensive KVStore synchronization solution
version = {version}

[package]
id = kvstore_syncthing
"""
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w') as f:
                f.write(content)
            return True

        with open(self.file_path, 'r') as f:
            content = f.read()

        # Update version line
        if re.search(r'^version\s*=', content, re.MULTILINE):
            content = re.sub(
                r'^version\s*=\s*.+$',
                f'version = {version}',
                content,
                flags=re.MULTILINE
            )
        else:
            # Add version to [launcher] stanza
            content = re.sub(
                r'(\[launcher\])',
                f'\\1\nversion = {version}',
                content
            )

        with open(self.file_path, 'w') as f:
            f.write(content)

        return True


class ChangelogHandler(VersionFileHandler):
    """Handler for CHANGELOG.md"""

    def read_version(self) -> Optional[str]:
        if not self.file_path.exists():
            return None

        with open(self.file_path, 'r') as f:
            content = f.read()

        # Find first version heading after [Unreleased]
        match = re.search(r'## \[(\d+\.\d+\.\d+[^\]]*)\]', content)
        return match.group(1) if match else None

    def write_version(self, version: str) -> bool:
        if not self.file_path.exists():
            return False

        with open(self.file_path, 'r') as f:
            content = f.read()

        today = datetime.utcnow().strftime('%Y-%m-%d')

        # Replace [Unreleased] with new version
        content = re.sub(
            r'## \[Unreleased\]',
            f'## [Unreleased]\n\n## [{version}] - {today}',
            content
        )

        with open(self.file_path, 'w') as f:
            f.write(content)

        return True


# =============================================================================
# Version Manager
# =============================================================================

class VersionManager:
    """Manages version across multiple files"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.handlers: List[VersionFileHandler] = []

        # Register known version files
        self._register_handlers()

    def _register_handlers(self):
        """Register handlers for known version files"""
        # globalConfig.json (UCC)
        global_config = self.project_root / "globalConfig.json"
        if global_config.exists():
            self.handlers.append(
                JSONVersionHandler(str(global_config), "meta.version")
            )

        # app.conf
        app_conf_paths = [
            self.project_root / "default" / "app.conf",
            self.project_root / "packages" / "kvstore_syncthing" / "default" / "app.conf",
        ]
        for path in app_conf_paths:
            self.handlers.append(AppConfHandler(str(path)))

        # package.json (if exists)
        package_json = self.project_root / "package.json"
        if package_json.exists():
            self.handlers.append(JSONVersionHandler(str(package_json)))

        # CHANGELOG.md
        changelog = self.project_root / "CHANGELOG.md"
        if changelog.exists():
            self.handlers.append(ChangelogHandler(str(changelog)))

    def get_current_version(self) -> Optional[SemanticVersion]:
        """Get current version from primary source"""
        for handler in self.handlers:
            version_str = handler.read_version()
            if version_str:
                try:
                    return SemanticVersion.parse(version_str)
                except ValueError:
                    continue
        return None

    def set_version(self, version: SemanticVersion) -> Dict[str, bool]:
        """Set version in all registered files"""
        results = {}
        version_str = str(version)

        for handler in self.handlers:
            try:
                success = handler.write_version(version_str)
                results[str(handler.file_path)] = success
            except Exception as e:
                print(f"Error updating {handler.file_path}: {e}")
                results[str(handler.file_path)] = False

        return results

    def bump(self, bump_type: str) -> Tuple[SemanticVersion, SemanticVersion]:
        """
        Bump version.

        Args:
            bump_type: major, minor, patch, or prerelease

        Returns:
            Tuple of (old_version, new_version)
        """
        current = self.get_current_version()
        if not current:
            current = SemanticVersion(0, 0, 0)

        if bump_type == "major":
            new_version = current.bump_major()
        elif bump_type == "minor":
            new_version = current.bump_minor()
        elif bump_type == "patch":
            new_version = current.bump_patch()
        elif bump_type == "prerelease":
            new_version = current.bump_prerelease()
        else:
            raise ValueError(f"Unknown bump type: {bump_type}")

        self.set_version(new_version)
        return current, new_version

    def set_prerelease(self, tag: str, num: Optional[int] = None) -> Tuple[SemanticVersion, SemanticVersion]:
        """Set pre-release tag on current version"""
        current = self.get_current_version()
        if not current:
            raise ValueError("No current version found")

        new_version = current.set_prerelease(tag, num)
        self.set_version(new_version)
        return current, new_version

    def promote(self) -> Tuple[SemanticVersion, SemanticVersion]:
        """Promote pre-release to release"""
        current = self.get_current_version()
        if not current:
            raise ValueError("No current version found")

        if not current.is_prerelease:
            raise ValueError("Current version is not a pre-release")

        new_version = current.promote()
        self.set_version(new_version)
        return current, new_version


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Semantic version manager for CI/CD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s show                      Show current version
  %(prog)s bump patch                1.0.0 -> 1.0.1
  %(prog)s bump minor                1.0.0 -> 1.1.0
  %(prog)s bump major                1.0.0 -> 2.0.0
  %(prog)s prerelease rc 1           1.0.0 -> 1.0.0-rc1
  %(prog)s bump prerelease           1.0.0-rc1 -> 1.0.0-rc2
  %(prog)s promote                   1.0.0-rc2 -> 1.0.0
  %(prog)s set 2.0.0-beta1           Set specific version
"""
    )

    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # show command
    subparsers.add_parser("show", help="Show current version")

    # bump command
    bump_parser = subparsers.add_parser("bump", help="Bump version")
    bump_parser.add_argument(
        "type",
        choices=["major", "minor", "patch", "prerelease"],
        help="Version component to bump"
    )

    # prerelease command
    pre_parser = subparsers.add_parser("prerelease", help="Set pre-release tag")
    pre_parser.add_argument("tag", help="Pre-release tag (alpha, beta, rc)")
    pre_parser.add_argument("num", type=int, nargs="?", help="Pre-release number")

    # promote command
    subparsers.add_parser("promote", help="Remove pre-release tag")

    # set command
    set_parser = subparsers.add_parser("set", help="Set specific version")
    set_parser.add_argument("version", help="Version string (e.g., 2.0.0-beta1)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    manager = VersionManager(args.root)

    if args.command == "show":
        version = manager.get_current_version()
        if args.json:
            print(json.dumps({
                "version": str(version) if version else None,
                "major": version.major if version else None,
                "minor": version.minor if version else None,
                "patch": version.patch if version else None,
                "prerelease": version.prerelease if version else None,
                "prerelease_num": version.prerelease_num if version else None,
                "is_prerelease": version.is_prerelease if version else None,
            }))
        else:
            print(f"Current version: {version}")

    elif args.command == "bump":
        old, new = manager.bump(args.type)
        if args.json:
            print(json.dumps({"old": str(old), "new": str(new)}))
        else:
            print(f"Bumped {args.type}: {old} -> {new}")

    elif args.command == "prerelease":
        old, new = manager.set_prerelease(args.tag, args.num)
        if args.json:
            print(json.dumps({"old": str(old), "new": str(new)}))
        else:
            print(f"Set pre-release: {old} -> {new}")

    elif args.command == "promote":
        old, new = manager.promote()
        if args.json:
            print(json.dumps({"old": str(old), "new": str(new)}))
        else:
            print(f"Promoted: {old} -> {new}")

    elif args.command == "set":
        try:
            version = SemanticVersion.parse(args.version)
            current = manager.get_current_version()
            results = manager.set_version(version)

            if args.json:
                print(json.dumps({
                    "old": str(current) if current else None,
                    "new": str(version),
                    "files": results
                }))
            else:
                print(f"Set version: {current} -> {version}")
                for file, success in results.items():
                    status = "updated" if success else "skipped"
                    print(f"  {file}: {status}")

        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
