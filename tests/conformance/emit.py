"""Emit the conformance fixtures as .shard files for a foreign runtime.

python tests/conformance/emit.py <outdir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from cases import emit_all


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    written = emit_all(Path(argv[1]))
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
