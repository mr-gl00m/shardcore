"""Dispatch `python -m shardcore <subcommand>`.

Subcommands:
    verify    Check a bundle's content against its manifest (integrity).
    diagnose  Report how far a bundle is from the current spec (drift).
    migrate   Migrate a bundle forward to the current spec and repack it.
    neuron    Run the Neuronshard reference tick engine on a bundle.
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
    from .model import STATUS_CURRENT

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
    print(f"{diag.identity}: {diag.status} (target spec {args.target})")
    for finding in diag.findings:
        mig = f" [{finding.migration}]" if finding.migration else ""
        print(f"  [{finding.severity}] {finding.code}{mig}: {finding.detail}")
    return 0 if diag.status == STATUS_CURRENT else 1


def main(argv: Iterable[str]) -> int:
    argv = list(argv)
    if len(argv) < 2:
        print(
            "usage: python -m shardcore <verify|diagnose|migrate|neuron> [args...]", file=sys.stderr
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
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


def _cli_entry() -> None:
    sys.exit(main(sys.argv))


if __name__ == "__main__":
    _cli_entry()
