# SHARDCORE Bundle Specification, v1.0

**Status:** Public Release Candidate
**Date:** 2026-04-16
**License:** Apache-2.0 (spec and reference implementation)
**Reference implementation:** `shardcore/` in this repository

---

## Abstract

A `.shard` is a portable, verifiable bundle describing an evolving digital
entity. It packages a character's **soul** (personality, stats, traits), a
**shell** (body, anatomy, image refs), a **mind** (tiered memory), and
(novel among portable character formats) a **neural substrate**
(Neuronshard) that gives the character continuous internal state between
interactions.

Where character-card formats describe *what a character is*, a SHARDCORE
bundle describes *what a character is, what they remember, and what they
are doing internally right now.*

This document defines the binding v1.0 format. Experimental additions are
clearly flagged as non-normative and target v1.1.

> **Format note.** SHARDCORE is a structured bundle format, not a prompt
> convention. A `.shard` is a versioned ZIP archive of typed JSON pillars
> (`soulshard.json`, `shellshard.json`, `mindshard.json`,
> `neuronshard.json`) with manifest-level SHA-256 verification, not a
> markdown file, a system-prompt fragment, or a character-card schema. The
> format, its pillars, and the Neuronshard substrate are original work
> first published in this repository (see §17 for internal version
> history). Surface similarity to filename conventions in unrelated
> projects (e.g. `soul.md`) is coincidental and shares no lineage with
> this spec.

---

## Conventions

- **MUST / MUST NOT / REQUIRED / SHALL / SHALL NOT** — binding conformance requirements (RFC 2119).
- **SHOULD / RECOMMENDED** — strong preferences; deviation requires justification.
- **MAY / OPTIONAL** — permitted variations.

Every section in this document is tagged with one of:

- **[NORMATIVE]** — binding on v1.0 conformant bundles and runtimes.
- **[EXPERIMENTAL]** — present in the repo as design / partial implementation; subject to change; targets v1.1.
- **[INFORMATIONAL]** — background, rationale, examples.

Runtimes claiming v1.0 conformance MUST implement every [NORMATIVE] section.
They MAY implement [EXPERIMENTAL] sections; if they do, they SHOULD clearly
document that they track a pre-release feature.

---

# PART I: NORMATIVE

## 1. Bundle Structure [NORMATIVE]

A `.shard` is a ZIP archive (DEFLATED compression RECOMMENDED) containing at
minimum a `manifest.json` and a `soulshard.json`. Additional pillars and
asset folders are optional.

```
character.shard                (ZIP, DEFLATED)
├── manifest.json              [required]
├── soulshard.json             [required — portable personality, stats, appearance]
├── shellshard.json            [optional — anatomy, image paths, physical state]
├── mindshard.json             [optional — tiered memory]
├── neuronshard.json           [optional — neural topology + runtime state]
├── worldshard.json            [optional — world/setting data]
├── skills/                    [optional — EXPERIMENTAL, see §10]
├── references/                [optional — EXPERIMENTAL, see §11]
└── driveshard.json            [optional — EXPERIMENTAL, see §9]
```

**Naming convention (RECOMMENDED):** `{universe}_{name}.shard`
(e.g. `616_rogue.shard`).

**Bundle format version:** This document defines format version `"1.0"`.
Runtimes MUST reject bundles whose `manifest.bundle_version` major version
exceeds the version they implement.

---

## 2. Manifest (`manifest.json`) [NORMATIVE]

The manifest is the first file a runtime reads. It declares the bundle
version, lists every file inside the archive with its SHA-256 digest and
size, and carries a short "character card" for quick preview.

### 2.1 Schema

