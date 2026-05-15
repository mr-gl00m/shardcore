"""Conformance — spec §3 (soul), §4 (shell), §5 (mind).

A v1.0 runtime that reads a three-pillar bundle MUST:
  - surface every required soulshard field (name, stat_block, etc.);
  - preserve unknown fields on save (forward compatibility, §17.3);
  - produce a semantically-equal manifest when rewriting the same bundle
    from the same inputs.

This test loads the standard bundle, pulls canonical fields, rewrites
it, and diffs. "Byte-identical" is too strong (zip timestamps, compress
order) — we require **content hash equality** on each pillar after
rewrite.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from shardcore.verify import verify_bundle

from .conftest import (
    build_bundle,
    minimal_soulshard,
    standard_mindshard,
    standard_shellshard,
)


def _read_pillar(bundle: Path, name: str) -> bytes:
    with zipfile.ZipFile(bundle, "r") as zf:
        return zf.read(name)


def _read_manifest(bundle: Path) -> dict:
    return json.loads(_read_pillar(bundle, "manifest.json"))


# ─── Required-field surfacing ────────────────────────────────

def test_soulshard_required_fields_present(standard_bundle: Path):
    soul = json.loads(_read_pillar(standard_bundle, "soulshard.json"))
    for key in ("name", "identity", "personality", "stat_block"):
        assert key in soul, f"soulshard missing required field: {key}"
    for stat in ("STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS"):
        assert stat in soul["stat_block"], f"stat_block missing required stat: {stat}"
        assert 1 <= soul["stat_block"][stat] <= 10


def test_shellshard_canonical_fields_present(standard_bundle: Path):
    shell = json.loads(_read_pillar(standard_bundle, "shellshard.json"))
    assert "anatomy_profile" in shell
    assert "character_state" in shell


def test_mindshard_has_version_and_tiers(standard_bundle: Path):
    mind = json.loads(_read_pillar(standard_bundle, "mindshard.json"))
    assert mind.get("version") in ("2.0", "2.1")
    for tier in ("short_term", "long_term", "core", "archive"):
        assert tier in mind, f"mindshard missing tier: {tier}"
        assert isinstance(mind[tier], list)


# ─── Manifest integrity on a three-pillar bundle ─────────────

def test_manifest_lists_every_pillar(standard_bundle: Path):
    manifest = _read_manifest(standard_bundle)
    files = manifest["files"]
    for pillar in ("soulshard.json", "shellshard.json", "mindshard.json"):
        assert pillar in files
        entry = files[pillar]
        assert "sha256" in entry and "size" in entry
        assert len(entry["sha256"]) == 64
        assert entry["size"] == len(_read_pillar(standard_bundle, pillar))


def test_manifest_digests_match_actual_bytes(standard_bundle: Path):
    manifest = _read_manifest(standard_bundle)
    for name, meta in manifest["files"].items():
        actual = hashlib.sha256(_read_pillar(standard_bundle, name)).hexdigest()
        assert actual == meta["sha256"], f"digest mismatch for {name}"


# ─── Semantic round-trip ─────────────────────────────────────

def test_rewriting_same_inputs_produces_same_digests(tmp_path: Path):
    a = build_bundle(
        tmp_path / "a.shard",
        soul=minimal_soulshard(),
        shell=standard_shellshard(),
        mind=standard_mindshard(),
    )
    b = build_bundle(
        tmp_path / "b.shard",
        soul=minimal_soulshard(),
        shell=standard_shellshard(),
        mind=standard_mindshard(),
    )
    man_a = _read_manifest(a)["files"]
    man_b = _read_manifest(b)["files"]
    for name in man_a:
        assert man_a[name]["sha256"] == man_b[name]["sha256"], (
            f"canonical serialization should produce identical digest for {name}"
        )


def test_unknown_fields_are_preserved_on_reparse(standard_bundle: Path, tmp_path: Path):
    """Spec §17.3 — unknown fields MUST survive a load/save cycle."""
    soul = json.loads(_read_pillar(standard_bundle, "soulshard.json"))
    soul["__future_field__"] = {"invented_by": "v1.1", "payload": [1, 2, 3]}
    rebuilt = build_bundle(
        tmp_path / "rebuilt.shard",
        soul=soul,
        shell=json.loads(_read_pillar(standard_bundle, "shellshard.json")),
        mind=json.loads(_read_pillar(standard_bundle, "mindshard.json")),
    )
    reloaded = json.loads(_read_pillar(rebuilt, "soulshard.json"))
    assert reloaded["__future_field__"] == {"invented_by": "v1.1", "payload": [1, 2, 3]}
    assert verify_bundle(rebuilt) == []
