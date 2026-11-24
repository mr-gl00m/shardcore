# SHARDCORE Roadmap

This document describes concrete milestones with acceptance criteria,
not aspirations. Dates are intent, not contract.

Spec references below point at [`SHARDCORE_Spec_v1.12.md`](SHARDCORE_Spec_v1.12.md).

---

## v1.13: Epistemic memory (spec text not started)

**Goal:** a memory says where it came from, a belief is data with evidence, and
active memory degrades entry by entry when the budget runs out.

- [x] The design questions decided (2026-11-23).
- [ ] Spec v1.13 text: mind@2.2 (`epistemic_status`, `provenance`, `mind.beliefs`),
      the projection's beliefs section, and a projection contract version.
- [ ] Projection contract 2 is opt-in; contract 1 stays the default.
- [ ] Reference library, golden texts and `vendor/shard_projection.gd` at v1.13.
- [ ] QUICKENING moves `quickening/beliefs@1.0` into `mind.beliefs`.
- [ ] Ecosystem check passes.
- [ ] Library 1.13.0 released, and only then stamped into any shard. Upgrading the
      live library is optional.

---

## v1.12: neuron@1.1, body stimulus, and writers that keep versions (spec ratified 2026-11-23, amended 2026-11-24)

**Goal:** a neural substrate that propagates and learns, tied to the body; and no
update that moves anyone who did not take it. Library 1.12.0 carries everything
from v1.10 and v1.11, which were ratified but never released as libraries.

- [x] Spec v1.12 ratified (`SHARDCORE_Spec_v1.12.md`, decisions in its record).
- [x] Reference library at 1.12: `shell@1.12`, `neuron@1.1` default, `shardcore/brain/`.
- [x] A save keeps the shard's version, a new shard takes the lowest that covers its
      content, `min_writer` is honored, an upgrade keeps the earlier file.
- [x] Checked against a frozen copy of every helper that shipped in an app, and of
      both public libraries.
- [x] `diagnose` says `behind`, where it said `outdated`, for a conforming bundle.
- [x] README carries the compatibility promise.
- [x] Library 1.12.0 released.
- [ ] Library 1.12.0 on PyPI.

---

## v1.11: Revision chain, merge, reference projection (spec ratified, never released as a library)

**Goal:** order and reconcile copies of one identity, so a character can be
taken through several apps and come back without one app's edits silently
replacing another's; and make "the same shard reads the same way in every
runtime" true in code.

Landed:

- **One Python implementation.** The vendored helper is `shardcore/core.py`,
  and the library imports it instead of keeping its own copies.
- **`manifest.revision`** (spec 11.5): `n`, `prior`, a 16-deep `history`,
  `merged`; `compare_revisions` and `common_ancestor`.
- **Merge** (spec 11.5.3): `merge_members`, `merge_bundles`, `write_merge`,
  base states from the backup vault; `python -m shardcore compare` / `merge`.
- **Anatomy parts map** (spec 6.3, `shell@1.10`) and migration `0017`;
  revision stamping as migration `0016`; `stale_schema_ids` drift.
- **Reference projection** `shardcore/projection.py` with golden texts, and
  its GDScript port `vendor/shard_projection.gd`. QUICKENING runs on it.
- **Self-contained spec**: v1.0 and addendum material folded in.

Acceptance:

- [x] Conformance suite covers a revised bundle, a malformed revision, a v1.10
      bundle, and a list-shape shell (27 fixtures), plus 7 projection goldens.
- [x] Python and GDScript agree on revision stamping, comparison, and every
      projection golden text (`tests/test_vendor_gdscript.py`,
      `tests/test_vendor_projection_gdscript.py`).
- [x] `tools/ecosystem/ecosystem.py check` passes across all eleven consumers,
      with the contract checking revision descent on every write path.
- [x] Example bundles rebuild and diagnose `current` at v1.11.
- [ ] AI Rift and Djinn Redux build their character prompt from the reference
      projection.
- [ ] Cross-platform CI matrix green on the 1.11 tree.

---

## v1.10: Identity and offspring lineage (spec ratified, library unreleased)

**Goal:** give bred, cloned, and fused characters a hash-pinned record of their
parents, and give every bundle an identity that survives edits so a pedigree
can be resolved.

Landed:

- **`manifest.shard_id`** (spec 11.4.1): minted once, preserved on every save.
- **`relationship: "offspring"`** with a `parents` array of role-tagged,
  hash-pinned entries (spec 11.4.2). Parents only; no inherited canon.
- **Numeric version comparison** made normative (spec section 3).
- **Library:** `shardcore.lineage`, a builder that mints ids and validates
  lineage, migration `0015`, and five new conformance fixtures.

Acceptance:

- [x] `tests/conformance/cases.py` covers both lineage shapes, tolerated
      malformed lineage, a v1.9 bundle, and a broken `shard_id` (23 fixtures).
- [x] A v1.9 bundle migrates to v1.10 with a deterministic `shard_id`; a
      second migrate is a no-op.
- [x] Example bundles rebuild and diagnose `current` at v1.10.
- [x] `tools/ecosystem/ecosystem.py check` passes across every consumer
      (eight then; eleven by v1.11): vendored copies identical, every write path through the
      contract fixtures, isolation, and each consumer's own tests.
- [ ] Cross-platform CI matrix green on the 1.10 tree.

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

- [ ] Schema frozen from the one working writer (QUICKENING,
      `quickening/drives.py`): `drives[name] = {value, growth_per_hour,
      critical}`, `chemicals[name] = {value, half_life_hours}`, `goals`,
      `tick = {last_tick_utc, tick_count}`, `regulators` (spec PART II).
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
`shard_id`, `lineage`, and `attestation` manifest fields are the on-ramp.

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
