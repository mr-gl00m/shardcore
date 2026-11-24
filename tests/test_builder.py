"""Fresh bundle builder tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from shardcore import build_bundle, json_member_bytes, verify_bundle
from shardcore.builder import BundleBuildError

STAMP = "2026-07-14T00:00:00Z"


def soul(name: str = "Builder Test") -> bytes:
    return json_member_bytes({"name": name, "version": "2.1"})


def test_builds_and_reads_fresh_bundle(tmp_path: Path) -> None:
    target = tmp_path / "fresh.shard"
    document = build_bundle(
        target,
        shard_name="Fresh",
        members={
            "soulshard.json": soul("Fresh"),
            "extensions/nexus/profile.json": json_member_bytes({"schema": "nexus/test@1.0"}),
        },
        schemas={"extensions/nexus/profile.json": "nexus/test@1.0"},
        manifest_fields={"card": {"name": "Fresh"}},
        created=STAMP,
        immutable=True,
    )

    assert target.exists()
    assert document.state.integrity_ok
    assert document.manifest()["immutable"] is True
    assert document.json_member("extensions/nexus/profile.json")["schema"] == "nexus/test@1.0"
    assert verify_bundle(target) == []


def test_builder_output_is_repeatable(tmp_path: Path) -> None:
    first = tmp_path / "first.shard"
    second = tmp_path / "second.shard"
    arguments = {
        "shard_name": "Repeatable",
        "members": {"soulshard.json": soul("Repeatable")},
        "shard_id": "0d1e2f3a-4b5c-4d6e-8f70-819203a4b5c6",
        "created": STAMP,
        "last_modified_utc": STAMP,
    }

    build_bundle(first, **arguments)
    build_bundle(second, **arguments)

    assert first.read_bytes() == second.read_bytes()


def test_rejects_existing_target_without_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "existing.shard"
    target.write_bytes(b"original")

    with pytest.raises(BundleBuildError, match="already exists"):
        build_bundle(target, shard_name="Existing", members={"soulshard.json": soul()})
    assert target.read_bytes() == b"original"


def test_overwrite_replaces_target_after_verification(tmp_path: Path) -> None:
    target = tmp_path / "replace.shard"
    target.write_bytes(b"old")

    document = build_bundle(
        target,
        shard_name="Replacement",
        members={"soulshard.json": soul("Replacement")},
        overwrite=True,
        created=STAMP,
    )

    assert document.json_member("soulshard.json")["name"] == "Replacement"
    assert verify_bundle(target) == []


def test_rejects_member_without_schema(tmp_path: Path) -> None:
    with pytest.raises(BundleBuildError, match="schema"):
        build_bundle(
            tmp_path / "schema.shard",
            shard_name="Schema",
            members={"soulshard.json": soul(), "extensions/vendor/data.bin": b"data"},
        )


def test_rejects_unsafe_member_name(tmp_path: Path) -> None:
    with pytest.raises(BundleBuildError, match="member name"):
        build_bundle(
            tmp_path / "unsafe.shard",
            shard_name="Unsafe",
            members={"soulshard.json": soul(), "../escape.json": b"{}"},
            schemas={"../escape.json": "test/data@1.0"},
        )


def test_rejects_reserved_manifest_fields(tmp_path: Path) -> None:
    with pytest.raises(BundleBuildError, match="reserved"):
        build_bundle(
            tmp_path / "reserved.shard",
            shard_name="Reserved",
            members={"soulshard.json": soul()},
            manifest_fields={"files": {}},
        )


def test_rejects_invalid_timestamp(tmp_path: Path) -> None:
    with pytest.raises(BundleBuildError, match="UTC"):
        build_bundle(
            tmp_path / "time.shard",
            shard_name="Time",
            members={"soulshard.json": soul()},
            created="2026-07-14",
        )


def test_rejects_size_cap_before_write(tmp_path: Path) -> None:
    target = tmp_path / "large.shard"
    with pytest.raises(BundleBuildError, match="size cap"):
        build_bundle(
            target,
            shard_name="Large",
            members={"soulshard.json": soul()},
            max_member_bytes=4,
        )
    assert not target.exists()
