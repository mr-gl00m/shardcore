# Changelog

All notable changes to SHARDCORE are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project
versions the **specification** and the **reference library** on the same
cadence; entries note both version numbers. As of v1.9 the two are in
lockstep at 1.9.0.

## [Unreleased]

## [1.12.0 / Spec v1.12] - 2026-11-24

The first release since 1.9.0. Spec v1.10 and v1.11 were ratified and never
released as libraries, so this carries all three.

### Highlights

- **Saving never changes a shard's version.** A save keeps the version and schema
  ids a shard declares, an upgrade is asked for and keeps the earlier file, and an
  app older than a shard can save it when the shard's `min_writer` allows.
- **A character keeps one identity.** `shard_id` survives every save, bred and
  branched characters pin their parents, and two copies of one character compare
  as the same, newer, older or diverged. Diverged copies merge.
- **A neural substrate that propagates and learns.** `neuron@1.1` is the default
  for new neuronshards. `neuron@1.0` is frozen and still runs.

### Added

- `shardcore/core.py`: a stdlib-only reader and writer to vendor as one file, with
  a GDScript port for Godot (`vendor/shardcore.gd`). It keeps versions
  (`kept_spec`), honors `manifest.min_writer`, raises `UpgradeNeededError` when an
  edit needs more than a shard declares, upgrades when told
  (`pack_bundle(upgrade_to=...)`), and restores an earlier state at its own version
  (`content_of`).
- Identity and offspring lineage (spec 11.4): `manifest.shard_id`, and a lineage
  shape for characters bred, cloned or fused from hash-pinned parents
  (`new_shard_id`, `derived_shard_id`, `offspring_lineage`, `lineage_errors`).
- Revision chain and three-way merge (spec 11.5): `manifest.revision`,
  `compare_revisions`, `common_ancestor`, `merge_bundles`, `write_merge`, and
  `python -m shardcore compare` and `merge`.
- `neuron@1.1` (spec 8.10) and its reference engine, `shardcore.brain`: synapse
  counts on edges, `SENSE` nodes, pooled inhibition, and an `experience` block.
  Body stimulus (8.9) and `parts[id].neural` (6.3) tie a body to it.
- The projection contract as code: `shardcore.projection`, with golden texts and a
  GDScript port.
- The shell's anatomy as a parts map (spec 6.3), `anatomy_parts_map`.
- `read_bundle_document`, a strict in-memory reader for runtimes, and
  `build_bundle`, which writes, verifies and atomically places a new bundle.
- `diagnose` status `behind`: the bundle keeps its own version's rules and a newer
  version exists. Finding `saved_below_floor`: an app older than `min_writer` saved
  it.
- A backup vault that keeps every bundle state a writer replaces
  (`python -m shardcore backup`), off unless a workspace configures it.
- `tools/ecosystem/`, which keeps vendored copies identical and runs every app's
  real write paths against the fixtures (`docs/ecosystem.md`).
- Eleven more conformance fixtures (29 in all) and 7 projection golden texts.

### Changed

- Migration reaches spec 1.12, through `0015` (identity), `0016` (revision) and
  `0017` (anatomy). To an older target it stamps that version's schema ids. In
  place, it keeps the earlier file.
- **Migrating a bundle turns list-shape anatomy into the parts map.** An app that
  reads `external_parts` or `internal_parts` finds nothing afterwards. See the
  migration notes.
- **`diagnose` calls a conforming older bundle `behind`, where it said `outdated`,**
  and the command exits 0 for it.
- Versions compare per component as integers: `1.10` is newer than `1.9`.
- `diagnose` calls a bundle `current` only when the strict reader accepts it
  (`strict_read_failed` otherwise).
- The spec is one document: the v1.0 sections and the v1.1 addendum are folded in.

### Migration from 1.9.0

Reading needs no change. A 1.9.0 reader opens 1.12 bundles, and this library opens
every 1.x bundle. Before an app writes with this release:

- **Anatomy.** After a migration, read `anatomy_profile["parts"][id]`, not the lists:

  ```python
  # before
  for part in anatomy["external_parts"]:
      use(part["id"], part)

  # after
  for pid, part in anatomy["parts"].items():
      use(pid, part)
  ```

- **Versions.** Compare `spec_version` as integers. `"1.10" < "1.9"` is true for
  strings.
