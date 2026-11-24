"""Identity and lineage tests (spec section 11.4)."""

from __future__ import annotations

import json
import uuid
import zipfile
from pathlib import Path
from typing import Any

import pytest
from conftest import CANONICAL_STAT_BLOCK, build_shard

from shardcore import (
    build_bundle,
    derived_shard_id,
    diagnose,
    json_member_bytes,
    lineage_errors,
    manifest_digest,
    migrate_bundle,
    new_shard_id,
    offspring_lineage,
    read_bundle,
    read_bundle_document,
    shard_id_error,
)
from shardcore.builder import BundleBuildError
from shardcore.document import BundleDocument
from shardcore.model import STATUS_CURRENT
from shardcore.registry import SPEC_VERSION

STAMP = "2026-10-16T00:00:00Z"
HASH_A = "a" * 64
HASH_B = "b" * 64


def soul(name: str) -> bytes:
    return json_member_bytes(
        {
            "name": name,
            "identity": f"{name} is a lineage fixture.",
            "personality": "Deterministic.",
            "stat_block": dict(CANONICAL_STAT_BLOCK),
        }
    )


def parent(tmp_path: Path, name: str, shard_id: str) -> BundleDocument:
    return build_bundle(
        tmp_path / f"{name.lower()}.shard",
        shard_name=name,
        members={"soulshard.json": soul(name)},
        manifest_fields={"card": {"name": name}},
        shard_id=shard_id,
        created=STAMP,
    )


# ---- shard_id -----------------------------------------------------------------


def test_new_shard_id_is_random_uuid4() -> None:
    first, second = new_shard_id(), new_shard_id()
    assert first != second
    assert uuid.UUID(first).version == 4
    assert first == first.lower()


def test_derived_shard_id_is_stable_uuid5() -> None:
    assert derived_shard_id(HASH_A) == derived_shard_id(HASH_A)
    assert derived_shard_id(HASH_A) != derived_shard_id(HASH_B)
    assert uuid.UUID(derived_shard_id(HASH_A)).version == 5


@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "", None])
def test_derived_shard_id_rejects_non_digests(bad: Any) -> None:
    with pytest.raises(ValueError):
        derived_shard_id(bad)


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("6f1c0d2e-4b8a-4c3e-9a51-2d7e8f90b1a4", True),
        ("popeye-prime", True),  # addendum 3.1's slug-style id stays valid
        ("", False),
        ("   ", False),
        (42, False),
        ("x" * 129, False),
        ("tab\there", False),
    ],
)
def test_shard_id_error(value: Any, valid: bool) -> None:
    assert (shard_id_error(value) is None) is valid


# ---- lineage validation ---------------------------------------------------------


def test_offspring_two_parents_is_valid() -> None:
    lineage = {
        "relationship": "offspring",
        "parents": [
            {"role": "dam", "shard_id": "dam-id", "manifest_sha256": HASH_A, "label": "Dam"},
            {"role": "sire", "manifest_sha256": HASH_B},
        ],
    }
    assert lineage_errors(lineage) == []


def test_offspring_single_parent_clone_is_valid() -> None:
    lineage = {
        "relationship": "offspring",
        "parents": [{"role": "source", "manifest_sha256": HASH_A}],
    }
    assert lineage_errors(lineage) == []


def test_branch_addendum_example_is_valid() -> None:
    lineage = {
        "relationship": "interpretation",
        "parent": {"shard_id": "popeye-prime", "manifest_sha256": HASH_A, "label": "Popeye"},
        "ancestry": ["popeye-prime"],
        "origin_appearance": {"work": "Thimble Theatre", "year": 1929},
        "branch_point": {"inherited_canon": ["canon-0001"], "dropped_canon": ["canon-0005"]},
    }
    assert lineage_errors(lineage) == []


@pytest.mark.parametrize(
    ("lineage", "expected"),
    [
        ("parent.shard", "must be an object"),
        ({"parent": "genesis.shard"}, "relationship"),
        ({"relationship": ["offspring"]}, "relationship"),
        ({"relationship": "sibling"}, "relationship"),
        ({"relationship": "offspring", "parents": []}, "non-empty array"),
        ({"relationship": "offspring", "parents": ["dam"]}, "must be an object"),
        (
            {"relationship": "offspring", "parents": [{"manifest_sha256": HASH_A}]},
            "role must be a non-empty string",
        ),
        (
            {"relationship": "offspring", "parents": [{"role": "dam", "manifest_sha256": "abc"}]},
            "manifest_sha256",
        ),
        (
            {
                "relationship": "offspring",
                "parents": [{"role": "dam", "manifest_sha256": HASH_A, "shard_id": 7}],
            },
            "parents[0].shard_id",
        ),
        (
            {
                "relationship": "offspring",
                "parents": [{"role": "dam", "manifest_sha256": HASH_A}],
                "branch_point": {"inherited_canon": ["canon-0001"]},
            },
            "branch_point is not allowed for offspring",
        ),
        (
            {
                "relationship": "offspring",
                "parents": [{"role": "dam", "manifest_sha256": HASH_A}],
                "ancestry": ["grandparent"],
            },
            "ancestry is not allowed for offspring",
        ),
        ({"relationship": "derivative", "parent": "genesis.shard"}, "parent must be an object"),
        (
            {
                "relationship": "derivative",
                "parent": {"manifest_sha256": HASH_A},
                "parents": [{"role": "dam", "manifest_sha256": HASH_A}],
            },
            "only allowed for offspring",
        ),
        (
            {"relationship": "original", "parent": {"manifest_sha256": HASH_A}},
            "not allowed for an original",
        ),
    ],
)
def test_lineage_errors_name_the_problem(lineage: Any, expected: str) -> None:
    errors = lineage_errors(lineage)
    assert errors, f"expected an error for {lineage!r}"
    assert any(expected in error for error in errors), errors


