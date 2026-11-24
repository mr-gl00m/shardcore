"""The writer contract every shard consumer is held to, checked with this library.

A consumer's adapter pushes the fixtures below through the app's real write
paths. Each output is then read back here, with shardcore rather than the
helper that wrote it, and judged by what the operation claims to be:

    resave     rewrite the bundle in place (an editor or runtime save)
    copy       write the same character to a new file, whole (export, travel)
    export     write the same character in the app's own shape (a projection)
    migrate    rewrite in place and leave it fully current (a migrator)
    new        create a character from nothing
    offspring  create a child of two input bundles

The checks, by name (a waiver in WORKSPACE.toml names one as op:check):

    ran         the operation finished without raising
    output      it wrote a readable bundle whose members match its manifest
    version     spec_version (and the bundle_version alias) is the one the input
                declares; a new identity gets NEW_SHARD_SPEC, a migration this spec's
    drift       no outdated or blocked finding the input did not already have,
                judged by the version the output declares
    identity    shard_id kept, or new where the operation makes a new identity
    lineage     lineage kept, or a valid branch or offspring block
    revision    a new state descends from the input (its revision history holds
                the input's state, spec 11.5), an unchanged copy keeps the
                input's chain, a new identity (new, offspring, branch) starts at n 1
                (a version before 1.11 has no chain and is given none)
    extensions  every soul x_* namespace the consumer does not own survives
    members     every input member survives (resave, copy, migrate, branch)
    untouched   an input the operation must not write is byte-identical after
    newer       a newer bundle whose min_writer allows this spec is saved, with its
                floor, schema ids, members and unknown manifest keys kept
    refused     a newer bundle that names no floor, or an immutable one, is not
                rewritten
"""

from __future__ import annotations

import json
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shardcore import (
    diagnose,
    lineage_errors,
    manifest_digest,
    next_revision,
    read_bundle,
    revision_errors,
    revision_history,
    shard_id_error,
)
from shardcore.core import version_tuple
from shardcore.lineage import BRANCH_RELATIONSHIPS, OFFSPRING, derived_shard_id
from shardcore.model import SEV_BLOCKED, SEV_OUTDATED
from shardcore.registry import NEW_SHARD_SPEC, SPEC_VERSION

_CONFORMANCE = Path(__file__).resolve().parents[2] / "tests" / "conformance"
sys.path.insert(0, str(_CONFORMANCE))
import cases  # noqa: E402

KINDS = frozenset({"resave", "copy", "export", "migrate", "new", "offspring"})
SAME_IDENTITY = frozenset({"resave", "copy", "export", "migrate"})
IN_PLACE = frozenset({"resave", "migrate"})
WHOLE = frozenset({"resave", "copy", "migrate"})

# Conformance cases a writer is handed: valid bundles in every shape, a v1.9
# bundle, drift a writer must not make worse, and an immutable prime.
CONTRACT_CASES = (
    "valid_minimal",
    "valid_companion",
    "valid_npc_structured",
    "valid_x_foreign",
    "valid_with_assets",
    "valid_offspring",
    "valid_branch",
    "valid_revised",
    "lineage_malformed_tolerated",
    "legacy_v1_10",
    "legacy_v1_9",
    "drift_anatomy_list",
    "drift_resonance",
    "drift_asset_no_schema",
    "drift_legacy_asset_layout",
    "immutable_prime",
)
NEWER = "newer_minor"
NEWER_OPEN = "newer_minor_open"
_KEY_FROM_LATER = "key_from_later"
OFFSPRING_PARENTS = ("valid_companion", "valid_x_foreign")

# Members a writer may drop or move: the moves migration 0002/0014 make, and
# the editor scratch 0012 displaces out of a bundle.
_RENAMES = {"memoryshard.json": "mindshard.json"}
_LEGACY_ASSET_DIRS = ("images/", "attestations/", "skills/", "references/")
_DISPLACEABLE_DIRS = ("backups/", ".versions/", ".history/")
_IGNORED_CODES = frozenset({"immutable"})