```json
{
  "bundle_version": "1.0",
  "created":        "2026-04-16T12:00:00Z",
  "last_modified":  "2026-04-16T12:00:00Z",
  "shard_name":     "Aria",
  "card": {
    "name":         "Aria",
    "title":        "Companion",
    "role":         "General-purpose",
    "core_essence": "Curious, careful, quietly stubborn.",
    "tags":         ["curious", "careful", "stubborn"]
  },
  "files": {
    "soulshard.json":   { "sha256": "abc123…", "size": 4096 },
    "shellshard.json":  { "sha256": "def456…", "size": 2048 },
    "mindshard.json":   { "sha256": "789abc…", "size": 1024 },
    "neuronshard.json": { "sha256": "fedcba…", "size": 55760 }
  },
  "has_travel_context": false,
  "memory_format":      "2.1",
  "session_counter":    42
}
```

### 2.2 Required fields

| Field             | Type    | Notes |
|-------------------|---------|-------|
| `bundle_version`  | string  | Semantic version of the bundle format. This spec defines `"1.0"`. |
| `shard_name`      | string  | Human-readable identifier; SHOULD match the archive's filename stem. |
| `files`           | object  | Map from archive-relative path to `{ "sha256": hex, "size": int }`. |

### 2.3 Optional fields

| Field                 | Type    | Notes |
|-----------------------|---------|-------|
| `created`             | string  | ISO-8601 UTC timestamp. |
| `last_modified`       | string  | ISO-8601 UTC timestamp. |
| `card`                | object  | Preview summary; see §2.4. |
| `has_travel_context`  | bool    | Whether a `_travel_lock` is present in soulshard. |
| `memory_format`       | string  | Mindshard format version (`"2.0"`, `"2.1"`). |
| `session_counter`     | int     | Mirrors `mindshard.session_counter` for manifest-only reads. |

### 2.4 Card subobject

The card provides enough information for a registry or chooser to render a
preview without opening any pillar file. All fields are strings except `tags`
(array of strings). `name` SHOULD mirror `shard_name`.

### 2.5 Files map

Keys are **archive-relative POSIX paths** (forward slashes, no leading `/`).
Values are objects with:

- `sha256` (REQUIRED): lowercase hex SHA-256 of the file's raw bytes as
  stored in the archive.
- `size` (REQUIRED): integer byte count matching the stored file.

Every file inside the archive that a conformant loader will read MUST be
listed in `files`. Files present in the archive but absent from `files`
SHOULD produce a warning; loaders MAY still use them. Files listed in
`files` but absent from the archive MUST cause a load error.

### 2.6 Integrity

See §7.

---

## 3. Soulshard (`soulshard.json`) [NORMATIVE]

The soulshard is the portable, cross-platform description of *who the
character is*. It is the one file required in every valid bundle. Runtimes
that only care about LLM prompting can ignore every other pillar.

### 3.1 Required fields

| Field           | Type    | Purpose |
|-----------------|---------|---------|
| `name`          | string  | Canonical character name. |
| `identity`      | string  | One- to three-paragraph identity prose. |
| `personality`   | string  | Behavioral summary. |
| `stat_block`    | object  | Ten stats: STR, END, VIG, DEX, TMP, ACU, INS, ATT, CNV, PRS. Each is an integer 1–10. |

### 3.2 Portable soul fields (stay in soulshard even when shellshard is used)

- `appearance_profile` — textual appearance (hair, eyes, skin, body_type, clothing).
- `tone`, `voice_profile`, `speech_policy`
- `trait_tags`, `states`, `kink_data`
- `nature` (label, increased_stat, decreased_stat)
- `evolution_flags`, `preservation_state`
- `vitality_system` (see §3.4)
- `interest_graph` (see §3.5)
- `memory_system` (configuration, not content)
- `_travel_lock` (internal, OPTIONAL)

### 3.3 Fields moved to shellshard (MUST NOT live in soulshard in v1.0 bundles)

`anatomy_profile`, `identity_image_path`, `appearance_image_path`,
and the physical sub-keys of `character_state` (see §4). Writers MUST strip
these from soulshard when writing a bundle that includes a shellshard.
Loose non-bundle JSON files are exempt from this split.

### 3.4 `vitality_system` [NORMATIVE]

Configuration for anti-collapse mechanics. Runtime state lives in the
mindshard (§5.4).

