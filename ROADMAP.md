# SHARDCORE Roadmap

This document describes concrete milestones with acceptance criteria,
not aspirations. Dates are intent, not contract.

Spec references below point at [`SHARDCORE_Spec_v1.9.md`](SHARDCORE_Spec_v1.9.md).

---

## v1.9: The v1 capstone (shipped, this repo)

**Goal:** reshape the format around one required pillar plus optional,
self-describing pillars; fix how the format versions itself; and revive
`shardcore` as the single reference implementation with a real write and
migrate path.

Shipped:

- **The reshape.** Soul is the one required pillar; every other pillar is
  optional and carries a per-member `schema` id. Canon, stat, body, and a
  unified `assets/` folder are defined optional pillars.
- **Honest versioning.** A single `spec_version` is the negotiated field;
  `bundle_version` is a deprecated alias; `memory_format` is removed; the
  mind pillar self-describes.
- **Conformance profiles and model tiers** (section 4) and a deterministic
  **projection contract** (section 10).
- **Reference library with a write path.** Read, verify, diagnose, and the
  v1.9 migration chain (0001 to 0014) with an atomic repack. New CLI
  subcommands `diagnose` and `migrate`.
- **Migration.** The whole internal library (87 bundles) migrated to v1.9;
  the chain is idempotent and reversible.

Acceptance (enforced at release):

- [x] **Example bundles verify.** `shardcore verify` and `diagnose` pass on
      every bundle under `examples/`, checked locally and by CI.
- [x] **Malformed bundles are rejected.** `tests/conformance/cases.py`
      builds 18 valid, drifted, and malformed fixtures programmatically and
      asserts the reader's conclusion about each.
- [x] **Migration round-trips.** A v1.0-era bundle migrates to `current`
      and verifies; a second migrate is a no-op.
- [x] **Cross-platform test matrix is green** on ubuntu / macos / windows
      x Python 3.10 to 3.13 via `.github/workflows/ci.yml`.
- [x] **Secret scans clean.** Gitleaks and trufflehog run on every push.

---

## Next: the substrate, in motion

**Target:** 2026 Q4.

v1.9 defines the pillars and the contracts. The surrounding machinery
(drives, dreams, introspection, validation, skills) is still experimental
or reserved. The next milestone lands reference implementations and
promotes them.

### Driveshard tick engine: promote `drive@0.1` toward normative

A drive is a named scalar with a half-life; chemicals decay; goals tier
like memory. Reference implementation slots next to `shardcore/neuron.py`.

- [ ] Schema frozen: `drives[name].value`, `.half_life_s`, `.last_kick`.
- [ ] `tick_drives(driveshard, dt)` decays every drive correctly, verified
      against a closed-form decay.
- [ ] Goals inherit and expire with mindshard tiers; core-goal removal is
      an explicit step, not automatic.
- [ ] Epigenetic inheritance documented and test-covered.

### Dream consolidator

Between-session pass over short-term memory that produces long-term
entries and writes `mindshard.dream_log`.

- [ ] Deterministic given a seed plus an input mindshard; no LLM call for
      the clustering step.
- [ ] Dream output schema frozen; a second run on unchanged inputs is a
      no-op.
- [ ] Optional Hebbian update on the neuronshard for co-active clusters,
      behind a flag.

### Introspection surface and validation rules

- [ ] `shardcore.introspect(bundle_or_runtime) -> IntrospectionReport`,
      causally sourced from neuronshard and driveshard state; no invented
      numbers.
- [ ] AST-whitelisted validation-rule evaluator with a `warn | refuse |
      log` policy; malicious rules cannot import, exec, open files, or
      allocate unbounded memory.

### Living-layer coupling

Couple the neural substrate, drives and chemistry, and memory into one
deterministic tick loop so a shard's internal state evolves as a whole
between sessions, not as three isolated layers.

- [ ] A single tick advances substrate, chemistry, and memory in a defined
      order with a serialized, resumable state.

---

## Make the library a library

**Target:** 2026 Q4 / 2027 Q1.

- [ ] `shardcore` published to PyPI with tagged releases; wheels produced
      by CI.
- [ ] Public Python API documented with type stubs; semver applies.
- [ ] Every first-party writer in the wider ecosystem routes bundle I/O
      through this library, so no app can down-convert a bundle on save.

---

## v2.x: Beyond a single bundle

v2 is speculative. Items here are design directions, not commitments.

### 2.1 Federated shard registry

A discovery layer so bundles can be published, mirrored, and verified by
signature: detached signatures over `manifest.json`, a minimal registry
protocol, and a reference `shardcore publish` / `shardcore pull` CLI. The
v1.9 `lineage` and `attestation` manifest fields are the on-ramp.

### 2.2 Cross-shard connectome

Inter-shard neuronshard edges, so a party of characters can carry
correlated internal state. Depends on clean drive and dream semantics.

### 2.3 Reservoir variants

Swappable substrate back-ends (rate-coded reservoirs, memristor-style
sparse recurrent nets) behind the stable neuronshard I/O interface.

### 2.4 Runtime in non-Python environments

A second reference implementation (Rust or Go) to shake out
language-dependent assumptions. A spec that exists in only one language
isn't a spec yet. The framework-free conformance suite in
`tests/conformance/cases.py` is built to be consumed from another runtime.

---

## Non-goals

- **LLM inference in-library.** `shardcore` will never ship an LLM backend.
  It describes format plus substrate; prompt and response plumbing belongs
  to consumers.
- **Mandatory tooling.** The spec is authoritative. A bundle produced by
  hand with no Python anywhere is as valid as one produced by the library.
- **Feature parity with the wider ecosystem's apps.** Those apps move to
  consume the public library as it stabilizes, but their roadmaps are
  independent from this one.

---

## How milestones get promoted

A feature moves from experimental to normative when all of:

1. A schema is frozen in the spec with a schema-id bump.
2. A reference implementation exists and passes dedicated tests.
3. The conformance suite is extended to cover the new surface.
4. At least one second consumer (another app, another language, or an
   external contributor's implementation) has exercised it.

Criterion 4 is the gating one. Features age out of experimental when
somebody else proves the surface is usable, not when the author says it is.
