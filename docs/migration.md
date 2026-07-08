# Migration to v1.9

Status: **normative** (spec section 12).

v1.0 bundles load and migrate forward to v1.9 without loss. Migration is
mechanical: a chain of small, idempotent, non-lossy transforms. When a shape
cannot be transformed without guessing, the migration refuses and the bundle
is skipped whole rather than corrupted. The spec is authoritative; this note
orients.

## The chain

Fourteen migrations, `0001` to `0014`, run in a fixed sequence (not id order).
The high points:

- Consolidate duplicate or mislabeled pillar members (`0012`).
- Rename `memoryshard.json` to `mindshard.json` (`0002`).
- Split shell fields out of the soul into `shellshard.json` (`0001`).
- Convert flat memory to tiered short-term / long-term / core / archive (`0003`).
- Drop `manifest.memory_format` (`0004`); stamp `spec_version` and the
  deprecated `bundle_version` alias (`0005`).
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
notes = migrate_bundle("old.shard", target="1.9", out="migrated.shard")
```

Or from the CLI:

```bash
python -m shardcore diagnose old.shard        # what would change, no writes
python -m shardcore migrate old.shard --out migrated.shard
```

`migrate_bundle` is atomic (temp file plus `os.replace`) but keeps no backup
and no run-log. If you migrate in place, keep your own copy first.

## Doing it in bulk

For migrating a whole library with backups, a hash-chained audit log, and
restore-on-failure, use a batch tool that wraps `migrate_bundle`. The library
gives you the transform; the safety envelope is the tool's job.

See [library.md](library.md) for the full API.
