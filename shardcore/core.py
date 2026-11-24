"""shardcore core: the one implementation of SHARDCORE v1.x bundle I/O.

This file is shardcore/core.py inside the shardcore package, and it is the
source of truth: the package's registry, lineage, backup vault, migrations and
reader import their constants and shared transforms from here instead of
keeping their own copies. It is also vendored (copied verbatim) into every app
that reads or writes .shard bundles, so all writers emit the same manifest
shape and all readers make the same trust decisions. Edit only this copy, then
run

    uv run python tools/ecosystem/ecosystem.py sync     (from shardcore)

to update every consumer listed in WORKSPACE.toml. `ecosystem.py check` fails
while any copy differs from this one. stdlib only, no third-party deps, no
imports from the rest of the package, so one file is the whole vendorable unit.

shortcut: the apps vendor it under its v1.9-era name, shardcore_v19.py, so their
imports stay put. Rename the copies (shardcore_v1.py) the next time every copy
moves together, or retire them once the apps import shardcore itself.

What a written bundle holds (spec sections 2.1-2.3, 5.1-5.5, 6, 11.4, 11.5):
  - manifest.spec_version is the version the shard already declared; a new shard
    gets NEW_SHARD_SPEC. bundle_version (deprecated alias) is the same. Raising
    it is a separate act (upgrade_to), never a side effect of a save
  - NO manifest.memory_format (the mind pillar self-describes via format_version)
  - every files entry carries {schema, sha256, size}; a save keeps declared ids
  - timestamps are ISO-8601 UTC with a trailing Z (created, last_modified_utc)
  - soul.stat_block is exactly the closed ten stats; Resonance lives at soul.resonance
  - recognized runtime fields nest under soul.x_nexus
  - static assets live under assets/
  - manifest.shard_id survives every save; a bundle without one gets one minted,
    whatever its version: an id left to be derived changes with every save
  - a branch gets a new shard_id and a lineage block pinning its parent
  - manifest.revision orders the states of one identity: every write is the
    prior state's n plus 1 and pins it; a new identity starts at n 1. A bundle
    declared before 1.11 has no chain and is given none
  - a shell anatomy_profile holds its parts as a map keyed by part id
  - a bundle newer than SPEC_VERSION is rewritten only when its min_writer allows
    this writer, and then keeps its version, ids and everything unknown here

Typical writer flow:

    members = {"soulshard.json": soul_bytes, "mindshard.json": mind_bytes}
    manifest = build_manifest(members, soul=soul_dict, prior_manifest=old_manifest)
    pack_bundle(path, members, soul=soul_dict, prior_manifest=old_manifest)

Typical reader flow:

    check_spec_major(manifest)               # reject a higher major
    verify_members(raw, manifest["files"])   # every listed member present + hash-match

Two copies of one identity (spec 11.5):

    compare_revisions(a_manifest, b_manifest)   # same, a_newer, b_newer, diverged, unknown
    result = merge_bundles(ours_path, theirs_path)   # base state from the backup vault
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import uuid
import zipfile
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeGuard

__all__ = [
    "SPEC_VERSION",
    "NEW_SHARD_SPEC",
    "OLDEST_KEPT_SPEC",
    "SUPPORTED_MAJOR",
    "MIND_FORMAT_VERSION",
    "CANONICAL_STATS",
    "DEFAULT_STAT",
    "STAT_LONG_FORMS",
    "SHELL_KEYS",
    "SHELL_STATE_KEYS",
    "X_NEXUS_KEYS",
    "ASSETS_SCHEMA",
    "PILLAR_SCHEMAS",
    "NEURON_SCHEMAS",
    "LEGACY_ASSET_PREFIXES",
    "IDENTITY_NAMESPACE",
    "BRANCH_RELATIONSHIPS",
    "MAX_SHARD_ID_LENGTH",
    "SHA256_HEX",
    "ShardError",
    "ShardIntegrityError",
    "FutureSpecError",
    "NewerSpecError",
    "UpgradeNeededError",
    "ImmutableShardError",
    "schema_for_member",
    "kept_spec",
    "content_spec",
    "min_writer",
    "read_manifest",
    "utc_now",
    "to_utc_z",
    "normalize_stat_block",
    "renest_x_nexus",
    "read_x_nexus_field",
    "prepare_soul_for_write",
    "tiered_mind",
    "ensure_tiered_mind",
    "build_card",
    "build_files_info",
    "canonical_json_bytes",
    "manifest_digest",
    "new_shard_id",
    "derived_shard_id",
    "shard_id_error",
    "mint_shard_id",
    "branch_manifest",
    "REVISION_HISTORY_MAX",
    "REVISION_RELATIONS",
    "revision_errors",
    "revision_history",
    "next_revision",
    "compare_revisions",
    "common_ancestor",
    "ANATOMY_LIST_KEYS",
    "anatomy_parts_map",
    "build_manifest",
    "pack_bundle",
    "keep_before_upgrade",
    "verify_members",
    "spec_major",
    "check_spec_major",
    "version_tuple",
    "check_spec_writable",
    "is_immutable",
    "assert_writable",
    "decay_status_effects",
    "BACKUP_VAULT_ENV",
    "backup_vault_dir",
    "record_bundle",
    "read_journal",
    "restore_bundle",
    "load_state",
    "read_bundle_members",
    "merge_members",
    "merge_bundles",
    "write_merge",
]

# --------------------------------------------------------------------------- #
# Versions
# --------------------------------------------------------------------------- #

SPEC_VERSION = "1.12"
# What a new shard is stamped with: the lowest version that covers what writers
# put in one (compatibility RFC section 4).
NEW_SHARD_SPEC = "1.12"
# The oldest form this helper writes. A save of an older shard upgrades it to
# NEW_SHARD_SPEC, as every writer since v1.9 has.
OLDEST_KEPT_SPEC = "1.9"
# The highest spec major this reader understands. A bundle whose spec_version
# major exceeds this must be refused (spec section 1, R2).
SUPPORTED_MAJOR = 1
MIND_FORMAT_VERSION = "2.1"

# --------------------------------------------------------------------------- #
# Soul stat block (spec section 5.1) - the closed ten
# --------------------------------------------------------------------------- #

CANONICAL_STATS: tuple[str, ...] = (
    "STR",
    "END",
    "VIG",
    "DEX",
    "TMP",
    "ACU",
    "INS",
    "ATT",
    "CNV",
    "PRS",
)
_CANONICAL_SET = frozenset(CANONICAL_STATS)

# Average default when a soul has no stat_block at all (spec 5.1). Matches the
# conformance suite's CANONICAL_STAT_BLOCK value.
DEFAULT_STAT = 5

# Long-form and case-variant stat keys fold onto the canonical abbreviations.
STAT_LONG_FORMS = {
    "STRENGTH": "STR",
    "ENDURANCE": "END",
    "VIGOR": "VIG",
    "DEXTERITY": "DEX",
    "TEMPERAMENT": "TMP",
    "ACUMEN": "ACU",
    "INSIGHT": "INS",
    "ATTUNEMENT": "ATT",
    "CONVICTION": "CNV",
    "PRESENCE": "PRS",
}

# --------------------------------------------------------------------------- #
# Shell split (spec section 5.3) - fields that belong in shellshard, not soul
# --------------------------------------------------------------------------- #

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

# --------------------------------------------------------------------------- #
# x_nexus (spec section 5.5) - the recognized runtime-extension fields shared
# across the Nexus runtimes.
# App-private state that is NOT one of these keys belongs under the app's own
# x_<vendor> namespace, which the app manages itself. preservation_state is
# deliberately NOT here: v1.9 section 5.2 keeps it a portable soul field.
# --------------------------------------------------------------------------- #

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

# --------------------------------------------------------------------------- #
# Schema-id registry (spec PART III)
# --------------------------------------------------------------------------- #

ASSETS_SCHEMA = "shardcore/assets@1.0"

PILLAR_SCHEMAS: dict[str, str] = {
    "soulshard.json": "shardcore/soul@1.9",
    "shellshard.json": "shardcore/shell@1.12",
    "mindshard.json": "shardcore/mind@2.1",
    "memoryshard.json": "shardcore/mind@2.1",
    "neuronshard.json": "shardcore/neuron@1.1",
    "canonshard.json": "shardcore/canon@1.0",
    "statshard.json": "shardcore/stat@1.0",
    "driveshard.json": "shardcore/drive@0.1",
    "worldshard.json": "shardcore/world@1.0",
}

_PREFIX_SCHEMAS: tuple[tuple[str, str], ...] = (
    ("body/", "shardcore/body@1.0"),
    ("assets/", ASSETS_SCHEMA),
    # Legacy top-level asset folders, still mapped pre-consolidation.
    ("images/", ASSETS_SCHEMA),
    ("attestations/", ASSETS_SCHEMA),
    ("skills/", ASSETS_SCHEMA),
    ("references/", ASSETS_SCHEMA),
)

_ASSET_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".ots",
)

LEGACY_ASSET_PREFIXES = ("images/", "attestations/", "skills/", "references/")


# The neuron pillar is the one whose schema id follows its content: the
# document's own "version" picks the id. PILLAR_SCHEMAS holds the id used when
# the bytes are not at hand or name a version this library does not know.
NEURON_SCHEMAS: dict[str, str] = {
    "1.0": "shardcore/neuron@1.0",
    "1.1": "shardcore/neuron@1.1",
}


# The ids a pillar has carried, newest first with the version each came in: a
# member added to a shard that declares an older version gets that version's id.
_SCHEMAS_SINCE: dict[str, tuple[tuple[tuple[int, ...], str], ...]] = {
    "shellshard.json": (
        ((1, 12), "shardcore/shell@1.12"),
        ((1, 11), "shardcore/shell@1.10"),
        ((1, 9), "shardcore/shell@1.9"),
    ),
    "neuronshard.json": (
        ((1, 12), "shardcore/neuron@1.1"),
        ((1, 9), "shardcore/neuron@1.0"),
    ),
}


def _neuron_schema(data: bytes) -> str | None:
    try:
        document = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return None
    version = document.get("version") if isinstance(document, dict) else None
    return NEURON_SCHEMAS.get(version) if isinstance(version, str) else None


def schema_for_member(name: str, data: bytes | None = None, spec: str | None = None) -> str | None:
    """The schema id for an archive member, or None when unmappable.

    Pass the member's bytes when they are at hand: a neuronshard is stamped by
    the version its document declares (NEURON_SCHEMAS). Pass spec for the id a
    shard of that version carries; the default is the current one.
    """
    if name == "neuronshard.json" and data is not None:
        own = _neuron_schema(data)
        if own is not None:
            return own
    declared = version_tuple(spec)
    if declared is not None:
        for since, schema in _SCHEMAS_SINCE.get(name, ()):
            if declared >= since:
                return schema
    direct = PILLAR_SCHEMAS.get(name)
    if direct is not None:
        return direct
    for prefix, schema in _PREFIX_SCHEMAS:
        if name.startswith(prefix):
            return schema
    if name.lower().endswith(_ASSET_EXTENSIONS):
        return ASSETS_SCHEMA
    return None


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class ShardError(Exception):
    """Base for every shardcore error."""


class ShardIntegrityError(ShardError):
    """A listed member is missing or its bytes disagree with the manifest sha256."""


class FutureSpecError(ShardError):
    """A bundle declares a spec_version major this reader does not support."""


class NewerSpecError(ShardError):
    """A bundle is newer (same major) than this writer may save."""


class UpgradeNeededError(ShardError):
    """The members hold something newer than the version the shard declares.

    Leave it out, or ask and write again with upgrade_to=needed.
    """

    def __init__(self, declared: str, needed: str) -> None:
        super().__init__(
            f"the shard declares spec {declared} and these members need {needed}; "
            f"write without them, or upgrade it (upgrade_to={needed!r})"
        )
        self.declared = declared
        self.needed = needed


class ImmutableShardError(ShardError):
    """An in-place write was attempted against a bundle marked immutable."""


# --------------------------------------------------------------------------- #
# Reading a prior manifest
# --------------------------------------------------------------------------- #


def read_manifest(path: str | os.PathLike[str]) -> dict[str, Any] | None:
    """Read and parse manifest.json from a .shard bundle, or None if absent.

    A convenience for the write path: load the prior manifest so a re-pack can
    preserve created/lineage/vendor keys and detect immutability. Returns None
    on any read/parse failure rather than raising, so a save is never blocked by
    an unreadable prior manifest.
    """
    try:
        with zipfile.ZipFile(os.fspath(path), "r") as archive:
            if "manifest.json" not in archive.namelist():
                return None
            obj = json.loads(archive.read("manifest.json"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #


def utc_now() -> str:
    """Current time as ISO-8601 UTC with a trailing Z: 2026-07-08T12:34:56Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_utc_z(value: Any) -> str | None:
    """Normalize a timestamp (datetime or ISO string) to UTC-with-Z, or None.

    A naive string is assumed local (the only defensible read of a datetime.now()
    stamp written on this machine), matching migration 0007.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        if value.endswith("Z"):
            return value
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Soul normalization (mirrors migrations 0013 and 0010)
# --------------------------------------------------------------------------- #


def _coerce_stat(stat: str, value: Any, notes: list[str], strict: bool) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if strict:
            raise ValueError(f"stat_block.{stat} is not numeric: {value!r}")
        # Unparseable stat: fall back to the average default rather than crash a
        # save. The writer path must never lose a bundle over one bad stat.
        notes.append(f"{stat} non-numeric {value!r}, stamped default {DEFAULT_STAT}")
        return DEFAULT_STAT
    coerced = int(round(value))
    clamped = min(10, max(1, coerced))
    if clamped != value:
        notes.append(f"{stat} {value!r} -> {clamped}")
    return clamped


def normalize_stat_block(soul: dict[str, Any], *, strict: bool = False) -> list[str]:
    """Fold soul.stat_block to the canonical ten stats, in place. Returns notes.

    What migration 0013 runs, and what every write runs:
      - long-form / case-variant keys fold onto the ten abbreviations
      - a Resonance key relocates to soul.resonance (kept as x_nexus.legacy_stats
        only if soul.resonance is already set to a different value)
      - any other unrecognized key is preserved under soul.x_nexus.legacy_stats
      - missing stats are stamped with the average default
      - a soul with no stat_block at all gets the all-default ten
    A non-numeric stat becomes the default on a write; with strict=True (the
    migrator, which never guesses) it raises ValueError instead.
    """
    block = soul.get("stat_block")
    if not isinstance(block, dict) or not block:
        soul["stat_block"] = {stat: DEFAULT_STAT for stat in sorted(CANONICAL_STATS)}
        return [f"no stat_block; stamped average default (all {DEFAULT_STAT})"]

    normalized: dict[str, Any] = {}
    legacy: dict[str, Any] = {}
    notes: list[str] = []
    for key, value in block.items():
        upper = key.upper()
        canonical = upper if upper in _CANONICAL_SET else STAT_LONG_FORMS.get(upper)
        if canonical is not None:
            normalized[canonical] = _coerce_stat(canonical, value, notes, strict)
        elif upper == "RESONANCE":
            if "resonance" in soul and soul["resonance"] != value:
                legacy[key] = value
                notes.append(f"stat_block.{key} kept as legacy (soul.resonance already set)")
            else:
                soul["resonance"] = value
                notes.append(f"relocated {key} to soul.resonance")
        else:
            legacy[key] = value
            notes.append(f"unrecognized stat {key} preserved under x_nexus.legacy_stats")

    for stat in sorted(_CANONICAL_SET - set(normalized)):
        normalized[stat] = DEFAULT_STAT
        notes.append(f"missing stat {stat} stamped {DEFAULT_STAT}")

    soul["stat_block"] = {stat: normalized[stat] for stat in sorted(normalized)}
    if legacy:
        nested = soul.get("x_nexus")
        nested = nested if isinstance(nested, dict) else {}
        legacy_stats = nested.get("legacy_stats")
        legacy_stats = legacy_stats if isinstance(legacy_stats, dict) else {}
        legacy_stats.update(legacy)
        nested["legacy_stats"] = legacy_stats
        soul["x_nexus"] = nested
    return notes


def renest_x_nexus(soul: dict[str, Any]) -> list[str]:
    """Move recognized runtime fields to soul.x_nexus, in place. Returns moved keys.

    Mirrors migration 0010. Top-level wins on collision (it is what the runtime
    was reading). App-private fields outside X_NEXUS_KEYS are untouched; the app
    manages its own x_<vendor> namespace.
    """
    nested = soul.get("x_nexus")
    nested = nested if isinstance(nested, dict) else {}
    moved: list[str] = []
    for key in sorted(X_NEXUS_KEYS):
        if key in soul:
            nested[key] = soul.pop(key)
            moved.append(key)
    if moved:
        soul["x_nexus"] = nested
    return moved


def read_x_nexus_field(soul: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read a runtime field from soul.x_nexus, falling back to the top level.

    The forward-compatible read for any of the X_NEXUS_KEYS: a migrated bundle
    carries them under x_nexus, a pre-migration soul (or loose JSON) still has
    them at the top level.
    """
    nexus = soul.get("x_nexus")
    if isinstance(nexus, Mapping) and key in nexus:
        return nexus[key]
    return soul.get(key, default)


