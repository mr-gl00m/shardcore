"""Reader and integrity tests."""

from __future__ import annotations

from pathlib import Path

from conftest import TEST_SHARD_ID, build_shard, current_bundle

from shardcore.bundle import read_bundle
from shardcore.registry import SPEC_VERSION


def test_reads_good_bundle(tmp_path: Path) -> None:
    shard = current_bundle(tmp_path / "good.shard")
    state = read_bundle(shard)

    assert state.readable
    assert state.is_zip
    assert state.manifest_present
    assert state.identity == "Test One"
    assert state.spec_version == SPEC_VERSION
    assert state.shard_id == TEST_SHARD_ID
    assert state.shard_id_error is None
    assert state.lineage_errors == ()
    assert state.integrity_ok
    assert state.mind_format_version == "2.1"


def test_reads_identity_and_lineage_problems(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "rei_branch_like.shard",
        pillars={"soulshard.json": {"name": "Branch"}},
        manifest={
            "spec_version": "1.9",
            "shard_name": "Branch",
            "shard_id": "",
            "lineage": {"parent": "genesis.shard"},
        },
    )
    state = read_bundle(shard)

    assert state.shard_id is None
    assert state.shard_id_error == "shard_id must be a non-empty string"
    assert state.lineage_errors
    assert "relationship" in state.lineage_errors[0]


def test_detects_hash_mismatch(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "bad.shard",
        pillars={"soulshard.json": {"name": "Broken"}},
        manifest={"spec_version": "1.1", "shard_name": "Broken"},
        corrupt="soulshard.json",
    )
    state = read_bundle(shard)

    assert state.readable
    assert not state.integrity_ok
    soul = next(p for p in state.pillars if p.name == "soulshard.json")
    assert not soul.integrity_ok
    assert soul.computed_sha256 != soul.manifest_sha256


def test_non_zip_is_unreadable(tmp_path: Path) -> None:
    shard = tmp_path / "junk.shard"
    shard.write_text("this is not a zip", encoding="utf-8")
    state = read_bundle(shard)

    assert not state.readable
    assert not state.is_zip
    assert state.error is not None


def test_missing_manifest_is_unreadable(tmp_path: Path) -> None:
    import zipfile

    shard = tmp_path / "nomanifest.shard"
    with zipfile.ZipFile(shard, "w") as archive:
        archive.writestr("soulshard.json", "{}")
    state = read_bundle(shard)

    assert not state.readable
    assert state.is_zip
    assert state.error is not None and "manifest" in state.error


def test_derives_identity_from_soul_when_manifest_bare(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "bare.shard",
        pillars={"soulshard.json": {"name": "From Soul"}},
        manifest={"spec_version": "1.1"},
    )
    state = read_bundle(shard)
    assert state.identity == "From Soul"
