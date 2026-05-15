# SHARDCORE Roadmap

This document describes concrete milestones with acceptance criteria,
not aspirations. Dates are intent, not contract.

Spec references below point at [`SHARDCORE_Spec_v1.0.md`](SHARDCORE_Spec_v1.0.md).

---

## v1.0: Public release (shipped, this repo)

**Goal:** ship a format spec that a second implementer can read once and
build against, plus a reference library small enough to read in an hour.

Shipped:

- Normative format spec for **soul**, **shell**, **mind**, and **neuron**
  pillars, with SHA-256 manifest integrity (§1–§8).
- `shardcore/` reference package: pure numpy, no LLM dependency.
  - `python -m shardcore verify <bundle>`: manifest + pillar validator.
  - `python -m shardcore neuron <bundle>`: LIF tick engine with optional
    state save.
- Neuronshard with **byte-identical round-trip** guarantee (§6.8) and a
  test verifying it.
- Conformance suite (`tests/conformance/`) of valid and malformed bundles.
- Apache-2.0 license on spec; MIT license on reference library.

Acceptance (enforced at release):

- [x] **Example bundles verify.** `shardcore verify` passes on every
      bundle under `examples/`, checked both locally and by CI.
- [x] **Malformed bundles are rejected.** `tests/conformance/` builds
      malformed bundles programmatically (via `conftest.py` fixtures)
      and asserts that each one fails verification with a readable
      error. No on-disk `invalid/` corpus is needed.
- [x] **Cross-platform test matrix is green.** `python -m pytest` runs
      on ubuntu / macos / windows × Python 3.10–3.13 via
      `.github/workflows/ci.yml` on every push and PR to `main`.
- [x] **Secret scans clean.** Gitleaks and trufflehog run on every push
      (`ci.yml::secret-scan`). A failed scan blocks merge.

---

## v1.1: The neural substrate, in motion

**Target:** 2026 Q3.

v1.0 made the neuronshard normative but left the surrounding machinery
(drives, dreams, introspection, validation) experimental. v1.1 lands
reference implementations for each and promotes them to normative.

### 1.1.1 Driveshard tick engine: promotes §9 to normative

A drive is a named scalar with a half-life; chemicals decay; goals tier
like memory (short-term → long-term → core). Reference implementation
slots next to `shardcore/neuron.py` as `shardcore/drive.py`.

Acceptance:

- [ ] Schema frozen: `drives[name].value`, `.half_life_s`, `.last_kick`.
- [ ] `tick_drives(driveshard, dt)` decays every drive correctly; verified
      by a round-trip test (`tick_drives` for N seconds produces the
      same final values as a single closed-form decay).
- [ ] Goals inherit/expire with mindshard tiers; core-goal removal
      requires an explicit `promote_to_core` step, not automatic.
- [ ] Genome linkage: driveshard reads base rates from `shellshard.genome`
      when present; otherwise falls back to default priors.
- [ ] Epigenetic inheritance documented and test-covered.

### 1.1.2 Dream consolidator: promotes §12 to normative

Between-session pass over short-term memory that produces long-term
entries and writes `mindshard.dream_log`.

Acceptance:

- [ ] Deterministic given a seed + input mindshard; no LLM call required
      for the clustering step (pure-local embeddings supplied or bundled
      as a pinned model).
- [ ] Dream output schema frozen: `dream_log[*].{cluster, entries,
      consolidated_text, promoted_to}`.
- [ ] Dream may trigger Hebbian updates on the neuronshard for co-active
      memory clusters; update is gated by a `dream.apply_hebbian` flag.
- [ ] Round-trip test: running dream on a bundle, reloading, running again
      on the *unchanged* inputs is a no-op.

### 1.1.3 Introspection surface: promotes §13 to normative

`shardcore.introspect(bundle_or_runtime) -> IntrospectionReport`.

Acceptance:

- [ ] Report fields frozen: `active_drives`, `chemistry`, `firing_now`,
      `inhibited`, `active_goals`, plus raw-state pointers for LLM
      grounding.