def prepare_soul_for_write(soul: dict[str, Any]) -> dict[str, Any]:
    """Normalize a soul for a v1.x write, in place: stat block + x_nexus re-nest.

    Does NOT split shell fields; that is app-specific (apps own shell_utils).
    Returns the same soul dict for chaining.
    """
    normalize_stat_block(soul)
    renest_x_nexus(soul)
    return soul


# --------------------------------------------------------------------------- #
# Memory pillar (mirrors migration 0003) - never write a bare array at v1.9
# --------------------------------------------------------------------------- #

_FLAT_ENTRY_KEYS = ("memories", "entries", "slots", "log")
_MIND_TIERS = ("short_term", "long_term", "core", "archive")


def tiered_mind(long_term: list[Any]) -> dict[str, Any]:
    """Empty mind@2.1 tiers with long_term holding the given entries (migration 0003)."""
    return {
        "format_version": MIND_FORMAT_VERSION,
        "short_term": {"slots": []},
        "long_term": {"slots": list(long_term)},
        "core": [],
        "archive": [],
    }


def ensure_tiered_mind(mind: Any) -> dict[str, Any]:
    """Return a v1.9 tiered mind@2.1 dict, never a bare array (mirror 0003).

    A flat list becomes long_term slots. An already-tiered dict is passed
    through with format_version stamped to 2.1. A flat dict carrying an entry
    list under a known key is folded, its other keys riding along. An empty or
    None mind becomes empty tiers.
    """
    if mind is None:
        return tiered_mind([])
    if isinstance(mind, list):
        return tiered_mind(mind)
    if not isinstance(mind, dict):
        return tiered_mind([])
    if any(tier in mind for tier in _MIND_TIERS):
        out = dict(mind)
        out["format_version"] = MIND_FORMAT_VERSION
        return out
    for key in _FLAT_ENTRY_KEYS:
        entries = mind.get(key)
        if isinstance(entries, list):
            rest = {k: v for k, v in mind.items() if k not in (key, "format_version")}
            tiered = tiered_mind(entries)
            tiered.update(rest)
            tiered["format_version"] = MIND_FORMAT_VERSION
            return tiered
    # Metadata-only flat dict: no entries to carry, empty tiers plus scalars.
    rest = {k: v for k, v in mind.items() if k != "format_version"}
    tiered = tiered_mind([])
    tiered.update(rest)
    tiered["format_version"] = MIND_FORMAT_VERSION
    return tiered


