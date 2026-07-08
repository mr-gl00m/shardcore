"""Shared helpers for building synthetic .shard bundles in tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


def _dump(obj: Any) -> bytes:
    return json.dumps(obj, indent=2).encode("utf-8")


def build_shard(
    path: Path,
    pillars: dict[str, Any],
    manifest: dict[str, Any],
    *,
    corrupt: str | None = None,
    schemas: dict[str, str] | None = None,
    list_files: bool = True,
) -> Path:
    """Write a valid .shard ZIP with a manifest whose hashes match the members.

    corrupt names a pillar whose manifest hash is deliberately wrong.
    schemas maps a pillar filename to a schema id recorded in manifest.files.
    """
    raw = {name: _dump(obj) for name, obj in pillars.items()}
    files: dict[str, Any] = {}
    for name, data in raw.items():
        entry: dict[str, Any] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        if schemas and name in schemas:
            entry["schema"] = schemas[name]
        files[name] = entry
    if corrupt and corrupt in files:
        files[corrupt]["sha256"] = "0" * 64

    full_manifest = dict(manifest)
    if list_files:
        full_manifest["files"] = files

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _dump(full_manifest))
        for name, data in raw.items():
            archive.writestr(name, data)
    return path


CANONICAL_STAT_BLOCK = {
    "STR": 5,
    "END": 5,
    "VIG": 5,
    "DEX": 5,
    "TMP": 5,
    "ACU": 5,
    "INS": 5,
    "ATT": 5,
    "CNV": 5,
    "PRS": 5,
}


def current_bundle(path: Path) -> Path:
    """A bundle already at the target format: produces zero findings."""
    return build_shard(
        path,
        pillars={
            "soulshard.json": {
                "name": "Test One",
                "version": "2.1",
                "stat_block": dict(CANONICAL_STAT_BLOCK),
            },
            "shellshard.json": {"anatomy_profile": {"template": "humanoid"}},
            "mindshard.json": {
                "format_version": "2.1",
                "short_term": {"slots": []},
                "long_term": {"slots": []},
                "core": [],
            },
        },
        manifest={
            "spec_version": "1.9",
            "bundle_version": "1.9",
            "shard_name": "Test One",
            "created": "2026-07-03T14:00:00Z",
            "last_modified": "2026-07-03T14:00:00Z",
        },
        schemas={
            "soulshard.json": "shardcore/soul@1.9",
            "shellshard.json": "shardcore/shell@1.9",
            "mindshard.json": "shardcore/mind@2.1",
        },
    )
