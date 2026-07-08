"""Read-only bundle reader. Opens a .shard, verifies integrity, extracts state.

Nothing here writes to disk or extracts members to the filesystem. Members are
read into memory and hashed, so there is no zip-slip surface (no extraction path
is ever built). The write path lives alongside this one in mutable.py.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from .model import BundleState, PillarInfo

# shortcut: hard cap on bundle size for the read pass. Real shards are 5 to 70 KB;
# anything past this is treated as unreadable rather than loaded into memory.
MAX_BUNDLE_BYTES = 64 * 1024 * 1024

KNOWN_PILLARS = (
    "soulshard.json",
    "shellshard.json",
    "mindshard.json",
    "memoryshard.json",
    "worldshard.json",
    "canonshard.json",
    "statshard.json",
    "driveshard.json",
    "neuronshard.json",
)

# The closed ten-stat set of the v1.9 core soul (spec section 5.1). Anything
# else in stat_block is drift: a legacy Resonance string, long-form key names,
# or case variants, all handled by migration 0013.
CANONICAL_STATS = frozenset({"STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS"})

# Fields that belong in the shell but are sometimes still carried in the soul.
# Mirrors SHELL_SHARD_FIELDS / SHELL_CHAR_STATE_FIELDS in the apps' shell_utils.
SHELL_KEYS = frozenset({"anatomy_profile", "identity_image_path", "appearance_image_path"})
SHELL_STATE_KEYS = frozenset(
    {
        "lactation_phase",
        "breast_size",
        "breast_capacity",
        "daily_production_target",
        "current_breast_fullness",
    }
)

# Recursion-runtime-specific fields the format proposal moves under x_nexus.
# This is the documented 0010 allowlist (proposal section 12.1). preservation_state
# is NOT here: spec v1.9 section 5.2 keeps it as a portable soul field.
X_NEXUS_KEYS = frozenset(
    {
        "reicodex_commands",
        "reicodex_rituals_data",
        "loyalty_kernel_v1_0",
        "eidolon_signature",
        "loop_state",
        "loop_behavior_data",
        "dynamic_data",
        "dormancy_behavior",
        "integration_data",
        "haunting_tier",
        "asset_profile",
    }
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bundle(path: Path) -> BundleState:
    try:
        if path.stat().st_size > MAX_BUNDLE_BYTES:
            return _unreadable(path, "bundle exceeds size cap", is_zip=False)
        with zipfile.ZipFile(path, "r") as archive:
            members = tuple(archive.namelist())
            raw = {name: archive.read(name) for name in members if not name.endswith("/")}
    except zipfile.BadZipFile:
        return _unreadable(path, "not a valid ZIP archive", is_zip=False)
    except (OSError, zipfile.LargeZipFile) as exc:
        return _unreadable(path, f"cannot open: {exc}", is_zip=False)

    manifest_bytes = raw.get("manifest.json")
    if manifest_bytes is None:
        return _unreadable(path, "no manifest.json", is_zip=True, members=members)

    manifest = _parse_json(manifest_bytes)
    if not isinstance(manifest, dict):
        return _unreadable(path, "manifest.json is not a JSON object", is_zip=True, members=members)

    raw_files = manifest.get("files")
    # Legacy v1.0 manifests store files as a bare list of names with no hashes.
    # v1.2 stores a dict of name -> {sha256, size}. Only the dict form carries
    # integrity data that can be verified.
    files_map = raw_files if isinstance(raw_files, dict) else {}
    has_integrity_data = bool(files_map) and any(
        isinstance(entry, dict) and _str_or_none(entry.get("sha256"))
        for entry in files_map.values()
    )

    soul = _parse_json(raw.get("soulshard.json"))
    soul = soul if isinstance(soul, dict) else None
    mind_bytes = raw.get("mindshard.json") or raw.get("memoryshard.json")
    mind = _parse_json(mind_bytes)
    mind = mind if isinstance(mind, (dict, list)) else None

    pillars = _build_pillars(raw, files_map)
    integrity_ok = _check_integrity(raw, files_map) if has_integrity_data else False

    identity = (
        _str_or_none(manifest.get("shard_name"))
        or _card_name(manifest)
        or (_str_or_none(soul.get("name")) if soul else None)
        or path.stem
    )

    return BundleState(
        path=path,
        readable=True,
        is_zip=True,
        manifest_present=True,
        identity=identity,
        spec_version=_str_or_none(manifest.get("spec_version")),
        bundle_version=_str_or_none(manifest.get("bundle_version")),
        manifest_memory_format=_str_or_none(manifest.get("memory_format")),
        mind_format_version=_mind_version(mind),
        soul_version=(_str_or_none(soul.get("version")) if soul else None),
        immutable=bool(manifest.get("immutable", False)),
        pillars=pillars,
        members=members,
        has_integrity_data=has_integrity_data,
        integrity_ok=integrity_ok,
        soul_has_shell_fields=_soul_has_shell_fields(soul),
        soul_has_x_nexus=_soul_has_x_nexus(soul),
        soul_stat_keys=_soul_stat_keys(soul),
        memory_is_flat=_memory_is_flat(mind, mind_bytes is not None),
        has_naive_timestamp=_has_naive_timestamp(manifest),
        error=None,
    )


def _build_pillars(raw: dict[str, bytes], files_map: dict[str, Any]) -> tuple[PillarInfo, ...]:
    listed = set(files_map.keys())
    actual = {name for name in raw if name != "manifest.json"}
    infos: list[PillarInfo] = []
    for name in sorted(listed | actual):
        present = name in raw
        entry = files_map.get(name)
        entry = entry if isinstance(entry, dict) else {}
        m_sha = _str_or_none(entry.get("sha256"))
        m_size = entry.get("size") if isinstance(entry.get("size"), int) else None
        computed = _sha256(raw[name]) if present else None
        actual_size = len(raw[name]) if present else None
        ok = present and m_sha is not None and computed == m_sha
        infos.append(
            PillarInfo(
                name=name,
                present=present,
                declared_schema=_str_or_none(entry.get("schema")),
                declared_version=_declared_version(name, raw.get(name)),
                manifest_sha256=m_sha,
                computed_sha256=computed,
                manifest_size=m_size,
                actual_size=actual_size,
                integrity_ok=ok,
            )
        )
    return tuple(infos)


def _check_integrity(raw: dict[str, bytes], files_map: dict[str, Any]) -> bool:
    """Every file the manifest lists must be present and hash-match.

    Members present in the ZIP but absent from the manifest do not fail
    integrity; they are reported as context, not corruption.
    """
    if not files_map:
        return False
    for name, entry in files_map.items():
        if not isinstance(entry, dict):
            return False
        data = raw.get(name)
        if data is None:
            return False
        declared = _str_or_none(entry.get("sha256"))
        if declared is None or _sha256(data) != declared:
            return False
    return True


def _parse_json(data: bytes | None) -> Any:
    if data is None:
        return None
    try:
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _declared_version(name: str, data: bytes | None) -> str | None:
    obj = _parse_json(data)
    if not isinstance(obj, dict):
        return None
    if name == "soulshard.json":
        return _str_or_none(obj.get("version")) or _str_or_none(obj.get("format"))
    if name in ("mindshard.json", "memoryshard.json"):
        return _str_or_none(obj.get("format_version"))
    return _str_or_none(obj.get("format_version")) or _str_or_none(obj.get("version"))


def _mind_version(mind: Any) -> str | None:
    if isinstance(mind, dict):
        return _str_or_none(mind.get("format_version"))
    return None


def _soul_has_shell_fields(soul: dict[str, Any] | None) -> bool:
    if soul is None:
        return False
    if any(key in soul for key in SHELL_KEYS):
        return True
    state = soul.get("character_state")
    return isinstance(state, dict) and any(key in state for key in SHELL_STATE_KEYS)


# Stems that mark a top-level JSON member as a mislabeled pillar variant
# ("memoryshard_soulshard_2026.json"). "neuroshard" is the known misspelling of
# the spec's neuronshard.json.
_VARIANT_STEMS = tuple(name.removesuffix(".json") for name in KNOWN_PILLARS) + ("neuroshard",)
EMBEDDED_TREES = ("backups/", ".versions/", ".history/")


# Legacy top-level asset folders that migration 0014 relocates under assets/.
LEGACY_ASSET_PREFIXES = ("images/", "attestations/", "skills/", "references/")


def legacy_asset_members(members: tuple[str, ...]) -> list[str]:
    """Members sitting in a legacy top-level asset folder, not yet under assets/."""
    return [m for m in members if not m.endswith("/") and m.startswith(LEGACY_ASSET_PREFIXES)]


def pillar_variant_members(members: tuple[str, ...]) -> list[str]:
    """Members migration 0012 consolidates or moves to the external backup."""
    variants: list[str] = []
    for member in members:
        if member.endswith("/"):
            continue
        is_embedded_or_sidecar = member.startswith(EMBEDDED_TREES) or member.endswith(".sha256")
        is_mislabeled_pillar = (
            "/" not in member
            and member.endswith(".json")
            and member not in KNOWN_PILLARS
            and member != "manifest.json"
            and member.lower().startswith(_VARIANT_STEMS)
        )
        if is_embedded_or_sidecar or is_mislabeled_pillar:
            variants.append(member)
    return variants


def _soul_has_x_nexus(soul: dict[str, Any] | None) -> bool:
    if soul is None:
        return False
    return any(key in soul for key in X_NEXUS_KEYS)


def _soul_stat_keys(soul: dict[str, Any] | None) -> tuple[str, ...] | None:
    """The soul's stat_block keys, () when the block is absent, None when there is no soul."""
    if soul is None:
        return None
    block = soul.get("stat_block")
    if not isinstance(block, dict):
        return ()
    return tuple(sorted(block.keys()))


