"""Keep every shard consumer on the current spec, and prove it.

Consumers (the apps that read or write .shard bundles) are listed in the
workspace's WORKSPACE.toml under [[consumers]]. From the shardcore root:

    uv run python tools/ecosystem/ecosystem.py sync [--check]
    uv run python tools/ecosystem/ecosystem.py check [--only NAME ...] [--skip-tests] [--keep DIR]

sync copies each vendored file (the shardcore_v19 helper, the conformance
cases) from shardcore into every consumer that carries one, keeping each
copy's line endings. --check only reports copies that differ.

check fails when any of these fails:
  1. a vendored copy differs from shardcore's
  2. the contract (contract.py): each consumer's adapter pushes the shardcore
     fixtures through the app's real write paths, in the app's own environment,
     and every output is judged here with shardcore
  3. isolation: the run changed a file under the consumer's root (outside its
     `ignore` globs) or in the vault
  4. the consumer's own test suite
  5. the compatibility suite (tests/compat): frozen old helpers against
     shardcore's, so no update locks out an app that did not take it

--only leaves out 5. A format or writer change is done when this passes.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import contract

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    raise SystemExit("ecosystem.py needs Python 3.11+ (tomllib)") from None

SHARDCORE_ROOT = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).resolve().parent / "runner.py"
_SKIP_DIRS = frozenset(
    {".venv", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules"}
)


@dataclass(frozen=True)
class Consumer:
    name: str
    root: Path
    vendored: dict[str, str]
    adapter: str | None
    tests: tuple[str, ...]
    owns: frozenset[str]
    ignore: tuple[str, ...]
    waive: dict[str, str]


@dataclass
class Report:
    consumer: Consumer
    jobs: int = 0
    failures: list[tuple[str, str, str]] = field(default_factory=list)  # (job, check, detail)
    waived: list[tuple[str, str, str]] = field(default_factory=list)  # (job, check, reason)
    tests: str = "skipped"
    tests_ok: bool = True
    seconds: float = 0.0


def find_workspace(start: Path) -> Path:
    for folder in (start, *start.parents):
        candidate = folder / "WORKSPACE.toml"
        if candidate.is_file():
            return candidate
    raise SystemExit(f"no WORKSPACE.toml above {start}")


def load_consumers(workspace: Path) -> tuple[list[Consumer], Path | None]:
    data = tomllib.loads(workspace.read_text(encoding="utf-8"))
    base = workspace.parent
    consumers = [
        Consumer(
            name=entry["name"],
            root=(base / entry["path"]).resolve(),
            vendored=dict(entry.get("vendored", {})),
            adapter=entry.get("adapter"),
            tests=tuple(entry.get("tests", ())),
            owns=frozenset(entry.get("owns", ())),
            ignore=tuple(entry.get("ignore", ())),
            waive=dict(entry.get("waive", {})),
        )
        for entry in data.get("consumers", [])
    ]
    vault = data.get("artifacts", {}).get("shards")
    return consumers, (base / vault).resolve() if vault else None


# --------------------------------------------------------------------------- #
# Vendored copies
# --------------------------------------------------------------------------- #


def _normalized(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def vendored_drift(consumers: list[Consumer]) -> list[tuple[Consumer, str, str]]:
    """(consumer, copy, problem) for every vendored copy that differs."""
    problems = []
    for consumer in consumers:
        for copy_rel, source_rel in consumer.vendored.items():
            source = SHARDCORE_ROOT / source_rel
            copy = consumer.root / copy_rel
            if not copy.is_file():
                problems.append((consumer, copy_rel, "missing"))
            elif _normalized(copy.read_bytes()) != _normalized(source.read_bytes()):
                problems.append((consumer, copy_rel, f"differs from shardcore {source_rel}"))
    return problems


def sync(consumers: list[Consumer], check_only: bool) -> int:
    drift = vendored_drift(consumers)
    for consumer, copy_rel, problem in drift:
        if check_only:
            print(f"  DIFF  {consumer.name:<14} {copy_rel}: {problem}")
            continue
        source = SHARDCORE_ROOT / consumer.vendored[copy_rel]
        copy = consumer.root / copy_rel
        data = _normalized(source.read_bytes())
        if copy.is_file() and b"\r\n" in copy.read_bytes():
            data = data.replace(b"\n", b"\r\n")
        copy.write_bytes(data)
        print(f"  synced {consumer.name:<14} {copy_rel}")
    if not drift:
        print("  every vendored copy matches shardcore")
    return 1 if (check_only and drift) else 0


# --------------------------------------------------------------------------- #
# Contract run
# --------------------------------------------------------------------------- #


def _uv(
    root: Path, args: list[str], env: dict[str, str], timeout: int = 900
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--offline", "--no-sync", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "SHARDCORE_CONTRACT_HOME": str(home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "QT_QPA_PLATFORM": "offscreen",
            "UV_NO_PROGRESS": "1",
            # Contract runs and consumer suites write test bundles, not characters.
            "SHARD_BACKUP_VAULT": "off",
        }
    )
    env.pop("VIRTUAL_ENV", None)  # let uv pick the consumer's own venv
    return env


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """{relative path: (size, mtime_ns)} for every file under root, cache dirs skipped."""
    files: dict[str, tuple[int, int]] = {}
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in _SKIP_DIRS:
                    stack.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                stat = entry.stat(follow_symlinks=False)
                rel = Path(entry.path).relative_to(root).as_posix()
                files[rel] = (stat.st_size, stat.st_mtime_ns)
    return files


def _changed(before: dict, after: dict, ignore: tuple[str, ...]) -> list[str]:
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    return [p for p in changed if not any(fnmatch.fnmatch(p, glob) for glob in ignore)]


def run_contract(
    consumer: Consumer, fixtures: dict[str, contract.Fixture], scratch: Path, vault: Path | None
) -> Report:
    report = Report(consumer)
    out = scratch / consumer.name
    home = out / "home"
    home.mkdir(parents=True)
    env = _env(home)
    adapter = str(consumer.root / consumer.adapter)

    described = _uv(consumer.root, ["python", str(RUNNER), adapter, "describe"], env)
    if described.returncode != 0:
        report.failures.append(("adapter", "ran", _tail(described)))
        return report
    jobs = contract.plan(json.loads(described.stdout.strip().splitlines()[-1]), fixtures)
    report.jobs = len(jobs)
    jobs_file = out / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            [{"id": j.id, "operation": j.operation, "inputs": list(j.inputs)} for j in jobs]
        ),
        encoding="utf-8",
    )

    root_before = snapshot(consumer.root)
    vault_before = snapshot(vault) if vault else {}
    ran = _uv(consumer.root, ["python", str(RUNNER), adapter, "run", str(jobs_file), str(out)], env)
    for path in _changed(root_before, snapshot(consumer.root), consumer.ignore):
        report.failures.append(("adapter", "isolation", f"changed {path} under the consumer root"))
    if vault:
        for path in _changed(vault_before, snapshot(vault), ()):
            report.failures.append(("adapter", "isolation", f"changed vault file {path}"))
    if ran.returncode != 0 or not (out / "results.json").is_file():
        report.failures.append(("adapter", "ran", _tail(ran)))
        return report

    results = {r["id"]: r for r in json.loads((out / "results.json").read_text(encoding="utf-8"))}
    for job in jobs:
        outcome = contract.judge(job, results[job.id], fixtures, consumer.owns)
        for check, detail in outcome.failures:
            fixture = job.id.split("--", 1)[1] if "--" in job.id else ""
            reason = consumer.waive.get(f"{job.operation}:{check}:{fixture}") or consumer.waive.get(
                f"{job.operation}:{check}"
            )
            if reason:
                report.waived.append((job.id, check, reason))
            else:
                report.failures.append((job.id, check, detail))
    return report


def run_tests(consumer: Consumer, report: Report, scratch: Path) -> None:
    if not consumer.tests:
        report.tests = "none"
        return
    env = _env(scratch / consumer.name / "tests_home")
    done = _uv(consumer.root, list(consumer.tests), env)
    report.tests = _summary(done)
    report.tests_ok = done.returncode == 0


def run_compat(scratch: Path) -> tuple[bool, str] | None:
    """The compatibility suite: (passed, its summary line). None where it is not shipped."""
    if not (SHARDCORE_ROOT / "tests" / "compat").is_dir():
        return None
    args = ["python", "-m", "pytest", "-q", "tests/compat"]
    done = _uv(SHARDCORE_ROOT, args, _env(scratch / "compat_home"))
    return done.returncode == 0, _summary(done)


def _summary(done: subprocess.CompletedProcess) -> str:
    lines = [line.strip() for line in (done.stdout + done.stderr).splitlines() if line.strip()]
    return next(
        (line.strip("= ") for line in reversed(lines) if " passed" in line or " failed" in line),
        lines[-1] if lines else "no output",
    )


def _tail(done: subprocess.CompletedProcess) -> str:
    lines = [line for line in (done.stdout + done.stderr).splitlines() if line.strip()]
    return " | ".join(lines[-4:]) or f"exit {done.returncode}"


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def print_reports(
    drift: list, reports: list[Report], compat: tuple[bool, str] | None = None
) -> bool:
    ok = not drift and (compat is None or compat[0])
    print("\nvendored copies")
    if drift:
        for consumer, copy_rel, problem in drift:
            print(f"  DIFF  {consumer.name:<14} {copy_rel}: {problem}")
    else:
        print("  every vendored copy matches shardcore")

    if compat is not None:
        print("\ncompatibility")
        print(f"  {'ok  ' if compat[0] else 'FAIL'} {compat[1]}")

    print("\nconsumers")
    for r in reports:
        bad_jobs = len({job for job, _check, _detail in r.failures})
        verdict = "ok  " if not r.failures and r.tests_ok else "FAIL"
        ok = ok and verdict == "ok  "
        contract_text = f"{r.jobs - bad_jobs}/{r.jobs} jobs" if r.consumer.adapter else "no adapter"
        if r.waived:
            contract_text += f", {len(r.waived)} waived"
        print(
            f"  {verdict} {r.consumer.name:<14} contract {contract_text:<22} tests {r.tests}  ({r.seconds:.0f}s)"
        )

    failures = [(r.consumer.name, *f) for r in reports for f in r.failures]
    if failures:
        print("\nfailures")
        for name, job, check, detail in failures:
            print(f"  {name:<14} {job:<40} {check:<10} {detail}")
    waived = [(r.consumer.name, *w) for r in reports for w in r.waived]
    if waived:
        print("\nwaived (known gaps, listed in WORKSPACE.toml)")
        for name, job, check, reason in waived:
            print(f"  {name:<14} {job:<40} {check:<10} {reason}")
    print(f"\nresult: {'PASS' if ok else 'FAIL'}")
    return ok


def check(
    consumers: list[Consumer],
    vault: Path | None,
    skip_tests: bool,
    keep: Path | None,
    with_compat: bool,
) -> int:
    print(f"shardcore ecosystem check: spec {contract.SPEC_VERSION}, {len(consumers)} consumers")
    drift = vendored_drift(consumers)
    scratch = keep or Path(tempfile.mkdtemp(prefix="shard_ecosystem_"))
    scratch.mkdir(parents=True, exist_ok=True)
    fixtures = contract.build_fixtures(scratch / "fixtures")
    compat = None
    if with_compat:
        print("  running compatibility ...", flush=True)
        compat = run_compat(scratch)
    reports = []
    for consumer in consumers:
        started = time.monotonic()
        print(f"  running {consumer.name} ...", flush=True)
        if consumer.adapter:
            report = run_contract(consumer, fixtures, scratch, vault)
        else:
            report = Report(consumer)
        if not skip_tests:
            run_tests(consumer, report, scratch)
        report.seconds = time.monotonic() - started
        reports.append(report)
    ok = print_reports(drift, reports, compat)
    if ok and keep is None:
        shutil.rmtree(scratch, ignore_errors=True)
    else:
        print(f"fixtures, adapter outputs and results kept in {scratch}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workspace", type=Path, help="WORKSPACE.toml (default: nearest above shardcore)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sync_cmd = sub.add_parser("sync", help="copy vendored files from shardcore into every consumer")
    sync_cmd.add_argument("--check", action="store_true", help="only report copies that differ")
    check_cmd = sub.add_parser("check", help="vendored copies, contract, isolation, consumer tests")
    check_cmd.add_argument("--only", nargs="+", metavar="NAME", help="check only these consumers")
    check_cmd.add_argument(
        "--skip-tests", action="store_true", help="skip the consumers' own suites"
    )
    check_cmd.add_argument(
        "--keep", type=Path, metavar="DIR", help="keep fixtures and outputs in DIR"
    )
    args = parser.parse_args(argv)

    workspace = args.workspace or find_workspace(SHARDCORE_ROOT)
    consumers, vault = load_consumers(workspace)
    if args.command == "sync":
        return sync(consumers, args.check)
    if args.only:
        unknown = set(args.only) - {c.name for c in consumers}
        if unknown:
            raise SystemExit(f"unknown consumer(s): {', '.join(sorted(unknown))}")
        consumers = [c for c in consumers if c.name in args.only]
    return check(consumers, vault, args.skip_tests, args.keep, with_compat=not args.only)


if __name__ == "__main__":
    raise SystemExit(main())
