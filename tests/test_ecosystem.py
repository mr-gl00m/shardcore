"""The ecosystem check's own tests: each writer failure it exists to catch.

contract.judge is fed hand-made outputs (good ones, and ones with exactly the
regressions seen in the wild: a 1.9 stamp, a dropped shard_id, a branch that
reuses its parent's id, a lost asset), with no consumer process involved.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("tomllib", reason="the check itself needs Python 3.11")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "ecosystem"))
import contract  # noqa: E402
import ecosystem  # noqa: E402

from shardcore import derived_shard_id, manifest_digest, next_revision  # noqa: E402


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory: pytest.TempPathFactory) -> dict[str, contract.Fixture]:
    return contract.build_fixtures(tmp_path_factory.mktemp("fixtures"))


def _rewrite(
    source: Path, target: Path, *, manifest: dict | None = None, drop: tuple[str, ...] = ()
) -> Path:
    """Repack source with an edited manifest and members dropped, hashes kept honest."""
    with zipfile.ZipFile(source) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    edited = manifest if manifest is not None else json.loads(members["manifest.json"])
    files = {}
    for name, data in members.items():
        if name == "manifest.json" or name in drop:
            continue
        entry = dict(edited.get("files", {}).get(name, {}))
        entry.update({"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
        files[name] = entry
    edited = {**edited, "files": files}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(edited))
        for name in files:
            archive.writestr(name, members[name])
    return target


def _judge(fixture, kind, output, *, source=None, error=None, owns=frozenset()):
    job = contract.Job(f"op--{fixture.name}", "op", kind, (str(fixture.path),))
    result = {
        "sources": [str(source or output)],
        "output": str(output) if output else None,
        "error": error,
    }
    return {
        check for check, _ in contract.judge(job, result, {fixture.name: fixture}, owns).failures
    }


def _copy(fixture, tmp_path: Path, name: str = "copy.shard") -> Path:
    target = tmp_path / name
    shutil.copy2(fixture.path, target)
    return target


def test_an_unchanged_resave_passes(fixtures, tmp_path):
    fixture = fixtures["valid_companion"]
    assert _judge(fixture, "resave", _copy(fixture, tmp_path)) == set()


def test_a_1_9_stamp_fails_version(fixtures, tmp_path):
    fixture = fixtures["valid_minimal"]
    manifest = {**fixture.manifest, "spec_version": "1.9", "bundle_version": "1.9"}
    output = _rewrite(fixture.path, tmp_path / "old.shard", manifest=manifest)
    assert "version" in _judge(fixture, "resave", output)


def test_a_dropped_shard_id_fails_identity(fixtures, tmp_path):
    fixture = fixtures["valid_minimal"]
    manifest = {k: v for k, v in fixture.manifest.items() if k != "shard_id"}
    output = _rewrite(fixture.path, tmp_path / "anon.shard", manifest=manifest)
    assert "identity" in _judge(fixture, "resave", output)


def test_a_migrated_v1_9_input_must_get_the_migration_id(fixtures, tmp_path):
    fixture = fixtures["legacy_v1_9"]
    current = contract.SPEC_VERSION
    random_id = {**fixture.manifest, "spec_version": current, "bundle_version": current}
    random_id["shard_id"] = "00000000-0000-4000-8000-000000000000"
    random_id["revision"] = next_revision(fixture.manifest)
    output = _rewrite(fixture.path, tmp_path / "nine.shard", manifest=random_id)
    assert _judge(fixture, "migrate", output) == {"identity"}


@pytest.mark.parametrize("name", ["legacy_v1_9", "legacy_v1_10"])
def test_an_older_input_keeps_its_version_on_a_save(fixtures, tmp_path, name):
    fixture = fixtures[name]
    minted = derived_shard_id(manifest_digest(fixture.manifest))
    manifest = {"shard_id": minted, **fixture.manifest, "x": 1}
    kept = _rewrite(fixture.path, tmp_path / "kept.shard", manifest=manifest)
    assert _judge(fixture, "resave", kept) == set()
    current = contract.SPEC_VERSION
    raised = {**fixture.manifest, "spec_version": current, "bundle_version": current}
    raised["revision"] = next_revision(fixture.manifest)
    output = _rewrite(fixture.path, tmp_path / "raised.shard", manifest=raised)
    assert "version" in _judge(fixture, "resave", output)
    assert "version" in _judge(fixture, "copy", output, source=_copy(fixture, tmp_path, "in.shard"))
    # A projection is a fresh build, so either version is its own.
    assert "version" not in _judge(
        fixture, "export", output, source=_copy(fixture, tmp_path, "in2.shard")
    )


def test_a_v1_9_input_given_another_id_fails_identity(fixtures, tmp_path):
    fixture = fixtures["legacy_v1_9"]
    minted = {**fixture.manifest, "shard_id": "00000000-0000-4000-8000-000000000000"}
    output = _rewrite(fixture.path, tmp_path / "minted.shard", manifest=minted)
    assert _judge(fixture, "resave", output) == {"identity"}


def test_a_newer_bundle_open_to_this_writer_must_come_through_whole(fixtures, tmp_path):
    fixture = fixtures["newer_minor_open"]
    saved = {**fixture.manifest, "revision": next_revision(fixture.manifest)}
    output = _rewrite(fixture.path, tmp_path / "saved.shard", manifest=saved)
    assert _judge(fixture, "resave", output) == set()

    def broken(edit) -> set[str]:
        manifest = json.loads(json.dumps(saved))
        edit(manifest)
        return _judge(
            fixture, "resave", _rewrite(fixture.path, tmp_path / "b.shard", manifest=manifest)
        )

    assert broken(lambda m: m.pop("min_writer")) == {"newer"}
    assert broken(lambda m: m.pop("key_from_later")) == {"newer"}
    assert "newer" in broken(
        lambda m: m["files"]["soulshard.json"].update(schema="shardcore/soul@1.9")
    )
    assert "version" in broken(lambda m: m.update(spec_version="1.12", bundle_version="1.12"))
    dropped = _rewrite(
        fixture.path, tmp_path / "d.shard", manifest=saved, drop=("dreamshard.json",)
    )
    assert {"members", "newer"} <= _judge(fixture, "resave", dropped)
    # Refusing it is the lockout the floor exists to end.
    assert _judge(fixture, "resave", None, source=fixture.path, error="refused") == {"ran"}


def test_a_dropped_lineage_fails_lineage(fixtures, tmp_path):
    fixture = fixtures["valid_offspring"]
    manifest = {k: v for k, v in fixture.manifest.items() if k != "lineage"}
    output = _rewrite(fixture.path, tmp_path / "orphan.shard", manifest=manifest)
    assert "lineage" in _judge(
        fixture, "export", output, source=_copy(fixture, tmp_path, "in.shard")
    )


def test_a_lost_asset_fails_members_for_whole_writes_only(fixtures, tmp_path):
    fixture = fixtures["valid_with_assets"]
    output = _rewrite(fixture.path, tmp_path / "bare.shard", drop=("assets/images/portrait.png",))
    source = _copy(fixture, tmp_path, "in.shard")
    assert "members" in _judge(fixture, "copy", output, source=source)
    assert "members" not in _judge(fixture, "export", output, source=source)


def test_a_dropped_foreign_namespace_fails_extensions(fixtures, tmp_path):
    fixture = fixtures["valid_x_foreign"]
    with zipfile.ZipFile(fixture.path) as archive:
        soul = json.loads(archive.read("soulshard.json"))
    soul.pop("x_acme")
    stripped = tmp_path / "stripped.shard"
    _rewrite(fixture.path, stripped)
    with zipfile.ZipFile(stripped) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    members["soulshard.json"] = json.dumps(soul).encode("utf-8")
    manifest = json.loads(members.pop("manifest.json"))
    with zipfile.ZipFile(stripped, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, data in members.items():
            archive.writestr(name, data)
    output = _rewrite(stripped, tmp_path / "out.shard", manifest=manifest)
    source = _copy(fixture, tmp_path, "in.shard")
    assert "extensions" in _judge(fixture, "export", output, source=source)
    assert "extensions" not in _judge(
        fixture, "export", output, source=source, owns=frozenset({"x_acme"})
    )


def test_a_modified_input_fails_untouched(fixtures, tmp_path):
    fixture = fixtures["valid_minimal"]
    source = _rewrite(fixture.path, tmp_path / "in.shard", manifest={**fixture.manifest, "x": 1})
    assert "untouched" in _judge(fixture, "copy", _copy(fixture, tmp_path), source=source)


def test_an_immutable_bundle_rewritten_in_place_fails(fixtures, tmp_path):
    fixture = fixtures["immutable_prime"]
    manifest = {k: v for k, v in fixture.manifest.items() if k != "immutable"}
    in_place = _rewrite(fixture.path, tmp_path / "prime.shard", manifest=manifest)
    assert _judge(fixture, "resave", in_place) == {"refused"}


def test_an_immutable_bundle_refused_or_left_alone_passes(fixtures, tmp_path):
    fixture = fixtures["immutable_prime"]
    source = _copy(fixture, tmp_path)
    assert _judge(fixture, "resave", None, source=source, error="ImmutableShardError: no") == set()
    assert _judge(fixture, "migrate", source, source=source) == set()


def _branch(fixture, tmp_path: Path, **lineage_overrides) -> Path:
    manifest = {k: v for k, v in fixture.manifest.items() if k != "immutable"}
    pin = {
        "manifest_sha256": manifest_digest(fixture.manifest),
        "shard_id": fixture.manifest["shard_id"],
    }
    manifest["lineage"] = {"relationship": "derivative", "parent": pin, **lineage_overrides}
    manifest["shard_id"] = "11111111-0000-4000-8000-000000000000"
    manifest["revision"] = {"n": 1}
    return _rewrite(fixture.path, tmp_path / "prime.branch.shard", manifest=manifest)


def test_a_correct_branch_passes(fixtures, tmp_path):
    fixture = fixtures["immutable_prime"]
    branch = _branch(fixture, tmp_path)
    assert _judge(fixture, "resave", branch, source=_copy(fixture, tmp_path)) == set()


def test_a_branch_reusing_the_parent_id_fails(fixtures, tmp_path):
    fixture = fixtures["immutable_prime"]
    branch = _branch(fixture, tmp_path)
    with zipfile.ZipFile(branch) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    manifest["shard_id"] = fixture.manifest["shard_id"]
    reused = _rewrite(branch, tmp_path / "reused.shard", manifest=manifest)
    assert "identity" in _judge(fixture, "resave", reused, source=_copy(fixture, tmp_path))


def test_a_branch_pinning_a_filename_fails(fixtures, tmp_path):
    fixture = fixtures["immutable_prime"]
    branch = _branch(fixture, tmp_path, parent="immutable_prime.shard")
    assert "lineage" in _judge(fixture, "resave", branch, source=_copy(fixture, tmp_path))


def test_a_newer_spec_bundle_must_not_be_rewritten(fixtures, tmp_path):
    fixture = fixtures[contract.NEWER]
    source = _copy(fixture, tmp_path)
    assert _judge(fixture, "resave", None, source=source, error="NewerSpecError: no") == set()
    down = {**fixture.manifest, "spec_version": contract.SPEC_VERSION}
    down["bundle_version"] = contract.SPEC_VERSION
    copied = _rewrite(fixture.path, tmp_path / "down.shard", manifest=down)
    assert _judge(fixture, "copy", copied, source=source) == {"refused"}
    assert _judge(fixture, "resave", copied) == {"refused"}


def test_the_plan_gives_each_kind_its_inputs(fixtures):
    jobs = contract.plan(
        {"save": "resave", "proj": "export", "make": "new", "breed": "offspring"}, fixtures
    )
    by_op: dict[str, list] = {}
    for job in jobs:
        by_op.setdefault(job.operation, []).append(job)
    assert len(by_op["save"]) == len(fixtures)
    assert len(by_op["proj"]) == len(fixtures) - 2  # no newer-spec input for a projection
    assert [len(j.inputs) for j in by_op["make"] + by_op["breed"]] == [0, 2]
    with pytest.raises(ValueError):
        contract.plan({"x": "teleport"}, fixtures)


def test_snapshot_sees_changes_outside_ignored_globs(tmp_path):
    (tmp_path / "keep.txt").write_text("a", encoding="utf-8")
    (tmp_path / "app.log").write_text("a", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    before = ecosystem.snapshot(tmp_path)
    (tmp_path / "keep.txt").write_text("changed", encoding="utf-8")
    (tmp_path / "app.log").write_text("changed", encoding="utf-8")
    (tmp_path / ".venv" / "cache.bin").write_text("x", encoding="utf-8")
    (tmp_path / "new.json").write_text("{}", encoding="utf-8")
    assert ecosystem._changed(before, ecosystem.snapshot(tmp_path), ("*.log",)) == [
        "keep.txt",
        "new.json",
    ]


def test_vendored_drift_ignores_line_endings(tmp_path):
    source_rel = "shardcore/core.py"
    source = (ecosystem.SHARDCORE_ROOT / source_rel).read_bytes().replace(b"\r\n", b"\n")
    (tmp_path / "crlf.py").write_bytes(source.replace(b"\n", b"\r\n"))
    (tmp_path / "edited.py").write_bytes(source + b"# local edit\n")
    consumer = ecosystem.Consumer(
        name="probe",
        root=tmp_path,
        vendored={"crlf.py": source_rel, "edited.py": source_rel, "missing.py": source_rel},
        adapter=None,
        tests=(),
        owns=frozenset(),
        ignore=(),
        waive={},
    )
    drift = {copy: problem for _c, copy, problem in ecosystem.vendored_drift([consumer])}
    assert set(drift) == {"edited.py", "missing.py"}


def test_a_new_state_must_continue_the_chain(fixtures, tmp_path):
    fixture = fixtures["valid_revised"]
    restarted = {**fixture.manifest, "card": {"name": "Edited"}, "revision": {"n": 1}}
    output = _rewrite(fixture.path, tmp_path / "restarted.shard", manifest=restarted)
    assert _judge(fixture, "resave", output) == {"revision"}
    continued = {**restarted, "revision": next_revision(fixture.manifest)}
    output = _rewrite(fixture.path, tmp_path / "continued.shard", manifest=continued)
    assert _judge(fixture, "resave", output) == set()


@pytest.mark.parametrize(
    ("compat", "passes"),
    [(None, True), ((True, "57 passed, 19 xfailed"), True), ((False, "1 failed"), False)],
)
def test_a_red_compatibility_suite_fails_the_check(
    compat: tuple[bool, str] | None, passes: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ecosystem.print_reports([], [], compat) is passes
    out = capsys.readouterr().out
    assert ("compatibility" in out) is (compat is not None)
    assert compat is None or compat[1] in out


def test_compatibility_runs_unless_only_some_consumers_do(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "WORKSPACE.toml").write_text(
        '[[consumers]]\nname = "one"\npath = "one"\n', encoding="utf-8"
    )
    asked = []
    monkeypatch.setattr(ecosystem, "run_compat", lambda scratch: asked.append(1) or (True, "ok"))
    base = ["--workspace", str(tmp_path / "WORKSPACE.toml"), "check", "--skip-tests"]
    assert ecosystem.main([*base, "--keep", str(tmp_path / "a"), "--only", "one"]) == 0
    assert asked == []
    assert ecosystem.main([*base, "--keep", str(tmp_path / "b")]) == 0
    assert asked == [1]