# ---- breeding through the reference writer -------------------------------------


def test_offspring_flow_pins_verified_parents(tmp_path: Path) -> None:
    dam = parent(tmp_path, "Akane", "dam-0001")
    sire = parent(tmp_path, "Hebiko", "sire-0001")

    lineage = offspring_lineage([("dam", dam), ("sire", sire)])
    child = build_bundle(
        tmp_path / "kit.shard",
        shard_name="Kit",
        members={"soulshard.json": soul("Kit")},
        manifest_fields={"lineage": lineage},
        created=STAMP,
    )

    recorded = child.manifest()["lineage"]
    assert recorded["relationship"] == "offspring"
    assert [p["role"] for p in recorded["parents"]] == ["dam", "sire"]
    assert recorded["parents"][0] == {
        "role": "dam",
        "shard_id": "dam-0001",
        "manifest_sha256": dam.manifest_sha256,
        "label": "Akane",
    }
    assert recorded["parents"][1]["manifest_sha256"] == sire.manifest_sha256
    assert child.state.shard_id not in {"dam-0001", "sire-0001"}
    assert "parent" not in recorded and "branch_point" not in recorded

    diag = diagnose(child.state, SPEC_VERSION)
    assert diag.status == STATUS_CURRENT
    assert [f.code for f in diag.findings if f.severity != "info"] == []


def test_parent_pin_matches_independent_digest(tmp_path: Path) -> None:
    dam = parent(tmp_path, "Akane", "dam-0001")
    with zipfile.ZipFile(dam.path) as archive:
        on_disk = json.loads(archive.read("manifest.json"))
    lineage = offspring_lineage([("source", dam)])
    assert lineage["parents"][0]["manifest_sha256"] == manifest_digest(on_disk)


def test_offspring_lineage_refuses_bad_input(tmp_path: Path) -> None:
    dam = parent(tmp_path, "Akane", "dam-0001")
    with pytest.raises(ValueError, match="at least one parent"):
        offspring_lineage([])
    with pytest.raises(ValueError, match="role"):
        offspring_lineage([(" ", dam)])

    broken = build_shard(
        tmp_path / "broken_id.shard",
        pillars={"soulshard.json": {"name": "Broken"}},
        manifest={"spec_version": "1.10", "shard_name": "Broken", "shard_id": 42},
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )
    with pytest.raises(ValueError, match="shard_id"):
        offspring_lineage([("dam", read_bundle_document(broken))])


def test_builder_mints_id_by_default(tmp_path: Path) -> None:
    built = build_bundle(
        tmp_path / "fresh.shard", shard_name="Fresh", members={"soulshard.json": soul("Fresh")}
    )
    assert uuid.UUID(built.manifest()["shard_id"]).version == 4
    assert built.manifest()["spec_version"] == SPEC_VERSION
    assert built.manifest()["revision"] == {"n": 1}


def test_builder_refuses_reused_parent_id(tmp_path: Path) -> None:
    dam = parent(tmp_path, "Akane", "dam-0001")
    with pytest.raises(BundleBuildError, match="reuses a parent"):
        build_bundle(
            tmp_path / "clone.shard",
            shard_name="Clone",
            members={"soulshard.json": soul("Clone")},
            manifest_fields={"lineage": offspring_lineage([("source", dam)])},
            shard_id="dam-0001",
        )


def test_builder_refuses_invalid_identity_and_lineage(tmp_path: Path) -> None:
    members = {"soulshard.json": soul("Bad")}
    with pytest.raises(BundleBuildError, match="reserved"):
        build_bundle(
            tmp_path / "a.shard",
            shard_name="Bad",
            members=members,
            manifest_fields={"shard_id": "x"},
        )
    with pytest.raises(BundleBuildError, match="shard_id"):
        build_bundle(tmp_path / "b.shard", shard_name="Bad", members=members, shard_id="")
    with pytest.raises(BundleBuildError, match="invalid lineage"):
        build_bundle(
            tmp_path / "c.shard",
            shard_name="Bad",
            members=members,
            manifest_fields={"lineage": {"relationship": "offspring", "parents": []}},
        )
    assert not any(tmp_path.glob("*.shard"))


# ---- migration end to end -------------------------------------------------------


def _v19_bundle(path: Path) -> Path:
    return build_shard(
        path,
        pillars={"soulshard.json": {"name": "Nine", "stat_block": dict(CANONICAL_STAT_BLOCK)}},
        manifest={
            "spec_version": "1.9",
            "bundle_version": "1.9",
            "shard_name": "Nine",
            "created": STAMP,
            "last_modified_utc": STAMP,
        },
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def test_migrate_v1_9_to_current(tmp_path: Path) -> None:
    source = _v19_bundle(tmp_path / "nine.shard")
    with zipfile.ZipFile(source) as archive:
        source_manifest = json.loads(archive.read("manifest.json"))

    first = tmp_path / "first.shard"
    second = tmp_path / "second.shard"
    notes = migrate_bundle(source, out=first)
    migrate_bundle(source, out=second)

    assert any(note.startswith("0015") for note in notes)
    migrated = read_bundle_document(first).manifest()
    assert migrated["spec_version"] == SPEC_VERSION
    assert migrated["bundle_version"] == SPEC_VERSION
    pin = manifest_digest(source_manifest)
    assert migrated["revision"] == {"n": 1, "prior": pin, "history": [pin]}
    assert migrated["shard_id"] == derived_shard_id(manifest_digest(source_manifest))
    assert read_bundle_document(second).manifest()["shard_id"] == migrated["shard_id"]

    assert diagnose(read_bundle(first), SPEC_VERSION).status == STATUS_CURRENT
    assert migrate_bundle(first) == []
