"""Migrate a .shard forward to the current spec, then repack it atomically.

migrate_bundle is the library's write path. It loads a bundle into a
MutableBundle, runs only the migrations the bundle actually needs (in the
sequence order migrations.ordered defines), and repacks. An upgrade in place
keeps the earlier file; there is no run-log and no restore on failure. A batch
tool that needs the full safety envelope (verify, restore-on-failure, an audit
log) wraps this one call.

A blocked bundle (integrity mismatch, immutable, or already ahead of the
target) raises MigrationError rather than being written. A bundle already at
the target is a no-op.

`python -m shardcore migrate <path.shard>` migrates in place; pass --out to
write the result elsewhere and leave the original untouched.
"""

from __future__ import annotations

import stat
import sys
from collections.abc import Iterable
from pathlib import Path

from .backup_vault import record_bundle
from .bundle import read_bundle
from .core import keep_before_upgrade
from .diagnose import diagnose
from .migrations import ordered
from .model import SEV_BLOCKED, STATUS_BLOCKED
from .mutable import MigrationError, MutableBundle, repack_atomic
from .registry import SPEC_VERSION

DEFAULT_TARGET = SPEC_VERSION


def migrate_bundle(
    path: str | Path, target: str = DEFAULT_TARGET, out: str | Path | None = None
) -> list[str]:
    """Migrate a bundle to `target` and repack it. Returns the applied notes.

    In place, an upgrade with no backup vault to record it keeps the earlier
    file beside the new one, as <name>.v<version>.bak.

    Returns an empty list when the bundle is already at the target (and, in
    that case, only rewrites the file when `out` names a different path).
    Raises MigrationError when the bundle is blocked or a migration cannot
    proceed without guessing or losing data.
    """
    src = Path(path)
    dst = Path(out) if out is not None else src

    diag = diagnose(read_bundle(src), target)
    if diag.status == STATUS_BLOCKED:
        reasons = "; ".join(f.detail for f in diag.findings if f.severity == SEV_BLOCKED)
        raise MigrationError(f"bundle is blocked, not migrating: {reasons}")

    bundle = MutableBundle.load(src)
    plan = ordered({f.migration for f in diag.findings if f.migration})
    if not plan:
        if out is not None and dst != src:
            repack_atomic(bundle, dst)
        return []

    for migration in plan:
        migration.fn(bundle, target)
    in_place = dst == src and bool(src.stat().st_mode & stat.S_IWRITE)
    if in_place and record_bundle(src, event="replaced") is None:
        keep_before_upgrade(src, target)
    repack_atomic(bundle, dst)
    return list(bundle.notes)


def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="shardcore migrate",
        description="Migrate a .shard forward to the current SHARDCORE spec and repack it.",
    )
    parser.add_argument("bundle", help="path to the .shard file")
    parser.add_argument(
        "--target", default=DEFAULT_TARGET, help="target spec version (default: %(default)s)"
    )
    parser.add_argument(
        "--out", default=None, help="write the migrated bundle here instead of in place"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        notes = migrate_bundle(args.bundle, target=args.target, out=args.out)
    except MigrationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    dest = args.out or args.bundle
    if notes:
        for note in notes:
            print(f"  {note}")
        print(f"OK: migrated {args.bundle} to spec {args.target} ({dest})")
    else:
        print(f"OK: {args.bundle} already at spec {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