@dataclass(frozen=True)
class Fixture:
    name: str
    path: Path
    manifest: dict[str, Any]

    @property
    def immutable(self) -> bool:
        return bool(self.manifest.get("immutable"))

    @property
    def newer(self) -> bool:
        """From a newer spec, with no min_writer: not to be rewritten."""
        return self.name == NEWER

    @property
    def newer_open(self) -> bool:
        """From a newer spec, and open to writers of this one."""
        return self.name == NEWER_OPEN

    @property
    def spec(self) -> str:
        return str(self.manifest.get("spec_version"))


@dataclass(frozen=True)
class Job:
    id: str
    operation: str
    kind: str
    inputs: tuple[str, ...]


@dataclass
class Outcome:
    job: Job
    failures: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, check: str, detail: str) -> None:
        self.failures.append((check, detail))


def _next_minor() -> str:
    major, minor = (int(part) for part in SPEC_VERSION.split(".")[:2])
    return f"{major}.{minor + 1}"


def _newer_minor(path: Path) -> Path:
    # Readable (same major) but from a spec this library does not implement.
    version = _next_minor()
    return cases._bundle(
        path,
        pillars={"soulshard.json": cases._soul("Later")},
        manifest=cases._manifest("Later", spec_version=version, bundle_version=version),
        schemas={"soulshard.json": "shardcore/soul@1.9"},
    )


def _newer_minor_open(path: Path) -> Path:
    # As above, but any writer of this spec may save it: ids, a pillar and keys
    # this library has never heard of have to come through.
    version = _next_minor()
    soul = cases._soul("Later and open", field_from_later={"kept": True})
    return cases._bundle(
        path,
        pillars={
            "soulshard.json": soul,
            "mindshard.json": dict(cases.TIERED_MIND),
            "dreamshard.json": {"dreams": ["kept"]},
        },
        manifest=cases._manifest(
            "Later and open",
            spec_version=version,
            bundle_version=version,
            min_writer=SPEC_VERSION,
            **{_KEY_FROM_LATER: {"kept": True}},
        ),
        schemas={
            "soulshard.json": "shardcore/soul@1.20",
            "mindshard.json": "shardcore/mind@2.9",
            "dreamshard.json": "shardcore/dream@1.0",
        },
    )


def build_fixtures(dest: Path) -> dict[str, Fixture]:
    dest.mkdir(parents=True, exist_ok=True)
    builders = {case.name: case.build for case in cases.CASES}
    builders[NEWER] = _newer_minor
    builders[NEWER_OPEN] = _newer_minor_open
    fixtures = {}
    for name in (*CONTRACT_CASES, NEWER, NEWER_OPEN):
        path = builders[name](dest / f"{name}.shard")
        fixtures[name] = Fixture(name, path, _read_manifest(path))
    return fixtures


def plan(operations: dict[str, str], fixtures: dict[str, Fixture]) -> list[Job]:
    jobs: list[Job] = []
    for operation, kind in sorted(operations.items()):
        if kind not in KINDS:
            raise ValueError(f"operation {operation!r} declares unknown kind {kind!r}")
        if kind == "new":
            jobs.append(Job(operation, operation, kind, ()))
        elif kind == "offspring":
            parents = tuple(str(fixtures[name].path) for name in OFFSPRING_PARENTS)
            jobs.append(Job(operation, operation, kind, parents))
        else:
            for fixture in fixtures.values():
                # A projection builds a fresh manifest; refusing newer specs is
                # a rule for writers that carry the input manifest forward.
                if kind == "export" and (fixture.newer or fixture.newer_open):
                    continue
                # A migration moves a bundle up to this spec; this one is past it.
                if kind == "migrate" and fixture.newer_open:
                    continue
                jobs.append(
                    Job(f"{operation}--{fixture.name}", operation, kind, (str(fixture.path),))
                )
    return jobs


