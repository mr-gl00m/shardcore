"""Drift detection and status classification tests."""

from __future__ import annotations

from pathlib import Path

from conftest import CANONICAL_STAT_BLOCK, TEST_SHARD_ID, build_shard, current_bundle

from shardcore.bundle import read_bundle
from shardcore.diagnose import diagnose
from shardcore.model import STATUS_BEHIND, STATUS_BLOCKED, STATUS_CURRENT, STATUS_OUTDATED
from shardcore.registry import SPEC_VERSION

TARGET = SPEC_VERSION


def _codes(shard: Path) -> set[str]:
    diag = diagnose(read_bundle(shard), TARGET)
    return {f.code for f in diag.findings}


def test_current_bundle_has_no_findings(tmp_path: Path) -> None:
    diag = diagnose(read_bundle(current_bundle(tmp_path / "cur.shard")), TARGET)
    assert diag.status == STATUS_CURRENT
    assert diag.findings == ()


def test_legacy_bundle_is_outdated(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "legacy.shard",
        pillars={
            "soulshard.json": {"name": "Legacy"},
            "memoryshard.json": {"format_version": "2.1", "short_term": {"slots": []}},
        },
        manifest={
            "bundle_version": "1.1",
            "shard_name": "Legacy",
            "memory_format": "2.0",
            "created": "2026-03-31T22:39:42.655247",
        },
    )
    codes = _codes(shard)
    diag = diagnose(read_bundle(shard), TARGET)

    assert diag.status == STATUS_OUTDATED
    assert "no_spec_version" in codes
    assert "legacy_bundle_version" in codes
    assert "uses_memoryshard" in codes
    # soul carries no shell fields, so bare shellshard absence is not drift
    assert "missing_shellshard" not in codes
    assert "manifest_has_memory_format" in codes
    assert "memory_format_mismatch" in codes
    assert "no_schema_ids" in codes
    assert "non_utc_timestamps" in codes


def test_integrity_mismatch_is_blocked(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "corrupt.shard",
        pillars={"soulshard.json": {"name": "Corrupt"}},
        manifest={"spec_version": "1.1", "shard_name": "Corrupt"},
        corrupt="soulshard.json",
    )
    diag = diagnose(read_bundle(shard), TARGET)
    assert diag.status == STATUS_BLOCKED
    assert any(f.code == "integrity_mismatch" for f in diag.findings)


def test_immutable_is_blocked(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "prime.shard",
        pillars={"soulshard.json": {"name": "Prime"}},
        manifest={"spec_version": "1.1", "shard_name": "Prime", "immutable": True},
        schemas={"soulshard.json": "shardcore/soul@2.1"},
    )
    diag = diagnose(read_bundle(shard), TARGET)
    assert diag.status == STATUS_BLOCKED
    assert any(f.code == "immutable" for f in diag.findings)


def test_future_spec_is_blocked(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "future.shard",
        pillars={"soulshard.json": {"name": "Future"}},
        manifest={"spec_version": "3.0", "shard_name": "Future"},
        schemas={"soulshard.json": "shardcore/soul@2.1"},
    )
    diag = diagnose(read_bundle(shard), TARGET)
    assert diag.status == STATUS_BLOCKED
    assert any(f.code == "future_spec" for f in diag.findings)


def test_soul_shell_and_extension_fields(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "naomi_like.shard",
        pillars={
            "soulshard.json": {
                "name": "Naomi Like",
                "character_state": {"daily_production_target": 30},
                "reicodex_rituals_data": {"ritual_enabled": False},
            },
            "shellshard.json": {"anatomy_profile": {}},
            "mindshard.json": {"format_version": "2.1", "short_term": {"slots": []}},
        },
        manifest={"spec_version": "1.1", "shard_name": "Naomi Like"},
        schemas={
            "soulshard.json": "shardcore/soul@2.1",
            "shellshard.json": "shardcore/shell@1.2",
            "mindshard.json": "shardcore/mind@2.1",
        },
    )
    diag = diagnose(read_bundle(shard), TARGET)
    codes = {f.code for f in diag.findings}
    assert "soul_carries_shell_fields" in codes
    assert "soul_runtime_extensions" in codes
    assert diag.status == STATUS_OUTDATED
    # the x_nexus re-nest is migration 0010 in the v1.9 chain (no longer deferred)
    ext = next(f for f in diag.findings if f.code == "soul_runtime_extensions")
    assert ext.severity == "outdated"
    assert ext.migration == "0010"


