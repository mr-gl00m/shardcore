# Changelog

All notable changes to SHARDCORE are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project
versions the **specification** and the **reference library** on the same
cadence until they diverge; entries note both version numbers.

## [Unreleased]

_Nothing yet._

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
  round-trip guarantee (spec §6.8). A shard reopened a week later
  resumes from the exact membrane voltages, synaptic accumulators,
  refractory timers, and learned weights it had when it was saved.
- **Vitality system** (spec §3.4): `core_decay`, `perturbation`, and
  `curiosity_engine` mechanics so that engagement produces something
  measurable at the substrate level. The feature is normative; runtimes
  MAY opt out per-bundle with `enabled: false`.
- **Conformance suite** (`tests/conformance/`): manifest integrity,
  three-pillar round-trip, and neuronshard persistence. Unit tests
  (`tests/unit/`) cover LIF dynamics and serializer round-trip.
- **Example bundles.** `examples/minimal.shard` (soul-only, smallest
  valid bundle) and `examples/standard.shard` (four-pillar bundle with
  a pre-warmed Neuronshard). Both pass the full conformance suite.
- **CI matrix.** Ubuntu / macos / windows × Python 3.10–3.13, plus
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
  mechanical; see spec §17.2.
- LLM inference is a deliberate non-goal for this repository.
  Downstream applications consume the format; `shardcore` only
  describes and substrates it.
- The spec is frozen. The library may evolve across 0.x releases
  (error messages, loader ergonomics, performance) without changing
  observable neuronshard dynamics, which are part of the spec contract.