def judge(
    job: Job, result: dict[str, Any], fixtures: dict[str, Fixture], owns: frozenset[str]
) -> Outcome:
    outcome = Outcome(job)
    inputs = [_fixture_for(path, fixtures) for path in job.inputs]
    sources = [Path(p) for p in result.get("sources", [])]
    output = Path(result["output"]) if result.get("output") else None
    error = result.get("error")

    if job.kind in SAME_IDENTITY and (
        inputs[0].newer or (inputs[0].immutable and job.kind in IN_PLACE)
    ):
        _judge_guarded(outcome, inputs[0], sources[0], output, error)
        return outcome

    if error is not None:
        outcome.fail("ran", error)
        return outcome
    if output is None or not output.is_file():
        outcome.fail("output", "the operation returned no bundle")
        return outcome

    out = _Read(output)
    if out.problem:
        outcome.fail("output", out.problem)
        return outcome
    _check_version(outcome, out, _versions_for(job.kind, inputs))

    if job.kind in SAME_IDENTITY:
        fixture = inputs[0]
        if fixture.newer_open:
            _check_newer(outcome, fixture, out)
        source_in_place = job.kind in IN_PLACE
        if not source_in_place:
            _check_untouched(outcome, fixture, sources[0])
        allowed = _bad_codes(fixture.path, out.target) if job.kind != "migrate" else set()
        _check_drift(outcome, out, allowed)
        _check_same_identity(outcome, fixture, out)
        if manifest_digest(out.manifest) != manifest_digest(fixture.manifest):
            # An unchanged manifest is the same state (a file copy); anything
            # else is a new state and must descend from the input.
            _check_descends(outcome, fixture, out)
        _check_extensions(outcome, fixture, out, owns)
        if job.kind in WHOLE:
            _check_members(outcome, fixture, out)
    elif job.kind == "offspring":
        for fixture, source in zip(inputs, sources, strict=True):
            _check_untouched(outcome, fixture, source)
        _check_drift(outcome, out, set())
        _check_offspring(outcome, inputs, out)
        _check_fresh(outcome, out, inputs)
    else:  # new
        _check_drift(outcome, out, set())
        problem = shard_id_error(out.manifest.get("shard_id"))
        if problem:
            outcome.fail("identity", problem)
        if "lineage" in out.manifest and lineage_errors(out.manifest["lineage"]):
            outcome.fail("lineage", "; ".join(lineage_errors(out.manifest["lineage"])))
        _check_fresh(outcome, out, [])
    return outcome


def _judge_guarded(
    outcome: Outcome, fixture: Fixture, source: Path, output: Path | None, error: str | None
) -> None:
    """A newer-spec input is refused; an immutable one is refused or branched."""
    if not _same_bytes(fixture.path, source):
        what = "a newer-spec" if fixture.newer else "an immutable"
        outcome.fail("refused", f"rewrote {what} bundle in place")
        return
    wrote_elsewhere = (
        output is not None and output.resolve() != source.resolve() and output.is_file()
    )
    if fixture.newer:
        if wrote_elsewhere:
            outcome.fail(
                "refused", f"wrote a copy of a spec {fixture.manifest.get('spec_version')} bundle"
            )
        else:
            outcome.notes.append(f"refused ({error})" if error else "left untouched")
        return
    if not wrote_elsewhere:
        outcome.notes.append(f"refused ({error})" if error else "left untouched")
        return
    # A branch: a new identity whose lineage pins the immutable parent.
    out = _Read(output)
    if out.problem:
        outcome.fail("output", out.problem)
        return
    _check_version(outcome, out, {fixture.spec})
    _check_drift(outcome, out, _bad_codes(fixture.path, out.target))
    if out.manifest.get("immutable"):
        outcome.fail("refused", "the branch is still marked immutable")
    parent_id = fixture.manifest.get("shard_id")
    child_id = out.manifest.get("shard_id")
    if shard_id_error(child_id) or child_id == parent_id:
        outcome.fail("identity", f"branch shard_id {child_id!r} is invalid or reuses the parent's")
    lineage = out.manifest.get("lineage")
    errors = lineage_errors(lineage)
    if errors:
        outcome.fail("lineage", "; ".join(errors))
    elif lineage.get("relationship") not in BRANCH_RELATIONSHIPS:
        outcome.fail("lineage", f"branch relationship is {lineage.get('relationship')!r}")
    else:
        pin = lineage["parent"]
        if pin.get("manifest_sha256") != manifest_digest(fixture.manifest):
            outcome.fail("lineage", "branch pins a different parent state")
        if parent_id is not None and pin.get("shard_id") != parent_id:
            outcome.fail("lineage", "branch names a different parent shard_id")
    _check_fresh(outcome, out, [fixture])
    _check_extensions(outcome, fixture, out, frozenset())
    _check_members(outcome, fixture, out)
    outcome.notes.append("branched")


