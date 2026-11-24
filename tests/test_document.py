"""Strict runtime document reader tests."""

from __future__ import annotations

import hashlib
import json
import warnings
import zipfile
from pathlib import Path

import pytest
from conftest import current_bundle

from shardcore.document import BundleReadError, read_bundle_document


def encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def manual_bundle(
    path: Path,
    *,
    members: list[tuple[str, bytes]],
    listed: dict[str, dict[str, object]] | None = None,
) -> Path:
    files = listed or {
        name: {
            "schema": "shardcore/soul@1.9" if name == "soulshard.json" else "test/data@1.0",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
        for name, data in members
    }
    manifest = {
        "spec_version": "1.9",
        "shard_name": "Strict Test",
        "files": files,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", encoded(manifest))
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Duplicate name:", category=UserWarning)
            for name, data in members:
                archive.writestr(name, data)
    return path


def test_reads_verified_members_and_json(tmp_path: Path) -> None:
    path = current_bundle(tmp_path / "good.shard")
    document = read_bundle_document(path)

    assert document.state.integrity_ok
    assert "soulshard.json" in document.member_names
    assert document.json_member("soulshard.json")["name"] == "Test One"
    assert len(document.manifest_sha256) == 64


def test_member_selection_still_verifies_full_bundle(tmp_path: Path) -> None:
    path = current_bundle(tmp_path / "selected.shard")
    document = read_bundle_document(path, members=["soulshard.json"])

    assert document.member_names == ("soulshard.json",)
    with pytest.raises(KeyError):
        document.member_bytes("mindshard.json")


def test_member_selection_rejects_corrupt_unretained_member(tmp_path: Path) -> None:
    soul = encoded({"name": "Selected"})
    extra = b"extra"
    listed = {
        "soulshard.json": {
            "schema": "shardcore/soul@1.9",
            "sha256": hashlib.sha256(soul).hexdigest(),
            "size": len(soul),
        },
        "assets/extra.bin": {
            "schema": "shardcore/assets@1.0",
            "sha256": "0" * 64,
            "size": len(extra),
        },
    }
    path = manual_bundle(
        tmp_path / "selected-corrupt.shard",
        members=[("soulshard.json", soul), ("assets/extra.bin", extra)],
        listed=listed,
    )

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path, members=["soulshard.json"])
    assert caught.value.code == "hash_mismatch"


def test_rejects_duplicate_member_names(tmp_path: Path) -> None:
    soul = encoded({"name": "Duplicate"})
    path = manual_bundle(
        tmp_path / "duplicate.shard",
        members=[("soulshard.json", soul), ("soulshard.json", soul)],
    )

    with pytest.raises(BundleReadError, match="duplicate") as caught:
        read_bundle_document(path)
    assert caught.value.code == "duplicate_member"


def test_rejects_undeclared_member(tmp_path: Path) -> None:
    soul = encoded({"name": "Extra"})
    extra = b"extra"
    listed = {
        "soulshard.json": {
            "schema": "shardcore/soul@1.9",
            "sha256": hashlib.sha256(soul).hexdigest(),
            "size": len(soul),
        }
    }
    path = manual_bundle(
        tmp_path / "extra.shard",
        members=[("soulshard.json", soul), ("assets/extra.bin", extra)],
        listed=listed,
    )

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path)
    assert caught.value.code == "undeclared_member"


def test_rejects_size_mismatch(tmp_path: Path) -> None:
    soul = encoded({"name": "Size"})
    listed = {
        "soulshard.json": {
            "schema": "shardcore/soul@1.9",
            "sha256": hashlib.sha256(soul).hexdigest(),
            "size": len(soul) + 1,
        }
    }
    path = manual_bundle(tmp_path / "size.shard", members=[("soulshard.json", soul)], listed=listed)

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path)
    assert caught.value.code == "size_mismatch"


def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    soul = encoded({"name": "Hash"})
    listed = {
        "soulshard.json": {
            "schema": "shardcore/soul@1.9",
            "sha256": "0" * 64,
            "size": len(soul),
        }
    }
    path = manual_bundle(tmp_path / "hash.shard", members=[("soulshard.json", soul)], listed=listed)

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path)
    assert caught.value.code == "hash_mismatch"


def test_rejects_invalid_json_member(tmp_path: Path) -> None:
    soul = b"{broken"
    path = manual_bundle(tmp_path / "json.shard", members=[("soulshard.json", soul)])

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path)
    assert caught.value.code == "json_syntax"


def test_rejects_unsafe_member_name(tmp_path: Path) -> None:
    soul = encoded({"name": "Unsafe"})
    path = manual_bundle(
        tmp_path / "unsafe.shard",
        members=[("soulshard.json", soul), ("../escape.json", encoded({}))],
    )

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path)
    assert caught.value.code == "invalid_member_name"


def test_rejects_per_member_size_cap(tmp_path: Path) -> None:
    soul = encoded({"name": "Large"})
    path = manual_bundle(tmp_path / "large.shard", members=[("soulshard.json", soul)])

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path, max_member_bytes=4)
    assert caught.value.code == "member_size"


def test_rejects_total_uncompressed_cap(tmp_path: Path) -> None:
    soul = encoded({"name": "Total"})
    path = manual_bundle(tmp_path / "total.shard", members=[("soulshard.json", soul)])

    with pytest.raises(BundleReadError) as caught:
        read_bundle_document(path, max_total_uncompressed_bytes=8)
    assert caught.value.code == "total_size"