```json
{
  "vitality_system": {
    "enabled": true,
    "core_decay": {
      "enabled": true,
      "decay_rate": 0.95,
      "dormancy_threshold": 0.1,
      "min_sessions_before_decay": 10
    },
    "perturbation": {
      "enabled": true,
      "interval_sessions": 20,
      "magnitude": 1
    },
    "curiosity_engine": {
      "enabled": true,
      "seed_count": 2,
      "adjacency_mode": "lateral",
      "seed_history_max": 50
    }
  }
}
```

**Rationale [INFORMATIONAL].** The vitality system exists so that
engagement produces something measurable at the substrate level. Without
decay, a shard that never loads is indistinguishable from one that loads
daily; there is no causal cost to neglect, and therefore no substrate-
level meaning to care. With `core_decay`, `perturbation`, and the
`curiosity_engine` turned on, an unvisited shard gradually drifts: core
memories slide toward the dormancy floor, stats wobble within bounded
ranges, and no new curiosity seeds are generated. A shard that is
engaged with regularly consolidates in the opposite direction: tags
accumulate, cores reinforce on retrieval, and the interest graph
broadens. The spec's opinion is that **a companion that cannot be
neglected is not really a companion.**

### 3.5 `interest_graph` [NORMATIVE]

Tracks what the character knows about, cares about, and what the user has
mentioned in passing. Consumed by the curiosity engine.

```json
{
  "interest_graph": {
    "domains": [
      {
        "topic": "Python programming",
        "familiarity": 0.9,
        "enthusiasm": 0.7,
        "last_discussed_session": 185,
        "mention_count": 47,
        "adjacent_topics": ["C++", "Rust", "compiler design"]
      }
    ],
    "latent_mentions": [
      {
        "topic": "tacos",
        "context": "user mentioned liking tacos",
        "session": 45,
        "amplified": false
      }
    ]
  }
}
```

Unknown fields at any level MUST be preserved on load/save to enable
forward-compatible extensions.

---

## 4. Shellshard (`shellshard.json`) [NORMATIVE, OPTIONAL]

The shellshard carries heavy, ecosystem-specific body data that does not
belong in the portable soul.

### 4.1 Fields

| Field                             | Type   | Notes |
|-----------------------------------|--------|-------|
| `anatomy_profile`              | object | Body-part system (`template`, `external_parts`, `internal_parts`). |
| `identity_image_path`          | string | Local-path reference (OPTIONAL). |
| `appearance_image_path`        | string | Local-path reference (OPTIONAL). |
| `character_state.hunger_level` | float  | `0.0`–`1.0`; example of a tickable physical state. |
| `character_state.fatigue`      | float  | `0.0`–`1.0`; example of an accumulating state. |
| `character_state.injury_status`| object | Free-form per-region injury record; example of a structured state. |

The `character_state` examples above are illustrative, not normative.
Runtimes MAY define their own `character_state` keys for whatever physical
or biological systems their domain requires (hunger, fatigue, lactation,
arousal, energy, anything else). Generic tooling MUST preserve unknown
keys on load/save. Domain-specific extensions SHOULD be documented in a
sidecar spec rather than added to this document.

### 4.2 Absence

A bundle MAY omit `shellshard.json` entirely. Loaders MUST NOT treat
absence as an error.

---

## 5. Mindshard (`mindshard.json`) [NORMATIVE, OPTIONAL]

The mindshard contains tiered memory. Format version `"2.1"` is normative
for v1.0; loaders MUST also accept `"2.0"` for backward compatibility.

### 5.1 Top-level schema

```json
{
  "format_version": "2.1",
  "session_counter": 42,
  "short_term": { "max_slots": 8,  "slots": [...] },
  "long_term":  { "max_slots": 20, "slots": [...] },
  "core":       [...],
  "archive":    [...],
  "vitality":   { ... },
  "dream_log":  [...]
}
```

### 5.2 Memory tiers