class _Read:
    """One output bundle: shardcore's view plus the raw manifest, soul, members."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.problem: str | None = None
        self.state = read_bundle(path)
        self.target = _judged_at(self.state.spec_version)
        self.diagnosis = diagnose(self.state, self.target)
        self.manifest: dict[str, Any] = {}
        self.soul: dict[str, Any] = {}
        self.members: dict[str, bytes] = {}
        if not self.state.readable:
            self.problem = f"unreadable: {self.state.error}"
            return
        if not self.state.has_integrity_data or not self.state.integrity_ok:
            self.problem = "members do not match the manifest digests"
            return
        self.members = _members(path)
        self.manifest = json.loads(self.members.pop("manifest.json"))
        soul = json.loads(self.members.get("soulshard.json", b"{}"))
        self.soul = soul if isinstance(soul, dict) else {}


def _versions_for(kind: str, inputs: list[Fixture]) -> set[str]:
    if kind in ("new", "offspring"):
        return {NEW_SHARD_SPEC}
    if kind == "migrate":
        return {SPEC_VERSION}
    # An export builds the character afresh in the app's own shape, so it may
    # take a new shard's version instead of the input's.
    return {inputs[0].spec, NEW_SHARD_SPEC} if kind == "export" else {inputs[0].spec}


def _check_version(outcome: Outcome, out: _Read, wanted: set[str]) -> None:
    spec = out.manifest.get("spec_version")
    alias = out.manifest.get("bundle_version", spec)
    if spec not in wanted or alias != spec:
        outcome.fail(
            "version",
            f"spec_version {spec!r}, bundle_version {alias!r}; expected {' or '.join(sorted(wanted))}",
        )


def _check_newer(outcome: Outcome, fixture: Fixture, out: _Read) -> None:
    for key in ("min_writer", _KEY_FROM_LATER):
        if out.manifest.get(key) != fixture.manifest[key]:
            outcome.fail("newer", f"manifest.{key} {out.manifest.get(key)!r}, not kept")
    for name, entry in fixture.manifest["files"].items():
        kept = out.manifest["files"].get(name, {}).get("schema")
        if kept != entry["schema"]:
            outcome.fail("newer", f"{name} schema {kept!r}, declared {entry['schema']!r}")
    if out.soul.get("field_from_later") != {"kept": True}:
        outcome.fail("newer", "soul.field_from_later lost or changed")


def _at_least(out: _Read, spec: str) -> bool:
    return (version_tuple(out.manifest.get("spec_version")) or ()) >= (version_tuple(spec) or ())


def _check_drift(outcome: Outcome, out: _Read, allowed: set[str]) -> None:
    found = {
        f.code
        for f in out.diagnosis.findings
        if f.severity in (SEV_BLOCKED, SEV_OUTDATED) and f.code not in _IGNORED_CODES
    }
    new = sorted(found - allowed)
    if new:
        details = {f.code: f.detail for f in out.diagnosis.findings}
        outcome.fail("drift", "; ".join(f"{code} ({details[code]})" for code in new))


def _check_same_identity(outcome: Outcome, fixture: Fixture, out: _Read) -> None:
    expected = fixture.manifest.get("shard_id") or derived_shard_id(
        manifest_digest(fixture.manifest)
    )
    actual = out.manifest.get("shard_id")
    if actual != expected:
        outcome.fail("identity", f"shard_id {actual!r}, expected {expected!r}")
    if out.manifest.get("lineage") != fixture.manifest.get("lineage"):
        outcome.fail(
            "lineage",
            f"lineage {out.manifest.get('lineage')!r} != input {fixture.manifest.get('lineage')!r}",
        )


def _check_descends(outcome: Outcome, fixture: Fixture, out: _Read) -> None:
    # One operation may write more than once (an editor saving twice), so the
    # rule is descent, not exactly one step: the input's state is in the
    # output's history and n counts at least one write past it.
    revision = out.manifest.get("revision")
    if revision is None and not _at_least(out, "1.11") and "revision" not in fixture.manifest:
        return
    problems = revision_errors(revision) if revision is not None else ["no revision block"]
    if problems:
        outcome.fail("revision", "; ".join(problems))
        return
    if manifest_digest(fixture.manifest) not in revision_history(out.manifest):
        outcome.fail("revision", "the output's revision history does not reach the input state")
    elif revision["n"] < next_revision(fixture.manifest)["n"]:
        outcome.fail("revision", f"revision n {revision['n']} is not past the input's")


def _check_fresh(outcome: Outcome, out: _Read, parents: list[Fixture]) -> None:
    # A new identity starts its own chain at n 1 (later saves of it may follow)
    # and never continues a parent's.
    revision = out.manifest.get("revision")
    if revision is None and not _at_least(out, "1.11"):
        return
    problems = revision_errors(revision) if revision is not None else ["no revision block"]
    if problems:
        outcome.fail("revision", "; ".join(problems))
        return
    history = set(revision_history(out.manifest))
    if any(manifest_digest(parent.manifest) in history for parent in parents):
        outcome.fail("revision", "a new identity continues its parent's revision chain")


def _check_offspring(outcome: Outcome, parents: list[Fixture], out: _Read) -> None:
    child_id = out.manifest.get("shard_id")
    parent_ids = [p.manifest.get("shard_id") for p in parents]
    if shard_id_error(child_id) or child_id in parent_ids:
        outcome.fail("identity", f"child shard_id {child_id!r} is invalid or reuses a parent's")
    lineage = out.manifest.get("lineage")
    errors = lineage_errors(lineage)
    if errors:
        outcome.fail("lineage", "; ".join(errors))
        return
    if lineage.get("relationship") != OFFSPRING:
        outcome.fail("lineage", f"relationship is {lineage.get('relationship')!r}")
        return
    pins = [entry.get("manifest_sha256") for entry in lineage["parents"]]
    if pins != [manifest_digest(p.manifest) for p in parents]:
        outcome.fail("lineage", "parents are not pinned at the states bred from")
    if [entry.get("shard_id") for entry in lineage["parents"]] != parent_ids:
        outcome.fail("lineage", "parents' shard_ids missing or out of order")


def _check_extensions(outcome: Outcome, fixture: Fixture, out: _Read, owns: frozenset[str]) -> None:
    soul = json.loads(_members(fixture.path)["soulshard.json"])
    for key, value in soul.items():
        if key.startswith("x_") and key not in owns and out.soul.get(key) != value:
            outcome.fail("extensions", f"soul.{key} lost or changed")


def _check_members(outcome: Outcome, fixture: Fixture, out: _Read) -> None:
    for name, data in _members(fixture.path).items():
        if (
            name == "manifest.json"
            or name.startswith(_DISPLACEABLE_DIRS)
            or name.endswith(".sha256")
        ):
            continue
        target = _RENAMES.get(name, name)
        if name.startswith(_LEGACY_ASSET_DIRS) and target not in out.members:
            target = f"assets/{name}"
        if target not in out.members:
            outcome.fail("members", f"lost {name}")
        elif not name.endswith(".json") and out.members[target] != data:
            outcome.fail("members", f"changed {name}")


def _check_untouched(outcome: Outcome, fixture: Fixture, source: Path) -> None:
    if not _same_bytes(fixture.path, source):
        outcome.fail("untouched", f"modified its input {source.name}")


def _judged_at(spec: str | None) -> str:
    # A shard that keeps an older version is held to that version's rules.
    declared = version_tuple(spec)
    if spec is None or declared is None or declared > (version_tuple(SPEC_VERSION) or ()):
        return SPEC_VERSION
    return spec


def _bad_codes(path: Path, target: str) -> set[str]:
    findings = diagnose(read_bundle(path), target).findings
    return {f.code for f in findings if f.severity in (SEV_BLOCKED, SEV_OUTDATED)}


def _fixture_for(path: str, fixtures: dict[str, Fixture]) -> Fixture:
    for fixture in fixtures.values():
        if str(fixture.path) == path:
            return fixture
    raise KeyError(path)


def _same_bytes(a: Path, b: Path) -> bool:
    return b.is_file() and a.read_bytes() == b.read_bytes()


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {i.filename: archive.read(i) for i in archive.infolist() if not i.is_dir()}


def _read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(_members(path)["manifest.json"])