- [ ] Values causally sourced from neuronshard + driveshard state;
      no template strings, no invented numbers.
- [ ] JSON-serializable; stable ordering; documented precision/units.

### 1.1.4 Validation rule evaluator: promotes §14 to normative

AST-whitelisted expression evaluator over the merged pillar state. The
reflex-rule parser used by the existing `.shards` apps is the starting
point.

Acceptance:

- [ ] Rule language documented: allowed operators, allowed paths, max
      expression depth, evaluation timeout.
- [ ] Violations produce structured errors (`{rule, path, expected,
      actual}`), never untyped strings.
- [ ] `policy` field defined: one of `warn | refuse | log`. Spec frozen.
- [ ] Attack surface tested: malicious rules cannot import, exec,
      open files, or allocate unbounded memory.

### 1.1.5 Skills folder: promotes §10 to normative (read-only)

v1.1 standardizes **read** semantics; learned write-back stays deferred.

Acceptance:

- [ ] Frontmatter schema validated on load.
- [ ] Always-on vs retrieval-gated activation defined in terms of
      driveshard/mindshard queries.
- [ ] Learned fields (`proficiency`, `xp`, `usage_count`) defined as
      read-only in v1.1; any write path is out-of-spec until v1.2.

---

## v1.2: Make the library a library

**Target:** 2026 Q4 / 2027 Q1.

Until now the library lives in-repo. v1.2 is about letting people
`pip install` it and letting **skills write back**.

Acceptance:

- [ ] `shardcore` published to PyPI with tagged releases; wheels
      produced by CI.
- [ ] Public Python API documented with type stubs; semver applies.
- [ ] Skills v1.4: learned write-back. `skill.use(shard, ...)` may
      increment `proficiency`/`xp`/`usage_count` and is the **only**
      sanctioned path that modifies skill markdown in place. Spec
      defines the locking / atomic-write contract.
- [ ] Reference retrieval layer (`shardcore/retrieve.py`) for
      `references/`, with per-document chunk strategies from the
      sidecar manifest.

---

## v2.x: Beyond a single bundle

v2 is speculative. Items here are design directions, not commitments.

### 2.1 Federated shard registry

A discovery layer so bundles can be published, mirrored, and verified
by signature. Includes:

- Signed manifests (detached signatures over `manifest.json`).
- A minimal registry protocol (HTTP; OCI-distribution-style layout).
- Reference registry implementation and a CLI (`shardcore publish`,
  `shardcore pull`).

### 2.2 Cross-shard connectome

Allow neuronshards to carry inter-shard edges, enabling a party of
characters to have correlated internal state (shared attention, shared
trauma). Research-grade; depends on clean v1.1 drive/dream semantics.

### 2.3 Reservoir variants

The v1.0 LIF engine is one choice. v2 opens the substrate to
swappable back-ends (rate-coded reservoirs, memristor-style sparse
recurrent nets) behind a stable neuronshard I/O interface. Grounded
in the reservoir-computing paper cited in §16.

### 2.4 Runtime in non-Python environments

A second reference implementation (Rust or Go) to shake out
language-dependent assumptions in the spec. A spec that exists in only
one language isn't a spec yet.

---

## Non-goals

- **LLM inference in-library.** `shardcore` will never ship an LLM
  backend. It describes format + substrate; prompt/response plumbing
  belongs to consumers.
- **Mandatory tooling.** The spec is authoritative. A bundle produced by
  hand with no Python anywhere in sight is as valid as one produced by
  the reference library.
- **Feature parity with internal `.shards` apps.** Those apps will move
  to consume the public library as it stabilizes, but their roadmaps are
  independent from this one.

---

## How milestones get promoted

A feature moves from [EXPERIMENTAL] to [NORMATIVE] when all of:

1. A schema is frozen in the spec with a version bump.
2. A reference implementation exists and passes dedicated tests.
3. The conformance suite is extended to cover the new surface.
4. At least one second consumer (another app, another language, or an
   external contributor's implementation) has exercised it.

Criterion #4 is the gating one. Features age out of experimental when
*somebody else* proves the surface is usable, not when the author says
it is.