- **`diagnose`.** Code that migrates on `outdated` now leaves a conforming 1.9
  bundle alone. Test for `behind` too if it should upgrade.
- **Older writers.** An app written to 1.9 may stamp a newer bundle back to 1.9
  without warning. `saved_below_floor` shows it when the bundle names a floor.

### Fixed

- `read_bundle` accepts a `str` path, as documented.
- `repack_atomic` refuses a read-only target at once instead of retrying.

## [1.9.0 / Spec v1.9] - 2026-07-08

The capstone of the v1 line and the next release after the public v1.0
baseline. v1.9 reshapes the format around a single required pillar plus
optional, self-describing pillars, fixes how the format versions itself,
and revives `shardcore` as the single reference implementation with a real
write and migrate path. v1.0 bundles load and migrate forward without loss.

### Added

- **Optional defined pillars.** `canonshard.json` (`shardcore/canon@1.0`,
  authored immutable events), `statshard.json` (`shardcore/stat@1.0`,
  game-system stat blocks), and the `body/` subsystem (`shardcore/body@1.0`,
  per-item sub-shards with `equipped.json` and `status_effects.json`) are
  now defined optional pillars. `worldshard.json` (`shardcore/world@1.0`)
  gains a dedicated section.
- **Unified `assets/` folder** (`shardcore/assets@1.0`). Images,
  OpenTimestamps receipts, skills, and references live under one folder
  and carry one schema id. The separate v1.0 `skills/` and `references/`
  folders fold in here.
- **`mindshard.structured` block** (spec section 7.3): an optional,
  consumer-namespaced home for deterministic non-narrative state (game NPC
  profiles, agent vectors), each key a schema id with a required
  `updated_utc`.
- **Conformance profiles and model tiers** (spec section 4). Profiles
  `companion`, `npc`, and `agent` declare a required-pillar set plus a tier
  floor. Model tiers `S`, `M`, and `L` describe how a bundle projects into
  small, medium, and large context budgets. Recorded in optional
  `manifest.conformance`.
- **The projection contract** (spec section 10): a deterministic mapping
  from bundle to system prompt, with a fixed section order and a never-trim
  set (canon, core memory, boundaries).
- **Provenance manifest fields** (optional): `lineage`, `attestation`, and
  `immutable`, folding in the v1.1 canon and branching work.
- **`shardcore` reference library, revived and expanded.** Beyond v1.0's
  read and verify, the library now writes: `MutableBundle` + `repack_atomic`
  (atomic temp-file-plus-replace), the v1.9 migration chain (`migrations`,
  0001 to 0014), drift detection (`diagnose`), the per-member schema-id
  registry (`registry`), and `migrate_bundle`. New CLI subcommands
  `diagnose` and `migrate` alongside `verify` and `neuron`.
- **Expanded conformance suite** (spec section 13): 18 self-contained golden
  fixtures in `tests/conformance/cases.py` plus `emit.py` to write them for
  a foreign runtime.

### Changed

- **Single negotiated version.** `spec_version` (`"1.9"`) is now the field a
  runtime negotiates on. New pillars join by adding a per-member `schema` id
  (`shardcore/<pillar>@<major.minor>`) to `manifest.files`, not by
  renumbering a bundle version.
- **Soul core versus `x_<vendor>`.** The soul top level is the portable,
  cross-model contract; runtime-specific fields move under an `x_<vendor>`
  namespace that other runtimes preserve and ignore. `x_nexus` is reserved
  for the Nexus Labs runtimes.
- **`stat_block` closed at exactly ten integer keys** (STR, END, VIG, DEX,
  TMP, ACU, INS, ATT, CNV, PRS). Game-system stats move to `statshard.json`.
  The legacy `Resonance` string relocates from `stat_block` to a soul-level
  `resonance` field.
- **The mind pillar self-describes** via its own `format_version` (`"2.1"`
  current, `"2.0"` accepted); the manifest no longer mirrors it.
- **Manifest timestamp is `last_modified_utc`**, ISO-8601 UTC with a
  trailing `Z`.
- **The soul is the one required pillar.** Every other pillar is optional;
  conformance profiles declare which optional pillars a given use case needs.
- **Library versioned in lockstep with the spec** at 1.9.0. `verify_bundle`
  keeps its v1.0 signature and routes through the shared reader.

