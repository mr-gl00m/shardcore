"""The backup vault: every written state recorded once, restorable byte for byte."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

from shardcore import backup_vault as bv
from shardcore import core
from shardcore.builder import build_bundle

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("vendored_helper", ROOT / "shardcore" / "core.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

SOUL = {
    "name": "Bessie",
    "identity": "x",
    "personality": "y",
    "stat_block": {
        s: 5 for s in ("STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS")
    },
}
IMAGE = b"\x89PNG" + bytes(range(256)) * 8


@pytest.fixture
def store(tmp_path, monkeypatch):
    vault = tmp_path / "backup_vault"
    monkeypatch.setenv(bv.BACKUP_VAULT_ENV, str(vault))
    monkeypatch.setenv(bv.BACKUP_APP_ENV, "tester")
    return vault


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def _pack(path: Path, soul: dict, image: bytes = IMAGE) -> None:
    members = {"soulshard.json": json.dumps(soul).encode(), "assets/images/b.png": image}
    sc.pack_bundle(path, members, soul=soul, prior_manifest=sc.read_manifest(path))


def test_every_write_is_journaled_and_objects_are_kept_once(store, tmp_path):
    bundle = tmp_path / "bessie.shard"
    _pack(bundle, SOUL)
    _pack(bundle, {**SOUL, "nature": {"label": "Shy"}})
    entries = bv.read_journal(store)
    assert [e["event"] for e in entries] == ["write", "write"]  # "replaced" equals the first write
    assert entries[0]["manifest_sha256"] != entries[1]["manifest_sha256"]
    assert {e["name"] for e in entries} == {"Bessie"}
    image_sha = entries[0]["members"]["assets/images/b.png"]
    assert entries[1]["members"]["assets/images/b.png"] == image_sha
    assert len(list((store / "objects").rglob("*"))) - len(list((store / "objects").glob("*"))) == 5


def test_a_state_written_by_another_program_is_kept_before_it_is_replaced(store, tmp_path):
    bundle = tmp_path / "bessie.shard"
    with zipfile.ZipFile(bundle, "w") as zf:  # a writer that does not record
        zf.writestr(
            "manifest.json", json.dumps({"spec_version": "1.10", "shard_name": "Old", "files": {}})
        )
        zf.writestr("soulshard.json", "{}")
    before = _members(bundle)
    _pack(bundle, SOUL)
    first = bv.read_journal(store)[0]
    assert first["event"] == "replaced" and first["name"] == "Old"
    bv.restore_bundle(store, first["manifest_sha256"][:10], tmp_path / "back.shard")
    assert _members(tmp_path / "back.shard") == before


def test_restore_rebuilds_the_exact_members_and_records_what_it_replaces(store, tmp_path):
    bundle = tmp_path / "bessie.shard"
    _pack(bundle, SOUL)
    old = bv.read_journal(store)[-1]
    original = _members(bundle)
    _pack(bundle, {**SOUL, "nature": {"label": "Shy"}})
    newer = _members(bundle)
    bv.restore_bundle(store, old["manifest_sha256"], bundle)
    assert _members(bundle) == original
    replaced = [e for e in bv.read_journal(store) if e["event"] == "replaced_by_restore"]
    assert len(replaced) == 1
    bv.restore_bundle(store, replaced[0]["manifest_sha256"], tmp_path / "undo.shard")
    assert _members(tmp_path / "undo.shard") == newer


def test_off_records_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv(bv.BACKUP_VAULT_ENV, "off")
    assert bv.backup_vault_dir() is None
    assert bv.record_bundle(tmp_path / "x.shard", event="write") is None


def test_default_location_skips_scratch_and_names_the_consumer(tmp_path, monkeypatch):
    monkeypatch.delenv(bv.BACKUP_VAULT_ENV, raising=False)
    monkeypatch.delenv(bv.BACKUP_APP_ENV, raising=False)
    workspace = tmp_path / "ws"
    (workspace / "apps" / "farmgame").mkdir(parents=True)
    toml = workspace / "WORKSPACE.toml"
    toml.write_text(
        '[artifacts]\nshards = ".vault/shards"\nbackup_vault = ".vault/bv"\n\n'
        '[[consumers]]\nname = "farmgame"\npath = "apps/farmgame"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(core, "_bv_workspace", lambda near: toml)
    monkeypatch.setattr(core, "_bv_origins", lambda: [workspace / "apps" / "farmgame" / "main.py"])
    assert bv.backup_vault_dir() == workspace / ".vault/bv"
    assert core._bv_app(None) == "farmgame"
    # tmp_path is under the OS temp dir: scratch, so nothing is recorded.
    bundle = workspace / "x.shard"
    _pack_env_off(bundle, monkeypatch)
    assert bv.record_bundle(bundle, event="write") is None
    assert not (workspace / ".vault/bv").exists()


def test_a_workspace_at_a_drive_root_serves_programs_elsewhere_on_it(tmp_path, monkeypatch):
    monkeypatch.delenv(bv.BACKUP_VAULT_ENV, raising=False)
    drive, other = tmp_path / "drive", tmp_path / "other"
    game = drive / "games" / "one" / "game.py"
    game.parent.mkdir(parents=True)
    other.mkdir()
    monkeypatch.setattr(core, "_bv_origins", lambda: [game])
    roots = (drive, other)
    monkeypatch.setattr(
        core, "_bv_drive_root", lambda p: next((r for r in roots if r in (p, *p.parents)), None)
    )
    save = other / "saves" / "x.shard"
    assert bv.backup_vault_dir(save) is None
    (drive / ".shards").mkdir()
    toml = drive / ".shards" / "WORKSPACE.toml"
    toml.write_text('[artifacts]\nbackup_vault = ".vault/bv"\n', encoding="utf-8")
    assert bv.backup_vault_dir(save) == drive / ".shards" / ".vault/bv"
    # A workspace above the program still comes first.
    nearer = game.parent / "WORKSPACE.toml"
    nearer.write_text('[artifacts]\nbackup_vault = "near"\n', encoding="utf-8")
    assert bv.backup_vault_dir(save) == game.parent / "near"


def test_no_machine_path_is_written_into_the_library():
    sources = [*(ROOT / "shardcore").rglob("*.py"), ROOT / "vendor" / "shardcore.gd"]
    assert [s.name for s in sources if ":/." in s.read_text(encoding="utf-8")] == []


def _pack_env_off(bundle: Path, monkeypatch) -> None:
    with monkeypatch.context() as m:
        m.setenv(bv.BACKUP_VAULT_ENV, "off")
        _pack(bundle, SOUL)


def test_library_writers_record(store, tmp_path):
    built = tmp_path / "built.shard"
    build_bundle(built, shard_name="Bessie", members={"soulshard.json": json.dumps(SOUL).encode()})
    assert [e["event"] for e in bv.read_journal(store)] == ["write"]
    assert bv.read_journal(store)[0]["path"] == built.resolve().as_posix()
