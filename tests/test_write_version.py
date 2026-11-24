"""The version a write stamps, and who may save what (spec sections 2.2 and 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from shardcore import build_bundle, core
from shardcore.bundle import read_bundle
from shardcore.diagnose import diagnose
from shardcore.migrate import migrate_bundle
from shardcore.registry import NEW_SHARD_SPEC, SPEC_VERSION

SOUL = {"name": "Versioned", "stat_block": dict.fromkeys(core.CANONICAL_STATS, 5)}
NEURON_1_1 = json.dumps({"version": "1.1"}).encode()
NEURON_1_0 = json.dumps({"version": "1.0"}).encode()
NEURAL_PART = json.dumps({"anatomy_profile": {"parts": {"heart": {"neural": {"n": 1.0}}}}}).encode()
PLAIN_PART = json.dumps({"anatomy_profile": {"parts": {"heart": {"name": "Heart"}}}}).encode()


def _members(**extra: bytes) -> dict[str, bytes]:
    return {"soulshard.json": json.dumps(SOUL).encode(), **extra}


def _state(
    spec: str | None, members: dict[str, bytes] | None = None, **keys: Any
) -> dict[str, Any]:
    """A prior manifest: a bundle state declaring spec."""
    manifest: dict[str, Any] = {"files": core.build_files_info(members or _members()), **keys}
    if spec is not None:
        manifest["spec_version"] = manifest["bundle_version"] = spec
    return manifest


# ---- which version ------------------------------------------------------------


@pytest.mark.parametrize(
    ("declared", "stamped"),
    [
        (None, NEW_SHARD_SPEC),
        ("1.9", "1.9"),
        ("1.10", "1.10"),
        ("1.11", "1.11"),
        (SPEC_VERSION, SPEC_VERSION),
        ("1.0", NEW_SHARD_SPEC),  # before 1.9 there is no form this helper writes
        ("not a version", NEW_SHARD_SPEC),
    ],
)
def test_a_save_stamps_what_the_shard_declares(declared: str | None, stamped: str) -> None:
    manifest = core.build_manifest(_members(), soul=SOUL, prior_manifest=_state(declared))
    assert manifest["spec_version"] == manifest["bundle_version"] == stamped


def test_a_legacy_bundle_version_alone_is_the_declared_version() -> None:
    prior = _state(None, bundle_version="1.10")
    assert core.kept_spec(prior) == "1.10"


def test_numeric_order_not_string_order() -> None:
    assert core.kept_spec(_state("1.9"), merged_with=_state("1.10")) == "1.10"
    assert core.kept_spec(_state("1.10"), merged_with=_state("1.9")) == "1.10"


def test_a_branch_keeps_its_parents_version_and_gets_an_id() -> None:
    child = core.branch_manifest(_state("1.9", shard_name="Prime"))
    manifest = core.build_manifest(_members(), soul=SOUL, prior_manifest=child)
    assert manifest["spec_version"] == "1.9"
    assert manifest["shard_id"] == child["shard_id"]
    assert "revision" not in manifest


# ---- content that needs more than the shard declares --------------------------


@pytest.mark.parametrize(
    "name, data", [("neuronshard.json", NEURON_1_1), ("shellshard.json", NEURAL_PART)]
)
def test_newer_content_in_an_older_shard_has_to_be_asked_for(name: str, data: bytes) -> None:
    members = _members(**{name: data})
    with pytest.raises(core.UpgradeNeededError) as caught:
        core.build_manifest(members, soul=SOUL, prior_manifest=_state("1.11"))
    assert (caught.value.declared, caught.value.needed) == ("1.11", "1.12")
    raised = core.build_manifest(
        members, soul=SOUL, prior_manifest=_state("1.11"), upgrade_to=caught.value.needed
    )
    assert raised["spec_version"] == "1.12"


def test_content_the_shard_already_held_never_blocks_a_save() -> None:
    held = _members(**{"neuronshard.json": NEURON_1_1})
    edited = {**held, "soulshard.json": json.dumps({**SOUL, "summary": "edited"}).encode()}
    manifest = core.build_manifest(edited, soul=SOUL, prior_manifest=_state("1.11", held))
    assert manifest["spec_version"] == "1.11"


@pytest.mark.parametrize(
    "extra", [{"neuronshard.json": NEURON_1_0}, {"shellshard.json": PLAIN_PART}]
)
def test_content_older_versions_have_is_no_reason_to_upgrade(extra: dict[str, bytes]) -> None:
    manifest = core.build_manifest(_members(**extra), soul=SOUL, prior_manifest=_state("1.9"))
    assert manifest["spec_version"] == "1.9"


def test_a_new_member_gets_the_id_of_the_shards_version() -> None:
    members = _members(**{"shellshard.json": PLAIN_PART})
    ids = {
        spec: core.build_manifest(members, soul=SOUL, prior_manifest=_state(spec))["files"][
            "shellshard.json"
        ]["schema"]
        for spec in ("1.9", "1.10", "1.11", "1.12")
    }
    assert ids == {
        "1.9": "shardcore/shell@1.9",
        "1.10": "shardcore/shell@1.9",
        "1.11": "shardcore/shell@1.10",
        "1.12": "shardcore/shell@1.12",
    }


def test_a_neuronshards_id_follows_its_document() -> None:
    prior = _state("1.12", _members(**{"neuronshard.json": NEURON_1_0}))
    members = _members(**{"neuronshard.json": NEURON_1_1})
    manifest = core.build_manifest(members, soul=SOUL, prior_manifest=prior)
    assert manifest["files"]["neuronshard.json"]["schema"] == "shardcore/neuron@1.1"


# ---- a restore -------------------------------------------------------------------


def test_a_restore_takes_the_restored_states_version_and_descends_from_the_head() -> None:
    held = _members(**{"shellshard.json": PLAIN_PART})
    old = _state("1.10", held, shard_id="kept-id", min_writer="1.9")
    old["files"]["shellshard.json"]["schema"] = "shardcore/shell@1.9"
    head = _state("1.12", held, shard_id="kept-id", min_writer="1.12", revision={"n": 1})
    manifest = core.build_manifest(held, soul=SOUL, prior_manifest=head, content_of=old)
    assert manifest["spec_version"] == manifest["bundle_version"] == "1.10"
    assert manifest["files"]["shellshard.json"]["schema"] == "shardcore/shell@1.9"
    assert manifest["min_writer"] == "1.9"
    assert manifest["revision"] == {
        "n": 2,
        "prior": core.manifest_digest(head),
        "history": [core.manifest_digest(head)],
    }


# ---- an explicit upgrade -------------------------------------------------------


def test_an_upgrade_moves_version_ids_identity_and_chain_together() -> None:
    held = _members(**{"shellshard.json": PLAIN_PART})
    prior = _state("1.9", held)
    prior["files"]["shellshard.json"]["schema"] = "shardcore/shell@1.9"
    manifest = core.build_manifest(held, soul=SOUL, prior_manifest=prior, upgrade_to="1.12")
    assert manifest["spec_version"] == "1.12"
    assert manifest["files"]["shellshard.json"]["schema"] == "shardcore/shell@1.12"
    assert core.shard_id_error(manifest["shard_id"]) is None
    assert manifest["revision"]["prior"] == core.manifest_digest(prior)


@pytest.mark.parametrize("wanted", ["1.9", "1.99", "2.0", "soon"])
def test_an_upgrade_goes_up_and_no_further_than_this_writer(wanted: str) -> None:
    with pytest.raises(ValueError, match="upgrade_to"):
        core.build_manifest(_members(), soul=SOUL, prior_manifest=_state("1.10"), upgrade_to=wanted)


@pytest.fixture
def no_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHARD_BACKUP_VAULT", "off")


def _raise(path: Path) -> None:
    manifest, members = core.read_bundle_members(path)
    core.pack_bundle(path, members, soul=SOUL, prior_manifest=manifest, upgrade_to="1.12")


@pytest.mark.usefixtures("no_vault")
def test_an_upgrade_keeps_the_earlier_file(tmp_path: Path) -> None:
    path = _at(tmp_path / "pip.shard", "1.10")
    original = path.read_bytes()
    _raise(path)
    assert core.read_bundle_members(path)[0]["spec_version"] == "1.12"
    assert (tmp_path / "pip.shard.v1.10.bak").read_bytes() == original
    # Undone and done again: the first copy is never overwritten.
    path.write_bytes(original)
    _raise(path)
    assert (tmp_path / "pip.shard.v1.10.bak").read_bytes() == original
    assert (tmp_path / "pip.shard.v1.10.2.bak").read_bytes() == original


@pytest.mark.usefixtures("no_vault")
def test_migrating_in_place_keeps_the_earlier_file(tmp_path: Path) -> None:
    path = _at(tmp_path / "pip.shard", "1.10")
    original = path.read_bytes()
    migrate_bundle(path, out=tmp_path / "copy.shard")
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.bak")) == []
    migrate_bundle(path)
    assert (tmp_path / "pip.shard.v1.10.bak").read_bytes() == original


@pytest.mark.usefixtures("no_vault")
def test_only_an_upgrade_leaves_a_copy(tmp_path: Path) -> None:
    path = _at(tmp_path / "pip.shard", "1.12")
    manifest, members = core.read_bundle_members(path)
    core.pack_bundle(path, members, soul=SOUL, prior_manifest=manifest)
    _raise(path)  # already there
    assert [p.name for p in tmp_path.iterdir()] == ["pip.shard"]


def test_a_backup_vault_takes_the_copy_instead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SHARD_BACKUP_VAULT", str(tmp_path / "vault"))
    path = _at(tmp_path / "pip.shard", "1.10")
    before = core.manifest_digest(core.read_bundle_members(path)[0])
    _raise(path)
    assert [p.name for p in tmp_path.glob("*.bak")] == []
    assert core.load_state(tmp_path / "vault", before) is not None


@pytest.mark.usefixtures("no_vault")
def test_an_upgrade_that_cannot_keep_a_copy_does_not_happen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _at(tmp_path / "pip.shard", "1.10")
    original = path.read_bytes()

    def full(*_: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(core.shutil, "copy2", full)
    with pytest.raises(OSError, match="disk full"):
        _raise(path)
    assert path.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == ["pip.shard"]


# ---- min_writer ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "floor", "allowed"),
    [
        ("1.99", SPEC_VERSION, True),
        ("1.99", "1.9", True),
        ("1.99", None, False),
        ("1.99", "1.98", False),
        ("1.99", "soon", False),  # malformed is absent
        ("1.99", 1.12, False),
        ("1.12", "1.13", False),  # below the floor, whatever spec_version says
        ("1.9", "1.13", False),
        ("1.12", "1.12", True),
        ("2.0", "1.9", False),  # a higher major is never opened by a floor
    ],
)
def test_min_writer_decides(spec: str, floor: Any, allowed: bool) -> None:
    keys = {} if floor is None else {"min_writer": floor}
    manifest = _state(spec, **keys)
    if allowed:
        core.check_spec_writable(manifest)
    else:
        with pytest.raises(core.NewerSpecError):
            core.check_spec_writable(manifest)


def test_a_merge_takes_the_higher_floor() -> None:
    ours, theirs = _state("1.12", min_writer="1.9"), _state("1.12", min_writer="1.12")
    manifest = core.build_manifest(_members(), soul=SOUL, prior_manifest=ours, merged_with=theirs)
    assert manifest["min_writer"] == "1.12"
    one = core.build_manifest(
        _members(), soul=SOUL, prior_manifest=_state("1.12"), merged_with=theirs
    )
    assert one["min_writer"] == "1.12"


def test_a_save_below_the_floor_shows_in_diagnose(tmp_path: Path) -> None:
    path = tmp_path / "shard.shard"
    doc = build_bundle(
        path,
        shard_name="Floor",
        members=_members(),
        manifest_fields={"min_writer": "1.12"},
    )
    assert doc.manifest()["min_writer"] == "1.12"
    codes = {f.code for f in diagnose(read_bundle(path), SPEC_VERSION).findings}
    assert "saved_below_floor" not in codes
    members = {n: d for n, d in core.read_bundle_members(path)[1].items() if n != "manifest.json"}
    manifest = {**doc.manifest(), "spec_version": "1.9", "bundle_version": "1.9"}
    core.pack_bundle(path, members, manifest=manifest)
    found = [
        f
        for f in diagnose(read_bundle(path), SPEC_VERSION).findings
        if f.code == "saved_below_floor"
    ]
    assert len(found) == 1 and found[0].severity == "blocked"


# ---- diagnosing and migrating at an older target -------------------------------


def _at(path: Path, spec: str) -> Path:
    held = _members(**{"shellshard.json": PLAIN_PART})
    prior = {"spec_version": spec, "bundle_version": spec, "shard_id": "kept-id", "files": {}}
    core.pack_bundle(path, held, soul=SOUL, prior_manifest=prior)
    return path


@pytest.mark.parametrize("spec", ["1.9", "1.10", "1.11", "1.12"])
def test_ids_are_judged_by_the_target_version(spec: str, tmp_path: Path) -> None:
    state = read_bundle(_at(tmp_path / "held.shard", spec))
    codes = {f.code for f in diagnose(state, spec).findings}
    assert "stale_schema_ids" not in codes and "stale_spec_version" not in codes
    newest = diagnose(state, SPEC_VERSION)
    assert newest.status == ("current" if spec == SPEC_VERSION else "behind")
    assert ("stale_spec_version" in {f.code for f in newest.findings}) is (spec != SPEC_VERSION)


def test_behind_is_only_for_bundles_that_keep_their_own_versions_rules(tmp_path: Path) -> None:
    path = _at(tmp_path / "held.shard", "1.10")
    assert diagnose(read_bundle(path), SPEC_VERSION).status == "behind"
    manifest, members = core.read_bundle_members(path)
    soul = {**SOUL, "eidolon_signature": "a runtime field outside x_nexus"}
    members["soulshard.json"] = json.dumps(soul).encode()
    core.pack_bundle(path, members, soul=soul, prior_manifest=manifest)
    assert diagnose(read_bundle(path), SPEC_VERSION).status == "outdated"
    old = {**manifest, "spec_version": "1.0", "bundle_version": "1.0"}
    core.pack_bundle(path, members, manifest=old)
    assert diagnose(read_bundle(path), SPEC_VERSION).status in ("outdated", "blocked")


def test_the_diagnose_command_passes_a_shard_that_is_behind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from shardcore.__main__ import _diagnose

    assert _diagnose([str(_at(tmp_path / "held.shard", "1.10"))]) == 0
    assert "behind at spec 1.10" in capsys.readouterr().out


def test_a_migration_to_an_older_target_stamps_that_versions_ids(tmp_path: Path) -> None:
    path = _at(tmp_path / "held.shard", "1.9")
    migrate_bundle(path, "1.11")
    manifest, _ = core.read_bundle_members(path)
    assert manifest["spec_version"] == "1.11"
    assert manifest["files"]["shellshard.json"]["schema"] == "shardcore/shell@1.10"
    assert diagnose(read_bundle(path), "1.11").status == "current"
