"""Bundle integrity validator, sharing the v1.9 reader's single hash path.

verify_bundle answers one question: does this .shard's content match what its
manifest claims? It checks the archive opens, manifest.json parses, the one
required pillar (soulshard.json) is present, and every file the manifest lists
is present with a matching SHA-256. Spec-conformance drift (schema ids, stale
version fields, legacy layout) is diagnose's job, not verify's.

This preserves the v1.0 contract `verify_bundle(path) -> list[str]` (an empty
list means valid) while routing the actual integrity check through
bundle.read_bundle, so there is one hashing code path in the library.

`python -m shardcore verify <path.shard>` exits 0 on success, 1 on any
violation.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from .bundle import read_bundle

REQUIRED_PILLARS = ("soulshard.json",)


def verify_bundle(path: str | Path) -> list[str]:
    """Return a list of violation messages. An empty list means the bundle is valid."""
    p = Path(path)
    if not p.exists():
        return [f"file does not exist: {p}"]

    state = read_bundle(p)
    if not state.readable:
        return [state.error or "cannot read bundle"]

    errors: list[str] = []
    present = {pillar.name for pillar in state.pillars if pillar.present}
    for pillar in REQUIRED_PILLARS:
        if pillar not in present:
            errors.append(f"missing required pillar: {pillar}")

    if not state.has_integrity_data:
        errors.append("manifest carries no per-file SHA-256 data to verify against")
        return errors

    for pillar in state.pillars:
        if pillar.manifest_sha256 is None:
            continue
        if not pillar.present:
            errors.append(f"manifest lists {pillar.name!r} but it is not in the archive")
        elif not pillar.integrity_ok:
            actual = pillar.computed_sha256 or "(absent)"
            errors.append(
                f"{pillar.name}: sha256 mismatch "
                f"(manifest={pillar.manifest_sha256[:12]}..., actual={actual[:12]}...)"
            )
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="shardcore verify",
        description="Validate a .shard bundle's integrity against its manifest (SHARDCORE v1.9).",
    )
    parser.add_argument("bundle", help="path to the .shard file")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="only print errors; no pass summary"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    errors = verify_bundle(args.bundle)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"OK: {args.bundle} passes integrity verification")
    return 0


if __name__ == "__main__":
    sys.exit(main())