### Deprecated

- **`bundle_version`** is a deprecated alias. A v1.9 writer stamps it equal
  to `spec_version` so v1.0 readers can still negotiate; a v1.9 reader
  ignores it when `spec_version` is present. It is removed at the 2.0 major.

### Removed

- **`manifest.memory_format`.** A v1.9 writer MUST NOT emit it; the mind
  pillar self-describes. A reader that finds it on a v1.0 bundle ignores it.

### Compatibility

- v1.0 bundles load and migrate forward on write. `memoryshard.json` is
  accepted forever as a fallback for `mindshard.json`. Flat memory arrays
  convert to tiered `short_term`/`long_term`/`core`/`archive`. Stat-less
  souls default to all-5 (logged, not authored). Unknown fields and unowned
  `x_*` namespaces are preserved on load and save. A reader rejects a bundle
  only when its `spec_version` MAJOR exceeds what the reader implements, so
  v1.0 runtimes still accept v1.9 bundles.
- First-party authoring apps in the wider ecosystem are being routed through
  this library. Until an app is, re-saving a bundle through it may
  down-convert the manifest to the legacy layout; `shardcore migrate` brings
  it back to v1.9.

## [0.1.0 / Spec v1.0] - 2026-05-15

First public release. The bundle format is frozen at v1.0; the reference
library ships at 0.1.0 as the first public implementation of it.

### Added

- **Specification** (`SHARDCORE_Spec_v1.0.md`, Apache-2.0) with normative
  sections for the manifest, soulshard, shellshard, mindshard, and
  neuronshard pillars, plus integrity and conformance requirements.
  Experimental sections reserve driveshard, the skills folder, the
  references folder, dream consolidation, the introspection surface,
  and neuro-symbolic validation rules for v1.1+.
- **Reference library** `shardcore/` (MIT): pure-numpy, no LLM
  dependency.
  - `shardcore.verify`: manifest + SHA-256 + required-pillar validator.
  - `shardcore.neuron`: LIF tick engine, topology builder derived from
    soulshard stats and traits, round-trip Neuronshard I/O.
  - `python -m shardcore verify|neuron` CLI, exits 0 on success and
    non-zero on any spec violation.
- **Neuronshard pillar.** Spiking-network substrate with byte-identical
  round-trip guarantee (spec section 6.8). A shard reopened a week later
  resumes from the exact membrane voltages, synaptic accumulators,
  refractory timers, and learned weights it had when it was saved.
- **Vitality system** (spec section 3.4): `core_decay`, `perturbation`, and
  `curiosity_engine` mechanics so that engagement produces something
  measurable at the substrate level. The feature is normative; runtimes
  MAY opt out per-bundle with `enabled: false`.
- **Conformance suite** (`tests/conformance/`): manifest integrity,
  three-pillar round-trip, and neuronshard persistence. Unit tests
  (`tests/unit/`) cover LIF dynamics and serializer round-trip.
- **Example bundles.** `examples/minimal.shard` (soul-only, smallest
  valid bundle) and `examples/standard.shard` (four-pillar bundle with
  a pre-warmed Neuronshard). Both pass the full conformance suite.
- **CI matrix.** Ubuntu / macos / windows x Python 3.10 to 3.13, plus
  `ruff` lint/format checks and gitleaks + trufflehog secret scans on
  every push.
- **Policies.** `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1),
  `CONTRIBUTING.md` (spec-vs-library RFC flow), `SECURITY.md` (threat
  model and coordinated-disclosure process).
- **Dual licensing.** Apache-2.0 on the specification (patent grant
  matters for a format meant to be reimplemented widely), MIT on the
  reference library (maximum permissive for downstream vendoring).

### Notes

- Pre-public bundle versions (internal `1.1`, `1.2`, and the `1.3`
  addendum) are not v1.0-conformant by versioning alone. Migration is
  mechanical; see spec section 17.2.
- LLM inference is a deliberate non-goal for this repository.
  Downstream applications consume the format; `shardcore` only
  describes and substrates it.
- The spec is frozen. The library may evolve across 0.x releases
  (error messages, loader ergonomics, performance) without changing
  observable neuronshard dynamics, which are part of the spec contract.

[1.12.0 / Spec v1.12]: https://github.com/mr-gl00m/shardcore/compare/v1.9.0...v1.12.0