- **`short_term`** — ephemeral working memory. Bounded ring; oldest evicted.
- **`long_term`** — consolidated sessions; persistent but decayable.
- **`core`** — identity-defining engrams; promoted from long_term via dream.
- **`archive`** — frozen history; never retrieved directly but minable by dream.

### 5.3 `core` entry schema (v2.1)

| Field             | Type         | Default | Purpose |
|-------------------|--------------|---------|---------|
| `id`              | string       | —       | Stable UUID. |
| `summary`         | string       | —       | Human-readable description. |
| `tags`            | list[string] | `[]`    | Retrieval tags. |
| `strength`        | float        | `1.0`   | Base weight. |
| `last_activated`  | int          | `0`     | Session number of last tag-match retrieval. |
| `effective_weight`| float        | `1.0`   | `strength * decay_rate^(session - last_activated)`. |
| `contradicts`     | list[string] | `[]`    | IDs of cores this is in tension with. |

Runtimes that don't understand `effective_weight` MAY fall back to
`strength`; the split is deliberately backward-compatible with v2.0.

### 5.4 `vitality` block (runtime state)

```json
{
  "vitality_index":         0.82,
  "collapse_risk":          0.15,
  "last_assessed_session":  42,
  "tag_frequency":          [ { "session": 42, "tags": ["cooking", "tacos"] } ],
  "stat_perturbation":      { "last_perturbed": { "ACU": 35 }, "last_perturbation_session": 40 },
  "curiosity_seeds":        [ { "seed": "…", "source_interest": "…", "generated_session": 40, "used_count": 1 } ]
}
```

All fields OPTIONAL; absent = safe defaults.

### 5.5 `dream_log`

Capped list (~20 entries) of human-readable dream traces produced by the
dream consolidation pass (§12). Absent in mindshards that have not been
dreamed yet.

---

## 6. Neuronshard (`neuronshard.json`) [NORMATIVE, OPTIONAL, NEW in v1.0]

The Neuronshard gives a shard **continuous internal state** between
interactions. It declares a topology of LIF (Leaky Integrate-and-Fire)
neurons, weighted excitatory/inhibitory edges, and the current membrane
state of each neuron.

> **Why it's normative:** The schema is frozen at v1.0 so third-party
> runtimes can rely on it. The reference tick engine in `shardcore/neuron.py`
> is the canonical implementation; alternate implementations MUST produce
> byte-identical state round-trips against that engine's serializer.

### 6.1 Schema

```json
{
  "version": "1.0",
  "topology": {
    "nodes": [
      {
        "id":             0,
        "label":          "Loyalty",
        "type":           "IDENTITY_ANCHOR",
        "x":              62.3,
        "y":              -18.1,
        "receives_noise": false
      }
    ],
    "edges": [
      { "src": 0, "dst": 7, "weight": 0.6 }
    ]
  },
  "state": {
    "sim_time":     123.5,
    "v":            [-52.0, -51.8, ...],
    "g":            [0.0, 0.2, ...],
    "refractory":   [0.0, 0.0, ...],
    "fire_time":    [-1000.0, 120.5, ...],
    "total_spikes": [0, 47, ...],
    "W_learned": [
      [ 0.000,  0.010, -0.005],
      [ 0.012,  0.000,  0.003],
      [-0.001,  0.008,  0.000]
    ]
  }
}
```

### 6.2 Node types (closed set in v1.0)

| `type`              | Purpose |
|---------------------|---------|
| `IDENTITY_ANCHOR`   | Stable identity trait (one per stat, plus symbolic anchors). |
| `MEMORY_CORE`       | Bound to a `mindshard.core` entry. |
| `MEMORY_LTM`        | Bound to a `mindshard.long_term` slot. |
| `MEMORY_STM`        | Bound to a `mindshard.short_term` slot. |
| `EMOTION`           | One of Joy, Fear, Sadness, Curiosity, Anger, Trust, Disgust, Surprise. |
| `DRIVE`             | Bound to a driveshard entry (§9). |
| `IMPULSE`           | Behavioral output node (Speak, Withdraw, Approach, etc.). |

