"""core.py as the apps vendor it: one file, loaded by path, outside the package.

Apps copy shardcore/core.py (as shardcore_v19.py) instead of importing
shardcore. Loading it by path proves the copy stands alone (no imports from
the rest of the package), and these tests hold what it writes to the library:
same version, same schema ids, same identity derivation, and bundles it writes
diagnose current here.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from shardcore import diagnose, lineage_errors, manifest_digest, read_bundle
from shardcore.bundle import X_NEXUS_KEYS
from shardcore.lineage import IDENTITY_NAMESPACE
from shardcore.registry import SPEC_VERSION, schema_for_member

HELPER = Path(__file__).resolve().parent.parent / "shardcore" / "core.py"


@pytest.fixture(scope="module")
def sc() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vendored_shardcore_v19", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _soul(name: str = "Parity") -> dict:
    return {
        "name": name,
        "identity": f"{name} checks the helper.",
        "personality": "Exact.",
        "stat_block": {"STR": 5, "TMP": 6},
    }


def _pack(sc: ModuleType, path: Path, soul: dict, **kwargs) -> dict:
    # Apps normalize the soul before every write; do the same here.
    soul = sc.prepare_soul_for_write(soul)
    members = {"soulshard.json": json.dumps(soul).encode("utf-8")}
    return sc.pack_bundle(path, members, soul=soul, **kwargs)


def _manifest(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json"))


def test_versions_and_registries_match_the_library(sc: ModuleType) -> None:
    assert sc.SPEC_VERSION == SPEC_VERSION
    assert sc.X_NEXUS_KEYS == X_NEXUS_KEYS
    assert sc.IDENTITY_NAMESPACE == IDENTITY_NAMESPACE
    names = [
        *sc.PILLAR_SCHEMAS,
        "body/items/a.json",
        "assets/images/a.png",
        "images/a.png",
        "portrait.webp",
        "notes.txt",
    ]
    for name in names:
        assert sc.schema_for_member(name) == schema_for_member(name), name


def test_written_bundle_diagnoses_current(sc: ModuleType, tmp_path: Path) -> None:
    target = tmp_path / "fresh.shard"
    _pack(sc, target, _soul())
    result = diagnose(read_bundle(target), SPEC_VERSION)
    assert result.status == "current", [f.code for f in result.findings]
    assert uuid.UUID(_manifest(target)["shard_id"]).version == 4


def test_identity_matches_migration_0015(sc: ModuleType) -> None:
    prior = {"spec_version": "1.9", "shard_name": "Nine", "files": {}}
    digest = manifest_digest(prior)
    assert sc.manifest_digest(prior) == digest
    assert sc.mint_shard_id(prior) == str(uuid.uuid5(IDENTITY_NAMESPACE, digest))
    # A seed dict with no files map is a new bundle, not a pre-1.10 one.
    assert uuid.UUID(sc.mint_shard_id({"card": {"name": "Seed"}})).version == 4


def test_save_keeps_shard_id(sc: ModuleType, tmp_path: Path) -> None:
    target = tmp_path / "kept.shard"
    prior = {"spec_version": "1.10", "shard_id": "kept-id", "files": {}}
    _pack(sc, target, _soul(), prior_manifest=prior)
    assert _manifest(target)["shard_id"] == "kept-id"


def test_branch_is_a_new_identity_with_valid_lineage(sc: ModuleType, tmp_path: Path) -> None:
    parent_path = tmp_path / "prime.shard"
    _pack(sc, parent_path, _soul("Prime"), immutable=True)
    parent = _manifest(parent_path)

    child_path = tmp_path / "prime.branch.shard"
    _pack(sc, child_path, _soul("Prime"), prior_manifest=sc.branch_manifest(parent))
    child = _manifest(child_path)

    assert child["shard_id"] != parent["shard_id"]
    assert "immutable" not in child
    assert lineage_errors(child["lineage"]) == []
    assert child["lineage"]["parent"] == {
        "manifest_sha256": manifest_digest(parent),
        "shard_id": parent["shard_id"],
        "label": "Prime",
    }
    assert diagnose(read_bundle(child_path), SPEC_VERSION).status == "current"


def test_versions_compare_numerically(sc: ModuleType) -> None:
    assert sc.version_tuple("1.10") > sc.version_tuple("1.9")
    assert sc.version_tuple("1.x") is None
    assert sc.version_tuple(1.1) is None


@pytest.mark.parametrize("declared", ["1.13", "1.99", "2.0"])
def test_newer_spec_is_never_rewritten(sc: ModuleType, tmp_path: Path, declared: str) -> None:
    prior = {"spec_version": declared, "shard_id": "x", "files": {}}
    with pytest.raises(sc.NewerSpecError):
        _pack(sc, tmp_path / "newer.shard", _soul(), prior_manifest=prior)
    assert not (tmp_path / "newer.shard").exists()


@pytest.mark.parametrize("declared", ["1.0", "1.9", "1.10", SPEC_VERSION])
def test_same_or_older_spec_is_rewritten(sc: ModuleType, declared: str) -> None:
    sc.check_spec_writable({"spec_version": declared})
    sc.check_spec_writable({"bundle_version": declared})
    sc.check_spec_writable(None)


# --------------------------------------------------------------------------- #
# decay_status_effects (addendum 5.6.1)
# --------------------------------------------------------------------------- #


def _effect(**fields: object) -> dict[str, object]:
    effect: dict[str, object] = {
        "id": "e1",
        "name": "drunk",
        "level": 10.0,
        "decay_rate_per_hour": 1.0,
        "applied_at_utc": "2026-05-26T12:00:00Z",
        "expires_at_utc": None,
        "effects": {"coordination": -3},
        "withdrawal_on_clear": False,
    }
    effect.update(fields)
    return effect


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 26, hour, minute, tzinfo=timezone.utc)


def test_decay_is_linear_and_rebases_the_anchor(sc: ModuleType) -> None:
    active, cleared = sc.decay_status_effects([_effect()], _at(14))
    assert cleared == []
    assert active[0]["level"] == pytest.approx(8.0)
    assert active[0]["applied_at_utc"] == "2026-05-26T14:00:00Z"


def test_decaying_twice_never_counts_the_same_hours_twice(sc: ModuleType) -> None:
    once, _ = sc.decay_status_effects([_effect()], _at(15))
    first, _ = sc.decay_status_effects([_effect()], _at(14))
    second, _ = sc.decay_status_effects(first, _at(15))
    assert second[0]["level"] == pytest.approx(once[0]["level"]) == pytest.approx(7.0)


def test_effect_clears_at_zero_level_or_at_expiry(sc: ModuleType) -> None:
    spent = _effect(id="spent", level=2.0)
    timed = _effect(id="timed", level=50.0, expires_at_utc="2026-05-26T13:00:00Z")
    lasting = _effect(id="lasting", level=50.0)
    active, cleared = sc.decay_status_effects([spent, timed, lasting], _at(14))
    assert [e["id"] for e in cleared] == ["spent", "timed"]
    assert [e["id"] for e in active] == ["lasting"]


def test_backwards_clock_decays_nothing(sc: ModuleType) -> None:
    active, _ = sc.decay_status_effects([_effect()], _at(9))
    assert active[0]["level"] == 10.0
    assert active[0]["applied_at_utc"] == "2026-05-26T12:00:00Z"


def test_unanchored_or_naive_effects_are_kept_as_they_are(sc: ModuleType) -> None:
    naive = _effect(id="naive", applied_at_utc="2026-05-26T12:00:00")
    missing = _effect(id="missing", applied_at_utc=None)
    active, cleared = sc.decay_status_effects([naive, missing, "junk"], _at(20))
    assert cleared == []
    assert active == [naive, missing]


def test_decay_does_not_touch_its_input(sc: ModuleType) -> None:
    effects = [_effect()]
    snapshot = json.dumps(effects, sort_keys=True)
    sc.decay_status_effects(effects, _at(16))
    assert json.dumps(effects, sort_keys=True) == snapshot
