"""Dispatch `python -m shardcore <subcommand>`.

Subcommands:
    verify    Check a bundle's content against its manifest (integrity).
    diagnose  Report how far a bundle is from the current spec (drift).
    migrate   Migrate a bundle forward to the current spec and repack it.
    neuron    Run the Neuronshard reference tick engine on a bundle.
    backup    The backup vault: where, history, restore, snapshot.
    compare   How two copies of one identity relate (spec 11.5).
    merge     Merge two diverged copies, the base from the backup vault.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable


def _diagnose(argv: list[str]) -> int:
    import argparse
    from pathlib import Path

    from . import __spec_version__
    from .bundle import read_bundle
    from .diagnose import diagnose
    from .model import STATUS_BEHIND, STATUS_CURRENT

    parser = argparse.ArgumentParser(
        prog="shardcore diagnose",
        description="Report a .shard's drift from the current SHARDCORE spec.",
    )
    parser.add_argument("bundle", help="path to the .shard file")
    parser.add_argument(
        "--target", default=__spec_version__, help="target spec version (default: %(default)s)"
    )
    args = parser.parse_args(argv)

    diag = diagnose(read_bundle(Path(args.bundle)), args.target)
    held = f" at spec {diag.state.spec_version}" if diag.status == STATUS_BEHIND else ""
    print(f"{diag.identity}: {diag.status}{held} (target spec {args.target})")
    for finding in diag.findings:
        mig = f" [{finding.migration}]" if finding.migration else ""
        print(f"  [{finding.severity}] {finding.code}{mig}: {finding.detail}")
    return 0 if diag.status in (STATUS_CURRENT, STATUS_BEHIND) else 1


def _compare(argv: list[str]) -> int:
    import argparse

    from .core import common_ancestor, compare_revisions, read_bundle_members

    parser = argparse.ArgumentParser(
        prog="shardcore compare", description="How two copies of one identity relate."
    )
    parser.add_argument("a", help="first .shard")
    parser.add_argument("b", help="second .shard")
    args = parser.parse_args(argv)
    a, _ = read_bundle_members(args.a)
    b, _ = read_bundle_members(args.b)
    relation = compare_revisions(a, b)
    print(relation)
    if relation == "diverged":
        print(f"  common state {common_ancestor(a, b)}")
    return 0


def _merge(argv: list[str]) -> int:
    import argparse

    from .core import merge_bundles, write_merge

    parser = argparse.ArgumentParser(
        prog="shardcore merge",
        description="Merge two diverged copies of one identity. Reports only, unless --out.",
    )
    parser.add_argument("ours", help="one copy; a conflict keeps its side unless --prefer says")
    parser.add_argument("theirs", help="the other copy")
    parser.add_argument("--out", help="write the merge here (may be OURS)")
    parser.add_argument("--vault", help="backup vault holding the base (default: the workspace's)")
    parser.add_argument(
        "--prefer",
        action="append",
        default=[],
        metavar="UNIT=SIDE",
        help="resolve a conflict: soulshard.json#nature=theirs (repeatable)",
    )
    args = parser.parse_args(argv)
    prefer = dict(item.rsplit("=", 1) for item in args.prefer)
    result = merge_bundles(args.ours, args.theirs, vault=args.vault, prefer=prefer)
    print(result["status"])
    if result["base"]:
        print(f"  base {result['base']}")
    for unit in result["conflicts"]:
        print(f"  conflict {unit}")
    if args.out and result["status"] in ("merged", "conflicts"):
        if result["conflicts"]:
            print("not written: resolve every conflict with --prefer first", file=sys.stderr)
            return 1
        manifest = write_merge(args.out, result)
        print(f"wrote {args.out} (revision {manifest['revision']['n']})")
    return 0 if result["status"] in ("same", "ours_newer", "theirs_newer", "merged") else 1


def main(argv: Iterable[str]) -> int:
    argv = list(argv)
    if len(argv) < 2:
        print(
            "usage: python -m shardcore <verify|diagnose|migrate|neuron|backup|compare|merge> [args...]",
            file=sys.stderr,
        )
        return 2
    cmd, rest = argv[1], argv[2:]
    if cmd == "verify":
        from . import verify

        return verify.main(rest)
    if cmd == "diagnose":
        return _diagnose(rest)
    if cmd == "migrate":
        from . import migrate

        return migrate.main(rest)
    if cmd == "neuron":
        from . import neuron

        return neuron.main(rest)
    if cmd == "backup":
        from . import backup_vault

        return backup_vault.main(rest)
    if cmd == "compare":
        return _compare(rest)
    if cmd == "merge":
        return _merge(rest)
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


def _cli_entry() -> None:
    sys.exit(main(sys.argv))


if __name__ == "__main__":
    _cli_entry()
