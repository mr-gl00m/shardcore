# The ecosystem check

A format change is cheap to make and expensive to land. A spec bump has to
reach every app that writes `.shard` bundles. Before 1.10, until it did, each of
those apps quietly rewrote newer bundles back to the old version. The v1.10 bump
found exactly that:
- every app stamped bundles back to 1.9;
- two of them copied a parent's `shard_id` onto its branch;
- three dropped `lineage` on export;
- one dropped other tools' members on a routine repack.

Every app's own tests passed throughout, because each one asserted its own
hard-coded `"1.9"`.

`tools/ecosystem/ecosystem.py` checks the whole set of consumers at once.
**A spec bump or writer change is done when `ecosystem.py check` passes.**

```
uv run python tools/ecosystem/ecosystem.py sync [--check]
uv run python tools/ecosystem/ecosystem.py check [--only NAME ...] [--skip-tests] [--keep DIR]
```

Run both from the shardcore root. `--keep` leaves the fixtures, every adapter
output, and `results.json` in `DIR` for inspection; a failing run keeps them
in its temp folder regardless.

## What it checks

1. **Vendored copies.** An app that cannot import this library carries a
   copy of `shardcore/core.py`, the stdlib-only core every library module
   builds on, saved as `shardcore_v19.py` (the name dates from v1.9; it writes
   the current spec). A Godot app carries `vendor/shardcore.gd`, the GDScript
   port of that core plus a strict in-memory reader. A tool that runs the conformance suite carries a copy of
   `tests/conformance/cases.py`. Every copy must match shardcore's, ignoring
   line endings. `sync` rewrites the copies; edit only shardcore's.
2. **The writer contract** (`tools/ecosystem/contract.py`).
   - Each consumer ships a small adapter that runs its real write paths: save,
     export, branch, discharge, breed, migrate.
   - The check hands every adapter the contract fixtures: the conformance
     cases a writer meets in practice, plus one bundle stamped with the next
     minor version.
   - It runs each adapter in the consumer's own environment, then judges every
     output with this library rather than with the helper that wrote it.
3. **Isolation.** A contract run must not change any file under the
   consumer's root (beyond its `ignore` globs) or in the vault.
4. **The consumer's own tests.**
5. **Compatibility**, when there is a `tests/compat/` suite. Frozen copies of
   the helpers a workspace's apps carried, against this library. This repository
   does not ship one. `--only` leaves this step out.

### Operation kinds and checks

An adapter declares a kind for each operation, and the kind decides which
checks apply:

| Kind | Meaning | Identity | Members kept |
|---|---|---|---|
| `resave` | rewrite in place (editor or runtime save) | kept | yes |
| `copy` | the same character to a new file, whole (export, travel) | kept | yes |
| `export` | the same character in the app's own shape (a projection) | kept | no |
| `migrate` | rewrite in place, and the result must be fully current | kept | yes |
| `new` | a character from nothing | new, valid | n/a |
| `offspring` | a child of two input bundles | new, parents pinned | n/a |

The checks are named so a waiver can cite them:

| Check | What fails it |
|---|---|
| `ran` | the operation raised |
| `output` | no bundle, unreadable, or members that disagree with the manifest |
| `version` | `spec_version` or the `bundle_version` alias is not the input's (a new identity: `NEW_SHARD_SPEC`; a migration: this spec's) |
| `drift` | an outdated or blocked finding the input did not already have, judged by the version the output declares |
| `identity` | `shard_id` changed, or a new identity reused an old id |
| `lineage` | lineage dropped or changed; a branch or offspring block that is invalid or pins the wrong state |
| `revision` | a new state whose revision history does not reach the input, or whose `n` is not past it; a new identity whose chain continues a parent's (spec 11.5). An unchanged file copy keeps the input's chain. |
| `extensions` | a soul `x_*` namespace the consumer does not own was lost or changed |
| `members` | an input member was lost (the moves and removals migrations make are allowed) |
| `untouched` | an input the operation must not write changed |
| `newer` | a newer bundle open to this spec lost its `min_writer`, schema ids or unknown keys |
| `refused` | a newer bundle that names no floor was rewritten, or an immutable one was rewritten in place |

An immutable input may be refused or branched. A branch must:
- take a new `shard_id`;
- carry a branch `lineage` block pinning the parent's `manifest_sha256` and
  `shard_id`;
- drop the `immutable` flag.

A save keeps the version a bundle declares, so no app raises one for the
others. A bundle from a newer minor is saved when its `min_writer` allows this
spec, and must come through whole. One that names no floor must not be
rewritten at all, in place or as a copy: the helper's `check_spec_writable`
(called by `build_manifest`) raises `NewerSpecError`. Either can be read.

## Consumers

Consumers are listed in the workspace's `WORKSPACE.toml` under
`[[consumers]]`. The comment block there documents the keys: `path`,
`vendored`, `adapter`, `tests`, `owns`, `ignore` and `waive`. A new app that
reads or writes bundles gets an entry there and an adapter. Nothing else
needs to know about it.

A `waive` entry (`"operation:check"` or `"operation:check:fixture"`)
records a known gap with its reason. Waived failures are listed on every
run, so the debt stays visible.

## Writing an adapter

The adapter lives in the consumer, conventionally at
`tests/shardcore_contract.py` (no `test_` prefix, so pytest skips it).
`tools/ecosystem/runner.py` imports it inside the consumer's venv. The
adapter is plain Python:

```python
OPERATIONS = {
    "save": {"kind": "resave", "run": save},
    "export": {"kind": "copy", "run": export},
}

def save(source: Path, *, work: Path) -> Path: ...    # one input
def pull(*, work: Path) -> Path: ...                  # kind "new": no input
def breed(a: Path, b: Path, *, work: Path) -> Path: ...  # kind "offspring"
def setup(home: Path) -> None: ...                    # optional, runs once
```

Each `run` receives copies of its inputs and returns the bundle it wrote.
Raising counts as a refusal where refusing is allowed, and as a failure
everywhere else. `SHARDCORE_CONTRACT_HOME` is set before the adapter is
imported. Point every app data root at it (save files, backups, rosters,
logs, sandboxes), so a run never touches real data; the isolation check is
the backstop. Drive the app's real code path, the one a user's action takes,
not a helper beneath it.

## Changing the format or the helper

1. Change the spec, `shardcore/core.py` (and any library module on top of
   it) and `vendor/shardcore.gd` together. There is one Python
   implementation: the library imports the core, so a Python change is made
   once. `tests/test_vendor_helper.py` loads `core.py` by path, the way an app
   vendors it, and checks it stands alone and writes bundles that diagnose
   `current`.
   `tests/test_vendor_gdscript.py` holds the GDScript helper to the same, under
   a headless Godot (`$GODOT`, skipped when there is none), and checks its
   reader accepts and rejects the conformance cases as `read_bundle_document`
   does.
2. `ecosystem.py sync`.
3. `ecosystem.py check`. Fix the consumers until it passes, or waive a gap
   with its reason.
4. Rebuild any packaged app.
