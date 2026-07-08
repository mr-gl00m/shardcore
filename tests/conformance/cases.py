"""Reference conformance suite for SHARDCORE v1.9 (spec section 13).

Self-contained on purpose: no pytest, no conftest, stdlib only, so a foreign
runtime can consume the fixtures without this repo's test harness. Each case
names a fixture bundle, how to build it deterministically, and what a
conformant reader must conclude about it.

Emit the fixtures as .shard files for another runtime with:

    python tests/conformance/emit.py <outdir>
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SPEC_VERSION = "1.9"

# Fixed timestamp so fixture bytes are reproducible run to run.
STAMP = "2026-07-06T00:00:00Z"

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

TIERED_MIND = {
    "format_version": "2.1",
    "short_term": {"slots": []},
    "long_term": {"slots": []},
    "core": [],
    "archive": [],
}


def _dump(obj: Any) -> bytes:
    return json.dumps(obj, indent=2, sort_keys=True).encode("utf-8")


def _soul(name: str, **extra: Any) -> dict[str, Any]:
    soul: dict[str, Any] = {
        "name": name,
        "identity": f"{name} is a conformance fixture.",
        "personality": "Deterministic.",
        "stat_block": dict(CANONICAL_STAT_BLOCK),
    }
    soul.update(extra)
    return soul


def _bundle(
    path: Path,
    pillars: dict[str, Any],
    manifest: dict[str, Any],
    schemas: dict[str, str] | None = None,
    corrupt: str | None = None,
    list_form_files: bool = False,
) -> Path:
    """Write a .shard whose manifest hashes match its members (unless corrupt)."""
    raw = {name: (obj if isinstance(obj, bytes) else _dump(obj)) for name, obj in pillars.items()}
    full = dict(manifest)
    if list_form_files:
        full["files"] = sorted(raw)
    else:
        files: dict[str, Any] = {}
        for name, data in raw.items():
            entry: dict[str, Any] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            if schemas and name in schemas:
                entry["schema"] = schemas[name]
            files[name] = entry
        if corrupt and corrupt in files:
            files[corrupt]["sha256"] = "0" * 64
        full["files"] = files
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _dump(full))
        for name, data in raw.items():
            archive.writestr(name, data)
    return path


def _v19_manifest(name: str, **extra: Any) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "spec_version": SPEC_VERSION,
        "bundle_version": SPEC_VERSION,
        "shard_name": name,
        "created": STAMP,
        "last_modified_utc": STAMP,
    }
    manifest.update(extra)
    return manifest


@dataclass(frozen=True)
class Case:
    """One fixture plus what a conformant reader must conclude about it."""

    name: str
    description: str
    build: Callable[[Path], Path]
    readable: bool = True
    status: str | None = None  # "current" | "outdated" | "blocked" | None = don't assert
    codes_include: frozenset[str] = frozenset()
    codes_exclude: frozenset[str] = frozenset()
    findings_empty: bool = False


# ---- valid bundles ---------------------------------------------------------


def _valid_minimal(path: Path) -> Path:
    return _bundle(
        path,
        pillars={"soulshard.json": _soul("Minimal")},
        manifest=_v19_manifest("Minimal"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def _valid_companion(path: Path) -> Path:
    return _bundle(
        path,
        pillars={
            "soulshard.json": _soul("Companion"),
            "shellshard.json": {"anatomy_profile": {"template": "humanoid"}},
            "mindshard.json": dict(TIERED_MIND),
        },
        manifest=_v19_manifest("Companion", conformance={"profile": "companion", "min_tier": "M"}),
        schemas={
            "soulshard.json": "shardcore/soul@1.9",
            "shellshard.json": "shardcore/shell@1.9",
            "mindshard.json": "shardcore/mind@2.1",
        },
    )


def _valid_npc_structured(path: Path) -> Path:
    mind = dict(TIERED_MIND)
    mind["structured"] = {
        "grudge/npc_profile@1.0": {
            "vectors": {"stealth_vs_aggression": 0.72},
            "flags": {"counter_smoke_active": True},
            "counters": {"smoke_grenades_used": 14},
            "updated_utc": STAMP,
        }
    }
    return _bundle(
        path,
        pillars={
            "soulshard.json": _soul("Sentry"),
            "mindshard.json": mind,
            "statshard.json": {"systems": {}},
        },
        manifest=_v19_manifest("Sentry", conformance={"profile": "npc", "min_tier": "S"}),
        schemas={
            "soulshard.json": "shardcore/soul@1.9",
            "mindshard.json": "shardcore/mind@2.1",
            "statshard.json": "shardcore/stat@1.0",
        },
    )


def _valid_x_foreign(path: Path) -> Path:
    # An unowned x_* namespace must not be treated as drift; readers preserve it.
    return _bundle(
        path,
        pillars={
            "soulshard.json": _soul("Foreign", x_acme={"private_state": {"k": 1}}),
            "mindshard.json": dict(TIERED_MIND),
        },
        manifest=_v19_manifest("Foreign"),
        schemas={"soulshard.json": "shardcore/soul@1.9", "mindshard.json": "shardcore/mind@2.1"},
    )


def _valid_with_assets(path: Path) -> Path:
    # A member under assets/ carrying the one asset schema is valid, not drift.
    return _bundle(
        path,
        pillars={
            "soulshard.json": _soul("Portrait"),
            "mindshard.json": dict(TIERED_MIND),
            "assets/images/portrait.png": b"\x89PNG\r\n\x1a\n fake image bytes",
        },
        manifest=_v19_manifest("Portrait"),
        schemas={
            "soulshard.json": "shardcore/soul@1.9",
            "mindshard.json": "shardcore/mind@2.1",
            "assets/images/portrait.png": "shardcore/assets@1.0",
        },
    )


# ---- legacy (readable, migratable) -----------------------------------------


def _legacy_v1_0(path: Path) -> Path:
    return _bundle(
        path,
        pillars={
            "soulshard.json": {"name": "Legacy", "stat_block": dict(CANONICAL_STAT_BLOCK)},
            "memoryshard.json": [{"entry": "flat memory"}],
        },
        manifest={
            "bundle_version": "1.0",
            "shard_name": "Legacy",
            "memory_format": "1.0",
            "created": "2026-03-31T22:39:42.655247",
        },
        list_form_files=True,
    )


def _drift_duplicate_variants(path: Path) -> Path:
    return _bundle(
        path,
        pillars={
            "soulshard.json": _soul("Cluttered"),
            "memoryshard_soulshard_2026.json": dict(TIERED_MIND),
            "soulshard.json.sha256": {"digest": "sidecar"},
            "backups/soulshard_backup_20260221.json": {"name": "old"},
            ".versions/objects/aa/deadbeef.json": {"blob": True},
        },
        manifest=_v19_manifest("Cluttered"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def _drift_no_stat_block(path: Path) -> Path:
    # A soul with no stat_block: outdated, migration stamps the average default.
    return _bundle(
        path,
        pillars={
            "soulshard.json": {"name": "Blank", "identity": "No stats yet.", "personality": "Flat."}
        },
        manifest=_v19_manifest("Blank"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def _drift_asset_no_schema(path: Path) -> Path:
    # An assets/ member listed without a schema id is drift: assets/ maps.
    return _bundle(
        path,
        pillars={
            "soulshard.json": _soul("Unschemed"),
            "assets/images/portrait.png": b"\x89PNG\r\n\x1a\n fake",
        },
        manifest=_v19_manifest("Unschemed"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def _drift_legacy_asset_layout(path: Path) -> Path:
    # A schemed image still in the legacy top-level images/ folder: 0014 moves it.
    return _bundle(
        path,
        pillars={
            "soulshard.json": _soul("Scattered"),
            "images/portrait.png": b"\x89PNG\r\n\x1a\n fake",
        },
        manifest=_v19_manifest("Scattered"),
        schemas={
            "soulshard.json": "shardcore/soul@1.9",
            "images/portrait.png": "shardcore/assets@1.0",
        },
    )


def _drift_resonance(path: Path) -> Path:
    block = dict(CANONICAL_STAT_BLOCK)
    block["Resonance"] = "Champagne Fizz"
    return _bundle(
        path,
        pillars={"soulshard.json": _soul("Fizzy", stat_block=block)},
        manifest=_v19_manifest("Fizzy"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


# ---- malformed (must reject or block) --------------------------------------


def _malformed_bad_digest(path: Path) -> Path:
    return _bundle(
        path,
        pillars={"soulshard.json": _soul("Corrupt")},
        manifest=_v19_manifest("Corrupt"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
        corrupt="soulshard.json",
    )


def _malformed_listed_missing(path: Path) -> Path:
    shard = _bundle(
        path,
        pillars={"soulshard.json": _soul("Ghosted")},
        manifest=_v19_manifest("Ghosted"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )
    # Rewrite the manifest to list a member that is not in the archive.
    with zipfile.ZipFile(shard, "r") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        members = {n: archive.read(n) for n in archive.namelist() if n != "manifest.json"}
    manifest["files"]["ghost.json"] = {"sha256": "0" * 64, "size": 2}
    with zipfile.ZipFile(shard, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _dump(manifest))
        for name, data in members.items():
            archive.writestr(name, data)
    return shard


def _malformed_future_major(path: Path) -> Path:
    return _bundle(
        path,
        pillars={"soulshard.json": _soul("Tomorrow")},
        manifest=_v19_manifest("Tomorrow", spec_version="9.0", bundle_version="9.0"),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def _malformed_not_zip(path: Path) -> Path:
    path.write_text("this is not a zip archive", encoding="utf-8")
    return path


def _malformed_no_manifest(path: Path) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("soulshard.json", _dump(_soul("Orphan")))
    return path


def _immutable_prime(path: Path) -> Path:
    return _bundle(
        path,
        pillars={"soulshard.json": _soul("Prime")},
        manifest=_v19_manifest("Prime", immutable=True),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def _safety_zip_slip(path: Path) -> Path:
    # A hostile member path. Readers must not extract it anywhere; in-memory
    # reads are safe by construction, extraction must resolve-and-reject.
    return _bundle(
        path,
        pillars={"soulshard.json": _soul("Hostile"), "../evil.json": {"payload": True}},
        manifest=_v19_manifest("Hostile"),
        schemas={"soulshard.json": "shardcore/soul@1.9", "../evil.json": "shardcore/soul@1.9"},
    )


CASES: tuple[Case, ...] = (
    Case(
        "valid_minimal",
        "manifest + soul only; spec section 1 minimum, fully current",
        _valid_minimal,
        status="current",
        findings_empty=True,
    ),
    Case(
        "valid_companion",
        "companion profile: soul + shell + tiered mind",
        _valid_companion,
        status="current",
        findings_empty=True,
    ),
    Case(
        "valid_npc_structured",
        "npc profile: mindshard.structured block + statshard",
        _valid_npc_structured,
        status="current",
        findings_empty=True,
    ),
    Case(
        "valid_x_foreign",
        "unowned x_acme namespace is preserved, never drift",
        _valid_x_foreign,
        status="current",
        codes_exclude=frozenset({"soul_runtime_extensions"}),
        findings_empty=True,
    ),
    Case(
        "valid_with_assets",
        "member under assets/ carrying shardcore/assets@1.0 is valid, not drift",
        _valid_with_assets,
        status="current",
        findings_empty=True,
    ),
    Case(
        "drift_no_stat_block",
        "soul with no stat_block; migration stamps the average default",
        _drift_no_stat_block,
        status="outdated",
        codes_include=frozenset({"no_stat_block"}),
    ),
    Case(
        "drift_asset_no_schema",
        "assets/ member listed without a schema id; assets/ maps so this is drift",
        _drift_asset_no_schema,
        status="outdated",
        codes_include=frozenset({"no_schema_ids"}),
    ),
    Case(
        "drift_legacy_asset_layout",
        "schemed image still in legacy top-level images/; migration 0014 relocates it",
        _drift_legacy_asset_layout,
        status="outdated",
        codes_include=frozenset({"legacy_asset_layout"}),
    ),
    Case(
        "legacy_v1_0",
        "pre-public bundle: list-form files, memoryshard, flat memory, naive timestamps",
        _legacy_v1_0,
        status="outdated",
        codes_include=frozenset(
            {
                "no_spec_version",
                "legacy_bundle_version",
                "uses_memoryshard",
                "flat_memory",
                "manifest_has_memory_format",
                "no_integrity_data",
                "non_utc_timestamps",
            }
        ),
    ),
    Case(
        "drift_duplicate_variants",
        "mislabeled memory pillar, digest sidecar, embedded backup/version trees",
        _drift_duplicate_variants,
        status="outdated",
        codes_include=frozenset({"duplicate_pillar_variants"}),
    ),
    Case(
        "drift_resonance",
        "legacy Resonance text still inside the ten-stat block",
        _drift_resonance,
        status="outdated",
        codes_include=frozenset({"nonstandard_stat_block"}),
    ),
    Case(
        "malformed_bad_digest",
        "stored bytes disagree with the manifest sha256; must never be silently accepted",
        _malformed_bad_digest,
        status="blocked",
        codes_include=frozenset({"integrity_mismatch"}),
    ),
    Case(
        "malformed_listed_missing",
        "manifest lists a member absent from the archive; load error per spec section 2.3",
        _malformed_listed_missing,
        status="blocked",
        codes_include=frozenset({"integrity_mismatch"}),
    ),
    Case(
        "malformed_future_major",
        "spec_version 9.0; must be rejected on the major-version rule",
        _malformed_future_major,
        status="blocked",
        codes_include=frozenset({"future_spec"}),
    ),
    Case(
        "malformed_not_zip",
        "not a ZIP archive at all",
        _malformed_not_zip,
        readable=False,
        status="blocked",
    ),
    Case(
        "malformed_no_manifest",
        "ZIP with no manifest.json trust root",
        _malformed_no_manifest,
        readable=False,
        status="blocked",
    ),
    Case(
        "immutable_prime",
        "manifest.immutable true; tooling must never write it in place",
        _immutable_prime,
        status="blocked",
        codes_include=frozenset({"immutable"}),
    ),
    Case(
        "safety_zip_slip",
        "hostile ../ member path; reading must not write outside any extraction root",
        _safety_zip_slip,
        # No status assertion: the contract here is only that reading is safe
        # and does not crash. Extraction-based readers must resolve-and-reject.
    ),
)


def emit_all(outdir: Path) -> list[Path]:
    """Write every fixture as <name>.shard plus an expectations.json manifest."""
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    expectations: dict[str, Any] = {"spec_version": SPEC_VERSION, "cases": {}}
    for case in CASES:
        target = outdir / f"{case.name}.shard"
        case.build(target)
        written.append(target)
        expectations["cases"][case.name] = {
            "description": case.description,
            "readable": case.readable,
            "status": case.status,
            "codes_include": sorted(case.codes_include),
            "codes_exclude": sorted(case.codes_exclude),
            "findings_empty": case.findings_empty,
        }
    expectations_path = outdir / "expectations.json"
    expectations_path.write_bytes(_dump(expectations))
    written.append(expectations_path)
    return written
