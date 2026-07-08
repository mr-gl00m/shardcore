# Changelog

All notable changes to SHARDCORE are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project
versions the **specification** and the **reference library** on the same
cadence; entries note both version numbers. As of v1.9 the two are in
lockstep at 1.9.0.

## [Unreleased]

_Nothing yet._

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