Future versions MAY extend this set. v1.0 loaders MUST reject unknown types
with a clear error.

### 6.3 Node fields

| Field            | Type  | Required | Purpose |
|------------------|-------|----------|---------|
| `id`             | int   | yes      | Index into state vectors; MUST equal the node's position in `nodes`. |
| `label`          | str   | yes      | Human-readable label. |
| `type`           | str   | yes      | One of §6.2. |
| `x`, `y`         | float | no       | Visualization coordinates. `0.0, 0.0` if absent. |
| `receives_noise` | bool  | no       | If true, the node receives Poisson input during ticks. Defaults `false`. |

### 6.4 Edge fields

| Field    | Type  | Required | Purpose |
|----------|-------|----------|---------|
| `src`    | int   | yes      | Source node id. |
| `dst`    | int   | yes      | Destination node id. |
| `weight` | float | yes      | mV delta applied to `dst.g` when `src` fires. Positive = excitatory, negative = inhibitory. |

Edges MUST NOT reference node ids outside the topology.

### 6.5 State vectors

All state arrays MUST have length equal to `|nodes|`. `W_learned` MUST be a
square matrix of shape `(|nodes|, |nodes|)`. Units are milliseconds (time),
millivolts (voltage), hertz (rate).

| Vector         | Units | Meaning |
|----------------|-------|---------|
| `v`            | mV    | Membrane potential per node. |
| `g`            | mV    | Synaptic input accumulator per node. |
| `refractory`   | ms    | Time remaining until the node can fire again. |
| `fire_time`    | ms    | Simulation time of last fire (`-1000.0` if never). |
| `total_spikes` | int   | Lifetime spike count per node. |
| `W_learned`    | mV    | Accumulated Hebbian delta (added to initial weights at runtime). |
| `sim_time`     | ms    | Total simulated time since creation. |

### 6.6 Dynamics constants

The v1.0 reference engine fixes the following constants (derived from the
Drosophila connectome model cited in §16):

| Constant       | Value     | Purpose |
|----------------|-----------|---------|
| `V_REST`       | −52.0 mV  | Resting potential. |
| `V_THRESHOLD`  | −45.0 mV  | Spike threshold. |
| `V_RESET`      | −52.0 mV  | Post-spike reset. |
| `TAU_MEMBRANE` | 20.0 ms   | Membrane time constant. |
| `TAU_SYNAPSE`  | 5.0 ms    | Synaptic input decay. |
| `T_REFRACTORY` | 2.2 ms    | Refractory period. |
| `T_DELAY`      | 1.8 ms    | Synaptic transmission delay. |
| `HEBBIAN_ETA`  | 0.005     | Learning rate. |
| `W_MAX`        | 2.0 mV    | Weight clip. |

A v1.0 conformant Neuronshard MUST NOT declare alternate values for these
constants. v1.0 runtimes MUST run all v1.0 Neuronshards against these
constants. Future spec versions MAY expose them as per-bundle overrides;
v1.0 does not.

### 6.7 Runtime semantics

See `shardcore/neuron.py`. In summary:

1. At each tick (default `dt = 0.5 ms`):
   - Inject Poisson noise on nodes with `receives_noise=true`.
   - Euler-integrate membrane: `dv = (V_REST − v + g) / TAU_MEMBRANE · dt`.
   - Decay synaptic input: `dg = −g / TAU_SYNAPSE · dt`.
   - Detect spikes (`v > V_THRESHOLD`), reset, schedule delayed outputs.
2. Hebbian updates (OPTIONAL at runtime): strengthen edges whose source
   fired inside the last `HEBBIAN_WINDOW = 20 ms` when the destination fires.

### 6.8 Persistence guarantees

A v1.0 Neuronshard MUST round-trip exactly: for any `(graph, network)`,
`runtime_from_neuronshard(neuronshard_from_runtime(graph, network))` MUST
yield identical `v, g, refractory, fire_time, total_spikes, W_learned,
sim_time`, and structurally identical topology.