def test_legacy_list_manifest_is_outdated_not_blocked(tmp_path: Path) -> None:
    import json
    import zipfile

    shard = tmp_path / "v10.shard"
    with zipfile.ZipFile(shard, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "bundle_version": "1.0",
                    "shard_name": "V10",
                    "files": ["soulshard.json", "memoryshard.json"],
                    "memory_format": "1.0",
                }
            ),
        )
        archive.writestr("soulshard.json", json.dumps({"name": "V10"}))
        archive.writestr("memoryshard.json", json.dumps({"format_version": "1.0"}))

    diag = diagnose(read_bundle(shard), TARGET)
    codes = {f.code for f in diag.findings}
    assert "no_integrity_data" in codes
    assert "integrity_mismatch" not in codes
    assert diag.status == STATUS_OUTDATED


def test_nonstandard_stat_block_detected(tmp_path: Path) -> None:
    from conftest import CANONICAL_STAT_BLOCK

    block = dict(CANONICAL_STAT_BLOCK)
    block["Resonance"] = "violet"
    shard = build_shard(
        tmp_path / "resonance.shard",
        pillars={"soulshard.json": {"name": "Res", "stat_block": block}},
        manifest={"spec_version": "1.1", "shard_name": "Res"},
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )
    codes = _codes(shard)
    assert "nonstandard_stat_block" in codes
    finding = next(
        f
        for f in diagnose(read_bundle(shard), TARGET).findings
        if f.code == "nonstandard_stat_block"
    )
    assert finding.migration == "0013"
    assert "Resonance" in finding.detail


def test_missing_stat_block_detected(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "nostats.shard",
        pillars={"soulshard.json": {"name": "No Stats"}},
        manifest={"spec_version": "1.1", "shard_name": "No Stats"},
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )
    assert "no_stat_block" in _codes(shard)


def test_duplicate_pillar_variants_detected(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "lacey_like.shard",
        pillars={
            "soulshard.json": {"name": "Lacey Like"},
            "memoryshard_soulshard_2026.json": {"format_version": "2.1"},
            "soulshard.json.sha256": {"digest": "irrelevant"},
            "backups/soulshard_backup_20260221.json": {"name": "old"},
        },
        manifest={"spec_version": "1.1", "shard_name": "Lacey Like"},
    )
    diag = diagnose(read_bundle(shard), TARGET)
    finding = next(f for f in diag.findings if f.code == "duplicate_pillar_variants")
    assert finding.migration == "0012"
    assert "memoryshard_soulshard_2026.json" in finding.detail
    assert "soulshard.json.sha256" in finding.detail
    assert "backups/soulshard_backup_20260221.json" in finding.detail


