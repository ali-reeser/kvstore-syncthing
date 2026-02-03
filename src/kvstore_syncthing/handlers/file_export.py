"""
File Export Handler - Offline/Air-gapped Sync

===============================================================================
PROVENANCE TRACKING
===============================================================================
File: src/kvstore_syncthing/handlers/file_export.py
Created: 2026-02-03
Author: Claude (AI Assistant - claude-opus-4-5-20251101)
Session: claude/kvstore-sync-solution-vPJQI
Type: Core Implementation

Change History:
-------------------------------------------------------------------------------
Date        Author      Type    Description
-------------------------------------------------------------------------------
2026-02-03  Claude/AI   CREATE  File export handler for offline/air-gapped
                                synchronization. Supports JSON, CSV formats
                                with optional compression and encryption.
-------------------------------------------------------------------------------

License: MIT

PURPOSE:
Enables KVStore synchronization for environments without direct network
connectivity. Exports create self-contained, verifiable packages that can
be transferred via secure media and imported on the destination.
===============================================================================
"""

import csv
import gzip
import hashlib
import io
import json
import logging
import os
import shutil
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Optional Encryption Support
# =============================================================================

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class FileExportConfig:
    """Configuration for file export destination"""
    name: str
    export_path: str  # Base directory for exports

    # Format options
    file_format: str = "json"  # json, csv
    compression: str = "gzip"  # none, gzip
    pretty_print: bool = False

    # File options
    file_naming: str = "{collection}_{timestamp}"
    max_file_size_mb: int = 100
    max_records_per_file: int = 50000

    # Include options
    include_schema: bool = True
    include_checksums: bool = True
    include_manifest: bool = True

    # Encryption
    encryption_enabled: bool = False
    encryption_password: Optional[str] = None  # For package encryption

    # Packaging
    create_package: bool = True  # Create tarball with all files
    package_format: str = "tar.gz"  # tar.gz, tar, zip


@dataclass
class ExportPackage:
    """Metadata for an export package"""
    package_id: str
    created_at: str
    source_host: str
    collections: List[Dict[str, Any]]
    files: List[Dict[str, Any]]
    total_records: int
    total_size_bytes: int
    checksum: str
    encrypted: bool = False
    schema_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "created_at": self.created_at,
            "source_host": self.source_host,
            "collections": self.collections,
            "files": self.files,
            "total_records": self.total_records,
            "total_size_bytes": self.total_size_bytes,
            "checksum": self.checksum,
            "encrypted": self.encrypted,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportPackage":
        return cls(**data)


# =============================================================================
# File Export Handler
# =============================================================================