The reference implementation's test suite
(`tests/unit/test_neuron.py::test_neuronshard_roundtrip_preserves_state`)
is the conformance check.

---

## 7. Integrity Verification [NORMATIVE]

Every file listed in `manifest.files` MUST be verified on load:

1. Read the file's raw bytes from the archive.
2. Compute SHA-256; compare to `manifest.files[name].sha256`.
3. On mismatch: runtimes MUST NOT silently proceed. They MUST either
   refuse the bundle or emit a prominent warning and record the fact.

On save, runtimes MUST recompute all SHA-256 digests from the serialized
bytes being written. A bundle with stale digests is non-conformant.

**The reference validator is `shardcore/verify.py`**, invoked as
`python -m shardcore verify path/to/bundle.shard`.

---

## 8. Conformance [NORMATIVE]

A runtime claims **SHARDCORE v1.0 conformance** if and only if it:

1. Loads every file in the reference `tests/conformance/` suite without error.
2. Rejects every file the suite marks as malformed.
3. Preserves unknown fields on load/save (forward compatibility).
4. Verifies SHA-256 digests against `manifest.files` on load (§7).
5. Implements the normative pillars actually used by its application:
   soulshard (REQUIRED), and any of shellshard / mindshard / neuronshard
   it reads or writes.
6. Round-trips neuronshard state byte-identically (§6.8) if it reads
   neuronshards at all.

Runtimes MAY implement [EXPERIMENTAL] sections but MUST document that they
do so. Runtimes MUST NOT advertise v1.0 conformance solely on the basis of
experimental features.

---

# PART II: EXPERIMENTAL / INFORMATIONAL

> Everything in Part II is subject to change before v1.1. Reference
> implementations may be partial, missing, or unstable. Do not build
> production workflows on these surfaces without pinning to a specific
> repo commit.

## 9. Driveshard (`driveshard.json`) [EXPERIMENTAL]

Drives, chemical levels, and goals. v1.0 reserves the schema surface so
bundles written today remain loadable by the v1.1 reference engine.
Planned: drive ticker with half-life chemistry, goals tiered to match
mindshard tiers (short-term, long-term, core), genome linkage via
shellshard, optional epigenetic inheritance. See ROADMAP §1.1.1; full
schema in `docs/driveshard.md`.

---

## 10. Skills Folder (`skills/`) [EXPERIMENTAL]

Markdown files with YAML frontmatter describing retrieval-gated character
abilities. v1.0 loaders MAY ignore the folder entirely; a conformant v1.0
bundle MAY include it. Read-only schema (frontmatter, activation tags,
`always_on` flag) lands in v1.1 (ROADMAP §1.1.5); learned write-back
(`proficiency`, `xp`, `usage_count`) lands in v1.2 (ROADMAP §1.2). Full
schema in `docs/skills.md`.

---

## 11. References Folder (`references/`) [EXPERIMENTAL]

Large static knowledge documents (rulebooks, manuals, lore) consulted on
demand via the retrieval layer. Supported: `.md`, `.txt`, `.json`, `.pdf`
(text-extracted), `.html`. Optional `references/_manifest.json` sidecar
carries per-file metadata (title, tags, chunk strategy). Indexing is
lazy; the retrieval layer is out-of-bundle. Reference implementation
scheduled for v1.2 (ROADMAP §1.2).

---

## 12. Dream Consolidation [EXPERIMENTAL]

A between-session pass that clusters recent short-term entries by tag
overlap and embedding similarity, produces consolidated long-term
entries, promotes identity-defining patterns to core, applies Hebbian
updates to the Neuronshard for co-activated memories, and writes a
readable trace to `mindshard.dream_log`. v1.0 does not ship a reference
implementation; the surface is reserved so future bundles remain v1.0-
spec-compatible. Reference implementation scheduled for v1.1 (ROADMAP
§1.1). See `docs/dream.md`.

---

