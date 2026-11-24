"""Parity between the GDScript helper (vendor/shardcore.gd) and this library.

Godot apps vendor shardcore.gd instead of the Python helper, so it is a third
writer and a second strict reader. These tests run it under a headless Godot
and hold its output to the library: same version, schema ids and identity
derivation, the same canonical JSON, bundles it writes diagnose current, and
its reader accepts and rejects the conformance cases as read_bundle_document
does.

Godot comes from $GODOT, else ~/.godot/Godot_v4.7.2-stable_win64_console.exe.
The module skips when neither exists.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from shardcore import diagnose, lineage_errors, manifest_digest, read_bundle
from shardcore.bundle import X_NEXUS_KEYS
from shardcore.document import BundleReadError, read_bundle_document
from shardcore.lineage import IDENTITY_NAMESPACE
from shardcore.registry import SPEC_VERSION, schema_for_member

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "vendor" / "shardcore.gd"
PY_HELPER = ROOT / "shardcore" / "core.py"
sys.path.insert(0, str(ROOT / "tests" / "conformance"))
import cases  # noqa: E402


def _godot() -> Path | None:
    candidates = [
        os.environ.get("GODOT"),
        str(Path.home() / ".godot" / "Godot_v4.7.2-stable_win64_console.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


GODOT = _godot()
pytestmark = pytest.mark.skipif(GODOT is None, reason="no Godot binary ($GODOT)")

# Runs each job against the helper and writes the results with the helper's own JSON
# writer, so integers come back as integers.
DRIVER = """
extends SceneTree

const SC = preload("res://shardcore.gd")


func _init() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else ""
	var jobs: Array = JSON.parse_string(FileAccess.get_file_as_string(args["jobs"]))
	var out := []
	for job in jobs:
		out.append(_run(job))
	var f := FileAccess.open(args["out"], FileAccess.WRITE)
	f.store_string(SC.json_text(out))
	f.close()
	quit()


func _run(job: Dictionary) -> Variant:
	match job["op"]:
		"constants":
			var schemas := {}
			for name in job["names"]:
				schemas[name] = SC.schema_for_member(name)
			var neuron := {}
			for text in job.get("neuron_documents", []):
				neuron[text] = SC.schema_for_member("neuronshard.json", (text as String).to_utf8_buffer())
			return {"spec": SC.SPEC_VERSION, "mind": SC.MIND_FORMAT_VERSION,
				"namespace": SC.IDENTITY_NAMESPACE, "x_nexus": SC.X_NEXUS_KEYS, "schemas": schemas,
				"neuron": neuron}
		"digest":
			return {"digest": SC.manifest_digest(job["manifest"]),
				"canonical": SC.canonical_json(job["manifest"]).get_string_from_utf8(),
				"minted": SC.mint_shard_id(job["manifest"])}
		"pack":
			var soul: Dictionary = SC.prepare_soul_for_write(job["soul"])
			var members := {"soulshard.json": SC.json_text(soul).to_utf8_buffer()}
			for name in job.get("members", {}):
				members[name] = (job["members"][name] as String).to_utf8_buffer()
			var r: Dictionary = SC.pack_bundle(job["path"], members, soul, job.get("prior"), job.get("opts", {}))
			return {"ok": r["ok"], "code": r.get("code", "")}
		"branch":
			var parent: Dictionary = SC.read_bundle(job["parent"])
			var soul: Dictionary = SC.prepare_soul_for_write(job["soul"])
			var members := {"soulshard.json": SC.json_text(soul).to_utf8_buffer()}
			var r: Dictionary = SC.pack_bundle(job["path"], members, soul, SC.branch_manifest(parent["manifest"]))
			return {"ok": r["ok"], "code": r.get("code", "")}
		"read":
			var r: Dictionary = SC.read_bundle(job["path"], job.get("opts", {}))
			return {"ok": r["ok"], "code": r.get("code", ""), "digest": r.get("manifest_sha256", "")}
		"less":
			return SC._version_less(SC.version_tuple(job["a"]), SC.version_tuple(job["b"]))
		"tuple":
			return SC.version_tuple(job["value"])
		"writable":
			return SC.check_spec_writable(job["manifest"])
		"stamp":
			var members := {}
			for name in job["members"]:
				members[name] = (job["members"][name] as String).to_utf8_buffer()
			var opts := {"now": "2026-01-02T03:04:05Z"}
			for key in ["merged_with", "upgrade_to"]:
				if job.get(key) != null:
					opts[key] = job[key]
			var m: Dictionary = SC.build_manifest(members, null, job["prior"], opts)
			m.erase("shard_id" if not job["prior"].has("shard_id") else "")
			return {"manifest": m, "kept": SC.kept_spec(job["prior"], job.get("merged_with")),
				"content": SC.content_spec(members)}
		"tiered":
			return SC.ensure_tiered_mind(job["mind"])
		"stats":
			var soul: Dictionary = job["soul"]
			SC.normalize_stat_block(soul)
			return soul
		"utc":
			return SC.to_utc_z(job["value"])
		"revision":
			return SC.next_revision(job.get("prior"), job.get("merged"))
		"compare":
			return [SC.compare_revisions(job["a"], job["b"]), SC.common_ancestor(job["a"], job["b"])]
		"written":
			var r: Dictionary = SC.read_bundle(job["path"])
			return r["manifest"].get("revision")
	return null