def _v19_current(path: Path, **manifest_extra: object) -> Path:
    """A bundle that was fully current at v1.9: nothing but the 1.10 additions missing."""
    from conftest import CANONICAL_STAT_BLOCK

    manifest = {"spec_version": "1.9", "bundle_version": "1.9", "shard_name": "Nine"}
    manifest.update(manifest_extra)
    return build_shard(
        path,
        pillars={"soulshard.json": {"name": "Nine", "stat_block": dict(CANONICAL_STAT_BLOCK)}},
        manifest=manifest,
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def test_v1_9_bundle_is_one_minor_behind(tmp_path: Path) -> None:
    diag = diagnose(read_bundle(_v19_current(tmp_path / "nine.shard")), TARGET)
    by_code = {f.code: f for f in diag.findings if f.severity != "info"}

    assert diag.status == STATUS_BEHIND
    assert set(by_code) == {"stale_spec_version", "no_shard_id"}
    assert by_code["stale_spec_version"].migration == "0005"
    assert by_code["no_shard_id"].migration == "0015"


def test_versions_compare_numerically(tmp_path: Path) -> None:
    # As strings "1.10" < "1.9" and as decimals 1.10 == 1.1; both orderings are wrong.
    nine = read_bundle(_v19_current(tmp_path / "nine.shard"))
    assert "future_spec" not in {f.code for f in diagnose(nine, "1.10").findings}

    ten = read_bundle(current_bundle(tmp_path / "ten.shard"))
    ten_codes = {f.code for f in diagnose(ten, "1.9").findings}
    assert "future_spec" in ten_codes
    assert "stale_spec_version" not in ten_codes


def test_shard_id_not_demanded_below_1_10(tmp_path: Path) -> None:
    diag = diagnose(read_bundle(_v19_current(tmp_path / "nine.shard")), "1.9")
    assert diag.status == STATUS_CURRENT
    assert [f.code for f in diag.findings if f.severity != "info"] == []


def test_invalid_shard_id_is_blocked(tmp_path: Path) -> None:
    shard = _v19_current(tmp_path / "broken_id.shard", shard_id=42)
    diag = diagnose(read_bundle(shard), TARGET)
    codes = {f.code for f in diag.findings}

    assert diag.status == STATUS_BLOCKED
    assert "invalid_shard_id" in codes
    # A broken id is never treated as absent, so 0015 is never planned over it.
    assert "no_shard_id" not in codes


def test_malformed_lineage_is_info_only(tmp_path: Path) -> None:
    # A real branch carried this exact shape: a bare filename as parent.
    shard = _v19_current(
        tmp_path / "branch.shard",
        spec_version=SPEC_VERSION,
        bundle_version=SPEC_VERSION,
        shard_id=TEST_SHARD_ID,
        lineage={"parent": "dx_rei_toei_genesis.shard"},
    )
    diag = diagnose(read_bundle(shard), TARGET)
    finding = next(f for f in diag.findings if f.code == "invalid_lineage")

    assert diag.status == STATUS_CURRENT
    assert finding.severity == "info"
    assert finding.migration is None


def test_flat_memory_detected(tmp_path: Path) -> None:
    shard = build_shard(
        tmp_path / "flat.shard",
        pillars={
            "soulshard.json": {"name": "Flat"},
            "shellshard.json": {},
            "mindshard.json": [{"entry": "old flat memory"}],
        },
        manifest={"spec_version": "1.1", "shard_name": "Flat"},
        schemas={
            "soulshard.json": "shardcore/soul@2.1",
            "shellshard.json": "shardcore/shell@1.2",
            "mindshard.json": "shardcore/mind@2.1",
        },
    )
    assert "flat_memory" in _codes(shard)


def _schema_less_member_bundle(path: Path, **manifest: object) -> Path:
    """A bundle the lenient reader passes and the strict reader rejects: one
    member listed with hashes but no schema id."""
    return build_shard(
        path,
        pillars={
            "soulshard.json": {"name": "Strict", "stat_block": dict(CANONICAL_STAT_BLOCK)},
            "extensions/nexus/profile.json": {"opaque": True},
        },
        manifest={"shard_name": "Strict", "created": "2026-07-03T14:00:00Z", **manifest},
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def test_strict_failure_blocks_an_otherwise_current_bundle(tmp_path: Path) -> None:
    shard = _schema_less_member_bundle(
        tmp_path / "strict.shard",
        spec_version=SPEC_VERSION,
        bundle_version=SPEC_VERSION,
        shard_id=TEST_SHARD_ID,
        last_modified_utc="2026-07-03T14:00:00Z",
    )
    diag = diagnose(read_bundle(shard), TARGET)
    finding = next(f for f in diag.findings if f.code == "strict_read_failed")

    assert diag.status == STATUS_BLOCKED
    assert finding.severity == "blocked"
    assert "no schema" in finding.detail


def test_strict_failure_stays_info_while_migrations_are_pending(tmp_path: Path) -> None:
    shard = _schema_less_member_bundle(
        tmp_path / "pending.shard",
        spec_version="1.9",
        bundle_version="1.9",
        last_modified_utc="2026-07-03T14:00:00Z",
    )
    diag = diagnose(read_bundle(shard), TARGET)
    finding = next(f for f in diag.findings if f.code == "strict_read_failed")

    assert diag.status == STATUS_OUTDATED
    assert finding.severity == "info"


def test_read_bundle_accepts_a_string_path(tmp_path: Path) -> None:
    shard = current_bundle(tmp_path / "cur.shard")
    assert diagnose(read_bundle(str(shard)), TARGET).status == STATUS_CURRENT
