"""Fresh SHARDCORE bundle construction with atomic verified output."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backup_vault import record_bundle
from .bundle import MAX_BUNDLE_BYTES
from .core import content_spec, version_tuple
from .document import (
    MAX_MEMBER_BYTES,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    BundleDocument,
    BundleReadError,
    read_bundle_document,
    validate_member_name,
)
from .lineage import lineage_errors, lineage_parent_ids, new_shard_id, shard_id_error
from .registry import NEW_SHARD_SPEC, schema_for_member

RESERVED_MANIFEST_FIELDS = frozenset(
    {
        "spec_version",
        "bundle_version",
        "shard_name",
        "shard_id",
        "created",
        "last_modified_utc",
        "immutable",
        "files",
        "memory_format",
        "revision",
    }
)


class BundleBuildError(ValueError):
    """Fresh bundle input cannot produce a conformant verified bundle."""


def json_member_bytes(value: Any) -> bytes:
    """Serialize one JSON member with stable UTF-8 formatting."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BundleBuildError(f"value cannot be serialized as JSON: {exc}") from exc


def build_bundle(
    path: str | Path,
    *,
    shard_name: str,
    members: Mapping[str, bytes],
    schemas: Mapping[str, str] | None = None,
    manifest_fields: Mapping[str, Any] | None = None,
    shard_id: str | None = None,
    created: str | None = None,
    last_modified_utc: str | None = None,
    immutable: bool = False,
    overwrite: bool = False,
    max_bundle_bytes: int = MAX_BUNDLE_BYTES,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_total_uncompressed_bytes: int = MAX_TOTAL_UNCOMPRESSED_BYTES,
) -> BundleDocument:
    """Build a new bundle, verify it, then atomically place it.

    It is stamped NEW_SHARD_SPEC, or later when its members need it.

    A fresh bundle is a new identity, so ``shard_id`` is minted when omitted
    and its revision chain starts at n 1 (spec 11.5). A save of an existing
    state goes through core.pack_bundle, which continues the chain.
    Pass the existing id when rebuilding a bundle that already has one, or a
    fixed id when byte-identical output matters. A ``lineage`` block in
    ``manifest_fields`` is validated (spec 11.4) and must not name the new
    bundle's own id as a parent.
    """
    target = Path(path)
    if not shard_name.strip():
        raise BundleBuildError("shard_name cannot be empty")
    if target.exists() and not overwrite:
        raise BundleBuildError(f"target already exists: {target}")
    if "soulshard.json" not in members:
        raise BundleBuildError("members must include soulshard.json")
    if "manifest.json" in members:
        raise BundleBuildError("manifest.json is created by the builder")

    supplied_schemas = dict(schemas or {})
    unknown_schema_names = sorted(set(supplied_schemas) - set(members))
    if unknown_schema_names:
        raise BundleBuildError(f"schema supplied for an absent member: {unknown_schema_names[0]!r}")

    encoded_members: dict[str, bytes] = {}
    files: dict[str, dict[str, Any]] = {}
    total_uncompressed = 0
    for name, data in members.items():
        try:
            validate_member_name(name)
        except BundleReadError as exc:
            raise BundleBuildError(str(exc)) from exc
        if not isinstance(data, bytes):
            raise BundleBuildError(f"member data must be bytes: {name!r}")
        if len(data) > max_member_bytes:
            raise BundleBuildError(f"member exceeds size cap: {name!r}")
        total_uncompressed += len(data)
        if total_uncompressed > max_total_uncompressed_bytes:
            raise BundleBuildError("members exceed total uncompressed size cap")
        schema = supplied_schemas.get(name) or schema_for_member(name, data)
        if not isinstance(schema, str) or not schema.strip():
            raise BundleBuildError(f"member has no schema id: {name!r}")
        encoded_members[name] = data
        files[name] = {
            "schema": schema,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }

    extra_manifest = dict(manifest_fields or {})
    reserved = sorted(RESERVED_MANIFEST_FIELDS & set(extra_manifest))
    if reserved:
        raise BundleBuildError(f"manifest_fields contains reserved key: {reserved[0]!r}")

    identity = new_shard_id() if shard_id is None else shard_id
    id_problem = shard_id_error(identity)
    if id_problem is not None:
        raise BundleBuildError(id_problem)
    if "lineage" in extra_manifest:
        problems = lineage_errors(extra_manifest["lineage"])
        if problems:
            raise BundleBuildError(f"invalid lineage: {problems[0]}")
        if identity in lineage_parent_ids(extra_manifest["lineage"]):
            raise BundleBuildError(
                "shard_id reuses a parent's shard_id; a new identity needs its own"
            )

    created_value = created or _utc_now()
    modified_value = last_modified_utc or created_value
    _validate_utc(created_value, "created")
    _validate_utc(modified_value, "last_modified_utc")
    spec = max(NEW_SHARD_SPEC, content_spec(encoded_members), key=version_tuple)
    manifest: dict[str, Any] = dict(extra_manifest)
    manifest.update(
        {
            "spec_version": spec,
            "bundle_version": spec,
            "created": created_value,
            "last_modified_utc": modified_value,
            "shard_name": shard_name,
            "shard_id": identity,
            "immutable": immutable,
            "revision": {"n": 1},
            "files": files,
        }
    )
    manifest_bytes = json_member_bytes(manifest)
    if len(manifest_bytes) + total_uncompressed > max_total_uncompressed_bytes:
        raise BundleBuildError("manifest and members exceed total uncompressed size cap")

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            _write_member(archive, "manifest.json", manifest_bytes)
            for name in sorted(encoded_members):
                _write_member(archive, name, encoded_members[name])
        if temporary.stat().st_size > max_bundle_bytes:
            raise BundleBuildError("built bundle exceeds compressed size cap")
        read_bundle_document(
            temporary,
            max_bundle_bytes=max_bundle_bytes,
            max_member_bytes=max_member_bytes,
            max_total_uncompressed_bytes=max_total_uncompressed_bytes,
        )
        if target.exists() and not overwrite:
            raise BundleBuildError(f"target appeared during build: {target}")
        if target.exists():
            record_bundle(target, event="replaced")
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    record_bundle(
        target, event="write", members={"manifest.json": manifest_bytes, **encoded_members}
    )
    return read_bundle_document(
        target,
        max_bundle_bytes=max_bundle_bytes,
        max_member_bytes=max_member_bytes,
        max_total_uncompressed_bytes=max_total_uncompressed_bytes,
    )


def _write_member(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, data)


def _validate_utc(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BundleBuildError(f"{field} must be an ISO-8601 UTC timestamp with Z suffix")
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise BundleBuildError(f"{field} is not a valid ISO-8601 timestamp") from exc


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
