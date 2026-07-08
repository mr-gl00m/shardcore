"""Unit tests for the v1.9 migration chain transforms."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from shardcore.migrations import REGISTRY, ordered
from shardcore.mutable import MigrationError, MutableBundle

TARGET = "1.9"


def _dump(obj: Any) -> bytes:
    return json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")


def make_bundle(
    pillars: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    times: dict[str, tuple[int, ...]] | None = None,
) -> MutableBundle:
    members = {"manifest.json": _dump(manifest if manifest is not None else {"shard_name": "T"})}
    for name, obj in pillars.items():
        members[name] = _dump(obj)
    return MutableBundle(Path("synthetic.shard"), members, times or {})


def run(migration_id: str, bundle: MutableBundle) -> None:
    REGISTRY[migration_id].fn(bundle, TARGET)


# ---- ordering ---------------------------------------------------------------


def test_ordered_forces_finalizers_and_sequences() -> None:
    plan = ordered({"0005", "0012", "0001"})
    ids = [m.id for m in plan]
    # 0008/0009/0011 always run; 0012 pulls in 0003 for adopted memory variants
    assert ids == ["0012", "0001", "0003", "0005", "0008", "0009", "0011"]


def test_ordered_empty_plan_stays_empty() -> None:
    assert ordered(set()) == []


# ---- 0002 rename ------------------------------------------------------------


def test_0002_renames_memoryshard() -> None:
    bundle = make_bundle({"memoryshard.json": {"format_version": "2.1"}})
    run("0002", bundle)
    assert "mindshard.json" in bundle.members
    assert "memoryshard.json" not in bundle.members


def test_0002_dual_pillars_displaces_memoryshard() -> None:
    bundle = make_bundle(
        {"memoryshard.json": {"old": True}, "mindshard.json": {"format_version": "2.1"}}
    )
    run("0002", bundle)
    assert "memoryshard.json" not in bundle.members
    assert "memoryshard.json" in bundle.displaced
    assert bundle.get_json("mindshard.json") == {"format_version": "2.1"}


# ---- 0003 flat memory -------------------------------------------------------


def test_0003_flat_array_to_tiered() -> None:
    entries = [{"entry": "one"}, {"entry": "two"}]
    bundle = make_bundle({"mindshard.json": entries})
    run("0003", bundle)
    mind = bundle.get_json("mindshard.json")
    assert mind["format_version"] == "2.1"
    assert mind["long_term"]["slots"] == entries
    assert mind["short_term"]["slots"] == []
    assert mind["core"] == [] and mind["archive"] == []


def test_0003_metadata_only_dict_to_empty_tiers() -> None:
    bundle = make_bundle({"mindshard.json": {"format_version": "1.0", "session_counter": 3}})
    run("0003", bundle)
    mind = bundle.get_json("mindshard.json")
    assert mind["format_version"] == "2.1"
    assert mind["long_term"]["slots"] == []
    assert mind["session_counter"] == 3


def test_0003_tiered_v1_gets_version_bump_only() -> None:
    tiers = {"format_version": "1.5", "short_term": {"slots": [{"a": 1}]}, "core": []}
    bundle = make_bundle({"mindshard.json": tiers})
    run("0003", bundle)
    mind = bundle.get_json("mindshard.json")
    assert mind["format_version"] == "2.1"
    assert mind["short_term"]["slots"] == [{"a": 1}]


def test_0003_unrecognizable_shape_refuses() -> None:
    bundle = make_bundle({"mindshard.json": {"format_version": "1.0", "blob": {"nested": True}}})
    with pytest.raises(MigrationError):
        run("0003", bundle)


# ---- 0001 shell split -------------------------------------------------------


def test_0001_moves_shell_fields_and_physical_state() -> None:
    soul = {
        "name": "N",
        "anatomy_profile": {"type": "human"},
        "identity_image_path": "n.png",
        "character_state": {"breast_size": "D", "morale": 80},
    }
    bundle = make_bundle({"soulshard.json": soul})
    run("0001", bundle)
    new_soul = bundle.get_json("soulshard.json")
    shell = bundle.get_json("shellshard.json")
    assert "anatomy_profile" not in new_soul
    assert "identity_image_path" not in new_soul
    assert new_soul["character_state"] == {"morale": 80}
    assert shell["anatomy_profile"] == {"type": "human"}
    assert shell["identity_image_path"] == "n.png"
    assert shell["character_state"] == {"breast_size": "D"}


def test_0001_soul_copy_wins_over_existing_shell() -> None:
    bundle = make_bundle(
        {
            "soulshard.json": {"name": "N", "anatomy_profile": {"type": "new"}},
            "shellshard.json": {"anatomy_profile": {"type": "stale"}},
        }
    )
    run("0001", bundle)
    assert bundle.get_json("shellshard.json")["anatomy_profile"] == {"type": "new"}


# ---- 0004 / 0005 / 0007 manifest --------------------------------------------


def test_0004_drops_memory_format() -> None:
    bundle = make_bundle({}, manifest={"shard_name": "T", "memory_format": "none"})
    run("0004", bundle)
    assert "memory_format" not in bundle.manifest()


def test_0005_stamps_spec_version_and_alias() -> None:
    bundle = make_bundle({}, manifest={"shard_name": "T", "bundle_version": "1.1"})
    run("0005", bundle)
    manifest = bundle.manifest()
    assert manifest["spec_version"] == TARGET
    assert manifest["bundle_version"] == TARGET


def test_0007_normalizes_naive_and_offset_timestamps() -> None:
    bundle = make_bundle(
        {},
        manifest={
            "shard_name": "T",
            "created": "2026-03-31T22:39:42.655247",
            "last_modified": "2026-03-31T22:39:42+02:00",
        },
    )
    run("0007", bundle)
    manifest = bundle.manifest()
    assert manifest["created"].endswith("Z")
    assert manifest["last_modified"] == "2026-03-31T20:39:42Z"


def test_0007_unparseable_timestamp_refuses() -> None:
    bundle = make_bundle({}, manifest={"shard_name": "T", "created": "sometime last week"})
    with pytest.raises(MigrationError):
        run("0007", bundle)


# ---- 0010 x_nexus -----------------------------------------------------------


def test_0010_renests_runtime_fields() -> None:
    soul = {
        "name": "N",
        "reicodex_commands": {"cmd": 1},
        "x_nexus": {"eidolon_signature": "keep"},
        "preservation_state": {"portable": True},
    }
    bundle = make_bundle({"soulshard.json": soul})
    run("0010", bundle)
    new_soul = bundle.get_json("soulshard.json")
    assert "reicodex_commands" not in new_soul
    assert new_soul["x_nexus"]["reicodex_commands"] == {"cmd": 1}
    assert new_soul["x_nexus"]["eidolon_signature"] == "keep"
    # preservation_state is a portable soul field (spec 5.2), never re-nested
    assert new_soul["preservation_state"] == {"portable": True}


# ---- 0013 stat block --------------------------------------------------------


def test_0013_folds_long_forms_and_case_variants() -> None:
    block = {
        "Presence": 7,
        "acu": 6,
        "STR": 5,
        "END": 5,
        "VIG": 5,
        "DEX": 5,
        "TMP": 5,
        "INS": 5,
        "ATT": 5,
        "CNV": 5,
    }
    bundle = make_bundle({"soulshard.json": {"name": "N", "stat_block": block}})
    run("0013", bundle)
    stats = bundle.get_json("soulshard.json")["stat_block"]
    assert stats["PRS"] == 7
    assert stats["ACU"] == 6
    assert set(stats) == {"STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS"}


def test_0013_relocates_resonance_to_soul() -> None:
    block = {
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
        "Resonance": "Champagne Fizz",
    }
    bundle = make_bundle({"soulshard.json": {"name": "N", "stat_block": block}})
    run("0013", bundle)
    soul = bundle.get_json("soulshard.json")
    assert soul["resonance"] == "Champagne Fizz"
    assert "Resonance" not in soul["stat_block"]


def test_0013_missing_block_stamps_average_default() -> None:
    from shardcore.migrations import STAT_DEFAULT_NOTE

    bundle = make_bundle({"soulshard.json": {"name": "N"}})
    run("0013", bundle)
    stats = bundle.get_json("soulshard.json")["stat_block"]
    assert len(stats) == 10
    assert set(stats.values()) == {5}
    # The stable marker note must be emitted so apply can log the defaulted soul.
    assert STAT_DEFAULT_NOTE in bundle.notes


def test_0013_unknown_keys_preserved_under_legacy_stats() -> None:
    block = {
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
        "Luck": 9,
    }
    bundle = make_bundle({"soulshard.json": {"name": "N", "stat_block": block}})
    run("0013", bundle)
    soul = bundle.get_json("soulshard.json")
    assert "Luck" not in soul["stat_block"]
    assert soul["x_nexus"]["legacy_stats"]["Luck"] == 9


def test_0013_clamps_out_of_range_values() -> None:
    block = {
        "STR": 14,
        "END": 0,
        "VIG": 5.6,
        "DEX": 5,
        "TMP": 5,
        "ACU": 5,
        "INS": 5,
        "ATT": 5,
        "CNV": 5,
        "PRS": 5,
    }
    bundle = make_bundle({"soulshard.json": {"name": "N", "stat_block": block}})
    run("0013", bundle)
    stats = bundle.get_json("soulshard.json")["stat_block"]
    assert stats["STR"] == 10
    assert stats["END"] == 1
    assert stats["VIG"] == 6


def test_0013_non_numeric_stat_refuses() -> None:
    block = {
        "STR": "high",
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
    bundle = make_bundle({"soulshard.json": {"name": "N", "stat_block": block}})
    with pytest.raises(MigrationError):
        run("0013", bundle)


# ---- 0012 consolidation -----------------------------------------------------


def test_0012_displaces_variants_and_adopts_memory() -> None:
    bundle = make_bundle(
        {
            "soulshard.json": {"name": "N"},
            "memoryshard_soulshard_2026.json": {"format_version": "2.1", "core": []},
            "soulshard.json.sha256": {"digest": "x"},
            "backups/soulshard_old.json": {"name": "old"},
        },
        times={
            "memoryshard_soulshard_2026.json": (2026, 1, 1, 0, 0, 0),
        },
    )
    run("0012", bundle)
    assert "mindshard.json" in bundle.members
    assert bundle.get_json("mindshard.json") == {"format_version": "2.1", "core": []}
    assert "memoryshard_soulshard_2026.json" in bundle.displaced
    assert "soulshard.json.sha256" in bundle.displaced
    assert "backups/soulshard_old.json" in bundle.displaced


def test_0012_does_not_adopt_when_canonical_memory_exists() -> None:
    bundle = make_bundle(
        {
            "soulshard.json": {"name": "N"},
            "mindshard.json": {"format_version": "2.1", "core": ["real"]},
            "memoryshard_extra.json": {"core": ["stale"]},
        }
    )
    run("0012", bundle)
    assert bundle.get_json("mindshard.json") == {"format_version": "2.1", "core": ["real"]}
    assert "memoryshard_extra.json" in bundle.displaced


# ---- 0008 / 0009 / 0011 manifest regeneration --------------------------------


def test_0008_regenerates_card_from_soul() -> None:
    soul = {"name": "Aria", "core_essence": "Curious.", "trait_tags": ["curious", "careful"]}
    bundle = make_bundle(
        {"soulshard.json": soul}, manifest={"shard_name": "Aria", "card": {"name": "Old"}}
    )
    run("0008", bundle)
    card = bundle.manifest()["card"]
    assert card["name"] == "Aria"
    assert card["core_essence"] == "Curious."
    assert card["tags"] == ["curious", "careful"]


def test_0009_stamps_schema_ids_including_assets() -> None:
    bundle = make_bundle(
        {"soulshard.json": {"name": "N"}, "mindshard.json": {"format_version": "2.1"}}
    )
    bundle.members["assets/images/portrait.png"] = b"\x89PNG fake"
    bundle.members["vendor_blob.dat"] = b"opaque unknown"
    run("0009", bundle)
    files = bundle.manifest()["files"]
    assert files["soulshard.json"]["schema"] == "shardcore/soul@1.9"
    assert files["mindshard.json"]["schema"] == "shardcore/mind@2.1"
    # Everything under assets/ carries the one asset schema (spec 2.3).
    assert files["assets/images/portrait.png"]["schema"] == "shardcore/assets@1.0"
    # A truly unmappable member still gets no invented schema id.
    assert "schema" not in files.get("vendor_blob.dat", {})


def test_0014_relocates_legacy_asset_folders() -> None:
    bundle = make_bundle({"soulshard.json": {"name": "N"}})
    bundle.members["images/portrait.png"] = b"img"
    bundle.members["attestations/receipt.ots"] = b"ots"
    bundle.members["skills/cook.json"] = b"{}"
    run("0014", bundle)
    assert "assets/images/portrait.png" in bundle.members
    assert "assets/attestations/receipt.ots" in bundle.members
    assert "assets/skills/cook.json" in bundle.members
    assert "images/portrait.png" not in bundle.members
    assert "attestations/receipt.ots" not in bundle.members
    assert "skills/cook.json" not in bundle.members


def test_0011_recomputes_hashes_and_prunes_gone_members() -> None:
    import hashlib

    bundle = make_bundle(
        {"soulshard.json": {"name": "N"}},
        manifest={
            "shard_name": "N",
            "files": {
                "soulshard.json": {"schema": "shardcore/soul@1.9", "sha256": "stale", "size": 0},
                "ghost.json": {"sha256": "0" * 64, "size": 2},
            },
        },
    )
    run("0011", bundle)
    files = bundle.manifest()["files"]
    assert "ghost.json" not in files
    entry = files["soulshard.json"]
    assert entry["schema"] == "shardcore/soul@1.9"
    assert entry["sha256"] == hashlib.sha256(bundle.members["soulshard.json"]).hexdigest()
    assert entry["size"] == len(bundle.members["soulshard.json"])