class FileExportHandler:
    """
    Handler for exporting KVStore collections to files.

    Supports:
    - JSON and CSV formats
    - Gzip compression
    - Optional encryption
    - Checksum verification
    - Multi-file exports for large collections
    - Package creation for easy transfer
    """

    def __init__(self, config: FileExportConfig):
        self.config = config
        self._ensure_export_path()

    def _ensure_export_path(self) -> None:
        """Ensure export directory exists"""
        Path(self.config.export_path).mkdir(parents=True, exist_ok=True)

    def _generate_filename(
        self,
        collection: str,
        part_num: Optional[int] = None
    ) -> str:
        """Generate filename based on pattern"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        filename = self.config.file_naming.format(
            collection=collection,
            timestamp=timestamp,
        )

        if part_num is not None:
            filename = f"{filename}_part{part_num:05d}"

        # Add extension
        if self.config.file_format == "json":
            filename += ".json"
        elif self.config.file_format == "csv":
            filename += ".csv"

        # Add compression extension
        if self.config.compression == "gzip":
            filename += ".gz"

        return filename

    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate SHA-256 checksum"""
        return f"sha256:{hashlib.sha256(data).hexdigest()}"

    def _compress_data(self, data: bytes) -> bytes:
        """Compress data if configured"""
        if self.config.compression == "gzip":
            return gzip.compress(data, compresslevel=6)
        return data

    def _decompress_data(self, data: bytes, filename: str) -> bytes:
        """Decompress data based on filename"""
        if filename.endswith(".gz"):
            return gzip.decompress(data)
        return data

    def _encrypt_data(self, data: bytes) -> Tuple[bytes, str]:
        """
        Encrypt data with password.

        Returns:
            Tuple of (encrypted_data, salt_hex)
        """
        if not ENCRYPTION_AVAILABLE:
            raise ImportError(
                "cryptography is required for encryption. "
                "Install: pip install cryptography"
            )

        if not self.config.encryption_password:
            raise ValueError("Encryption password not configured")

        # Generate salt
        salt = os.urandom(16)

        # Derive key from password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(
            kdf.derive(self.config.encryption_password.encode())
        )

        # Encrypt
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data)

        return encrypted, salt.hex()

    def _decrypt_data(self, data: bytes, salt_hex: str, password: str) -> bytes:
        """Decrypt data with password and salt"""
        if not ENCRYPTION_AVAILABLE:
            raise ImportError("cryptography is required for decryption")

        salt = bytes.fromhex(salt_hex)

        # Derive key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

        # Decrypt
        fernet = Fernet(key)
        return fernet.decrypt(data)

    def export_collection(
        self,
        records: List[Dict[str, Any]],
        collection: str,
        app: str,
        owner: str,
        source_host: str = "unknown",
        schema: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Export a collection to files.

        Args:
            records: Records to export
            collection: Collection name
            app: Splunk app
            owner: Splunk owner
            source_host: Source host name
            schema: Optional collection schema

        Returns:
            Tuple of (success, file_paths, export_info)
        """
        import uuid

        export_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Create export directory
        export_dir = Path(self.config.export_path) / f"{collection}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        export_dir.mkdir(parents=True, exist_ok=True)

        files_created = []
        file_infos = []
        total_size = 0

        try:
            # Split records into chunks if needed
            max_records = self.config.max_records_per_file
            chunks = [
                records[i:i + max_records]
                for i in range(0, len(records), max_records)
            ]

            for part_num, chunk in enumerate(chunks, start=1):
                # Generate filename
                filename = self._generate_filename(
                    collection,
                    part_num if len(chunks) > 1 else None
                )
                filepath = export_dir / filename

                # Serialize records
                if self.config.file_format == "json":
                    if self.config.pretty_print:
                        data_str = json.dumps(chunk, indent=2)
                    else:
                        data_str = json.dumps(chunk, separators=(',', ':'))
                    content_type = "application/json"
                else:
                    # CSV format
                    output = io.StringIO()
                    if chunk:
                        # Get all fields from all records
                        all_fields = set()
                        for record in chunk:
                            all_fields.update(record.keys())
                        fields = sorted(all_fields)

                        writer = csv.DictWriter(output, fieldnames=fields)
                        writer.writeheader()
                        writer.writerows(chunk)
                    data_str = output.getvalue()
                    content_type = "text/csv"

                data_bytes = data_str.encode('utf-8')

                # Compress
                data_bytes = self._compress_data(data_bytes)

                # Calculate checksum before encryption
                checksum = self._calculate_checksum(data_bytes)

                # Encrypt if enabled
                salt = None
                if self.config.encryption_enabled:
                    data_bytes, salt = self._encrypt_data(data_bytes)
                    filename += ".enc"
                    filepath = export_dir / filename

                # Write file
                with open(filepath, 'wb') as f:
                    f.write(data_bytes)

                files_created.append(str(filepath))
                file_infos.append({
                    "name": filename,
                    "size_bytes": len(data_bytes),
                    "record_count": len(chunk),
                    "checksum": checksum,
                    "encrypted": self.config.encryption_enabled,
                    "salt": salt,
                    "content_type": content_type,
                })
                total_size += len(data_bytes)

            # Export schema if enabled
            if self.config.include_schema and schema:
                schema_file = export_dir / "schema.json"
                schema_data = json.dumps(schema, indent=2).encode()
                with open(schema_file, 'wb') as f:
                    f.write(schema_data)
                files_created.append(str(schema_file))
                file_infos.append({
                    "name": "schema.json",
                    "size_bytes": len(schema_data),
                    "record_count": 0,
                    "checksum": self._calculate_checksum(schema_data),
                    "encrypted": False,
                    "content_type": "application/json",
                })

            # Create manifest
            manifest = {
                "export_id": export_id,
                "created_at": timestamp_str,
                "source_host": source_host,
                "collection": {
                    "name": collection,
                    "app": app,
                    "owner": owner,
                },
                "files": file_infos,
                "total_records": len(records),
                "total_size_bytes": total_size,
                "format": self.config.file_format,
                "compression": self.config.compression,
                "encrypted": self.config.encryption_enabled,
                "schema_version": "1.0",
            }

            # Calculate manifest checksum
            manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
            manifest["manifest_checksum"] = self._calculate_checksum(manifest_bytes)

            # Write manifest
            manifest_file = export_dir / "manifest.json"
            with open(manifest_file, 'w') as f:
                json.dump(manifest, f, indent=2)
            files_created.append(str(manifest_file))

            # Create import instructions
            instructions = self._generate_import_instructions(manifest)
            instructions_file = export_dir / "IMPORT_INSTRUCTIONS.txt"
            with open(instructions_file, 'w') as f:
                f.write(instructions)
            files_created.append(str(instructions_file))

            # Create package if enabled
            if self.config.create_package:
                package_path = self._create_package(export_dir, collection, timestamp)
                if package_path:
                    files_created.append(package_path)
                    manifest["package_file"] = os.path.basename(package_path)

            logger.info(
                f"Exported {len(records)} records from {collection} "
                f"to {export_dir}"
            )

            return True, files_created, manifest

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False, files_created, {"error": str(e)}

    def _create_package(
        self,
        export_dir: Path,
        collection: str,
        timestamp: datetime
    ) -> Optional[str]:
        """Create a package (tarball) of the export"""
        try:
            package_name = f"{collection}_{timestamp.strftime('%Y%m%d_%H%M%S')}"

            if self.config.package_format == "tar.gz":
                package_path = Path(self.config.export_path) / f"{package_name}.tar.gz"
                with tarfile.open(package_path, "w:gz") as tar:
                    tar.add(export_dir, arcname=package_name)

            elif self.config.package_format == "tar":
                package_path = Path(self.config.export_path) / f"{package_name}.tar"
                with tarfile.open(package_path, "w") as tar:
                    tar.add(export_dir, arcname=package_name)

            elif self.config.package_format == "zip":
                package_path = Path(self.config.export_path) / f"{package_name}.zip"
                shutil.make_archive(
                    str(package_path).replace(".zip", ""),
                    "zip",
                    self.config.export_path,
                    export_dir.name
                )
            else:
                return None

            logger.info(f"Created package: {package_path}")
            return str(package_path)

        except Exception as e:
            logger.error(f"Failed to create package: {e}")
            return None

    def _generate_import_instructions(self, manifest: Dict[str, Any]) -> str:
        """Generate human-readable import instructions"""
        collection = manifest.get("collection", {})

        instructions = f"""
================================================================================
KVSTORE SYNCTHING - EXPORT PACKAGE
================================================================================

Export ID: {manifest.get('export_id')}
Created:   {manifest.get('created_at')}
Source:    {manifest.get('source_host')}

Collection Information:
  Name:  {collection.get('name')}
  App:   {collection.get('app')}
  Owner: {collection.get('owner')}

Records:   {manifest.get('total_records')}
Size:      {manifest.get('total_size_bytes')} bytes
Encrypted: {manifest.get('encrypted')}

================================================================================
IMPORT INSTRUCTIONS
================================================================================

1. Transfer this package to the destination Splunk instance

2. Extract the package (if using tar.gz):
   tar -xzf {collection.get('name')}*.tar.gz

3. Navigate to the KVStore Syncthing app on the destination

4. Go to Configuration > Import

5. Select the manifest.json file or the extracted directory

6. Verify the checksums match before proceeding

7. Select the target collection (or use the original name)

8. Click Import to restore the data

================================================================================
VERIFICATION
================================================================================

Manifest Checksum: {manifest.get('manifest_checksum')}

Files included:
"""
        for f in manifest.get("files", []):
            instructions += f"  - {f['name']}: {f['record_count']} records, checksum {f['checksum']}\n"

        if manifest.get("encrypted"):
            instructions += """
================================================================================
DECRYPTION NOTICE
================================================================================

This export is encrypted. You will need the encryption password that was
used during export to decrypt and import the data.

================================================================================
"""

        return instructions

    def import_from_files(
        self,
        import_path: str,
        password: Optional[str] = None
    ) -> Tuple[bool, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Import collection from exported files.

        Args:
            import_path: Path to manifest.json or export directory
            password: Decryption password if encrypted

        Returns:
            Tuple of (success, records, import_info)
        """
        import_path = Path(import_path)

        # Find manifest
        if import_path.is_file() and import_path.name == "manifest.json":
            manifest_path = import_path
            export_dir = import_path.parent
        elif import_path.is_dir():
            manifest_path = import_path / "manifest.json"
            export_dir = import_path
        else:
            return False, [], {"error": "Invalid import path"}

        if not manifest_path.exists():
            return False, [], {"error": "manifest.json not found"}

        try:
            # Read manifest
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Verify manifest checksum
            manifest_copy = {k: v for k, v in manifest.items() if k != "manifest_checksum"}
            manifest_bytes = json.dumps(manifest_copy, sort_keys=True).encode()
            expected_checksum = manifest.get("manifest_checksum")
            actual_checksum = self._calculate_checksum(manifest_bytes)

            if expected_checksum and expected_checksum != actual_checksum:
                return False, [], {"error": "Manifest checksum mismatch"}

            # Check if encrypted
            if manifest.get("encrypted") and not password:
                return False, [], {"error": "Export is encrypted, password required"}

            # Import each data file
            all_records = []
            import_errors = []

            for file_info in manifest.get("files", []):
                filename = file_info["name"]

                # Skip non-data files
                if filename in ["schema.json", "manifest.json"]:
                    continue
                if filename.endswith(".txt"):
                    continue

                filepath = export_dir / filename

                if not filepath.exists():
                    import_errors.append(f"File not found: {filename}")
                    continue

                # Read file
                with open(filepath, 'rb') as f:
                    data_bytes = f.read()

                # Decrypt if needed
                if file_info.get("encrypted"):
                    if not password:
                        import_errors.append(f"Cannot decrypt {filename}: no password")
                        continue
                    salt = file_info.get("salt")
                    if not salt:
                        import_errors.append(f"Cannot decrypt {filename}: no salt")
                        continue
                    data_bytes = self._decrypt_data(data_bytes, salt, password)

                # Verify checksum
                if self.config.include_checksums:
                    actual = self._calculate_checksum(data_bytes)
                    expected = file_info.get("checksum")
                    if expected and actual != expected:
                        import_errors.append(f"Checksum mismatch: {filename}")
                        continue

                # Decompress
                data_bytes = self._decompress_data(data_bytes, filename)

                # Parse records
                data_str = data_bytes.decode('utf-8')

                if file_info.get("content_type") == "application/json" or filename.endswith((".json", ".json.gz", ".json.gz.enc")):
                    records = json.loads(data_str)
                else:
                    # CSV
                    reader = csv.DictReader(io.StringIO(data_str))
                    records = list(reader)

                all_records.extend(records)

            # Import info
            import_info = {
                "export_id": manifest.get("export_id"),
                "source_host": manifest.get("source_host"),
                "collection": manifest.get("collection"),
                "records_imported": len(all_records),
                "errors": import_errors,
            }

            if import_errors:
                logger.warning(f"Import completed with errors: {import_errors}")
            else:
                logger.info(f"Imported {len(all_records)} records")

            return len(import_errors) == 0, all_records, import_info

        except Exception as e:
            logger.error(f"Import failed: {e}")
            return False, [], {"error": str(e)}

    def list_exports(self) -> List[Dict[str, Any]]:
        """List available exports in export directory"""
        exports = []
        export_path = Path(self.config.export_path)

        # Find manifest files
        for manifest_path in export_path.rglob("manifest.json"):
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

                exports.append({
                    "path": str(manifest_path.parent),
                    "export_id": manifest.get("export_id"),
                    "created_at": manifest.get("created_at"),
                    "collection": manifest.get("collection", {}).get("name"),
                    "records": manifest.get("total_records"),
                    "size_bytes": manifest.get("total_size_bytes"),
                    "encrypted": manifest.get("encrypted"),
                })
            except Exception:
                continue

        # Sort by creation time, newest first
        exports.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return exports

    def verify_export(self, export_path: str) -> Tuple[bool, List[str]]:
        """
        Verify integrity of an export.

        Returns:
            Tuple of (all_valid, errors)
        """
        errors = []
        export_path = Path(export_path)

        # Find manifest
        if export_path.is_file():
            manifest_path = export_path
            export_dir = export_path.parent
        else:
            manifest_path = export_path / "manifest.json"
            export_dir = export_path

        if not manifest_path.exists():
            return False, ["manifest.json not found"]

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Verify manifest checksum
            manifest_copy = {k: v for k, v in manifest.items() if k != "manifest_checksum"}
            manifest_bytes = json.dumps(manifest_copy, sort_keys=True).encode()
            expected = manifest.get("manifest_checksum")
            actual = self._calculate_checksum(manifest_bytes)

            if expected and expected != actual:
                errors.append("Manifest checksum mismatch")

            # Verify each file
            for file_info in manifest.get("files", []):
                filename = file_info["name"]
                filepath = export_dir / filename

                if not filepath.exists():
                    errors.append(f"Missing file: {filename}")
                    continue

                with open(filepath, 'rb') as f:
                    data = f.read()

                expected_checksum = file_info.get("checksum")
                actual_checksum = self._calculate_checksum(data)

                if expected_checksum and expected_checksum != actual_checksum:
                    errors.append(f"Checksum mismatch: {filename}")

            return len(errors) == 0, errors

        except Exception as e:
            return False, [str(e)]

    def cleanup_old_exports(self, days: int = 30) -> int:
        """
        Remove exports older than specified days.

        Returns:
            Number of exports removed
        """
        import datetime as dt

        removed = 0
        cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
        export_path = Path(self.config.export_path)

        for item in export_path.iterdir():
            if not item.is_dir():
                continue

            manifest_path = item / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

                created_str = manifest.get("created_at", "")
                if created_str:
                    created = dt.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    if created.replace(tzinfo=None) < cutoff:
                        shutil.rmtree(item)
                        removed += 1
                        logger.info(f"Removed old export: {item}")

            except Exception as e:
                logger.warning(f"Error processing {item}: {e}")

        return removed
