# Migration to v1.12

Status: **normative** (spec section 12).

Migrating is your choice: a save keeps the version a bundle declares (spec
section 3).

v1.11, v1.10, v1.9 and v1.0 bundles load and migrate forward to v1.12 without loss. Migration is
mechanical: a chain of small, idempotent, non-lossy transforms. When a shape
cannot be transformed without guessing, the migration refuses and the bundle
is skipped whole rather than corrupted. The spec is authoritative; this note
orients.

## From v1.11

`0005` restamps `spec_version` (and the deprecated alias) to `1.12`, and `0009`
restamps the shell (`shell@1.10` becomes `shell@1.12`). A `neuron@1.0`
neuronshard is left as it is: no faithful conversion exists.

## From v1.10

The v1.11 steps above (`shell@1.9` becomes `shell@1.12`).
`0017` folds a list-shape shell anatomy into the parts map (spec 6.3); and
`0016`, which runs on every migration write, stamps `manifest.revision` with
the pre-migration manifest as its prior state (spec 11.5).

## From v1.9

The v1.10 steps above, and `0015`, which mints `shard_id` when the manifest has none. The id is a
UUIDv5 of the bundle's pre-migration manifest digest under the namespace fixed
in spec section 12, so migrating the same input twice, or with another
conformant migrator, yields the same id. A present but broken `shard_id` blocks
the bundle for manual repair; it is never replaced, because lineage elsewhere
may already name it. Malformed `lineage` is reported as an info finding and
left alone: fixing it needs the parent bundle.

## The chain

Seventeen migrations, `0001` to `0017`, run in a fixed sequence (not id order).
The high points:

- Consolidate duplicate or mislabeled pillar members (`0012`).
- Rename `memoryshard.json` to `mindshard.json` (`0002`).
- Split shell fields out of the soul into `shellshard.json` (`0001`).
- Convert flat memory to tiered short-term / long-term / core / archive (`0003`).
- Drop `manifest.memory_format` (`0004`); stamp `spec_version` and the
  deprecated `bundle_version` alias (`0005`); mint `shard_id` (`0015`).
- Normalize timestamps to ISO-8601 UTC (`0007`).
- Re-nest recognized runtime fields under `x_nexus` (`0010`).
- Relocate legacy top-level asset folders under `assets/` (`0014`).
- Normalize `stat_block` to the canonical ten, relocating `Resonance` to a
  soul-level field and defaulting a stat-less soul to all-5 (logged) (`0013`).
- Regenerate `manifest.card`, stamp per-member schema ids, and recompute every
  SHA-256 (`0008`, `0009`, `0011`, always last).

A bundle that fails its own integrity check MUST NOT be migrated silently.

## Doing it with the library

```python
from shardcore import migrate_bundle

# migrate a copy, leaving the original untouched
notes = migrate_bundle("old.shard", out="migrated.shard")
```

Or from the CLI:

```bash
python -m shardcore diagnose old.shard        # what would change, no writes
python -m shardcore migrate old.shard --out migrated.shard
```

`migrate_bundle` is atomic (temp file plus `os.replace`). An upgrade in place
keeps the earlier file as `<name>.v<version>.bak`, or in the backup vault where
there is one. There is no run-log.

## Doing it in bulk

For migrating a whole library with backups, a hash-chained audit log, and
restore-on-failure, use a batch tool that wraps `migrate_bundle`. The library
gives you the transform; the safety envelope is the tool's job.

See [library.md](library.md) for the full API.
