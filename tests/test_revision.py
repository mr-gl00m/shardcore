"""The revision chain and merge (spec 11.5): ordering and reconciling copies of one identity."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pytest

from shardcore import core
from shardcore.registry import SPEC_VERSION

STATS = {s: 5 for s in core.CANONICAL_STATS}


def _soul(**extra: Any) -> dict[str, Any]:
    return {
        "name": "Bessie",
        "identity": "A maid.",
        "personality": "Calm.",
        "stat_block": dict(STATS),
        **extra,
    }


def _mind(*archive: str) -> dict[str, Any]:
    return {
        "format_version": "2.1",
        "short_term": {"slots": []},
        "long_term": {"slots": []},
        "core": [],
        "archive": [{"entry_title": title} for title in archive],
    }


def _members(
    soul: dict[str, Any], mind: dict[str, Any] | None = None, **extra: bytes
) -> dict[str, bytes]:
    members = {"soulshard.json": json.dumps(soul, indent=2).encode()}
    if mind is not None:
        members["mindshard.json"] = json.dumps(mind, indent=2).encode()
    members.update(extra)
    return members


def _save(
    path: Path, members: dict[str, bytes], prior: dict[str, Any] | None = None
) -> dict[str, Any]:
    soul = json.loads(members["soulshard.json"])
    return core.pack_bundle(path, members, soul=soul, prior_manifest=prior)


def _read(path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    return core.read_bundle_members(path)


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "backup_vault"
    monkeypatch.setenv(core.BACKUP_VAULT_ENV, str(store))
    monkeypatch.setenv(core.BACKUP_APP_ENV, "tester")
    return store


# ---- the chain -----------------------------------------------------------------


def test_a_new_bundle_starts_at_one(tmp_path: Path) -> None:
    manifest = _save(tmp_path / "b.shard", _members(_soul()))
    assert manifest["revision"] == {"n": 1}
    assert manifest["spec_version"] == SPEC_VERSION


def test_each_save_pins_the_state_it_replaces(tmp_path: Path) -> None:
    first = _save(tmp_path / "b.shard", _members(_soul()))
    second = _save(tmp_path / "b.shard", _members(_soul(nature="kind")), prior=first)
    third = _save(tmp_path / "b.shard", _members(_soul(nature="kinder")), prior=second)
    d1, d2 = core.manifest_digest(first), core.manifest_digest(second)
    assert second["revision"] == {"n": 2, "prior": d1, "history": [d1]}
    assert third["revision"] == {"n": 3, "prior": d2, "history": [d2, d1]}
    assert core.revision_errors(third["revision"]) == []


def test_history_is_capped_and_starts_with_prior(tmp_path: Path) -> None:
    manifest = _save(tmp_path / "b.shard", _members(_soul()))
    for i in range(core.REVISION_HISTORY_MAX + 5):
        manifest = _save(tmp_path / "b.shard", _members(_soul(nature=str(i))), prior=manifest)
    revision = manifest["revision"]
    assert revision["n"] == core.REVISION_HISTORY_MAX + 6
    assert len(revision["history"]) == core.REVISION_HISTORY_MAX
    assert revision["history"][0] == revision["prior"]


def test_a_pre_1_11_state_starts_the_chain_pinned() -> None:
    old = {"spec_version": "1.10", "shard_id": "id-1", "files": {}}
    pin = core.manifest_digest(old)
    assert core.next_revision(old) == {"n": 1, "prior": pin, "history": [pin]}


def test_a_seed_or_branch_is_a_fresh_identity(tmp_path: Path) -> None:
    assert core.next_revision({"card": {"name": "Seed"}}) == {"n": 1}
    parent = _save(tmp_path / "p.shard", _members(_soul()))
    parent = _save(tmp_path / "p.shard", _members(_soul(nature="set")), prior=parent)
    branch = core.branch_manifest(parent)
    assert "files" not in branch and "revision" not in branch
    written = _save(tmp_path / "branch.shard", _members(_soul()), prior=branch)
    assert written["revision"] == {"n": 1}
    assert written["shard_id"] != parent["shard_id"]


@pytest.mark.parametrize(
    ("revision", "problem"),
    [
        ({"n": 0}, "revision.n"),
        ({"n": True}, "revision.n"),
        ({"n": 2}, "required"),
        ({"n": 2, "prior": "x"}, "prior must be"),
        ({"n": 2, "prior": "a" * 64, "history": ["b" * 64]}, "history[0]"),
        ({"n": 2, "prior": "a" * 64, "history": ["a" * 64] * 17}, "more than 16"),
        ({"n": 2, "prior": "a" * 64, "merged": 5}, "merged"),
        ("seven", "object"),
    ],
)
def test_revision_errors(revision: Any, problem: str) -> None:
    assert any(problem in error for error in core.revision_errors(revision))


# ---- comparing two states ---------------------------------------------------------


def _forked(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    base = _save(tmp_path / "base.shard", _members(_soul(), _mind("met")))
    ours = _save(tmp_path / "ours.shard", _members(_soul(nature="kind"), _mind("met")), prior=base)
    theirs = _save(tmp_path / "theirs.shard", _members(_soul(), _mind("met", "talked")), prior=base)
    return base, ours, theirs


def test_compare_orders_states(tmp_path: Path) -> None:
    base, ours, theirs = _forked(tmp_path)
    assert core.compare_revisions(ours, dict(ours)) == "same"
    assert core.compare_revisions(ours, base) == "a_newer"
    assert core.compare_revisions(base, ours) == "b_newer"
    assert core.compare_revisions(ours, theirs) == "diverged"
    assert core.common_ancestor(ours, theirs) == core.manifest_digest(base)


def test_compare_without_chains_is_unknown() -> None:
    a = {"shard_id": "x", "files": {}, "card": {"name": "A"}}
    b = {"shard_id": "x", "files": {}, "card": {"name": "B"}}
    assert core.compare_revisions(a, b) == "unknown"
    assert core.common_ancestor(a, b) is None


def test_compare_refuses_two_identities() -> None:
    with pytest.raises(ValueError):
        core.compare_revisions({"shard_id": "x"}, {"shard_id": "y"})


# ---- merging ----------------------------------------------------------------------


def test_disjoint_changes_merge_without_conflict() -> None:
    base = _members(_soul(x_farmgame={"eggs": 1}), _mind("met"))
    ours = _members(_soul(nature="kind", x_farmgame={"eggs": 1}), _mind("met"))
    theirs = _members(_soul(x_farmgame={"eggs": 9}), _mind("met", "talked"))
    merged, conflicts = core.merge_members(base, ours, theirs)
    assert conflicts == []
    soul = json.loads(merged["soulshard.json"])
    assert soul["nature"] == "kind" and soul["x_farmgame"] == {"eggs": 9}
    assert merged["mindshard.json"] == theirs["mindshard.json"]  # one side's bytes, untouched


def test_both_changing_one_unit_is_a_conflict_until_resolved() -> None:
    base = _members(_soul(nature="calm"))
    ours = _members(_soul(nature="kind"))
    theirs = _members(_soul(nature="cruel"))
    merged, conflicts = core.merge_members(base, ours, theirs)
    assert conflicts == ["soulshard.json#nature"]
    assert json.loads(merged["soulshard.json"])["nature"] == "kind"
    resolved, left = core.merge_members(
        base, ours, theirs, prefer={"soulshard.json#nature": "theirs"}
    )
    assert left == [] and json.loads(resolved["soulshard.json"])["nature"] == "cruel"


def test_structured_blocks_are_units_per_schema() -> None:
    def mind(house: int, social: int) -> dict[str, Any]:
        out = _mind()
        out["structured"] = {
            "cbg/house_ledger@1.0": {"counters": {"visits": house}},
            "cbg/social_talk@1.0": {"counters": {"talks": social}},
        }
        return out

    base, ours, theirs = (_members(_soul(), mind(h, s)) for h, s in ((1, 1), (2, 1), (1, 5)))
    merged, conflicts = core.merge_members(base, ours, theirs)
    assert conflicts == []
    structured = json.loads(merged["mindshard.json"])["structured"]
    assert structured["cbg/house_ledger@1.0"]["counters"]["visits"] == 2
    assert structured["cbg/social_talk@1.0"]["counters"]["talks"] == 5

    _, both = core.merge_members(base, ours, _members(_soul(), mind(3, 1)))
    assert both == ["mindshard.json#structured#cbg/house_ledger@1.0"]


def test_members_added_removed_and_binary() -> None:
    base = _members(_soul(), **{"assets/images/a.png": b"A", "body/items/x.json": b"{}"})
    ours = _members(_soul(), **{"assets/images/a.png": b"A2", "assets/images/new.png": b"N"})
    theirs = _members(_soul(), **{"assets/images/a.png": b"A", "body/items/x.json": b"{}"})
    merged, conflicts = core.merge_members(base, ours, theirs)
    assert conflicts == []
    assert merged["assets/images/a.png"] == b"A2"
    assert merged["assets/images/new.png"] == b"N"
    assert "body/items/x.json" not in merged  # ours removed it, theirs left it alone

    _, binary = core.merge_members(base, ours, _members(_soul(), **{"assets/images/a.png": b"A3"}))
    assert "assets/images/a.png" in binary


def test_the_bessie_round_trip_merges(tmp_path: Path, vault: Path) -> None:
    # Released once, then edited in one app and talked to in another from the
    # same file: two copies, one base, both edits kept.
    discharged = tmp_path / "bessie.shard"
    base = _save(discharged, _members(_soul(nature="shy"), _mind("discharged")))
    editor, runtime = tmp_path / "editor.shard", tmp_path / "rift.shard"
    shutil.copy(discharged, editor)
    shutil.copy(discharged, runtime)
    _save(editor, _members(_soul(nature="bold"), _mind("discharged")), prior=base)
    _save(runtime, _members(_soul(nature="shy"), _mind("discharged", "talked in rift")), prior=base)

    result = core.merge_bundles(editor, runtime)
    assert result["status"] == "merged" and result["conflicts"] == []
    assert result["base"] == core.manifest_digest(base)

    out = tmp_path / "merged.shard"
    written = core.write_merge(out, result)
    assert written["revision"]["merged"] == core.manifest_digest(result["theirs"])
    manifest, members = _read(out)
    assert json.loads(members["soulshard.json"])["nature"] == "bold"
    assert [e["entry_title"] for e in json.loads(members["mindshard.json"])["archive"]] == [
        "discharged",
        "talked in rift",
    ]
    assert core.compare_revisions(manifest, result["ours"]) == "a_newer"
    assert core.compare_revisions(manifest, result["theirs"]) == "a_newer"


def test_merge_reports_newer_same_and_missing_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(core.BACKUP_VAULT_ENV, "off")
    a = tmp_path / "a.shard"
    base = _save(a, _members(_soul()))
    b = tmp_path / "b.shard"
    shutil.copy(a, b)
    assert core.merge_bundles(a, b)["status"] == "same"
    _save(b, _members(_soul(nature="later")), prior=base)
    assert core.merge_bundles(a, b)["status"] == "theirs_newer"
    assert core.merge_bundles(b, a)["status"] == "ours_newer"
    c = tmp_path / "c.shard"
    shutil.copy(a, c)
    _save(c, _members(_soul(nature="other")), prior=base)
    result = core.merge_bundles(b, c, vault=tmp_path / "empty_vault")
    assert result["status"] == "no_base" and result["members"] is None
    with pytest.raises(ValueError):
        core.write_merge(tmp_path / "x.shard", result)


def test_read_bundle_members_verifies(tmp_path: Path) -> None:
    path = tmp_path / "b.shard"
    _save(path, _members(_soul()))
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        soul = archive.read("soulshard.json")
    manifest["files"]["soulshard.json"]["sha256"] = "0" * 64
    bad = tmp_path / "bad.shard"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("soulshard.json", soul)
    with pytest.raises(core.ShardIntegrityError):
        core.read_bundle_members(bad)
