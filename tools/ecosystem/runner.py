"""Run a consumer's contract adapter inside that consumer's own environment.

The ecosystem check starts this with the consumer's interpreter (`uv run` in
the consumer root), so the adapter imports the app exactly as the app does.
Stdlib only and Python 3.10+, since it runs under every consumer's venv.

    python runner.py <adapter.py> describe
    python runner.py <adapter.py> run <jobs.json> <out_dir>

An adapter is a plain module:

    OPERATIONS = {"save": {"kind": "resave", "run": save}, ...}

    def save(source: Path, *, work: Path) -> Path | None: ...

`run` takes one path per job input (none for kind "new", two for "offspring")
plus a keyword-only `work` directory it may write into, and returns the bundle
it wrote. An optional `setup(home: Path)` runs once before the first job. Before
the adapter is imported, SHARDCORE_CONTRACT_HOME names a scratch directory the
adapter points every app data root at, so a run never touches real app data.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import traceback
from pathlib import Path
from types import ModuleType


def _load_adapter(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("shardcore_contract_adapter", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load adapter {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _describe(adapter: ModuleType) -> dict:
    return {name: op["kind"] for name, op in adapter.OPERATIONS.items()}


def _run(adapter: ModuleType, jobs: list[dict], out_dir: Path) -> list[dict]:
    setup = getattr(adapter, "setup", None)
    if setup is not None:
        setup(Path(os.environ["SHARDCORE_CONTRACT_HOME"]))
    results = []
    for job in jobs:
        work = out_dir / job["id"]
        sources: list[Path] = []
        for index, raw in enumerate(job["inputs"]):
            source = Path(raw)
            # One folder per input, so two inputs with one file name never collide.
            copy = work / "in" / str(index) / source.name
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copy)
            sources.append(copy)
        result = {
            "id": job["id"],
            "sources": [str(p) for p in sources],
            "output": None,
            "error": None,
        }
        try:
            output = adapter.OPERATIONS[job["operation"]]["run"](*sources, work=work)
            result["output"] = str(output) if output is not None else None
        except Exception as exc:  # noqa: BLE001 - every failure is a result, never a crash
            tail = traceback.format_exc().strip().splitlines()[-3:]
            result["error"] = f"{type(exc).__name__}: {exc}"
            result["trace"] = tail
        results.append(result)
    return results


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[2] not in {"describe", "run"}:
        print(__doc__, file=sys.stderr)
        return 2
    adapter = _load_adapter(Path(argv[1]).resolve())
    if argv[2] == "describe":
        print(json.dumps(_describe(adapter)))
        return 0
    jobs = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
    out_dir = Path(argv[4])
    results = _run(adapter, jobs, out_dir)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
