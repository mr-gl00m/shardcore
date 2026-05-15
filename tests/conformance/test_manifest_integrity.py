"""Conformance — spec §2 (manifest) + §7 (integrity).

A v1.0 runtime MUST:
  - accept a bundle whose files all match the manifest's SHA-256 digests;
  - reject a bundle where any listed file's bytes differ from its digest;
  - reject a bundle where a manifest-listed file is missing;
  - reject a bundle with no manifest.json at all.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from shardcore.verify import verify_bundle

from .conftest import drop_bundle_file, rewrite_bundle_file


# ─── Happy path ──────────────────────────────────────────────

def test_valid_minimal_bundle_passes(minimal_bundle: Path):
    errors = verify_bundle(minimal_bundle)
    assert errors == []


def test_valid_standard_bundle_passes(standard_bundle: Path):
    errors = verify_bundle(standard_bundle)
    assert errors == []


def test_valid_neuron_bundle_passes(neuron_bundle: Path):
    errors = verify_bundle(neuron_bundle)
    assert errors == []


# ─── Detection of tampering ──────────────────────────────────

def test_tampered_soulshard_byte_triggers_failure(minimal_bundle: Path, tmp_path: Path):
    tampered = tmp_path / "tampered.shard"
    rewrite_bundle_file(
        minimal_bundle, tampered, "soulshard.json", b'{"name":"Tampered"}',
    )
    errors = verify_bundle(tampered)
    assert errors, "tampered soulshard must not pass"
    assert any("sha256 mismatch" in e for e in errors)
    assert any("soulshard.json" in e for e in errors)


def test_tampered_shellshard_byte_triggers_failure(standard_bundle: Path, tmp_path: Path):
    tampered = tmp_path / "tampered.shard"
    rewrite_bundle_file(
        standard_bundle, tampered, "shellshard.json", b'{"anatomy_profile":{}}',
    )
    errors = verify_bundle(tampered)
    assert any("sha256 mismatch" in e and "shellshard.json" in e for e in errors)


def test_manifest_listed_file_missing_triggers_failure(standard_bundle: Path, tmp_path: Path):
    broken = tmp_path / "missing.shard"
    drop_bundle_file(standard_bundle, broken, "mindshard.json")
    errors = verify_bundle(broken)
    assert any("mindshard.json" in e and "not in the archive" in e for e in errors)


# ─── Malformed manifest rejection ────────────────────────────

def test_missing_manifest_rejected(tmp_path: Path):
    bad = tmp_path / "no_manifest.shard"
    with zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("soulshard.json", b'{"name":"Lost"}')
    errors = verify_bundle(bad)
    assert any("manifest.json" in e for e in errors)


def test_unparseable_manifest_rejected(tmp_path: Path):
    bad = tmp_path / "bad_json.shard"
    with zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", b"{ not valid json")
        zf.writestr("soulshard.json", b'{"name":"ok"}')
    errors = verify_bundle(bad)
    assert any("not valid JSON" in e for e in errors)


def test_missing_required_pillar_rejected(tmp_path: Path):
    """Spec §1: soulshard.json is required."""
    bad = tmp_path / "no_soul.shard"
    import hashlib, json
    manifest = {
        "bundle_version": "1.0",
        "shard_name": "broken",
        "files": {},
    }
    with zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest).encode())
    errors = verify_bundle(bad)
    assert any("soulshard.json" in e for e in errors)


def test_non_zip_file_rejected(tmp_path: Path):
    bad = tmp_path / "not_a_zip.shard"
    bad.write_bytes(b"this is not a zip file")
    errors = verify_bundle(bad)
    assert any("zip" in e.lower() for e in errors)


def test_nonexistent_file_rejected(tmp_path: Path):
    errors = verify_bundle(tmp_path / "does_not_exist.shard")
    assert any("does not exist" in e for e in errors)
