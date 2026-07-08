"""The v1.9 migration chain (spec section 12, proposal section 5).

Each migration is a small pure transform on a MutableBundle. Detection lives
in diagnose.py: the apply engine plans a shard from its findings' migration
ids, so plan output and applied work can never disagree. Every transform is
written to be idempotent and non-lossy; when a shape cannot be transformed
without guessing, it raises MigrationError and the shard is skipped whole.

Sequence order (proposal section 5): 0012 first (it must see the raw member
set), then the legacy splitters, then manifest and soul normalization, with
0008 and 0011 always last.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .bundle import (
    CANONICAL_STATS,
    LEGACY_ASSET_PREFIXES,
    SHELL_KEYS,
    SHELL_STATE_KEYS,
    X_NEXUS_KEYS,
    pillar_variant_members,
)
from .mutable import MigrationError, MutableBundle
from .registry import schema_for_member

# Long-form and case-variant stat keys fold onto the canonical abbreviations.
_STAT_LONG_FORMS = {
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

# Average default when a soul has no stat_block at all (spec 5.1). Matches the
# conformance suite's CANONICAL_STAT_BLOCK fixture value; stamping it is the
# only way a stat-less soul can reach the required ten-stat shape without an
# authoring pass, and the plan output names it before any write happens.
_DEFAULT_STAT = 5

# Stable marker note 0013 emits when it applies the average default. The apply
# engine detects this exact string to log every defaulted soul (spec 5.1
# requires the migrator to record each one), so it must not drift.
STAT_DEFAULT_NOTE = f"0013: no stat_block; stamped average default (all {_DEFAULT_STAT})"

_TIMESTAMP_KEYS = ("created", "last_modified", "modified", "last_modified_utc")

# Keys under which a flat legacy memory dict may carry its entry list.
_FLAT_ENTRY_KEYS = ("memories", "entries", "slots", "log")

_MEMORY_TIERS = ("short_term", "long_term", "core", "archive")


@dataclass(frozen=True)
class Migration:
    id: str
    sequence: int
    description: str
    fn: Callable[[MutableBundle, str], None]


def _m0012_consolidate_pillar_variants(bundle: MutableBundle, target: str) -> None:
    variants = pillar_variant_members(tuple(bundle.members))
    if not variants:
        return

    # If the bundle has no canonical memory pillar but does carry a mislabeled
    # memory variant, adopt the newest variant's content as mindshard.json
    # before displacing. Newest by ZIP mtime, name as the deterministic
    # tie-break. Everything displaced lands in the external backup.
    has_memory = "mindshard.json" in bundle.members or "memoryshard.json" in bundle.members
    memory_variants = [
        name
        for name in variants
        if "/" not in name and name.lower().startswith(("memoryshard", "mindshard"))
    ]
    adopted: str | None = None
    if not has_memory and memory_variants:
        adopted = max(memory_variants, key=lambda n: (bundle.member_times.get(n, ()), n))
        bundle.members["mindshard.json"] = bundle.members[adopted]
        bundle.note(f"0012: adopted {adopted} as mindshard.json")

    for name in variants:
        bundle.displace(name)
    bundle.note(f"0012: displaced {len(variants)} variant member(s) to external backup")


def _m0002_rename_memoryshard(bundle: MutableBundle, target: str) -> None:
    if "memoryshard.json" not in bundle.members:
        return
    if "mindshard.json" in bundle.members:
        bundle.displace("memoryshard.json")
        bundle.note("0002: displaced memoryshard.json (mindshard.json already present)")
    else:
        bundle.rename("memoryshard.json", "mindshard.json")
        bundle.note("0002: renamed memoryshard.json to mindshard.json")


def _m0001_split_legacy_soul(bundle: MutableBundle, target: str) -> None:
    soul = bundle.get_json("soulshard.json")
    if not isinstance(soul, dict):
        raise MigrationError("soulshard.json is missing or not an object")
    shell = bundle.get_json("shellshard.json")
    shell = shell if isinstance(shell, dict) else {}

    moved: list[str] = []
    for key in sorted(SHELL_KEYS):
        if key in soul:
            # The soul copy is what the runtime was using; it wins on collision.
            shell[key] = soul.pop(key)
            moved.append(key)

    state = soul.get("character_state")
    if isinstance(state, dict):
        physical = {key: state.pop(key) for key in sorted(SHELL_STATE_KEYS) if key in state}
        if physical:
            shell_state = shell.get("character_state")
            if not isinstance(shell_state, dict):
                shell_state = {}
            shell_state.update(physical)
            shell["character_state"] = shell_state
            moved.append("character_state." + "/".join(sorted(physical)))
        if not state:
            soul.pop("character_state")

    if moved:
        bundle.put_json("soulshard.json", soul)
        bundle.put_json("shellshard.json", shell)
        bundle.note("0001: moved to shell: " + ", ".join(moved))


def _m0003_flat_memory_to_tiered(bundle: MutableBundle, target: str) -> None:
    mind = bundle.get_json("mindshard.json")
    if mind is None:
        return

    if isinstance(mind, list):
        tiered = _tiered(long_term=mind)
        bundle.put_json("mindshard.json", tiered)
        bundle.note(f"0003: converted flat memory array ({len(mind)} entries) to tiered long_term")
        return

    if not isinstance(mind, dict):
        raise MigrationError("mindshard.json is neither an array nor an object")

    if any(tier in mind for tier in _MEMORY_TIERS):
        # Already tiered; only the internal version is stale.
        if str(mind.get("format_version", "")).startswith("1") or "format_version" not in mind:
            mind["format_version"] = "2.1"
            bundle.put_json("mindshard.json", mind)
            bundle.note("0003: tiered memory kept, format_version stamped 2.1")
        return

    for key in _FLAT_ENTRY_KEYS:
        entries = mind.get(key)
        if isinstance(entries, list):
            rest = {k: v for k, v in mind.items() if k not in (key, "format_version")}
            tiered = _tiered(long_term=entries)
            tiered.update(rest)  # unknown fields ride along, never dropped
            bundle.put_json("mindshard.json", tiered)
            bundle.note(
                f"0003: converted flat memory dict (key {key!r}, {len(entries)} entries) to tiered"
            )
            return

    # Metadata-only legacy shard ({"format_version": "1.0"} and the like):
    # no entries to carry, so empty tiers plus the scalar fields is lossless.
    if all(not isinstance(v, (dict, list)) for v in mind.values()):
        rest = {k: v for k, v in mind.items() if k != "format_version"}
        tiered = _tiered(long_term=[])
        tiered.update(rest)
        bundle.put_json("mindshard.json", tiered)
        bundle.note("0003: metadata-only flat memory converted to empty tiers")
        return

    raise MigrationError("flat mindshard has no recognizable entry list; not transforming blind")


def _tiered(long_term: list[Any]) -> dict[str, Any]:
    return {
        "format_version": "2.1",
        "short_term": {"slots": []},
        "long_term": {"slots": list(long_term)},
        "core": [],
        "archive": [],
    }


def _m0004_drop_memory_format(bundle: MutableBundle, target: str) -> None:
    manifest = bundle.manifest()
    if "memory_format" in manifest:
        manifest.pop("memory_format")
        bundle.put_json("manifest.json", manifest)
        bundle.note("0004: dropped manifest.memory_format")


def _m0005_stamp_spec_version(bundle: MutableBundle, target: str) -> None:
    manifest = bundle.manifest()
    before = manifest.get("spec_version")
    manifest["spec_version"] = target
    manifest["bundle_version"] = target  # deprecated alias, spec section 2.2
    bundle.put_json("manifest.json", manifest)
    bundle.note(f"0005: spec_version {before or '(none)'} -> {target} (alias stamped)")


def _m0006_reconcile_internal_version(bundle: MutableBundle, target: str) -> None:
    # The only known intra-bundle disagreement is manifest.memory_format vs
    # the mindshard's own format_version, and 0004 (sequenced earlier) removes
    # the manifest side entirely: the pillar self-describes, so there is
    # nothing left to negotiate. Guard defensively rather than silently trust.
    manifest = bundle.manifest()
    if "memory_format" in manifest:
        manifest.pop("memory_format")
        bundle.put_json("manifest.json", manifest)
        bundle.note("0006: dropped straggler memory_format (pillar self-describes)")


def _m0007_normalize_timestamps(bundle: MutableBundle, target: str) -> None:
    manifest = bundle.manifest()
    changed = []
    for key in _TIMESTAMP_KEYS:
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        if value.endswith("Z"):
            continue
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise MigrationError(f"manifest.{key} is not a parseable timestamp: {value!r}") from exc
        if parsed.tzinfo is None:
            # shortcut: naive stamps were written by datetime.now() on this
            # machine; local tz is the only defensible assumption.
            parsed = parsed.astimezone()
        manifest[key] = parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        changed.append(key)
    if changed:
        bundle.put_json("manifest.json", manifest)
        bundle.note("0007: normalized to UTC: " + ", ".join(changed))


def _m0010_renest_x_nexus(bundle: MutableBundle, target: str) -> None:
    soul = bundle.get_json("soulshard.json")
    if not isinstance(soul, dict):
        return
    nested = soul.get("x_nexus")
    nested = nested if isinstance(nested, dict) else {}
    moved = []
    for key in sorted(X_NEXUS_KEYS):
        if key in soul:
            # Top level is what the runtime was reading; it wins on collision.
            nested[key] = soul.pop(key)
            moved.append(key)
    if moved:
        soul["x_nexus"] = nested
        bundle.put_json("soulshard.json", soul)
        bundle.note("0010: re-nested under x_nexus: " + ", ".join(moved))


def _m0013_normalize_stat_block(bundle: MutableBundle, target: str) -> None:
    soul = bundle.get_json("soulshard.json")
    if not isinstance(soul, dict):
        return
    block = soul.get("stat_block")

    if not isinstance(block, dict) or not block:
        soul["stat_block"] = {stat: _DEFAULT_STAT for stat in sorted(CANONICAL_STATS)}
        bundle.put_json("soulshard.json", soul)
        bundle.note(STAT_DEFAULT_NOTE)
        return

    normalized: dict[str, Any] = {}
    legacy: dict[str, Any] = {}
    notes: list[str] = []
    for key, value in block.items():
        upper = key.upper()
        canonical = upper if upper in CANONICAL_STATS else _STAT_LONG_FORMS.get(upper)
        if canonical is not None:
            normalized[canonical] = _coerce_stat(canonical, value, notes)
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

    for stat in sorted(CANONICAL_STATS - set(normalized)):
        normalized[stat] = _DEFAULT_STAT
        notes.append(f"missing stat {stat} stamped {_DEFAULT_STAT}")

    soul["stat_block"] = {stat: normalized[stat] for stat in sorted(normalized)}
    if legacy:
        nested = soul.get("x_nexus")
        nested = nested if isinstance(nested, dict) else {}
        legacy_stats = nested.get("legacy_stats")
        legacy_stats = legacy_stats if isinstance(legacy_stats, dict) else {}
        legacy_stats.update(legacy)
        nested["legacy_stats"] = legacy_stats
        soul["x_nexus"] = nested
    bundle.put_json("soulshard.json", soul)
    bundle.note("0013: " + "; ".join(notes) if notes else "0013: stat_block already canonical")


def _coerce_stat(stat: str, value: Any, notes: list[str]) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MigrationError(f"stat_block.{stat} is not numeric: {value!r}")
    coerced = int(round(value))
    clamped = min(10, max(1, coerced))
    if clamped != value:
        notes.append(f"{stat} {value!r} -> {clamped}")
    return clamped


def _m0014_relocate_legacy_assets(bundle: MutableBundle, target: str) -> None:
    """Move legacy top-level asset folders under a single assets/ folder.

    `images/portrait.png` becomes `assets/images/portrait.png`: the origin
    subfolder is preserved and no bytes change. Runs before schema stamping
    (0009) and integrity recompute (0011), so the moved members get
    shardcore/assets@1.0 and correct hashes at their new paths.
    """
    moved: list[str] = []
    for name in list(bundle.members):
        if name.endswith("/") or not name.startswith(LEGACY_ASSET_PREFIXES):
            continue
        new_name = "assets/" + name
        if new_name in bundle.members:
            raise MigrationError(f"asset relocation collision at {new_name}")
        bundle.rename(name, new_name)
        moved.append(name)
    if moved:
        bundle.note(f"0014: relocated {len(moved)} asset member(s) under assets/")


def _m0008_regen_card(bundle: MutableBundle, target: str) -> None:
    soul = bundle.get_json("soulshard.json")
    if not isinstance(soul, dict):
        return
    manifest = bundle.manifest()
    card = manifest.get("card")
    card = dict(card) if isinstance(card, dict) else {}
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
    if card:
        manifest["card"] = card
        bundle.put_json("manifest.json", manifest)
        bundle.note("0008: regenerated manifest.card from soul")


def _m0009_stamp_schema_ids(bundle: MutableBundle, target: str) -> None:
    manifest = bundle.manifest()
    files = manifest.get("files")
    files = files if isinstance(files, dict) else {}
    stamped = []
    for name in bundle.members:
        if name == "manifest.json":
            continue
        schema = schema_for_member(name)
        if schema is None:
            continue
        entry = files.get(name)
        entry = entry if isinstance(entry, dict) else {}
        if entry.get("schema") != schema:
            entry["schema"] = schema
            stamped.append(name)
        files[name] = entry
    manifest["files"] = files
    bundle.put_json("manifest.json", manifest)
    if stamped:
        bundle.note("0009: stamped schema ids on " + ", ".join(sorted(stamped)))


def _m0011_recompute_integrity(bundle: MutableBundle, target: str) -> None:
    manifest = bundle.manifest()
    old = manifest.get("files")
    old = old if isinstance(old, dict) else {}
    files: dict[str, Any] = {}
    for name in sorted(bundle.members):
        if name == "manifest.json":
            continue
        prior = old.get(name)
        entry = dict(prior) if isinstance(prior, dict) else {}
        data = bundle.members[name]
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        entry["size"] = len(data)
        files[name] = entry
    manifest["files"] = files
    bundle.put_json("manifest.json", manifest)
    bundle.note(f"0011: recomputed digests for {len(files)} member(s)")


_ALL = (
    Migration(
        "0012",
        10,
        "consolidate duplicate or mislabeled pillar variants",
        _m0012_consolidate_pillar_variants,
    ),
    Migration("0002", 20, "rename memoryshard.json to mindshard.json", _m0002_rename_memoryshard),
    Migration(
        "0001",
        30,
        "split shell fields out of the soul into shellshard.json",
        _m0001_split_legacy_soul,
    ),
    Migration(
        "0003",
        40,
        "convert flat memory to tiered STM/LTM/core/archive",
        _m0003_flat_memory_to_tiered,
    ),
    Migration("0004", 50, "drop manifest.memory_format", _m0004_drop_memory_format),
    Migration(
        "0005", 60, "collapse version fields into a single spec_version", _m0005_stamp_spec_version
    ),
    Migration(
        "0006",
        70,
        "reconcile intra-bundle version disagreements",
        _m0006_reconcile_internal_version,
    ),
    Migration(
        "0007", 80, "normalize manifest timestamps to ISO-8601 UTC", _m0007_normalize_timestamps
    ),
    Migration("0010", 90, "re-nest recognized runtime fields under x_nexus", _m0010_renest_x_nexus),
    Migration(
        "0014", 95, "relocate legacy asset folders under assets/", _m0014_relocate_legacy_assets
    ),
    Migration(
        "0013", 100, "normalize stat_block to the canonical ten stats", _m0013_normalize_stat_block
    ),
    Migration("0008", 110, "regenerate manifest.card from the soul", _m0008_regen_card),
    Migration("0009", 120, "stamp per-pillar schema ids", _m0009_stamp_schema_ids),
    Migration(
        "0011", 130, "recompute every SHA-256 and rewrite the manifest", _m0011_recompute_integrity
    ),
)

REGISTRY: dict[str, Migration] = {m.id: m for m in _ALL}

# 0008 and 0011 run whenever anything else does (proposal section 5). 0009
# joins them because it must stamp the post-consolidation member set: a plan
# computed on the original bundle cannot know which members will exist after
# 0012/0002 reshuffle them, and 0009 is a no-op when nothing needs stamping.
ALWAYS_RUN = ("0008", "0009", "0011")


def ordered(ids: set[str]) -> list[Migration]:
    """The execution plan for a set of migration ids, in sequence order."""
    if ids:
        ids = ids | set(ALWAYS_RUN)
    if "0012" in ids:
        # Consolidation can adopt a mislabeled memory variant as the mind
        # pillar; the adopted content may be flat, so the tiering pass must
        # follow (it is a no-op on already-tiered memory).
        ids = ids | {"0003"}
    known = [REGISTRY[i] for i in ids if i in REGISTRY]
    return sorted(known, key=lambda m: m.sequence)