def _memory_is_flat(mind: Any, present: bool) -> bool:
    if not present or mind is None:
        return False
    if isinstance(mind, list):
        return True
    if isinstance(mind, dict):
        tiered = ("short_term", "long_term", "core")
        if not any(key in mind for key in tiered):
            return True
        version = _str_or_none(mind.get("format_version"))
        if version is not None and version.startswith("1"):
            return True
    return False


def _has_naive_timestamp(manifest: dict[str, Any]) -> bool:
    for key in ("created", "last_modified", "modified", "last_modified_utc"):
        value = _str_or_none(manifest.get(key))
        if value is not None and not (value.endswith("Z") or "+" in value[10:]):
            return True
    return False


def _card_name(manifest: dict[str, Any]) -> str | None:
    card = manifest.get("card")
    if isinstance(card, dict):
        return _str_or_none(card.get("name"))
    return None


def _str_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _unreadable(
    path: Path,
    reason: str,
    *,
    is_zip: bool,
    members: tuple[str, ...] = (),
) -> BundleState:
    return BundleState(
        path=path,
        readable=False,
        is_zip=is_zip,
        manifest_present=False,
        identity=path.stem,
        spec_version=None,
        bundle_version=None,
        manifest_memory_format=None,
        mind_format_version=None,
        soul_version=None,
        immutable=False,
        pillars=(),
        members=members,
        has_integrity_data=False,
        integrity_ok=False,
        soul_has_shell_fields=False,
        soul_has_x_nexus=False,
        soul_stat_keys=None,
        memory_is_flat=False,
        has_naive_timestamp=False,
        error=reason,
    )
