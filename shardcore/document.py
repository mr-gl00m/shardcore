"""Strict, verified, in-memory access to SHARDCORE bundle members."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

from .bundle import MAX_BUNDLE_BYTES, read_bundle
from .lineage import manifest_digest
from .model import BundleState

MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SPEC_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+$")


class BundleReadError(ValueError):
    """A bundle cannot be exposed as a verified runtime document."""

    def __init__(self, code: str, message: str, *, member: str | None = None):
        super().__init__(message)
        self.code = code
        self.member = member


@dataclass(frozen=True)
class BundleDocument:
    """Verified member bytes and parsed manifest for one bundle."""

    path: Path
    state: BundleState
    manifest_sha256: str
    _manifest_bytes: bytes
    _members: Mapping[str, bytes]

    @property
    def member_names(self) -> tuple[str, ...]:
        return tuple(self._members)

    def manifest(self) -> dict[str, Any]:
        document = _parse_json(self._manifest_bytes, "manifest.json")
        if not isinstance(document, dict):
            raise BundleReadError("manifest_type", "manifest.json is not a JSON object")
        return document

    def member_bytes(self, name: str) -> bytes:
        try:
            return self._members[name]
        except KeyError as exc:
            raise KeyError(f"bundle member was not retained: {name}") from exc

    def json_member(self, name: str) -> Any:
        return _parse_json(self.member_bytes(name), name)


def validate_member_name(name: str) -> None:
    """Reject names that are ambiguous, absolute, or unsafe as archive paths."""
    if not name or "\x00" in name or "\\" in name:
        raise BundleReadError("invalid_member_name", f"invalid archive member name: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or name.startswith("/") or name.endswith("/"):
        raise BundleReadError("invalid_member_name", f"invalid archive member name: {name!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise BundleReadError("invalid_member_name", f"invalid archive member name: {name!r}")
    if path.as_posix() != name:
        raise BundleReadError("invalid_member_name", f"non-canonical member name: {name!r}")


def read_bundle_document(
    path: str | Path,
    members: Iterable[str] | None = None,
    *,
    max_bundle_bytes: int = MAX_BUNDLE_BYTES,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_total_uncompressed_bytes: int = MAX_TOTAL_UNCOMPRESSED_BYTES,
    reject_undeclared: bool = True,
    require_schemas: bool = True,
    validate_json: bool = True,
) -> BundleDocument:
    """Read and verify a bundle, retaining requested members in memory.

    Every declared member is read and verified even when ``members`` selects a
    smaller retained set. Nothing is extracted to the filesystem.
    """
    bundle_path = Path(path)
    try:
        bundle_size = bundle_path.stat().st_size
    except OSError as exc:
        raise BundleReadError("cannot_stat", f"cannot stat bundle: {exc}") from exc
    if bundle_size > max_bundle_bytes:
        raise BundleReadError("bundle_size", "bundle exceeds compressed size cap")

    requested = None if members is None else tuple(members)
    if requested is not None:
        for name in requested:
            validate_member_name(name)

    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            names = [info.filename for info in infos]
            duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
            if duplicates:
                raise BundleReadError(
                    "duplicate_member",
                    f"duplicate archive member name: {duplicates[0]!r}",
                    member=duplicates[0],
                )
            for name in names:
                validate_member_name(name)
            oversized = next((info for info in infos if info.file_size > max_member_bytes), None)
            if oversized is not None:
                raise BundleReadError(
                    "member_size",
                    f"archive member exceeds size cap: {oversized.filename!r}",
                    member=oversized.filename,
                )
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > max_total_uncompressed_bytes:
                raise BundleReadError(
                    "total_size",
                    "archive exceeds total uncompressed size cap",
                )
            raw = {info.filename: archive.read(info) for info in infos}
    except BundleReadError:
        raise
    except zipfile.BadZipFile as exc:
        raise BundleReadError("bad_zip", "bundle is not a valid ZIP archive") from exc
    except (OSError, RuntimeError, zipfile.LargeZipFile) as exc:
        raise BundleReadError("cannot_read", f"cannot read bundle: {exc}") from exc

    manifest_bytes = raw.get("manifest.json")
    if manifest_bytes is None:
        raise BundleReadError("missing_manifest", "bundle has no manifest.json")
    manifest = _parse_json(manifest_bytes, "manifest.json")
    if not isinstance(manifest, dict):
        raise BundleReadError("manifest_type", "manifest.json is not a JSON object")
    spec_version = manifest.get("spec_version")
    if not isinstance(spec_version, str) or SPEC_VERSION_PATTERN.fullmatch(spec_version) is None:
        raise BundleReadError("spec_version", "manifest.spec_version is missing or invalid")
    shard_name = manifest.get("shard_name")
    if not isinstance(shard_name, str) or not shard_name.strip():
        raise BundleReadError("shard_name", "manifest.shard_name is missing or empty")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise BundleReadError("files_type", "manifest.files is not a JSON object")
    if "manifest.json" in files:
        raise BundleReadError("manifest_self_listed", "manifest.json cannot list itself")

    actual_names = set(raw) - {"manifest.json"}
    declared_names = set(files)
    missing = sorted(declared_names - actual_names)
    if missing:
        raise BundleReadError(
            "missing_member",
            f"manifest lists an absent member: {missing[0]!r}",
            member=missing[0],
        )
    undeclared = sorted(actual_names - declared_names)
    if reject_undeclared and undeclared:
        raise BundleReadError(
            "undeclared_member",
            f"archive contains an undeclared member: {undeclared[0]!r}",
            member=undeclared[0],
        )
    if "soulshard.json" not in declared_names:
        raise BundleReadError("missing_soul", "manifest does not list soulshard.json")

    for name, entry in files.items():
        validate_member_name(name)
        if not isinstance(entry, dict):
            raise BundleReadError(
                "file_entry_type",
                f"manifest file entry is not an object: {name!r}",
                member=name,
            )
        declared_sha256 = entry.get("sha256")
        if (
            not isinstance(declared_sha256, str)
            or SHA256_PATTERN.fullmatch(declared_sha256) is None
        ):
            raise BundleReadError(
                "file_hash",
                f"manifest file entry has an invalid SHA-256: {name!r}",
                member=name,
            )
        declared_size = entry.get("size")
        if (
            not isinstance(declared_size, int)
            or isinstance(declared_size, bool)
            or declared_size < 0
        ):
            raise BundleReadError(
                "file_size",
                f"manifest file entry has an invalid size: {name!r}",
                member=name,
            )
        schema = entry.get("schema")
        if require_schemas and (not isinstance(schema, str) or not schema.strip()):
            raise BundleReadError(
                "file_schema",
                f"manifest file entry has no schema: {name!r}",
                member=name,
            )
        data = raw[name]
        if len(data) != declared_size:
            raise BundleReadError(
                "size_mismatch",
                f"member size does not match manifest: {name!r}",
                member=name,
            )
        if hashlib.sha256(data).hexdigest() != declared_sha256:
            raise BundleReadError(
                "hash_mismatch",
                f"member SHA-256 does not match manifest: {name!r}",
                member=name,
            )
        if validate_json and name.endswith(".json"):
            _parse_json(data, name)

    retained_names = tuple(sorted(actual_names)) if requested is None else requested
    absent_requested = [name for name in retained_names if name not in actual_names]
    if absent_requested:
        raise BundleReadError(
            "requested_member_missing",
            f"requested member is absent: {absent_requested[0]!r}",
            member=absent_requested[0],
        )
    retained = MappingProxyType({name: raw[name] for name in retained_names})
    state = read_bundle(bundle_path)
    if not state.readable or not state.integrity_ok:
        raise BundleReadError(
            "reference_verification",
            state.error or "reference reader did not accept bundle integrity",
        )
    return BundleDocument(
        path=bundle_path,
        state=state,
        manifest_sha256=manifest_digest(manifest),
        _manifest_bytes=manifest_bytes,
        _members=retained,
    )


def _parse_json(data: bytes, name: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BundleReadError(
            "json_encoding",
            f"JSON member is not strict UTF-8: {name!r}",
            member=name,
        ) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BundleReadError(
            "json_syntax",
            f"JSON member is invalid: {name!r}: {exc}",
            member=name,
        ) from exc
