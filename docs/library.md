# Using the reference library

Status: **reference implementation** (spec PART III).

`shardcore` is the single reference implementation of bundle I/O: open, verify,
diagnose, migrate, and repack. A writer that goes through it produces a
spec-conformant v1.9 bundle by construction, so the integrity and save rules of
spec section 9 hold without every app re-deriving them. The bundle I/O surface
is standard-library only; `numpy` is needed only for the neuron substrate.

## Read and verify

```python
from shardcore import read_bundle, verify_bundle

state = read_bundle("character.shard")   # BundleState, never raises on bad input
print(state.readable, state.spec_version, state.integrity_ok)

errors = verify_bundle("character.shard")  # [] means valid
```

`read_bundle` reads every member into memory and hashes it; it never extracts
to disk, so there is no zip-slip surface. `verify_bundle` keeps its v1.0
signature (a list of violation strings, empty means valid).

## Diagnose drift

```python
from shardcore import read_bundle, diagnose

diag = diagnose(read_bundle("character.shard"), "1.9")
print(diag.status)   # "current" | "outdated" | "blocked"
for f in diag.findings:
    print(f.severity, f.code, f.migration, f.detail)
```

## Migrate and repack

```python
from shardcore import migrate_bundle

notes = migrate_bundle("old.shard", target="1.9", out="migrated.shard")
```

The lower-level pieces are public too: `MutableBundle` (an in-memory mutable
view), `repack_atomic` (the atomic writer), and `schema_for_member` (the
per-member schema-id registry).

## The substrate

```python
from shardcore.neuron import build_brain_from_shard, LIFNetwork
```

`shardcore.neuron` carries the LIF tick engine and Neuronshard I/O forward from
v1.0 unchanged, including the byte-identical state round-trip.

## CLI

```bash
python -m shardcore verify   <bundle>
python -m shardcore diagnose <bundle>
python -m shardcore migrate  <bundle> [--out OUT] [--target 1.9]
python -m shardcore neuron   <bundle> [--ticks N] [--save STATE.json]
```

All commands exit 0 on success, non-zero on any violation.

## What the library is not

It is not a batch migration tool. `migrate_bundle` is atomic but keeps no
backup and no run-log; the full backup / verify / restore-on-failure envelope
belongs to a tool that wraps it. See [migration.md](migration.md).
