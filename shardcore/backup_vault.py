"""The backup vault: every bundle state a program writes, kept for reversal.

One global store beside the shard vault (default <workspace>/.vault/backup_vault),
content-addressed like git. Each archive member's bytes are stored once, under
objects/<aa>/<sha256>, so a save that changes one pillar adds only that pillar
and an image is kept once however often its character is saved. Every recorded
state appends one line to journal/<app>.jsonl: time, program, event, file path,
shard_id, name, manifest digest, and the member -> sha256 map that rebuilds the
exact bundle. A state already recorded as the same program's last entry for the
same path is not journaled twice.

Where it records:

    SHARD_BACKUP_VAULT=<dir>   that directory, every write (temp paths included)
    SHARD_BACKUP_VAULT=off     nothing
    unset                      the backup_vault artifact (default .vault/backup_vault)
                               of the first WORKSPACE.toml found above the bundle,
                               this file, the running program, or the working
                               directory, then of a .shards folder at the root of
                               the drive any of those is on. None found: nothing.
                               Paths under the OS temp dir are scratch (tests,
                               editor unpacks, contract runs) and are skipped.

Recording never blocks a save: a failure is logged and swallowed, so the worst
case is a state with no backup, never a save that fails because of one.

The functions live in shardcore/core.py, the one implementation that apps
vendor, so every program records into the same layout; vendor/shardcore.gd
carries a port of record_bundle. This module is the CLI over them.

    python -m shardcore backup where
    python -m shardcore backup history [--id ID] [--name NAME] [--app APP] [--limit N]
    python -m shardcore backup restore <manifest_sha256 or prefix> <dest.shard>
    python -m shardcore backup snapshot <file or folder>...
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from .core import (
    BACKUP_APP_ENV,
    BACKUP_VAULT_DEFAULT,
    BACKUP_VAULT_ENV,
    backup_vault_dir,
    read_journal,
    record_bundle,
    restore_bundle,
)

__all__ = [
    "BACKUP_APP_ENV",
    "BACKUP_VAULT_DEFAULT",
    "BACKUP_VAULT_ENV",
    "backup_vault_dir",
    "main",
    "read_journal",
    "record_bundle",
    "restore_bundle",
]


def _bv_bundles(paths: Iterable[str]) -> Iterable[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(path.rglob("*.shard"))
        elif path.is_file():
            yield path


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="shardcore backup", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("where", help="print the backup vault in use")
    history = sub.add_parser("history", help="list recorded states, oldest first")
    history.add_argument("--id", dest="shard_id")
    history.add_argument("--name")
    history.add_argument("--app")
    history.add_argument("--limit", type=int, default=50)
    restore = sub.add_parser("restore", help="rebuild a recorded state as a .shard")
    restore.add_argument("digest", help="manifest_sha256, or enough of its start to be unique")
    restore.add_argument("dest", help="where to write the .shard")
    snapshot = sub.add_parser("snapshot", help="record existing bundles as they are now")
    snapshot.add_argument("paths", nargs="+", help=".shard files or folders (searched recursively)")
    args = parser.parse_args(argv)

    store = backup_vault_dir()
    if store is None:
        print(
            "backup vault: off (SHARD_BACKUP_VAULT=off, or no WORKSPACE.toml found)",
            file=sys.stderr,
        )
        return 1
    if args.command == "where":
        print(store)
        return 0
    if args.command == "history":
        entries = read_journal(store, shard_id=args.shard_id, name=args.name, app=args.app)
        for e in entries[-args.limit :]:
            print(
                f"{e.get('utc')}  {e.get('manifest_sha256', '')[:12]}  {e.get('app')}:{e.get('event')}"
                f"  {e.get('name')}  {e.get('path')}"
            )
        print(f"{len(entries)} state(s)", file=sys.stderr)
        return 0
    if args.command == "restore":
        print(restore_bundle(store, args.digest, args.dest))
        return 0
    recorded = 0
    for bundle in _bv_bundles(args.paths):
        if record_bundle(bundle, event="snapshot", vault=store, app="backup_snapshot"):
            recorded += 1
        else:
            print(f"skipped {bundle}", file=sys.stderr)
    print(f"recorded {recorded} bundle(s) in {store}")
    return 0