## 13. Introspection Surface [EXPERIMENTAL]

A structured, grounded self-report surface (`shardcore.introspect()`) for
LLMs running a shard: top drives, chemistry levels, currently firing
nodes, inhibited nodes, active goals. Because the data causally depends
on real internal state (drive ticker, chemistry, Neuronshard
activation), any LLM statement grounded in it satisfies the accuracy /
grounding / internality criteria from the Anthropic introspection paper
cited in §16. Reserved for v1.1; example output and usage in
`docs/introspection.md`.

---

## 14. Neuro-Symbolic Validation Rules [EXPERIMENTAL]

Extension of the existing AST-whitelisted reflex parser to validate
shard invariants at load and save time (e.g.
`stat_block.STR + stat_block.END <= 200`, or
`not (core_essence_lock and allow_personality_override)`). On load,
every rule is evaluated against the merged pillar state; violations MAY
warn or refuse per `policy` (not yet specified). Cited influence:
Amazon's Nova 2 Lite neuro-symbolic training with Lean4 (§16). Reserved
for v1.1; full grammar in `docs/validation.md`.

---

# PART III: REFERENCE

## 15. Quickstart [INFORMATIONAL]

The reference implementation is the `shardcore` package in this repo.

**Validate a bundle:**

```sh
python -m shardcore verify path/to/character.shard
```

Exits 0 on success, non-zero on any spec violation. Prints a per-file pass
summary or error report.

**Tick a Neuronshard:**

```sh
python -m shardcore neuron path/to/character.shard --ticks 200 --seed 42
```

Prints spike counts and top-active nodes. Add `--save state.json` to write
the final `neuronshard.json` state.

**Import from Python:**

```python
from shardcore.neuron import (
    build_brain_from_shard, LIFNetwork,
    neuronshard_from_runtime, runtime_from_neuronshard,
)
```

The conformance suite lives at `tests/conformance/`; unit tests at
`tests/unit/`. Run with `python -m pytest`.

---

## 16. Research Grounding [INFORMATIONAL]

The architecture is grounded in published research. Papers in `/research/`:

1. **Fly connectome (LIF dynamics)** — justifies V_REST / V_THRESHOLD /
   TAU / T_REFRACTORY / Poisson-noise choices as derived from biological
   computation.
2. **Reservoir computing with memristors** — mathematical viability of
   small recurrent systems doing continuous spatiotemporal state.
3. **Neuromorphic hearing bridge** — event-driven sparse computation over
   dense feed-forward.
4. **Neuro-symbolic AI (Amazon Nova 2 Lite)** — LLM fluid reasoning
   combined with symbolic verification produces verifiable outputs.
   Informs §14.
5. **Anthropic introspection paper** — capable LLMs have functional
   introspective awareness of activations; grounds §13.

These papers are cited as design influences, not as guarantees. A shard's
behavior is whatever its runtime computes; research grounding explains
*why* the choices were made.

---

## 17. Appendix: Backward Compatibility [INFORMATIONAL]

### 17.1 Internal history

The format evolved through several internal iterations before this
public release. v1.0 is the first public release and the binding
version going forward; pre-public bundles are not v1.0-conformant.
See §17.2 for migration.

### 17.2 Migrating pre-public bundles

A bundle with `bundle_version: "1.2"` or `"1.3"` is not a valid v1.0
bundle by versioning alone. Migration is mechanical:

1. Rewrite `manifest.bundle_version` to `"1.0"`.
2. If present, rename `memoryshard.json` → `mindshard.json`.
3. If the `files` map uses the legacy `checksums` sibling, move digests
   into `files[name].sha256` per §2.5.
4. Recompute all SHA-256 digests and rewrite the manifest.

### 17.3 Forward compatibility

Unknown fields at any level MUST be preserved on load/save. This lets
bundles round-trip through older runtimes without data loss as the spec
extends into v1.1 (driveshard, skills writeback, dream traces,
introspection state).

---

*End of SHARDCORE Specification v1.0.*