# --------------------------------------------------------------------------- #
# Shell anatomy (spec section 6): the parts map
# --------------------------------------------------------------------------- #

# The editor list shape an anatomy_profile carried before spec 1.11.
ANATOMY_LIST_KEYS = ("external_parts", "internal_parts", "modifiers", "show_internal")
# Editor placeholders that mean "no value" on a list-shape part.
_ANATOMY_NO_SIZE = ("", "Custom")
_ANATOMY_LIFTED_STATS = ("capacity_ml", "sensitivity")


def _anatomy_part_id(entry: Mapping[str, Any], taken: set[str], strict: bool) -> str:
    part_id = entry.get("id")
    if isinstance(part_id, str) and part_id.strip():
        return part_id
    if strict:
        raise ValueError(f"anatomy part without an id: {entry.get('name')!r}")
    stem = re.sub(r"[^a-z0-9]+", "_", str(entry.get("name") or "part").lower()).strip("_") or "part"
    candidate, n = stem, 2
    while candidate in taken:
        candidate, n = f"{stem}_{n}", n + 1
    return candidate


def _anatomy_map_part(entry: Mapping[str, Any], part_id: str, internal: bool) -> dict[str, Any]:
    part = {k: copy.deepcopy(v) for k, v in entry.items() if k != "stats"}
    part["id"] = part_id
    if part.get("size") in _ANATOMY_NO_SIZE:
        part.pop("size", None)
    if part.get("accessories") == "":
        part.pop("accessories")
    stats = entry.get("stats")
    if isinstance(stats, Mapping):
        rest = {k: copy.deepcopy(v) for k, v in stats.items() if k not in _ANATOMY_LIFTED_STATS}
        for key in _ANATOMY_LIFTED_STATS:
            if key in stats and key not in part:
                part[key] = stats[key]
        if rest:
            part["stats"] = rest
    tags = part.get("tags")
    tags = [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []
    if internal and "internal" not in tags:
        tags.append("internal")
    part["tags"] = tags
    return part


def anatomy_parts_map(shell: dict[str, Any], *, strict: bool = False) -> list[str]:
    """Hold shell.anatomy_profile's parts as the spec 6 map, in place. Returns notes.

    The editor list shape (external_parts and internal_parts, each part
    {id, name, part_type, size, stats, tags, accessories, fluid_type}) becomes
    parts[id]: stats.capacity_ml and stats.sensitivity move onto the part, any
    other stats stay under the part's stats, and a part from internal_parts
    carries the "internal" tag, which is how the editor's split survives. The
    legacy modifiers list is read only when neither list is there; spec 1.10
    writers stored it as a copy of the two. show_internal is a display toggle
    and goes. The editor's "Custom" size and empty accessories mean no value
    and are dropped. Every other anatomy_profile key (template, body_type,
    measurements, ...) rides along.

    A profile that already has a parts map keeps every part in it; a list part
    whose id the map lacks is added. A profile with no parts gets an empty map.
    Returns [] when the profile was already a map with no list keys beside it.
    strict (the migrator, which never guesses): a part without an id, or two
    different parts under one id, raises ValueError; otherwise the first gets an
    id from its name and the second a numbered one.
    """
    profile = shell.get("anatomy_profile")
    if not isinstance(profile, dict):
        return []
    existing = profile.get("parts")
    if isinstance(existing, dict) and not any(key in profile for key in ANATOMY_LIST_KEYS):
        return []
    parts: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    from_map = set(parts)
    lists: list[tuple[Any, bool | None]] = [
        (profile.get("external_parts"), False),
        (profile.get("internal_parts"), True),
    ]
    if not any(isinstance(entries, list) for entries, _ in lists):
        lists = [(profile.get("modifiers"), None)]
    added = 0
    for entries, internal in lists:
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            is_internal = (
                internal if internal is not None else "internal" in (entry.get("tags") or [])
            )
            part_id = _anatomy_part_id(entry, set(parts), strict)
            part = _anatomy_map_part(entry, part_id, bool(is_internal))
            if part_id in parts:
                if part_id in from_map or parts[part_id] == part:
                    continue  # the map's own part wins over a list copy of it
                if strict:
                    raise ValueError(f"two different anatomy parts share the id {part_id!r}")
                part_id = _anatomy_part_id({"name": part_id}, set(parts), False)
                part["id"] = part_id
            parts[part_id] = part
            added += 1
    for key in ANATOMY_LIST_KEYS:
        profile.pop(key, None)
    profile["parts"] = parts
    return [f"anatomy_profile: {added} list part(s) into the parts map, {len(from_map)} kept"]


# --------------------------------------------------------------------------- #
# Body status effects (spec A.5.6): wall-clock decay
# --------------------------------------------------------------------------- #


def _effect_time(value: Any) -> datetime | None:
    """A status-effect timestamp with Z or an explicit offset, else None.

    A naive stamp is rejected: guessing its zone shifts decay by hours.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def decay_status_effects(
    effects: Any, now: datetime | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Decay body status effects to wall time ``now``; return (active, cleared).

    Spec A.5.6.1: level falls by decay_rate_per_hour for every hour since
    applied_at_utc, elapsed clamped at zero (a clock that went backwards decays
    nothing), and an effect clears when its level reaches 0 or ``now`` is at or
    past expires_at_utc. Each active effect comes back rebased, with level as
    of ``now`` and applied_at_utc set to ``now``, so writing it back and
    decaying again later never counts the same hours twice. An effect without
    a usable applied_at_utc is kept unchanged. Both lists are copies; the
    input is not touched. Withdrawal (A.5.6.2) is runtime policy: a cleared
    effect with withdrawal_on_clear is the caller's cue.
    """
    when = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    active: list[dict[str, Any]] = []
    cleared: list[dict[str, Any]] = []
    if not isinstance(effects, list):
        return active, cleared
    for raw in effects:
        if not isinstance(raw, dict):
            continue
        effect = copy.deepcopy(raw)
        applied = _effect_time(effect.get("applied_at_utc"))
        if applied is None:
            active.append(effect)
            continue
        rate = effect.get("decay_rate_per_hour") or 0
        level = effect.get("level") or 0
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            rate = 0
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            level = 0
        elapsed = max(0.0, (when - applied).total_seconds() / 3600.0)
        current = float(level) - float(rate) * elapsed
        expires = _effect_time(effect.get("expires_at_utc"))
        if current <= 0 or (expires is not None and when >= expires):
            cleared.append(effect)
            continue
        if elapsed > 0:
            effect["level"] = current
            effect["applied_at_utc"] = stamp
        active.append(effect)
    return active, cleared


# --------------------------------------------------------------------------- #
# Identity and lineage (spec 11.4, mirrors shardcore/lineage.py and 0015)
# --------------------------------------------------------------------------- #

# Spec section 12: migration 0015 derives ids under this namespace, so every
# conformant writer mints the same id for the same pre-1.10 bundle.
IDENTITY_NAMESPACE = uuid.UUID("7e027d65-5d78-55a0-b193-cd8e1ecdccc3")

BRANCH_RELATIONSHIPS = frozenset({"interpretation", "derivative", "alternate-universe"})

MAX_SHARD_ID_LENGTH = 128
SHA256_HEX = re.compile(r"^[a-f0-9]{64}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def canonical_json_bytes(value: Any) -> bytes:
    """Spec 11.1 canonical form: sorted keys, no insignificant whitespace, UTF-8."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """The spec 11.1 manifest_sha256 of a parsed manifest (what lineage pins)."""
    return hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()


def new_shard_id() -> str:
    """A fresh identity: random UUIDv4, lowercase hyphenated (spec 11.4.1)."""
    return str(uuid.uuid4())


def derived_shard_id(manifest_sha256: str) -> str:
    """The deterministic id migration 0015 mints for an existing bundle (spec 12)."""
    if not isinstance(manifest_sha256, str) or not SHA256_HEX.fullmatch(manifest_sha256):
        raise ValueError("manifest_sha256 must be 64 lowercase hex characters")
    return str(uuid.uuid5(IDENTITY_NAMESPACE, manifest_sha256))


def shard_id_error(value: Any) -> str | None:
    """Why value is not a valid shard_id, or None when it is (spec 11.4.1)."""
    if not isinstance(value, str) or not value.strip():
        return "shard_id must be a non-empty string"
    if len(value) > MAX_SHARD_ID_LENGTH:
        return f"shard_id exceeds {MAX_SHARD_ID_LENGTH} characters"
    if _CONTROL_CHARS.search(value):
        return "shard_id contains control characters"
    return None


def mint_shard_id(prior_manifest: Mapping[str, Any] | None = None) -> str:
    """The shard_id for a write whose manifest has none yet (spec 11.4.1, 12).

    A prior bundle manifest (one with a files map) gets the id migration 0015
    derives from it, so an app save and the migrator agree on the same bundle,
    and so do two copies of it saved separately. Anything else, including a
    seed dict that only carries a card, is a new bundle and gets a random id.
    """
    if isinstance(prior_manifest, Mapping) and "files" in prior_manifest:
        return derived_shard_id(manifest_digest(prior_manifest))
    return new_shard_id()


def branch_manifest(
    parent: Mapping[str, Any], *, relationship: str = "derivative"
) -> dict[str, Any]:
    """The prior manifest for a branch of parent, ready for build_manifest.

    Spec 11.2 routes edits of an immutable shard to a branch; spec 11.4 says
    what the branch records. It drops the immutable flag, gets a new shard_id
    (a branch never reuses its parent's), and replaces any inherited lineage
    with a branch block pinning the exact parent state by manifest_sha256.
    Deeper ancestry is resolved by following the parent's shard_id. It also
    drops the parent's files map and revision: a branch is a new identity, so
    build_manifest starts its revision chain at n 1 (spec 11.5).
    """
    if relationship not in BRANCH_RELATIONSHIPS:
        raise ValueError(
            f"branch relationship must be one of: {', '.join(sorted(BRANCH_RELATIONSHIPS))}"
        )
    pin: dict[str, Any] = {"manifest_sha256": manifest_digest(parent)}
    parent_id = parent.get("shard_id")
    if shard_id_error(parent_id) is None:
        pin["shard_id"] = parent_id
    card = parent.get("card")
    label = card.get("name") if isinstance(card, Mapping) else None
    if not (isinstance(label, str) and label.strip()):
        label = parent.get("shard_name")
    if isinstance(label, str) and label.strip():
        pin["label"] = label

    child = dict(parent)
    for key in ("immutable", "files", "revision"):
        child.pop(key, None)
    child["shard_id"] = new_shard_id()
    child["lineage"] = {"relationship": relationship, "parent": pin}
    return child


# --------------------------------------------------------------------------- #
# Revision chain (spec 11.5): the order of one identity's states
# --------------------------------------------------------------------------- #

# Prior states a manifest remembers, newest first (about 1 KB of digests).
REVISION_HISTORY_MAX = 16
REVISION_RELATIONS = ("same", "a_newer", "b_newer", "diverged", "unknown")


def _is_count(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_digest(value: Any) -> TypeGuard[str]:
    return isinstance(value, str) and SHA256_HEX.fullmatch(value) is not None


def revision_errors(revision: Any) -> list[str]:
    """Every way a manifest.revision block departs from spec 11.5. Empty means valid."""
    if not isinstance(revision, Mapping):
        return ["revision must be an object"]
    errors: list[str] = []
    n = revision.get("n")
    if not _is_count(n) or n < 1:
        errors.append("revision.n must be an integer of 1 or more")
    prior = revision.get("prior")
    if prior is not None and not _is_digest(prior):
        errors.append("revision.prior must be 64 lowercase hex characters")
    if prior is None and _is_count(n) and n > 1:
        errors.append("revision.prior is required when revision.n is above 1")
    history = revision.get("history")
    if history is not None:
        if not isinstance(history, list) or not all(_is_digest(d) for d in history):
            errors.append("revision.history must be an array of manifest digests")
        elif len(history) > REVISION_HISTORY_MAX:
            errors.append(f"revision.history holds more than {REVISION_HISTORY_MAX} digests")
        elif history and history[0] != prior:
            errors.append("revision.history[0] must equal revision.prior")
    merged = revision.get("merged")
    if merged is not None and not _is_digest(merged):
        errors.append("revision.merged must be 64 lowercase hex characters")
    return errors


def _revision_n(manifest: Mapping[str, Any]) -> int:
    revision = manifest.get("revision")
    n = revision.get("n") if isinstance(revision, Mapping) else None
    return n if _is_count(n) and n > 0 else 0


def revision_history(manifest: Mapping[str, Any]) -> list[str]:
    """The prior-state digests a manifest records, newest first (spec 11.5).

    A malformed block gives what is still usable: the valid digests in
    history, else a valid prior, else nothing. Never raises.
    """
    revision = manifest.get("revision")
    if not isinstance(revision, Mapping):
        return []
    history = revision.get("history")
    if isinstance(history, list):
        digests = [d for d in history if _is_digest(d)]
        if digests:
            return digests[:REVISION_HISTORY_MAX]
    prior = revision.get("prior")
    return [prior] if _is_digest(prior) else []


def _is_bundle_state(manifest: Any) -> bool:
    # A bundle manifest carries a files map. A seed dict, or a branch's prior
    # (branch_manifest drops the map), is no prior state: a fresh identity.
    return isinstance(manifest, Mapping) and "files" in manifest


def next_revision(
    prior_manifest: Mapping[str, Any] | None,
    *,
    merged_with: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The revision block for a write that replaces prior_manifest's state.

    No prior bundle state (a new bundle, a branch, an offspring): {"n": 1}.
    Otherwise n is the prior's n plus 1 (an absent or malformed revision
    counts as 0, so the first write of a pre-1.11 bundle is n 1 with its prior
    pinned), prior is the replaced state's manifest_sha256, and history is
    prior followed by the prior's own history, capped at REVISION_HISTORY_MAX.

    A merge passes the other side as merged_with: n is one past the larger of
    the two, merged pins the other side, and history interleaves both chains
    (prior, the other side, then each one's history in turn, each digest
    once), so either input compares as older than the merge.
    """
    if prior_manifest is None or not _is_bundle_state(prior_manifest):
        return {"n": 1}
    prior = manifest_digest(prior_manifest)
    chains = [[prior, *revision_history(prior_manifest)]]
    n = _revision_n(prior_manifest) + 1
    merged: str | None = None
    if merged_with is not None and _is_bundle_state(merged_with):
        merged = manifest_digest(merged_with)
        chains.append([merged, *revision_history(merged_with)])
        n = max(n, _revision_n(merged_with) + 1)
    history: list[str] = []
    for depth in range(max(len(chain) for chain in chains)):
        for chain in chains:
            if depth < len(chain) and chain[depth] not in history:
                history.append(chain[depth])
    revision: dict[str, Any] = {"n": n, "prior": prior, "history": history[:REVISION_HISTORY_MAX]}
    if merged is not None:
        revision["merged"] = merged
    return revision


def compare_revisions(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    """How two states of one identity relate (spec 11.5), from their manifests.

    same       equal manifest digests: one state
    a_newer    b's state is in a's history, so a descends from b
    b_newer    the mirror case
    diverged   neither descends from the other and their histories share a
               state (common_ancestor names it)
    unknown    the histories never meet; revision.n hints which is later and
               proves nothing
    Raises ValueError when the shard_ids differ: states of different
    identities have no order.
    """
    if a.get("shard_id") != b.get("shard_id"):
        raise ValueError("compare_revisions needs two states of one shard_id")
    digest_a, digest_b = manifest_digest(a), manifest_digest(b)
    if digest_a == digest_b:
        return "same"
    history_a, history_b = revision_history(a), revision_history(b)
    if digest_b in history_a:
        return "a_newer"
    if digest_a in history_b:
        return "b_newer"
    if set(history_a) & set(history_b):
        return "diverged"
    return "unknown"


def common_ancestor(a: Mapping[str, Any], b: Mapping[str, Any]) -> str | None:
    """The newest state both manifests descend from, in a's order, or None."""
    seen = set(revision_history(b))
    return next((digest for digest in revision_history(a) if digest in seen), None)


# --------------------------------------------------------------------------- #
# Backup vault (shardcore/backup_vault.py): every written state, for reversal
# --------------------------------------------------------------------------- #

_bv_logger = logging.getLogger("shardcore.backup_vault")
BACKUP_VAULT_ENV = "SHARD_BACKUP_VAULT"
BACKUP_APP_ENV = "SHARD_APP"
BACKUP_VAULT_DEFAULT = ".vault/backup_vault"
# A workspace kept in this folder at the root of a drive is found by programs that
# live elsewhere on that drive.
BACKUP_DRIVE_FOLDER = ".shards"
_BACKUP_MAX_BUNDLE_BYTES = 256 * 1024 * 1024
_BACKUP_LINE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*=\s*"([^"]*)"')


def _bv_workspace_toml(start: Path) -> Path | None:
    """The first WORKSPACE.toml at or above start."""
    try:
        here = start.resolve()
    except OSError:
        return None
    for folder in (here, *here.parents):
        candidate = folder / "WORKSPACE.toml"
        if candidate.is_file():
            return candidate
    return None


def _bv_read_workspace(toml: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    """[artifacts] and the [[consumers]] name/path pairs: the two flat string
    tables this needs, read line by line (no tomllib on Python 3.10)."""
    artifacts: dict[str, str] = {}
    consumers: list[dict[str, str]] = []
    section = ""
    for raw in toml.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("["):
            section = line
            if line == "[[consumers]]":
                consumers.append({})
            continue
        match = _BACKUP_LINE.match(line)
        if not match:
            continue
        key, value = match.groups()
        if section == "[artifacts]":
            artifacts[key] = value
        elif section == "[[consumers]]" and key in ("name", "path"):
            consumers[-1][key] = value
    return artifacts, consumers


def _bv_origins() -> list[Path]:
    """Where this process lives: this file, the program, the working dir."""
    origins = [Path(__file__)]
    if sys.argv and sys.argv[0]:
        origins.append(Path(sys.argv[0]))
    origins.append(Path.cwd())
    return origins


def _bv_drive_root(start: Path) -> Path | None:
    try:
        return Path(start.resolve().anchor)
    except OSError:
        return None


def _bv_workspace(near: Path | None) -> Path | None:
    starts = ([near] if near is not None else []) + _bv_origins()
    for start in starts:
        found = _bv_workspace_toml(start)
        if found is not None:
            return found
    for start in starts:
        root = _bv_drive_root(start)
        candidate = root / BACKUP_DRIVE_FOLDER / "WORKSPACE.toml" if root else None
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def backup_vault_dir(near: str | os.PathLike[str] | None = None) -> Path | None:
    """Where states are recorded, or None when recording is off (module doc)."""
    setting = os.environ.get(BACKUP_VAULT_ENV, "").strip()
    if setting.lower() == "off":
        return None
    if setting:
        return Path(setting)
    toml = _bv_workspace(Path(near) if near is not None else None)
    if toml is None:
        return None
    artifacts, _ = _bv_read_workspace(toml)
    return toml.parent / artifacts.get("backup_vault", BACKUP_VAULT_DEFAULT)


def _bv_app(app: str | None) -> str:
    """The journal a program writes: app, else SHARD_APP, else the workspace
    consumer whose folder holds this process, else the program's name."""
    name = app or os.environ.get(BACKUP_APP_ENV, "")
    if not name:
        toml = _bv_workspace(None)
        if toml is not None:
            _, consumers = _bv_read_workspace(toml)
            for origin in _bv_origins():
                try:
                    where = os.path.normcase(str(origin.resolve()))
                except OSError:
                    continue
                for consumer in consumers:
                    root = os.path.normcase(str((toml.parent / consumer.get("path", "")).resolve()))
                    if consumer.get("name") and (where == root or where.startswith(root + os.sep)):
                        name = consumer["name"]
                        break
                if name:
                    break
    if not name and sys.argv and sys.argv[0]:
        name = Path(sys.argv[0]).stem
    return re.sub(r"[^a-z0-9_-]+", "_", (name or "unknown").lower()).strip("_") or "unknown"


def _bv_in_temp(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    except OSError:
        return False


def _bv_put(objects: Path, data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")  # what zipfile.writestr stores for a str member
    sha = hashlib.sha256(data).hexdigest()
    target = objects / sha[:2] / sha
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=sha[:8] + ".", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    return sha


def _bv_last_entry(journal: Path) -> dict[str, Any] | None:
    if not journal.is_file():
        return None
    with journal.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - 65536))
        lines = handle.read().splitlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            return entry
    return None


def record_bundle(
    path: str | os.PathLike[str],
    *,
    event: str,
    app: str | None = None,
    members: Mapping[str, bytes] | None = None,
    vault: str | os.PathLike[str] | None = None,
) -> str | None:
    """Record the bundle state at path in the backup vault.

    members, when given, are the exact archive members just written (with
    manifest.json); otherwise the file is read. Returns the recorded manifest
    digest, or None when recording is off, the path is scratch, or recording
    failed (logged, never raised).
    """
    target = Path(path)
    try:
        explicit = os.environ.get(BACKUP_VAULT_ENV, "").strip().lower() not in ("", "off")
        store = Path(vault) if vault is not None else backup_vault_dir(target)
        if store is None or (vault is None and not explicit and _bv_in_temp(target)):
            return None
        if members is None:
            if not target.is_file() or target.stat().st_size > _BACKUP_MAX_BUNDLE_BYTES:
                return None
            with zipfile.ZipFile(target, "r") as archive:
                members = {
                    info.filename: archive.read(info)
                    for info in archive.infolist()
                    if not info.is_dir()
                }
        manifest = json.loads(members["manifest.json"])
        if not isinstance(manifest, dict):
            return None
        digest = manifest_digest(manifest)
        journal = store / "journal" / f"{_bv_app(app)}.jsonl"
        where = target.resolve().as_posix()
        last = _bv_last_entry(journal)
        if last and last.get("path") == where and last.get("manifest_sha256") == digest:
            return digest
        shas = {name: _bv_put(store / "objects", data) for name, data in sorted(members.items())}
        card = manifest.get("card")
        entry = {
            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "app": journal.stem,
            "event": event,
            "path": where,
            "shard_id": manifest.get("shard_id"),
            "name": manifest.get("shard_name")
            or (card.get("name") if isinstance(card, dict) else None),
            "manifest_sha256": digest,
            "members": shas,
        }
        journal.parent.mkdir(parents=True, exist_ok=True)
        # shortcut: one write() per line, no file lock. Each program has its own
        # journal, so only two copies of one program writing at the same instant
        # could interleave a line; read_journal skips a line that fails to parse.
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        return digest
    except Exception as exc:  # a backup must never block the save it guards
        _bv_logger.warning("backup vault: could not record %s (%s)", target, exc)
        return None


def read_journal(
    vault: str | os.PathLike[str],
    *,
    shard_id: str | None = None,
    name: str | None = None,
    app: str | None = None,
) -> list[dict[str, Any]]:
    """Every journaled state, oldest first, filtered by id, name (case-blind
    substring) or program."""
    entries: list[dict[str, Any]] = []
    folder = Path(vault) / "journal"
    if not folder.is_dir():
        return entries
    for journal in sorted(folder.glob("*.jsonl")):
        if app and journal.stem != app:
            continue
        for line in journal.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if shard_id and entry.get("shard_id") != shard_id:
                continue
            if name and name.lower() not in str(entry.get("name") or "").lower():
                continue
            entries.append(entry)
    entries.sort(key=lambda e: (str(e.get("utc")), str(e.get("app"))))
    return entries


def restore_bundle(
    vault: str | os.PathLike[str], manifest_sha256: str, dest: str | os.PathLike[str]
) -> Path:
    """Rebuild the journaled state whose manifest digest is (or starts with)
    manifest_sha256 at dest. A file already at dest is recorded first, so the
    restore is itself reversible. Raises ValueError for no or several matches
    and for an object that is missing or does not match its digest."""
    store, target = Path(vault), Path(dest)
    matches = {
        e["manifest_sha256"]: e
        for e in read_journal(store)
        if str(e.get("manifest_sha256", "")).startswith(manifest_sha256)
    }
    if len(matches) != 1:
        raise ValueError(
            f"{len(matches)} states match {manifest_sha256!r}; give more of the digest"
        )
    entry = next(iter(matches.values()))
    members: dict[str, bytes] = {}
    for member, sha in entry["members"].items():
        data = (store / "objects" / sha[:2] / sha).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError(f"object {sha} for {member} is damaged")
        members[member] = data
    if target.exists():
        record_bundle(target, event="replaced_by_restore", vault=store, app="backup_restore")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", members.pop("manifest.json"))
            for member in sorted(members):
                archive.writestr(member, members[member])
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def load_state(vault: str | os.PathLike[str], manifest_sha256: str) -> dict[str, bytes] | None:
    """The members (manifest.json among them) of the journaled state whose
    manifest digest is exactly manifest_sha256, read into memory, or None when
    the vault never recorded it. Raises ValueError for a missing or damaged
    object: the state was recorded and cannot be rebuilt."""
    store = Path(vault)
    for entry in reversed(read_journal(store)):
        if entry.get("manifest_sha256") != manifest_sha256:
            continue
        members: dict[str, bytes] = {}
        for member, sha in entry["members"].items():
            try:
                data = (store / "objects" / sha[:2] / sha).read_bytes()
            except OSError as exc:
                raise ValueError(f"object {sha} for {member} is missing") from exc
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError(f"object {sha} for {member} is damaged")
            members[member] = data
        return members
    return None


# --------------------------------------------------------------------------- #
# Manifest construction (mirrors migrations 0005/0007/0008/0009/0011/0015)
# --------------------------------------------------------------------------- #


def build_card(
    soul: Mapping[str, Any] | None, prior_card: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Regenerate manifest.card from the soul (mirror 0008), over any prior card.

    Guards a string identity: v1.9 soul.identity is a string, so title/role are
    pulled from soul top level, never soul.identity.get(...).
    """
    card: dict[str, Any] = dict(prior_card) if isinstance(prior_card, Mapping) else {}
    if not isinstance(soul, Mapping):
        return card
    for card_key, soul_key in (
        ("name", "name"),
        ("title", "title"),
        ("role", "role"),
        ("core_essence", "core_essence"),
    ):
        value = soul.get(soul_key)
        if isinstance(value, str) and value.strip():
            card[card_key] = value
    tags = soul.get("trait_tags") or soul.get("traits")
    if isinstance(tags, list):
        clean = [t for t in tags if isinstance(t, str)][:12]
        if clean:
            card["tags"] = clean
    return card


def _schema_version(schema: str) -> tuple[int, ...]:
    return version_tuple(schema.rpartition("@")[2]) or ()


def _declared_schema(name: str, manifests: Iterable[Mapping[str, Any] | None]) -> str | None:
    # A merge has two sides; the member may be either's, so the higher id holds.
    found: str | None = None
    for manifest in manifests:
        files = manifest.get("files") if isinstance(manifest, Mapping) else None
        entry = files.get(name) if isinstance(files, Mapping) else None
        schema = entry.get("schema") if isinstance(entry, Mapping) else None
        if (
            isinstance(schema, str)
            and schema.strip()
            and (found is None or _schema_version(schema) > _schema_version(found))
        ):
            found = schema
    return found


def build_files_info(
    members: Mapping[str, bytes],
    *,
    keep_from: Iterable[Mapping[str, Any] | None] = (),
    spec: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the manifest.files map: {schema, sha256, size} per member.

    manifest.json, if present in members, is skipped (it is not self-referential).
    A member keeps the schema id it declares in keep_from (the manifests this
    write replaces), except a neuronshard, whose id follows its document. Any
    other member gets the id a shard of version spec carries. A member with no
    known schema id still gets sha256 + size (integrity holds even when the
    schema is unknown), just no schema key.
    """
    replaced = tuple(keep_from)
    files: dict[str, dict[str, Any]] = {}
    for name in sorted(members):
        if name == "manifest.json" or name.endswith("/"):
            continue
        data = members[name]
        entry: dict[str, Any] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
        schema = _neuron_schema(data) if name == "neuronshard.json" else None
        schema = schema or _declared_schema(name, replaced)
        schema = schema or schema_for_member(name, data, spec)
        if schema is not None:
            entry["schema"] = schema
        files[name] = entry
    return files


# --------------------------------------------------------------------------- #
# The version a write stamps (compatibility RFC sections 3 and 4)
# --------------------------------------------------------------------------- #


def _declared_spec(manifest: Any) -> str | None:
    if not isinstance(manifest, Mapping):
        return None
    for key in ("spec_version", "bundle_version"):
        text = manifest.get(key)
        if isinstance(text, str) and version_tuple(text) is not None:
            return text.strip()
    return None


def _later(a: str | None, b: str | None) -> str | None:
    if a is None or b is None:
        return a or b
    return a if (version_tuple(a) or ()) >= (version_tuple(b) or ()) else b


def kept_spec(
    prior_manifest: Mapping[str, Any] | None,
    *,
    merged_with: Mapping[str, Any] | None = None,
) -> str:
    """The spec_version a write stamps: the one the shard already declares.

    A merge takes the higher of its sides. A new shard, and one older than
    OLDEST_KEPT_SPEC, gets NEW_SHARD_SPEC.
    """
    held = _later(_declared_spec(prior_manifest), _declared_spec(merged_with))
    if held is None or (version_tuple(held) or ()) < (version_tuple(OLDEST_KEPT_SPEC) or ()):
        return NEW_SHARD_SPEC
    return held


def content_spec(members: Mapping[str, bytes]) -> str:
    """The lowest version that covers these members.

    Only what a version added counts: a neuron@1.1 document and parts[id].neural
    came in 1.12 (spec 8.10, 6.3). Anything else a 1.9 shard can hold.
    """
    neuron = members.get("neuronshard.json")
    if neuron is not None and _neuron_schema(neuron) == NEURON_SCHEMAS["1.1"]:
        return "1.12"
    try:
        shell = json.loads(members.get("shellshard.json", b"{}"))
    except (ValueError, UnicodeDecodeError):
        return OLDEST_KEPT_SPEC
    anatomy = shell.get("anatomy_profile") if isinstance(shell, dict) else None
    parts = anatomy.get("parts") if isinstance(anatomy, dict) else None
    if isinstance(parts, dict) and any(
        isinstance(part, dict) and "neural" in part for part in parts.values()
    ):
        return "1.12"
    return OLDEST_KEPT_SPEC


def _write_spec(
    members: Mapping[str, bytes],
    prior_manifest: Mapping[str, Any] | None,
    merged_with: Mapping[str, Any] | None,
    upgrade_to: str | None,
) -> str:
    spec = kept_spec(prior_manifest, merged_with=merged_with)
    if upgrade_to is not None:
        wanted, held = version_tuple(upgrade_to), version_tuple(spec)
        if wanted is None or wanted < (held or ()) or wanted > (version_tuple(SPEC_VERSION) or ()):
            raise ValueError(f"upgrade_to {upgrade_to!r} must be from {spec} to {SPEC_VERSION}")
        spec = upgrade_to
    # Content the shard already held is not this write's doing.
    seen: set[Any] = set()
    for manifest in (prior_manifest, merged_with):
        files = manifest.get("files") if isinstance(manifest, Mapping) else None
        for name, entry in files.items() if isinstance(files, Mapping) else ():
            if isinstance(entry, Mapping):
                seen.add((name, entry.get("sha256")))
    fresh = {
        name: data
        for name, data in members.items()
        if name in ("neuronshard.json", "shellshard.json")
        and (name, hashlib.sha256(data).hexdigest()) not in seen
    }
    needed = content_spec(fresh)
    if (version_tuple(needed) or ()) > (version_tuple(spec) or ()):
        if _is_bundle_state(prior_manifest):
            raise UpgradeNeededError(spec, needed)
        spec = needed  # a new identity takes the version it needs
    return spec


def build_manifest(
    members: Mapping[str, bytes],
    *,
    soul: Mapping[str, Any] | None = None,
    prior_manifest: Mapping[str, Any] | None = None,
    shard_name: str | None = None,
    immutable: bool | None = None,
    extra: Mapping[str, Any] | None = None,
    now: str | None = None,
    merged_with: Mapping[str, Any] | None = None,
    upgrade_to: str | None = None,
    content_of: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete manifest for the given member bytes.

    Refuses (NewerSpecError) a prior_manifest (or merged_with) this writer may
    not save (check_spec_writable), and raises UpgradeNeededError when a changed
    member needs a newer version than the shard declares. Otherwise preserves
    unknown keys from prior_manifest (shard_id, lineage, conformance, min_writer,
    vendor fields), then forces these over them:
      - spec_version / bundle_version -> kept_spec, or upgrade_to when given
      - min_writer -> on a merge, the higher of its sides
      - memory_format removed
      - created preserved from prior (or now), last_modified_utc -> now, bare
        last_modified removed
      - card regenerated from soul over any prior card
      - shard_id kept as is when present (even an invalid one: diagnose
        surfaces it and nothing replaces it), else minted by mint_shard_id
      - revision derived by next_revision: the prior state's n plus 1, pinned,
        or n 1 for a new identity; a merge passes the other side as
        merged_with. A version without the chain (before 1.11) gets none unless
        one is there
      - files rebuilt from the exact member bytes, declared schema ids kept; an
        upgrade refreshes them

    prior_manifest is the state this write replaces: the manifest of the file
    as loaded, or the one the last save returned. Passing an older one makes
    the new state look diverged from the save before it.

    A restore writes an earlier state's members on top of a later one. Pass the
    earlier manifest as content_of: the version, schema ids and min_writer are
    its, and the revision chain still runs from prior_manifest.

    members must be the payload bytes only (no manifest.json). The returned
    manifest is what you then serialize and write as manifest.json.
    """
    check_spec_writable(prior_manifest)
    check_spec_writable(merged_with)
    check_spec_writable(content_of)
    held = prior_manifest if content_of is None else content_of
    spec = _write_spec(members, held, merged_with, upgrade_to)
    level = version_tuple(spec) or ()
    stamp = now or utc_now()
    manifest: dict[str, Any] = dict(prior_manifest) if isinstance(prior_manifest, Mapping) else {}

    # Forbidden and superseded keys.
    manifest.pop("memory_format", None)
    manifest.pop("last_modified", None)  # bare local-time key is replaced by _utc

    manifest["spec_version"] = spec
    manifest["bundle_version"] = spec  # deprecated alias, spec 2.2
    if merged_with is not None or content_of is not None:
        floor = _later(min_writer(held), min_writer(merged_with))
        manifest.pop("min_writer", None)
        if floor is not None:
            manifest["min_writer"] = floor

    created = manifest.get("created")
    manifest["created"] = to_utc_z(created) or stamp
    manifest["last_modified_utc"] = stamp

    if shard_name is not None:
        manifest["shard_name"] = shard_name
    elif "shard_name" not in manifest and isinstance(soul, Mapping):
        name = soul.get("name")
        if isinstance(name, str) and name.strip():
            manifest["shard_name"] = name

    if soul is not None:
        manifest["card"] = build_card(soul, manifest.get("card"))

    if immutable is not None:
        manifest["immutable"] = bool(immutable)

    if extra:
        manifest.update(extra)

    if "shard_id" not in manifest:
        manifest["shard_id"] = mint_shard_id(prior_manifest)

    if level >= (1, 11) or "revision" in manifest:
        manifest["revision"] = next_revision(prior_manifest, merged_with=merged_with)
    replaced = () if upgrade_to is not None else (held, merged_with)
    manifest["files"] = build_files_info(members, keep_from=replaced, spec=spec)
    return manifest


# --------------------------------------------------------------------------- #
# Packing (atomic write, forward-slash arcnames, DEFLATED)
# --------------------------------------------------------------------------- #


def keep_before_upgrade(target: Path, upgrade_to: str) -> None:
    """Copy the file an upgrade replaces beside itself, as <name>.v<version>.bak.

    An upgrade can be undone (compatibility RFC section 4). The backup vault
    keeps the earlier file where there is one; this is for everywhere else. A
    failure here stops the upgrade.
    """
    declared = _declared_spec(read_bundle_members(target)[0]) or "unknown"
    if version_tuple(declared) == version_tuple(upgrade_to):
        return
    number = 1
    kept = target.with_name(f"{target.name}.v{declared}.bak")
    while kept.exists():
        number += 1
        kept = target.with_name(f"{target.name}.v{declared}.{number}.bak")
    shutil.copy2(target, kept)


def pack_bundle(
    path: str | os.PathLike[str],
    members: Mapping[str, bytes],
    *,
    soul: Mapping[str, Any] | None = None,
    prior_manifest: Mapping[str, Any] | None = None,
    shard_name: str | None = None,
    immutable: bool | None = None,
    extra: Mapping[str, Any] | None = None,
    now: str | None = None,
    manifest: Mapping[str, Any] | None = None,
    backup_event: str = "write",
    merged_with: Mapping[str, Any] | None = None,
    upgrade_to: str | None = None,
    content_of: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a .shard atomically. Returns the manifest that was written.

    Pass a prebuilt manifest, or let it be built from soul/prior_manifest/etc.
    The manifest hashes the exact member bytes written, so there is no drift
    between what the manifest claims and what the archive holds.

    members are the payload files only; manifest.json is added here. Member
    names are written with forward slashes regardless of host OS.

    Both states land in the backup vault (record_bundle): the file being
    replaced, whoever wrote it, and the one written, journaled as
    backup_event (a program names its own, e.g. "discharge"). An upgrade
    (upgrade_to) with no vault keeps the replaced file beside the new one.
    """
    target = Path(path)
    if manifest is None:
        manifest = build_manifest(
            members,
            soul=soul,
            prior_manifest=prior_manifest,
            shard_name=shard_name,
            immutable=immutable,
            extra=extra,
            now=now,
            merged_with=merged_with,
            upgrade_to=upgrade_to,
            content_of=content_of,
        )
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".tmp", prefix=target.name + ".", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    written: dict[str, bytes] = {"manifest.json": manifest_bytes}
    try:
        with (
            os.fdopen(fd, "wb") as raw_tmp,
            zipfile.ZipFile(raw_tmp, "w", zipfile.ZIP_DEFLATED) as archive,
        ):
            archive.writestr("manifest.json", manifest_bytes)
            for name in sorted(members):
                if name == "manifest.json" or name.endswith("/"):
                    continue
                arcname = name.replace(os.sep, "/")
                archive.writestr(arcname, members[name])
                written[arcname] = members[name]
        if target.exists():
            recorded = record_bundle(target, event="replaced")
            if upgrade_to is not None and recorded is None:
                keep_before_upgrade(target, upgrade_to)
        os.replace(tmp_path, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise
    record_bundle(target, event=backup_event, members=written)
    return dict(manifest)


# --------------------------------------------------------------------------- #
# Reading trust decisions
# --------------------------------------------------------------------------- #


def spec_major(manifest: Mapping[str, Any]) -> int:
    """The spec major of a manifest, reading spec_version then bundle_version.

    Returns 1 when neither is present or parseable (a version-less legacy bundle
    is treated as within-major, since it long predates any 2.x).
    """
    for key in ("spec_version", "bundle_version"):
        value = manifest.get(key)
        if isinstance(value, str) and value.strip():
            head = value.strip().split(".", 1)[0]
            try:
                return int(head)
            except ValueError:
                continue
    return 1


def check_spec_major(manifest: Mapping[str, Any], *, max_major: int = SUPPORTED_MAJOR) -> None:
    """Raise FutureSpecError if the bundle's spec major exceeds what we support."""
    major = spec_major(manifest)
    if major > max_major:
        version = manifest.get("spec_version") or manifest.get("bundle_version") or "?"
        raise FutureSpecError(
            f"bundle spec_version {version} (major {major}) exceeds supported major {max_major}"
        )


def verify_members(
    raw: Mapping[str, bytes],
    files_map: Mapping[str, Any],
    *,
    require_all_listed: bool = True,
) -> None:
    """Verify every manifest.files entry is present and hash-matches.

    raw maps member name -> its bytes (as read from the archive). Raises
    ShardIntegrityError on the first listed member that is missing, has no
    sha256, or whose bytes disagree. With require_all_listed=True (the default,
    and what a runtime should use) a listed-but-absent member is an error, per
    spec 2.3. A legacy list-form files map (a bare list of names) carries no
    hashes, so nothing can be verified: that is reported by returning without
    raising only when the map is empty of dict entries.
    """
    if not isinstance(files_map, Mapping) or not files_map:
        raise ShardIntegrityError("manifest has no verifiable files map")
    for name, entry in files_map.items():
        if not isinstance(entry, Mapping):
            raise ShardIntegrityError(f"manifest.files[{name!r}] is not an object")
        data = raw.get(name)
        if data is None:
            if require_all_listed:
                raise ShardIntegrityError(
                    f"manifest lists {name!r} but it is absent from the archive"
                )
            continue
        declared = entry.get("sha256")
        if not isinstance(declared, str) or not declared.strip():
            raise ShardIntegrityError(f"manifest.files[{name!r}] has no sha256")
        if hashlib.sha256(data).hexdigest() != declared:
            raise ShardIntegrityError(f"integrity mismatch on {name!r}")


_VERSION_TEXT = re.compile(r"[0-9]+(\.[0-9]+)*")


def version_tuple(value: Any) -> tuple[int, ...] | None:
    """A version string as integers, compared per component (spec section 3).

    "1.10" is (1, 10), so it sorts after "1.9"; string or float comparison
    gets that wrong. None for anything that is not dotted digits.
    """
    if not isinstance(value, str) or not _VERSION_TEXT.fullmatch(value.strip()):
        return None
    return tuple(int(part) for part in value.strip().split("."))


def min_writer(manifest: Mapping[str, Any] | None) -> str | None:
    """manifest.min_writer when it is a version, else None."""
    text = manifest.get("min_writer") if isinstance(manifest, Mapping) else None
    return text.strip() if isinstance(text, str) and version_tuple(text) is not None else None


def check_spec_writable(manifest: Mapping[str, Any] | None) -> None:
    """Raise NewerSpecError when this writer may not save the bundle.

    Reading it is fine (same major). manifest.min_writer names the oldest spec
    whose writers can save a bundle without breaking it: below that this writer
    refuses, whatever spec_version says. A bundle newer than SPEC_VERSION that
    names no floor is refused too. build_manifest calls this on its
    prior_manifest; a writer that builds its own manifest calls it on the
    manifest it is about to replace.
    """
    if not isinstance(manifest, Mapping):
        return
    written = version_tuple(SPEC_VERSION) or ()
    declared_text = _declared_spec(manifest)
    declared = version_tuple(declared_text) or ()
    floor_text = min_writer(manifest)
    floor = version_tuple(floor_text) or ()
    if floor > written:
        why = f"bundle needs a writer of spec {floor_text} or later"
    elif declared > written and (not floor or declared[0] > SUPPORTED_MAJOR):
        why = f"bundle spec_version {declared_text} is newer than this writer's"
    else:
        return
    raise NewerSpecError(
        f"{why}; this one implements {SPEC_VERSION} and will not rewrite it. Update the vendored "
        "shardcore_v19 helper (shardcore: tools/ecosystem/ecosystem.py sync)."
    )


def is_immutable(manifest: Mapping[str, Any]) -> bool:
    """Whether a manifest declares the bundle immutable (spec 2.2)."""
    return bool(manifest.get("immutable", False))


def assert_writable(manifest: Mapping[str, Any] | None, *, context: str = "") -> None:
    """Raise ImmutableShardError if this manifest marks the bundle immutable.

    Call this in a save path before overwriting a loaded bundle in place. An
    immutable prime/reference shard must be branched to a new filename instead,
    with branch_manifest(parent) as the branch's prior manifest.
    """
    if manifest is not None and is_immutable(manifest):
        where = f" ({context})" if context else ""
        raise ImmutableShardError(f"bundle is marked immutable; refuse in-place write{where}")


def read_bundle_members(path: str | os.PathLike[str]) -> tuple[dict[str, Any], dict[str, bytes]]:
    """A .shard's manifest and its verified members (manifest.json not among them).

    Read into memory; nothing is extracted. Raises ShardError for an archive
    that cannot be read, duplicate member names, or a missing or non-object
    manifest, FutureSpecError for a higher spec major, and ShardIntegrityError
    for a listed member that is absent or fails its digest.
    """
    try:
        with zipfile.ZipFile(os.fspath(path), "r") as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ShardError(f"{path}: duplicate archive member names")
            raw = {info.filename: archive.read(info) for info in infos}
    except (OSError, zipfile.BadZipFile) as exc:
        raise ShardError(f"{path}: cannot read bundle ({exc})") from exc
    try:
        manifest = json.loads(raw.pop("manifest.json"))
    except (KeyError, ValueError) as exc:
        raise ShardError(f"{path}: no readable manifest.json") from exc
    if not isinstance(manifest, dict):
        raise ShardError(f"{path}: manifest.json is not an object")
    check_spec_major(manifest)
    verify_members(raw, manifest.get("files") or {})
    return manifest, raw


# --------------------------------------------------------------------------- #
# Merge (spec 11.5.3): two diverged states and the base they share
# --------------------------------------------------------------------------- #

_ABSENT: Any = object()
MERGE_SIDES = ("ours", "theirs")


def _merge_unit(base: Any, ours: Any, theirs: Any) -> tuple[Any, bool]:
    """Three-way rule for one unit: (value, conflicted). Ours on a conflict."""
    if ours == theirs:
        return ours, False
    if ours == base:
        return theirs, False
    if theirs == base:
        return ours, False
    return ours, True


def _json_object(data: Any) -> Any:
    if data is _ABSENT:
        return _ABSENT
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _merge_keys(
    unit: str,
    base: dict[str, Any],
    ours: dict[str, Any],
    theirs: dict[str, Any],
    prefer: Mapping[str, str],
    conflicts: list[str],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in [
        *ours,
        *(k for k in theirs if k not in ours),
        *(k for k in base if k not in ours and k not in theirs),
    ]:
        b, o, t = base.get(key, _ABSENT), ours.get(key, _ABSENT), theirs.get(key, _ABSENT)
        here = f"{unit}#{key}"
        if (
            unit == "mindshard.json"
            and key == "structured"
            and all(isinstance(v, dict) or v is _ABSENT for v in (b, o, t))
            and o is not _ABSENT
            and t is not _ABSENT
        ):
            # spec 7.3: each consumer-schema block is its owner's unit.
            value: Any = _merge_keys(
                here, b if isinstance(b, dict) else {}, o, t, prefer, conflicts
            )
        else:
            value, conflicted = _merge_unit(b, o, t)
            if conflicted:
                if prefer.get(here) == "theirs":
                    value = t
                elif here not in prefer:
                    conflicts.append(here)
        if value is not _ABSENT:
            merged[key] = value
    return merged


def merge_members(
    base: Mapping[str, bytes],
    ours: Mapping[str, bytes],
    theirs: Mapping[str, bytes],
    *,
    prefer: Mapping[str, str] | None = None,
) -> tuple[dict[str, bytes], list[str]]:
    """Three-way merge of bundle members. Returns (members, conflicts).

    The unit is the smallest thing one owner changes (spec 11.5.3): each
    top-level key of a JSON object member (so every soul x_<vendor> namespace,
    and every portable soul field, is its own unit), each mindshard.structured
    schema block (spec 7.3), and every other member whole. A unit only one
    side changed takes that side; a unit both sides changed the same way takes
    it; a unit both changed differently is a conflict, named
    "member#key" or "mindshard.json#structured#<schema id>". A conflict listed
    in prefer as "ours" or "theirs" takes that side; any other keeps ours and
    is returned in conflicts. A member whose merged value equals one side's
    keeps that side's bytes; a merged JSON member is written indent 2.
    manifest.json is never merged (the write builds a new one).
    """
    choose = dict(prefer or {})
    merged: dict[str, bytes] = {}
    conflicts: list[str] = []
    names = sorted((set(base) | set(ours) | set(theirs)) - {"manifest.json"})
    for name in names:
        b, o, t = base.get(name, _ABSENT), ours.get(name, _ABSENT), theirs.get(name, _ABSENT)
        if o == t:
            if o is not _ABSENT:
                merged[name] = o
            continue
        if name.endswith(".json"):
            jb, jo, jt = _json_object(b), _json_object(o), _json_object(t)
            if (
                isinstance(jo, dict)
                and isinstance(jt, dict)
                and (jb is _ABSENT or isinstance(jb, dict))
            ):
                value = _merge_keys(
                    name, jb if isinstance(jb, dict) else {}, jo, jt, choose, conflicts
                )
                if value == jo:
                    merged[name] = o
                elif value == jt:
                    merged[name] = t
                else:
                    merged[name] = json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8")
                continue
        value, conflicted = _merge_unit(b, o, t)
        if conflicted:
            if choose.get(name) == "theirs":
                value = t
            elif name not in choose:
                conflicts.append(name)
        if value is not _ABSENT:
            merged[name] = value
    return merged, conflicts


def merge_bundles(
    ours: str | os.PathLike[str],
    theirs: str | os.PathLike[str],
    *,
    vault: str | os.PathLike[str] | None = None,
    prefer: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reconcile two copies of one identity (spec 11.5), the base from the vault.

    Returns {"status", "base", "members", "conflicts", "ours", "theirs"}, the
    last two being the input manifests:

      same, ours_newer, theirs_newer   nothing to merge; members is the
                                       newer (or only) state's
      merged      diverged; the base was found and every unit resolved
      conflicts   diverged; members holds ours for the units in conflicts
                  (pass prefer to resolve them and call again)
      no_base     diverged, but the vault never recorded the base state
      unknown     the revision chains never meet
    members is None for no_base and unknown. Write a merged result with
    write_merge. Raises ValueError when the two have different shard_ids.
    """
    ours_manifest, ours_members = read_bundle_members(ours)
    theirs_manifest, theirs_members = read_bundle_members(theirs)
    relation = compare_revisions(ours_manifest, theirs_manifest)
    result: dict[str, Any] = {
        "status": relation,
        "base": None,
        "members": None,
        "conflicts": [],
        "ours": ours_manifest,
        "theirs": theirs_manifest,
    }
    if relation in ("same", "a_newer"):
        result["status"] = "same" if relation == "same" else "ours_newer"
        result["members"] = ours_members
        return result
    if relation == "b_newer":
        result["status"] = "theirs_newer"
        result["members"] = theirs_members
        return result
    if relation == "unknown":
        return result
    base_digest = common_ancestor(ours_manifest, theirs_manifest)
    store = Path(vault) if vault is not None else backup_vault_dir(ours)
    base = load_state(store, base_digest) if store is not None and base_digest else None
    result["base"] = base_digest
    if base is None:
        result["status"] = "no_base"
        return result
    members, conflicts = merge_members(base, ours_members, theirs_members, prefer=prefer)
    result.update(
        members=members, conflicts=conflicts, status="conflicts" if conflicts else "merged"
    )
    return result


def write_merge(
    path: str | os.PathLike[str], result: Mapping[str, Any], *, backup_event: str = "merge"
) -> dict[str, Any]:
    """Write a merge_bundles result whose status is merged (or conflicts the
    caller accepts) as one new state: prior is ours, merged pins theirs, so
    both inputs compare as older (spec 11.5.3). Returns the written manifest."""
    if result.get("members") is None or result.get("status") not in ("merged", "conflicts"):
        raise ValueError(f"nothing to write for a {result.get('status')!r} merge result")
    members = result["members"]
    soul = _json_object(members.get("soulshard.json", _ABSENT))
    return pack_bundle(
        path,
        members,
        soul=soul if isinstance(soul, dict) else None,
        prior_manifest=result["ours"],
        merged_with=result["theirs"],
        backup_event=backup_event,
    )
