"""Bundle validator — checks manifest SHA-256 sums against file contents.

Validates a .shard bundle against the v1.0 spec:
  1. manifest.json exists and parses
  2. Every file listed in manifest["files"] exists in the zip
  3. Every listed file's SHA-256 matches its declared digest
  4. Required pillars (soulshard.json) are present

`python -m shardcore verify <path.shard>` exits 0 on success, non-zero on any
spec violation. Prints a per-file pass/fail report.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Iterable

REQUIRED_PILLARS = ("soulshard.json",)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_bundle(path: str | Path) -> list[str]:
    """Return a list of violation messages. Empty list means the bundle is valid."""
    p = Path(path)
    errors: list[str] = []

    if not p.exists():
        return [f"file does not exist: {p}"]
    if not zipfile.is_zipfile(p):
        return [f"not a valid zip archive: {p}"]

    with zipfile.ZipFile(p, "r") as zf:
        names = set(zf.namelist())

        if "manifest.json" not in names:
            return ["missing required file: manifest.json"]

        try:
            manifest = json.loads(zf.read("manifest.json"))
        except json.JSONDecodeError as exc:
            return [f"manifest.json is not valid JSON: {exc}"]

        for pillar in REQUIRED_PILLARS:
            if pillar not in names:
                errors.append(f"missing required pillar: {pillar}")

        files = manifest.get("files")
        if not isinstance(files, dict):
            errors.append('manifest.files must be an object of {name: {sha256, size}}')
            return errors

        for name, meta in files.items():
            if name not in names:
                errors.append(f"manifest lists {name!r} but it is not in the archive")
                continue
            if not isinstance(meta, dict):
                errors.append(f"manifest.files[{name!r}] must be an object")
                continue
            expected = meta.get("sha256")
            if not isinstance(expected, str):
                errors.append(f"manifest.files[{name!r}].sha256 must be a string")
                continue
            actual = _sha256(zf.read(name))
            if actual != expected:
                errors.append(
                    f"{name}: sha256 mismatch (manifest={expected[:12]}…, actual={actual[:12]}…)"
                )

    return errors


def main(argv: Iterable[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="shardcore.verify",
        description="Validate a .shard bundle against the SHARDCORE v1.0 spec.",
    )
    parser.add_argument("bundle", help="path to the .shard file")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="only print errors; no pass summary")
    args = parser.parse_args(list(argv) if argv is not None else None)

    errors = verify_bundle(args.bundle)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"OK: {args.bundle} conforms to SHARDCORE v1.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
