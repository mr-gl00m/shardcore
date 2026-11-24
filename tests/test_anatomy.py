"""The shell anatomy parts map (spec 6) and migration 0017."""

from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from shardcore import core, diagnose, migrate_bundle, read_bundle
from shardcore.model import STATUS_CURRENT
from shardcore.registry import SPEC_VERSION

EXTERNAL = [
    {
        "id": "breast_l",
        "name": "Left Breast",
        "part_type": "organ",
        "accessories": "",
        "size": "Small",
        "stats": {"capacity_ml": 80.0, "sensitivity": 55.0, "elasticity": 3},
        "tags": ["soft"],
    },
    {
        "id": "arm_l",
        "name": "Left Arm",
        "part_type": "limb",
        "accessories": "ring",
        "size": "Custom",
        "tags": [],
    },
]
INTERNAL = [
    {
        "id": "heart",
        "name": "Heart",
        "part_type": "organ",
        "stats": {"sensitivity": 50.0},
        "tags": [],
    }
]


def _shell(**profile: Any) -> dict[str, Any]:
    return {"anatomy_profile": {"template": "humanoid", "height": "170cm", **profile}}


def test_list_shape_becomes_the_parts_map() -> None:
    shell = _shell(
        external_parts=copy.deepcopy(EXTERNAL),
        internal_parts=copy.deepcopy(INTERNAL),
        show_internal=True,
        modifiers=copy.deepcopy(EXTERNAL + INTERNAL),
    )
    notes = core.anatomy_parts_map(shell)
    profile = shell["anatomy_profile"]
    assert notes and set(profile) == {"template", "height", "parts"}
    parts = profile["parts"]
    assert list(parts) == ["breast_l", "arm_l", "heart"]
    assert parts["breast_l"] == {
        "id": "breast_l",
        "name": "Left Breast",
        "part_type": "organ",
        "size": "Small",
        "capacity_ml": 80.0,
        "sensitivity": 55.0,
        "stats": {"elasticity": 3},
        "tags": ["soft"],
    }
    assert "size" not in parts["arm_l"] and parts["arm_l"]["accessories"] == "ring"
    assert parts["heart"]["tags"] == ["internal"]
    assert core.anatomy_parts_map(shell) == []  # already the map: nothing to do


def test_legacy_modifiers_alone_are_read() -> None:
    legacy = copy.deepcopy(EXTERNAL) + [{**INTERNAL[0], "tags": ["internal"]}]
    shell = _shell(modifiers=legacy)
    core.anatomy_parts_map(shell)
    assert list(shell["anatomy_profile"]["parts"]) == ["breast_l", "arm_l", "heart"]


def test_the_map_wins_over_list_copies_and_keeps_unmapped_list_parts() -> None:
    mapped = {
        "breast_l": {
            "id": "breast_l",
            "name": "Left Breast",
            "size": "DDD",
            "current_stored_ml": 40,
        }
    }
    shell = _shell(parts=copy.deepcopy(mapped), external_parts=copy.deepcopy(EXTERNAL))
    core.anatomy_parts_map(shell)
    parts = shell["anatomy_profile"]["parts"]
    assert parts["breast_l"] == mapped["breast_l"]
    assert "arm_l" in parts
    assert "external_parts" not in shell["anatomy_profile"]


def test_a_profile_without_parts_gets_an_empty_map() -> None:
    shell = {"anatomy_profile": {"build": "slim"}}
    core.anatomy_parts_map(shell)
    assert shell["anatomy_profile"] == {"build": "slim", "parts": {}}


def test_strict_never_guesses_ids() -> None:
    nameless = _shell(external_parts=[{"name": "Tail", "part_type": "appendage"}])
    with pytest.raises(ValueError, match="without an id"):
        core.anatomy_parts_map(copy.deepcopy(nameless), strict=True)
    core.anatomy_parts_map(nameless)
    assert list(nameless["anatomy_profile"]["parts"]) == ["tail"]

    clash = _shell(external_parts=[{"id": "x", "name": "A"}, {"id": "x", "name": "B"}])
    with pytest.raises(ValueError, match="share the id"):
        core.anatomy_parts_map(copy.deepcopy(clash), strict=True)
    core.anatomy_parts_map(clash)
    assert sorted(clash["anatomy_profile"]["parts"]) == ["x", "x_2"]


def _bundle(path: Path, soul: dict[str, Any], shell: dict[str, Any] | None, version: str) -> Path:
    members = {"soulshard.json": json.dumps(soul).encode()}
    if shell is not None:
        members["shellshard.json"] = json.dumps(shell).encode()
    files = {
        name: {
            "schema": core.schema_for_member(name),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
        for name, data in members.items()
    }
    manifest = {
        "spec_version": version,
        "bundle_version": version,
        "shard_name": soul["name"],
        "shard_id": "anatomy-0001",
        "created": "2026-11-01T00:00:00Z",
        "last_modified_utc": "2026-11-01T00:00:00Z",
        "files": files,
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, data in members.items():
            archive.writestr(name, data)
    return path


SOUL = {
    "name": "Listed",
    "identity": "x",
    "personality": "y",
    "stat_block": {s: 5 for s in core.CANONICAL_STATS},
}


def test_migration_0017_makes_a_list_shell_current(tmp_path: Path) -> None:
    shard = _bundle(
        tmp_path / "listed.shard",
        SOUL,
        _shell(external_parts=copy.deepcopy(EXTERNAL)),
        SPEC_VERSION,
    )
    assert "anatomy_list_shape" in {
        f.code for f in diagnose(read_bundle(shard), SPEC_VERSION).findings
    }
    notes = migrate_bundle(shard)
    assert any(note.startswith("0017") for note in notes)
    assert diagnose(read_bundle(shard), SPEC_VERSION).status == STATUS_CURRENT
    with zipfile.ZipFile(shard) as archive:
        shell = json.loads(archive.read("shellshard.json"))
        manifest = json.loads(archive.read("manifest.json"))
    assert set(shell["anatomy_profile"]["parts"]) == {"breast_l", "arm_l"}
    assert manifest["files"]["shellshard.json"]["schema"] == "shardcore/shell@1.12"


def test_anatomy_moved_out_of_the_soul_is_mapped_too(tmp_path: Path) -> None:
    soul = {
        **SOUL,
        "anatomy_profile": {"template": "humanoid", "external_parts": copy.deepcopy(EXTERNAL)},
    }
    shard = _bundle(tmp_path / "soulside.shard", soul, None, "1.10")
    migrate_bundle(shard)
    assert diagnose(read_bundle(shard), SPEC_VERSION).status == STATUS_CURRENT
    with zipfile.ZipFile(shard) as archive:
        shell = json.loads(archive.read("shellshard.json"))
    assert "parts" in shell["anatomy_profile"] and "external_parts" not in shell["anatomy_profile"]