"""


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("gd_helper")
    (root / "project.godot").write_text(
        'config_version=5\n\n[application]\nconfig/name="shardcore_gd"\n', encoding="utf-8"
    )
    shutil.copy2(HELPER, root / "shardcore.gd")
    (root / "driver.gd").write_text(DRIVER.lstrip(), encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def py() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vendored_shardcore_v19_for_gd", PY_HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gd(project: Path, jobs: list[dict[str, Any]]) -> list[Any]:
    jobs_file = project / "jobs.json"
    out_file = project / "out.json"
    jobs_file.write_text(json.dumps(jobs), encoding="utf-8")
    out_file.unlink(missing_ok=True)
    done = subprocess.run(
        # A script error leaves Godot idling instead of quitting; --quit-after ends it.
        [
            str(GODOT),
            "--headless",
            "--path",
            str(project),
            "--quit-after",
            "300",
            "-s",
            "res://driver.gd",
            "--",
            f"--jobs={jobs_file}",
            f"--out={out_file}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out_file.is_file(), done.stdout + done.stderr
    return json.loads(out_file.read_text(encoding="utf-8"))


def _soul(name: str = "Parity") -> dict[str, Any]:
    return {
        "name": name,
        "identity": f"{name} checks the GDScript helper.",
        "personality": "Exact.",
        "stat_block": {"STR": 5, "TMP": 6},
    }


def _manifest(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json"))


def test_constants_match_library(project: Path) -> None:
    names = [
        *cases_pillars(),
        "body/items/a.json",
        "assets/images/a.png",
        "images/a.png",
        "portrait.webp",
        "notes.txt",
    ]
    documents = [
        '{"version": "1.1"}',
        '{"version": "1.0"}',
        '{"version": "9.9"}',
        '{"version": 1.1}',
        "not json",
        "[]",
    ]
    [got] = gd(project, [{"op": "constants", "names": names, "neuron_documents": documents}])
    for text in documents:  # a neuronshard is stamped by the version its document declares
        assert got["neuron"][text] == schema_for_member("neuronshard.json", text.encode()), text
    assert got["neuron"]['{"version": "1.1"}'] == "shardcore/neuron@1.1"
    assert got["spec"] == SPEC_VERSION
    assert got["namespace"] == str(IDENTITY_NAMESPACE)
    assert frozenset(got["x_nexus"]) == X_NEXUS_KEYS
    for name in names:
        assert (got["schemas"][name] or None) == schema_for_member(name), name


def cases_pillars() -> list[str]:
    return [
        "soulshard.json",
        "shellshard.json",
        "mindshard.json",
        "memoryshard.json",
        "neuronshard.json",
        "canonshard.json",
        "statshard.json",
        "driveshard.json",
        "worldshard.json",
    ]


def test_canonical_json_and_identity_match(project: Path) -> None:
    manifests = [
        {"spec_version": "1.9", "shard_name": "Nine", "files": {}},
        {"b": 1, "B": 2, "a": [3, True, None, "x"], "_z": {"nested": {"k": -7, "j": 0}}},
        {
            "text": 'quote " slash \\ newline \n tab \t bell \u0007 del \u007f é snow ☃ emoji \U0001f3b0'
        },
        {
            "spec_version": "1.10",
            "files": {
                "soulshard.json": {"sha256": "0" * 64, "size": 4096, "schema": "shardcore/soul@1.9"}
            },
        },
    ]
    got = gd(project, [{"op": "digest", "manifest": m} for m in manifests])
    for manifest, result in zip(manifests, got, strict=True):
        digest = manifest_digest(manifest)
        assert result["digest"] == digest, (result["canonical"], manifest)
        if "files" in manifest:
            assert result["minted"] == str(uuid.uuid5(IDENTITY_NAMESPACE, digest))
    [seed] = gd(project, [{"op": "digest", "manifest": {"card": {"name": "Seed"}}}])
    assert uuid.UUID(seed["minted"]).version == 4


def test_written_bundle_diagnoses_current(project: Path, tmp_path: Path) -> None:
    target = tmp_path / "fresh.shard"
    [r] = gd(project, [{"op": "pack", "path": str(target), "soul": _soul()}])
    assert r["ok"], r
    result = diagnose(read_bundle(target), SPEC_VERSION)
    assert result.status == "current", [f.code for f in result.findings]
    read_bundle_document(target)
    assert uuid.UUID(_manifest(target)["shard_id"]).version == 4


def test_save_keeps_shard_id_and_unknown_keys(project: Path, tmp_path: Path) -> None:
    target = tmp_path / "kept.shard"
    prior = {
        "spec_version": "1.10",
        "shard_id": "kept-id",
        "files": {},
        "x_vendor": {"n": 3},
        "created": "2026-07-01T10:00:00+02:00",
        "memory_format": "old",
    }
    [r] = gd(project, [{"op": "pack", "path": str(target), "soul": _soul(), "prior": prior}])
    assert r["ok"], r
    manifest = _manifest(target)
    assert manifest["shard_id"] == "kept-id"
    assert manifest["x_vendor"] == {"n": 3}
    assert manifest["created"] == "2026-07-01T08:00:00Z"
    assert "memory_format" not in manifest
    assert manifest["spec_version"] == manifest["bundle_version"] == "1.10"  # a save keeps it


def test_branch_is_a_new_identity_with_valid_lineage(project: Path, tmp_path: Path) -> None:
    parent_path = tmp_path / "prime.shard"
    child_path = tmp_path / "prime.branch.shard"
    results = gd(
        project,
        [
            {
                "op": "pack",
                "path": str(parent_path),
                "soul": _soul("Prime"),
                "opts": {"immutable": True},
            },
            {
                "op": "branch",
                "parent": str(parent_path),
                "path": str(child_path),
                "soul": _soul("Prime"),
            },
        ],
    )
    assert all(r["ok"] for r in results), results
    parent = _manifest(parent_path)
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


@pytest.mark.parametrize("declared", ["1.13", "1.99", "2.0"])
def test_newer_spec_is_never_rewritten(project: Path, tmp_path: Path, declared: str) -> None:
    target = tmp_path / "newer.shard"
    prior = {"spec_version": declared, "shard_id": "x", "files": {}}
    [r, msg] = gd(
        project,
        [
            {"op": "pack", "path": str(target), "soul": _soul(), "prior": prior},
            {"op": "writable", "manifest": prior},
        ],
    )
    assert not r["ok"] and r["code"] == "newer_spec"
    assert msg
    assert not target.exists()


def test_the_stamped_version_matches_python(project: Path, py: ModuleType) -> None:
    soul = json.dumps({"name": "Stamp"})
    plain = {"soulshard.json": soul}
    neural = {
        **plain,
        "shellshard.json": json.dumps({"anatomy_profile": {"parts": {"h": {"neural": {}}}}}),
    }
    neuron = {**plain, "neuronshard.json": '{"version": "1.1"}'}

    def state(spec: str, members: dict[str, str], **keys: Any) -> dict[str, Any]:
        files = py.build_files_info({n: d.encode() for n, d in members.items()})
        return {"spec_version": spec, "bundle_version": spec, "files": files, **keys}

    jobs = [
        {"prior": state(spec, plain), "members": members}
        for spec in ("1.0", "1.9", "1.10", "1.11", "1.12")
        for members in (plain, neural, neuron)
    ]
    jobs += [
        {"prior": state("1.11", neuron), "members": neuron},  # held already
        {"prior": state("1.9", plain), "members": neural, "upgrade_to": "1.12"},
        {"prior": state("1.9", plain), "members": plain, "upgrade_to": "1.99"},
        {
            "prior": state("1.10", plain),
            "members": plain,
            "merged_with": state("1.11", plain, min_writer="1.9"),
        },
        {"prior": state("1.99", plain, min_writer="1.10"), "members": plain},
        {"prior": state("1.99", plain, min_writer="1.98"), "members": plain},
        {"prior": state("1.12", plain, min_writer="1.13"), "members": plain},
        {"prior": state("2.0", plain, min_writer="1.9"), "members": plain},
        {"prior": state("1.99", plain, min_writer="soon"), "members": plain},
    ]
    got = gd(project, [{"op": "stamp", **job} for job in jobs])
    for job, result in zip(jobs, got, strict=True):
        members = {n: d.encode() for n, d in job["members"].items()}
        assert result["kept"] == py.kept_spec(job["prior"], merged_with=job.get("merged_with"))
        assert result["content"] == py.content_spec(members)
        try:
            want = py.build_manifest(
                members,
                prior_manifest=job["prior"],
                merged_with=job.get("merged_with"),
                upgrade_to=job.get("upgrade_to"),
                now="2026-01-02T03:04:05Z",
            )
            if "shard_id" not in job["prior"]:
                want.pop("shard_id", None)  # minted from the digest, checked elsewhere
        except (py.ShardError, ValueError):
            want = {}
        assert result["manifest"] == want, job


def test_a_save_that_needs_an_upgrade_is_reported(project: Path, tmp_path: Path) -> None:
    target = tmp_path / "older.shard"
    prior = {"spec_version": "1.11", "shard_id": "kept-id", "files": {}}
    job = {"op": "pack", "path": str(target), "soul": _soul(), "prior": prior}
    newer = {**job, "members": {"neuronshard.json": '{"version": "1.1"}'}}
    [refused] = gd(project, [newer])
    assert refused == {"ok": False, "code": "upgrade_needed"}
    assert not target.exists()
    [plain] = gd(project, [job])
    assert plain["ok"] and _manifest(target)["spec_version"] == "1.11"
    original = target.read_bytes()
    [raised] = gd(project, [{**newer, "opts": {"upgrade_to": "1.12"}}])
    assert raised["ok"] and _manifest(target)["spec_version"] == "1.12"
    assert (tmp_path / "older.shard.v1.11.bak").read_bytes() == original
    [again] = gd(project, [{**newer, "prior": _manifest(target), "opts": {"upgrade_to": "1.12"}}])
    assert again["ok"] and len(list(tmp_path.glob("*.bak"))) == 1


def test_versions_compare_numerically(project: Path) -> None:
    less, bad, odd = gd(
        project,
        [
            {"op": "less", "a": "1.9", "b": "1.10"},
            {"op": "tuple", "value": "1.x"},
            {"op": "tuple", "value": 1.1},
        ],
    )
    assert less is True
    assert bad == [] and odd == []
    same = gd(
        project,
        [{"op": "writable", "manifest": {"spec_version": v}} for v in ("1.0", "1.9", SPEC_VERSION)],
    )
    assert same == ["", "", ""]


@pytest.mark.parametrize("lenient", [False, True], ids=["strict", "no_schemas_required"])
def test_reader_agrees_with_library(project: Path, tmp_path: Path, lenient: bool) -> None:
    built = {}
    for case in cases.CASES:
        built[case.name] = case.build(tmp_path / f"{case.name}.shard")
    opts = {"require_schemas": False} if lenient else {}
    got = gd(project, [{"op": "read", "path": str(path), "opts": opts} for path in built.values()])
    for (name, path), result in zip(built.items(), got, strict=True):
        try:
            document = read_bundle_document(path, require_schemas=not lenient)
        except BundleReadError as exc:
            assert not result["ok"], f"{name}: library rejects ({exc.code}), helper accepts"
            assert result["code"] == exc.code, f"{name}: {result['code']} != {exc.code}"
        else:
            if result["code"] == "future_spec":
                # The document reader leaves the major check to diagnose; a runtime must
                # refuse it on load (spec 13.2), and the helper is the runtime's reader.
                codes = {f.code for f in diagnose(read_bundle(path), SPEC_VERSION).findings}
                assert "future_spec" in codes, name
                continue
            assert result["ok"], f"{name}: library accepts, helper rejects ({result['code']})"
            assert result["digest"] == document.manifest_sha256, name


def test_reader_rejects_tampering(project: Path, tmp_path: Path) -> None:
    source = tmp_path / "plain.shard"
    gd(project, [{"op": "pack", "path": str(source), "soul": _soul()}])
    tampered = tmp_path / "tampered.shard"
    with (
        zipfile.ZipFile(source) as src,
        zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for info in src.infolist():
            data = src.read(info)
            if info.filename == "soulshard.json":
                data = data.replace(b"Exact.", b"Exakt.")
            dst.writestr(info.filename, data)
    [r] = gd(project, [{"op": "read", "path": str(tampered)}])
    assert not r["ok"] and r["code"] == "hash_mismatch"


def test_mind_and_stats_match_the_python_helper(project: Path, py: ModuleType) -> None:
    minds = [
        None,
        [{"id": "m1"}],
        {"memories": [{"id": "m2"}], "owner": "x"},
        {"core": [], "format_version": "2.0"},
        {"vitality": 1},
    ]
    souls = [
        {"name": "A"},
        {
            "name": "B",
            "stat_block": {"strength": 7.5, "Presence": 11, "Resonance": "hum", "luck": 3},
        },
        {"name": "C", "resonance": "set", "stat_block": {"STR": 2.5, "resonance": "other"}},
    ]
    got = gd(
        project,
        [{"op": "tiered", "mind": m} for m in minds] + [{"op": "stats", "soul": s} for s in souls],
    )
    for mind, result in zip(minds, got[: len(minds)], strict=True):
        assert result == py.ensure_tiered_mind(mind), mind
    for soul, result in zip(souls, got[len(minds) :], strict=True):
        expected = dict(soul)
        py.normalize_stat_block(expected)
        assert result == expected, soul


def test_utc_normalization(project: Path) -> None:
    values = [
        "2026-07-06T00:00:00Z",
        "2026-07-06T10:00:00+02:00",
        "2026-07-06T10:00:00.123-05:30",
        "nonsense",
        "",
    ]
    got = gd(project, [{"op": "utc", "value": v} for v in values])
    assert got == ["2026-07-06T00:00:00Z", "2026-07-06T08:00:00Z", "2026-07-06T15:30:00Z", "", ""]


def test_gd_writes_land_in_the_backup_vault_python_restores(
    project: Path, tmp_path: Path, monkeypatch
) -> None:
    from shardcore import backup_vault as bv

    store = tmp_path / "backup_vault"
    monkeypatch.setenv(bv.BACKUP_VAULT_ENV, str(store))
    monkeypatch.setenv(bv.BACKUP_APP_ENV, "")
    target = tmp_path / "house.shard"
    results = gd(
        project,
        [
            {
                "op": "pack",
                "path": str(target),
                "soul": _soul("House"),
                "opts": {"app": "gd_parity"},
            },
            {
                "op": "pack",
                "path": str(target),
                "soul": _soul("House Again"),
                "opts": {"app": "gd_parity"},
            },
        ],
    )
    assert all(r["ok"] for r in results), results
    entries = bv.read_journal(store, app="gd_parity")
    assert [e["event"] for e in entries] == ["write", "write"]
    assert entries[-1]["path"] == target.resolve().as_posix()
    assert entries[-1]["manifest_sha256"] == manifest_digest(_manifest(target))
    with zipfile.ZipFile(target) as archive:
        current = {n: archive.read(n) for n in archive.namelist()}
    bv.restore_bundle(store, entries[0]["manifest_sha256"], tmp_path / "first.shard")
    with zipfile.ZipFile(tmp_path / "first.shard") as archive:
        assert json.loads(archive.read("soulshard.json"))["name"] == "House"
    bv.restore_bundle(store, entries[-1]["manifest_sha256"], tmp_path / "last.shard")
    with zipfile.ZipFile(tmp_path / "last.shard") as archive:
        assert {n: archive.read(n) for n in archive.namelist()} == current


def _chain(py: ModuleType, length: int) -> list[dict]:
    manifests = [
        {"spec_version": SPEC_VERSION, "shard_id": "chain", "files": {}, "card": {"name": "0"}}
    ]
    for i in range(1, length):
        prior = manifests[-1]
        manifests.append({**prior, "card": {"name": str(i)}, "revision": py.next_revision(prior)})
    return manifests


def test_revision_chain_matches_the_python_helper(project: Path, py: ModuleType) -> None:
    states = _chain(py, 20)
    old = {"spec_version": "1.10", "shard_id": "chain", "files": {}}
    jobs = [{"op": "revision", "prior": s} for s in states]
    jobs += [
        {"op": "revision"},
        {"op": "revision", "prior": {"card": {"name": "seed"}}},
        {"op": "revision", "prior": old},
    ]
    jobs.append({"op": "revision", "prior": states[5], "merged": states[9]})
    expected = [py.next_revision(s) for s in states]
    expected += [
        {"n": 1},
        {"n": 1},
        py.next_revision(old),
        py.next_revision(states[5], merged_with=states[9]),
    ]
    assert gd(project, jobs) == expected


def test_compare_matches_the_python_helper(project: Path, py: ModuleType) -> None:
    states = _chain(py, 6)
    fork = {**states[3], "card": {"name": "fork"}, "revision": py.next_revision(states[3])}
    pairs = [
        (states[5], states[5]),
        (states[5], states[2]),
        (states[2], states[5]),
        (states[5], fork),
        ({"shard_id": "chain", "files": {}}, {"shard_id": "chain", "files": {}, "x": 1}),
        (states[1], {**states[1], "shard_id": "other"}),
    ]
    got = gd(project, [{"op": "compare", "a": a, "b": b} for a, b in pairs])
    want = []
    for a, b in pairs:
        try:
            relation = py.compare_revisions(a, b)
        except ValueError:
            relation = ""
        want.append([relation, py.common_ancestor(a, b) or ""])
    assert got == want


def test_gd_saves_continue_the_chain(project: Path, tmp_path: Path) -> None:
    target = tmp_path / "chain.shard"
    first, second = gd(
        project,
        [
            {"op": "pack", "path": str(target), "soul": _soul()},
            {"op": "written", "path": str(target)},
        ],
    )
    assert first["ok"] and second == {"n": 1}
    prior = json.loads(zipfile.ZipFile(target).read("manifest.json"))
    again, revision = gd(
        project,
        [
            {"op": "pack", "path": str(target), "soul": _soul(), "prior": prior},
            {"op": "written", "path": str(target)},
        ],
    )
    assert again["ok"]
    pin = manifest_digest(prior)
    assert revision == {"n": 2, "prior": pin, "history": [pin]}
