# SHARDCORE Bundle Specification, v1.9

**Status:** Ratified 2026-07-08. The next public version; supersedes v1.0.
**Date:** 2026-07-06 (ratified 2026-07-08)
**License:** Apache-2.0 (spec and reference implementation)
**Reference implementation:** the `shardcore` library (see PART III)
**Supersedes:** `SHARDCORE_Spec_v1.0.md` (v1.0 release archive at `.templates/.archive/release_v1.0.0/`)
**Folds in:** `SHARDCORE_Spec_v1.1_addendum.md` (canon, lineage, statshard, body), the v1.3 addendum (skills, references). The internal 1.1/1.2/1.3 numbering and the "v1.1 addendum" label are retired; section 11 fixes their place here, with pillar internals incorporated by reference to the addendum text.
**Companion:** `SHARDCORE_FORMAT_EVOLUTION_PROPOSAL.md` (rationale), `SHARD_UPDATER_PROPOSAL.md` (the migration tool that moves bundles to this version).

---

## Ratification record

Ratified by Cid on 2026-07-08 and applied to the live library the same day: 87/87 bundles migrated to v1.9, 0 failed, all verified `current` (apply run `20260708T090625Z-6a385429`, per-shard backups retained). The three decisions below are folded into the normative text; kept here as provenance.

- [x] **Asset schema id + folder (§1, §2.3, §12).** RESOLVED: all static assets (images, OpenTimestamps receipts, skills, references) live under one top-level `assets/` folder and carry one schema id, `shardcore/assets@1.0`. Origin subfolders (`assets/images/`, `assets/attestations/`, `assets/skills/`, `assets/references/`) are kept for clarity but not required. The earlier singular/plural split (`asset@1.0` vs `assets@1.0`) is collapsed and the singular is retired. Migration 0014 relocates any legacy top-level asset folder under `assets/`.
- [x] **Stat-less soul on migration (§5.1, §12).** RESOLVED: a soul with no `stat_block` defaults to average stats (every stat 5) on migration, and the migrator MUST log every soul it defaulted so the placeholders can be authored later. Written into §5.1 and §12 step 5.
- [x] **`preservation_state` stays portable (§5.2).** Confirmed: it is a portable soul field, not runtime-specific, so it does NOT move under `x_nexus`. This was a false positive in the migrator's allowlist, since corrected. No text change needed; listed here only to record the decision. Verify §5.2 still names it.

---

## Abstract

A `.shard` is a portable, verifiable bundle describing an evolving digital entity: a **soul** (portable identity, personality, stats), a **shell** (body, anatomy, image refs), a **mind** (tiered memory), and a **neural substrate** (Neuronshard) giving continuous internal state between interactions, plus optional pillars for canon, stats, drives, equipment, and world.

v1.9 is the capstone of the v1 line. It does not add new cognitive machinery. It fixes how the format versions itself, makes the portable soul honestly portable, and writes down the two contracts v1.0 left implicit: how a bundle projects into a prompt across models, and which subset of pillars a given use case needs. These changes are what let one format serve roleplay, game NPCs, and cross-model agents without each runtime reinterpreting it. The 2.0 major stays reserved for a change that genuinely breaks foreign readers.

---

## Changes from v1.0

Everything here is additive or a rename with a defined migration. No cognitive subsystem is removed.

1. **Single `spec_version`.** `manifest.bundle_version` becomes `manifest.spec_version`. It is the one version a runtime negotiates on.
2. **Per-pillar schema ids.** Each entry in `manifest.files` gains a `schema` id (`shardcore/<pillar>@<major.minor>`). The pillar's own internal version field becomes bookkeeping subordinate to the schema id.
3. **`memory_format` dropped from the manifest.** It duplicated and could contradict the mindshard's own `format_version`. The mind pillar self-describes.
4. **Soul core vs `x_<vendor>` extensions.** The portable soul carries only fields a foreign runtime can act on. Runtime-specific fields move under an `x_<vendor>` namespace that other runtimes preserve and ignore. This is the structural reshape v1.0 §3.3 pointed at.
5. **`mindshard.structured`.** An optional namespaced block for deterministic, non-narrative machine state (game NPC profiles, agent vectors).
6. **Reference projection contract and model tiers.** A defined, runtime-neutral mapping from bundle to system prompt, tiered for small to large models.
7. **Conformance profiles.** Named subsets (`companion`, `npc`, `agent`) a bundle declares and a runtime advertises.
8. **Canon, lineage, statshard, body promoted.** The v1.1 addendum pillars become defined optional pillars with schema ids.
9. **Migration path defined.** v1.0 and pre-public bundles migrate to v1.9 by the mechanical chain in section 12.
10. **Stays in major 1.** `spec_version` is `"1.9"`. Per v1.0 section 1 a runtime only rejects on a higher MAJOR, so v1.0 runtimes accept v1.9 bundles; to keep their negotiation working, a v1.9 writer also stamps `bundle_version: "1.9"` as a deprecated alias (section 2.2). The one structural move, the `x_<vendor>` re-nest, touches only fields the Nexus runtimes own, and those update in lockstep; foreign readers never consumed them.
11. **`stat_block` closed at ten.** The soul's stat block is exactly the ten numeric stats (section 5.1). The legacy `Resonance` string relocates to an optional soul-level `resonance` field; long-form and case-variant keys normalize to the canonical abbreviations (section 12).
12. **Pillar consolidation.** Duplicate or mislabeled pillar variants inside a bundle (a `memoryshard_*.json`, embedded `backups/`, `.versions/`, `.history/`, digest sidecars) consolidate into the single canonical pillar during migration (section 12).

---

## Conventions

- **MUST / MUST NOT / REQUIRED / SHALL / SHALL NOT**: binding (RFC 2119).
- **SHOULD / RECOMMENDED**: strong preference; deviation needs justification.
- **MAY / OPTIONAL**: permitted variation.

Sections are tagged **[NORMATIVE]**, **[EXPERIMENTAL]** (present as design or partial impl, subject to change), or **[INFORMATIONAL]**. A runtime claiming v1.9 conformance MUST implement every [NORMATIVE] section that applies to the pillars it reads or writes.

---

# PART I: NORMATIVE

## 1. Bundle structure [NORMATIVE]

A `.shard` is a ZIP archive (DEFLATED RECOMMENDED) containing at minimum `manifest.json` and `soulshard.json`.

```
character.shard                (ZIP, DEFLATED)
|-- manifest.json              [required]
|-- soulshard.json             [required]
|-- shellshard.json            [optional]
|-- mindshard.json             [optional]
|-- neuronshard.json           [optional]
|-- canonshard.json            [optional]
|-- statshard.json             [optional]
|-- driveshard.json            [optional, EXPERIMENTAL]
|-- worldshard.json            [optional]
|-- body/                      [optional]  equipped.json, items/<uuid>.json, status_effects.json
`-- assets/                    [optional]  images, receipts, skills, references (shardcore/assets@1.0)
    |-- images/                            identity/appearance art
    |-- attestations/                      OpenTimestamps receipts
    |-- skills/                            retrieval-gated abilities
    `-- references/                        static knowledge documents
```

Subfolders under `assets/` are a RECOMMENDED convention, not a requirement: a member at any depth under `assets/` is an asset. `body/` is deliberately not folded in; it is a live subsystem (section 11.3), not a static asset.

**Naming (RECOMMENDED):** `{universe}_{name}.shard`.

**Version rejection:** a runtime MUST reject a bundle whose `manifest.spec_version` major exceeds the version it implements.

## 2. Manifest (`manifest.json`) [NORMATIVE]

First file read. Declares the spec version, lists every readable file with its schema id, SHA-256, and size, and carries a preview card.

```json
{
  "spec_version": "1.9",
  "bundle_version": "1.9",
  "created": "2026-07-04T00:00:00Z",
  "last_modified_utc": "2026-07-04T00:00:00Z",
  "shard_name": "Aria",
  "immutable": false,
  "card": {
    "name": "Aria", "title": "Companion", "role": "General-purpose",
    "core_essence": "Curious, careful, quietly stubborn.",
    "tags": ["curious", "careful", "stubborn"]
  },
  "conformance": { "profile": "companion", "min_tier": "M" },
  "files": {
    "soulshard.json":   { "schema": "shardcore/soul@1.9",   "sha256": "…", "size": 4096 },
    "shellshard.json":  { "schema": "shardcore/shell@1.9",  "sha256": "…", "size": 2048 },
    "mindshard.json":   { "schema": "shardcore/mind@2.1",   "sha256": "…", "size": 1024 },
    "neuronshard.json": { "schema": "shardcore/neuron@1.0", "sha256": "…", "size": 55760 }
  },
  "session_counter": 42
}
```

### 2.1 Required fields

| Field | Type | Notes |
|---|---|---|
| `spec_version` | string | `MAJOR.MINOR`. This document defines `"1.9"`. The only version negotiated on. |
| `shard_name` | string | SHOULD match the archive filename stem. |
| `files` | object | Map from archive-relative POSIX path to a file entry (section 2.3). |

### 2.2 Optional fields

`created`, `last_modified_utc` (ISO-8601 UTC, `Z` suffix), `card`, `conformance` (section 4), `immutable` (section 11.2), `session_counter`, `lineage` (section 11.1), `attestation` (section 11.1), `has_travel_context`.

`bundle_version` is retained as a deprecated alias so v1.0 readers can keep negotiating: a v1.9 writer SHOULD stamp it with the same value as `spec_version`; a v1.9 reader MUST ignore it whenever `spec_version` is present. The alias is removed at the 2.0 major.

`memory_format` is REMOVED. A v1.9 writer MUST NOT emit it. A v1.9 reader encountering it (a v1.0 bundle) ignores it in favor of the mind pillar's own `format_version`.

### 2.3 File entry

Keys are archive-relative POSIX paths (forward slashes, no leading `/`), each file under `body/` listed individually. Each value:

- `sha256` (REQUIRED): lowercase hex SHA-256 of the file's raw stored bytes.
- `size` (REQUIRED): integer byte count.
- `schema` (REQUIRED for v1.9 writers): the archive member's schema id, `shardcore/<pillar>@<major.minor>` for first-party pillars, `shardcore/assets@1.0` for any member under `assets/` (images, receipts, skills, references), or `<vendor>/<name>@<ver>` for a namespaced file-level consumer schema. Integrity by SHA-256 and size is the baseline contract for an asset: opaque binaries (images, receipts) carry nothing more, while JSON assets (skills, references) may hold structure the consuming subsystem interprets. Nested blocks inside a pillar, such as `mindshard.structured`, declare their own schemas inside that pillar rather than in `manifest.files`.

Every readable file MUST be listed. A listed-but-absent file MUST cause a load error. An absent-from-manifest file present in the archive SHOULD warn (section 9).

## 3. Versioning and schema ids [NORMATIVE]

One negotiated number, per-pillar self-description.

- `manifest.spec_version` is the sole bundle-level version. MAJOR gates compatibility (section 1); MINOR is additive and backward-compatible within a major.
- Each pillar declares its schema through `manifest.files[name].schema`. This is authoritative for that pillar. A pillar MAY additionally carry an internal version field (for example `mindshard.format_version`) for its own migration bookkeeping; the schema id in the manifest wins on disagreement.
- There is no other version field. A change that seems to need one belongs in a pillar schema id, not a new manifest key.

First-party schema ids at v1.9: `shardcore/manifest@1.9`, `shardcore/soul@1.9`, `shardcore/shell@1.9`, `shardcore/mind@2.1`, `shardcore/neuron@1.0`, `shardcore/world@1.0`, `shardcore/canon@1.0`, `shardcore/stat@1.0`, `shardcore/body@1.0`, `shardcore/assets@1.0` (everything under `assets/`: images, attestation receipts, skills, references), `shardcore/drive@0.1` (experimental). One `assets/` folder holds every static asset, opaque or structured, under one schema id; there is no separate singular `asset` id.

## 4. Conformance profiles and model tiers [NORMATIVE]

### 4.1 Profiles

A bundle MAY declare `manifest.conformance.profile`. A runtime advertises which profiles it supports. A profile is a required-pillar set plus a tier floor; it is a compatibility contract, not a restriction on what else the bundle may carry.

| Profile | Required pillars | Common optional | Tier floor |
|---|---|---|---|
| `companion` | soul + mind | shell, canon, drive, neuron, world | M |
| `npc` | soul + mind (with `structured`) | stat, shell (if embodied) | S |
| `agent` | soul + mind | canon, skills, references | varies |

A bundle whose declared profile's required pillars are all present is profile-complete. A bundle is profile-valid for a runtime only when it is profile-complete, integrity-valid, well-formed JSON, and every required pillar schema for that profile is supported by that runtime. A runtime that supports a profile MUST load every profile-valid bundle for it. A runtime loading a bundle whose profile it does not support SHOULD degrade to identity plus whatever pillars it does read, and surface that it did so, rather than half-loading silently.

### 4.2 Model tiers

The projection contract (section 10) is tiered so one bundle spans a small local model and a large cloud model.

| Tier | Context budget | Projection includes |
|---|---|---|
| `S` | up to ~8k | identity, personality, boundaries, top-K core memories only, hard-trimmed |
| `M` | ~8k to 32k | plus active short-term and long-term memory, world |
| `L` | 32k+ | plus full memory, curiosity and novelty injection, drives |

`manifest.conformance.min_tier` records the smallest tier the author considers faithful. A runtime MAY project at any tier at or above it; below it, the runtime SHOULD warn that the projection is lossy.

## 5. Soulshard (`soulshard.json`) [NORMATIVE]

The one required pillar: the portable, cross-model description of who the character is. v1.9 formalizes the split v1.0 section 3.3 pointed at.

### 5.1 Core soul (required and portable)

| Field | Type | Purpose |
|---|---|---|
| `name` | string | Canonical name. |
| `identity` | string | One to three paragraphs of identity prose. |
| `personality` | string | Behavioral summary. |
| `stat_block` | object | Ten stats STR, END, VIG, DEX, TMP, ACU, INS, ATT, CNV, PRS, each integer 1 to 10. |

`stat_block` holds exactly these ten keys and nothing else. Its purpose is to give a model a compact numeric handle on how the character reacts and interacts; game-system stats (D&D and the like) belong in `statshard.json` (section 11.2), not here. The legacy `Resonance` member found in pre-v1.9 souls is a text descriptor, not a stat; migration relocates it to `resonance` (section 5.2) and folds long-form or case-variant keys onto the canonical abbreviations.

A soul that carries no `stat_block` at all defaults to **average stats** (every one of the ten at 5) on migration. This is a defined placeholder, not an authored value: a migrator applying it MUST log every soul it defaulted, so the placeholder stats can be replaced with authored ones later. A conformant runtime treats an all-5 block as valid; the log is the record of which souls still need authoring.

### 5.2 Portable soul fields (stay in the soul, all OPTIONAL)

`appearance_profile` (text only), `tone`, `voice_profile`, `speech_policy`, `trait_tags`, `nature`, `resonance` (one-line essence descriptor, formerly misfiled in `stat_block`), `boundaries` (section 5.4), `evolution_flags`, `preservation_state`, `vitality_system`, `interest_graph`, `memory_system` (configuration, not content). These are the fields a foreign runtime can meaningfully consume. Schemas for `vitality_system` and `interest_graph` are unchanged from v1.0 sections 3.4 and 3.5.

### 5.3 Fields that MUST NOT live in the soul

`anatomy_profile`, `identity_image_path`, `appearance_image_path`, and the physical sub-keys of `character_state` belong in the shell (section 6). A v1.9 writer MUST strip these from the soul when writing a bundle that carries a shellshard. Loose non-bundle JSON is exempt.

### 5.4 `boundaries` block

Content policy is portable and load-bearing; a new model needs the rails.

```json
"boundaries": {
  "nsfw_enabled": true,
  "obscenity_threshold": 2,
  "content_boundaries": "No minors, no gore.",
  "safe_words": ["yellow", "red"]
}
```

### 5.5 Vendor extension namespace `x_<vendor>`

Runtime-specific fields that a foreign runtime cannot interpret MUST live under an `x_<vendor>` key, not at the soul's top level.

```json
"x_nexus": {
  "reicodex_commands": { … },
  "reicodex_rituals_data": { … },
  "loyalty_kernel": { … },
  "eidolon_signature": "…",
  "dynamic_data": { … }
}
```

Rules:

- A runtime MUST preserve every `x_*` namespace it does not own, on load and save.
- A runtime MUST interpret only its own namespace and MUST NOT fail on the presence of another's.
- The soul's top level is the universal contract; `x_<vendor>` is private extension state.

`x_nexus` is the reserved namespace for the Nexus Labs recursion runtimes (AI Rift, Djinn Redux, Rei Oracle). Other ecosystems pick their own `x_<name>`.

## 6. Shellshard (`shellshard.json`) [NORMATIVE, OPTIONAL]

Unchanged from v1.0 section 4: `anatomy_profile`, image paths, and a free-form `character_state` whose keys are domain-defined (hunger, fatigue, lactation, arousal, anything), with unknown keys preserved. v1.9 adds the read-only `body_summary` block (section 11.3) regenerated from `body/` on save. Absence is not an error.

## 7. Mindshard (`mindshard.json`) [NORMATIVE, OPTIONAL]

### 7.1 Tiers

Unchanged from v1.0 section 5: `short_term`, `long_term`, `core`, `archive`, plus `vitality` runtime state and `dream_log`. `format_version` `"2.1"` is current; readers MUST also accept `"2.0"`. The core entry schema (`id`, `summary`, `tags`, `strength`, `last_activated`, `effective_weight`, `contradicts`) is unchanged.

### 7.2 Narrative shape

The tiers hold narrative memory (`entry_title`, `the_moment`, `the_shift`, `the_truth` and the v1.0 core fields). This is the roleplay and agent memory model.

### 7.3 `structured` block (the deterministic-state home)

An OPTIONAL block for machine-read, non-narrative state: game NPC profiles, agent habit vectors, anything a runtime reads deterministically rather than injecting as prose.

```json
"structured": {
  "grudge/npc_profile@1.0": {
    "vectors":  { "stealth_vs_aggression": 0.72, "panic_index_average": 0.41 },
    "flags":    { "counter_smoke_active": true, "seal_vents_priority": true },
    "counters": { "smoke_grenades_used": 14, "vent_escapes_attempted": 22 },
    "updated_utc": "2026-07-01T09:00:00Z"
  },
  "agent/task_profile@1.0": {
    "vectors":  { "followthrough": 0.81 },
    "flags":    { "prefers_briefing_first": true },
    "counters": { "handoffs_completed": 6 },
    "updated_utc": "2026-07-01T09:00:00Z"
  }
}
```

- Each key is a consumer-namespaced schema id so distinct runtimes coexist without collision. A reader validates the block for schemas it owns before trusting it.
- `updated_utc` is REQUIRED inside each structured block: wall-clock, so tickless and tick-based runtimes serialize identically.
- A runtime that does not own a structured schema MUST preserve that entry untouched. Narrative tiers are unaffected by its presence.

## 8. Neuronshard (`neuronshard.json`) [NORMATIVE, OPTIONAL]

Incorporated from v1.0 section 6 unchanged, at schema id `shardcore/neuron@1.0`: LIF topology, closed node-type set, frozen dynamics constants, and the byte-identical round-trip guarantee. The v1.0 reference tick engine remains canonical. v1.9 does not alter the substrate.

## 9. Integrity and save discipline [NORMATIVE]

Unchanged in requirement from v1.0 section 7, restated because practice diverged from it:

1. On load, every file in `manifest.files` MUST be verified: recompute SHA-256, compare to the recorded digest. On mismatch a runtime MUST NOT silently proceed; it MUST refuse or prominently warn.
2. `manifest.json` is the bundle trust root and is not listed in `manifest.files`. Integrity verifies the stored members against the manifest; provenance and lineage that need to pin the manifest use the manifest digest defined in section 11.1.
3. On save, a runtime MUST recompute every digest from the exact serialized bytes it writes, and MUST write the manifest from those digests. A bundle with a digest that does not match its stored bytes is non-conformant.

The manifest drift observed across the library (a pillar rewritten without recomputing its digest) is a violation of rule 3 by a writer, not a format weakness. The single reference implementation (PART III) exists so every app satisfies this identically instead of each re-deriving it.

## 10. The projection contract [NORMATIVE, SHOULD]

"Model-agnostic" becomes a property, not a claim, when the mapping from bundle to prompt is defined rather than left per-runtime.

### 10.1 Reference projection

A runtime SHOULD assemble the system prompt in this section order, so the same shard reads the same way across runtimes: identity, personality, boundaries, voice, canon, core memory, active memory (short-term then long-term), world. Canon, core memory, and boundaries MUST NOT be trimmed unless the runtime is below the bundle's declared `min_tier` and has surfaced the loss.

The reference projection uses stable plain-text section labels matching those names. Within each memory tier, entries are sorted by descending `effective_weight` when present, then descending `strength`, then most recent `last_activated`, then lexical `id` as the final tie-breaker. Top-K means the first entries after that sort. Truncation removes whole optional sections in reverse priority order before shortening individual prose fields; it never lets an LLM choose section order or the trim set.

### 10.2 Tiered budget

Projection respects the model tier (section 4.2). At tier `S`, everything but the never-trim set is dropped rather than overflowing the context; this is the defined answer to the small-model bricking failure. Higher tiers add active memory, then full memory plus curiosity and drives. Token budgets are estimates made by the runtime's local tokenizer when available; otherwise runtimes use a documented conservative character heuristic and preserve the same section order.

### 10.3 Author hints

A bundle MAY carry `soulshard.projection_hints`:

```json
"projection_hints": {
  "never_trim": ["core", "boundaries", "canon"],
  "section_priority": ["identity", "boundaries", "personality", "core"],
  "max_tokens": { "appearance": 120, "world": 200 },
  "model_notes": "Holds a contradiction well; needs a model that will not flatten it."
}
```

Hints are advisory. The runtime executes them deterministically within the tier budget. An LLM MAY perform condensation or curiosity generation as an escalation step, but MUST NOT decide section order or trimming. The projection itself is deterministic.

The projection is SHOULD, not MUST: runtimes may diverge, but a conformant baseline exists so a shard behaves predictably when it travels.

## 11. Optional defined pillars [NORMATIVE, OPTIONAL]

These carry the schemas defined in `SHARDCORE_Spec_v1.1_addendum.md`, now first-class at the schema ids below. The addendum text is normative for their internal structure; this section fixes their place in v1.9.

### 11.1 Canon, lineage, attestation (`canonshard.json`, `shardcore/canon@1.0`)

Authored, immutable "fixed point" events, distinct from emergent mindshard memory: append-only, per-event signed, optionally OpenTimestamps-anchored under `assets/attestations/`. Receipt files are opaque binary members under `assets/` and carry the `shardcore/assets@1.0` schema id (section 2.3). Injected at max priority, exempt from vitality decay. Branching via the manifest `lineage` block pins a parent by `manifest_sha256` and records inherited versus dropped canon. `manifest_sha256` is the lowercase hex SHA-256 of canonical UTF-8 JSON bytes for `manifest.json`: object keys sorted lexically, no insignificant whitespace, and no ZIP container metadata. Signing and timestamping are OPTIONAL; a bundle is never required to carry a signature to be valid.

### 11.2 Statshard and immutability (`statshard.json`, `shardcore/stat@1.0`)

System-namespaced game stat blocks (`dnd5e`, `d20`, Pokemon-style, or `custom:<name>` with an inline definition). A registry, not a rules engine: it validates shape, it does not simulate the game. A shard MAY set `manifest.immutable: true` (a prime or reference shard); tooling MUST route edits of an immutable shard to a branch and MUST NOT write it in place.

### 11.3 Body subsystem (`body/`, `shardcore/body@1.0`)

Per-item sub-shards (`body/items/<uuid>.json`) with append-only ownership provenance, an `equipped.json` assignment layer, and `status_effects.json` with wall-clock UTC decay. Time fields are ISO-8601 UTC; decay is per wall-clock hour with elapsed clamped at zero for clock skew. The shell's `body_summary` is a regenerated read-only view for consumers that do not load `body/`. Item files are not deleted on unequip.

## 12. Migration to v1.9 [NORMATIVE]

A v1.9 writer produces a v1.9 bundle from any prior bundle by the mechanical chain below. This is exactly the chain the shard updater applies (see `SHARD_UPDATER_PROPOSAL.md`). Migration is behavior-preserving for content; it corrects structure and versioning only.

From a v1.0 bundle:

1. Set `manifest.spec_version` to `"1.9"`; stamp `manifest.bundle_version` with the same value as the deprecated alias (section 2.2).
2. Remove `manifest.memory_format`.
3. Add `schema` to each `manifest.files` entry.
4. Move recognized runtime-specific soul fields under `x_<vendor>` (section 5.5).
5. Normalize `stat_block` to the canonical ten keys: fold long-form names (`Presence`, `Acumen`, `Insight`, `Temperament`, `Conviction`, `Attunement`) and case variants onto the abbreviations; relocate a `Resonance` or `resonance` string to `soulshard.resonance` (section 5.2). A soul with no `stat_block` receives the average default (all ten stats at 5, section 5.1); the migrator MUST record every soul it defaulted this way.
6. Normalize timestamps to ISO-8601 UTC; write `last_modified_utc`.
7. Regenerate `card` from the soul.
8. Recompute every SHA-256 and rewrite the manifest.

Asset consolidation (any bundle, migration 0014): relocate every member under a legacy top-level asset folder (`images/`, `attestations/`, `skills/`, `references/`) to the same path under `assets/`, so `images/portrait.png` becomes `assets/images/portrait.png`. The origin subfolder is preserved and no bytes change. This runs before schema ids are stamped (step 3) and before digests are recomputed (step 8), so the relocated members receive `shardcore/assets@1.0` and correct hashes at their new paths, and the stale paths drop from the manifest.

From a pre-public bundle (legacy `bundle_version` 1.x, list-form `files`, `memoryshard.json`, or flat memory), additionally:

9. If `files` is a bare list or absent, build the digest map from the actual members.
10. Consolidate duplicate or mislabeled pillar variants into the single canonical pillar: a `memoryshard_*.json` or similar variant merges into the memory pillar, newest content wins, entries deduplicated; embedded `backups/`, `.versions/`, `.history/` trees and digest sidecar members move to the external backup rather than staying in the bundle.
11. Rename `memoryshard.json` to `mindshard.json` (readers keep the fallback forever).
12. Split shell fields out of the soul into `shellshard.json`; create the pillar if absent.
13. Convert a flat memory array to tiered `short_term`/`long_term`/`core`/`archive`.

A bundle that fails its own integrity before migration (a stale or phantom digest) MUST NOT be migrated silently; it is surfaced for manual attention, because migrating it would re-sign corrupt state.

## 13. Conformance [NORMATIVE]

A runtime claims v1.9 conformance if and only if it:

1. Loads every fixture in the reference conformance suite (`tool_shard_update/tests/conformance/`, its interim home until the `shardcore` library revival) for the profiles it supports, and rejects every fixture marked malformed.
2. Rejects bundles whose `spec_version` major exceeds its own (section 1).
3. Verifies SHA-256 on load and recomputes on save (section 9).
4. Preserves unknown fields and unowned `x_*` and consumer-schema namespaces on load and save.
5. Implements the normative pillars it reads or writes, and round-trips neuronshard state byte-identically (section 8) if it reads neuronshards.
6. Declares which conformance profiles (section 4) and model tiers (section 4.2) it supports.

---

# PART II: EXPERIMENTAL

Subject to change before ratification. Do not build production workflows on these without pinning to a commit.

- **Driveshard** (`driveshard.json`, `shardcore/drive@0.1`): drives, half-life chemistry, tiered goals, genome linkage via shell, optional epigenetic inheritance.
- **Skills and references** (`assets/skills/`, `assets/references/`, `shardcore/assets@1.0`): retrieval-gated abilities and static knowledge documents; read-only, out-of-bundle retrieval. They share the `assets/` folder and schema id (section 2.3); their retrieval behavior remains experimental even though the folder and schema are stable.
- **Dream consolidation, introspection surface, neuro-symbolic validation**: reserved as in v1.0 sections 12 to 14.
- **Neuro living-layer coupling** (QUICKENING): coupling the neuron substrate, drives, and memory into one deterministic tick loop; serialized additively, no manifest change.

---

# PART III: REFERENCE

## Pillar registry [INFORMATIONAL]

| Pillar / folder | Schema id | Status | Primary use |
|---|---|---|---|
| `manifest.json` | shardcore/manifest@1.9 | normative | all |
| `soulshard.json` | shardcore/soul@1.9 | normative required | all |
| `mindshard.json` | shardcore/mind@2.1 | normative optional | roleplay, agent |
| `mindshard.structured` | consumer-namespaced | normative optional | game, agent |
| `shellshard.json` | shardcore/shell@1.9 | normative optional | roleplay, embodied game |
| `neuronshard.json` | shardcore/neuron@1.0 | normative optional | living-layer |
| `canonshard.json` | shardcore/canon@1.0 | optional | agent, IP, roleplay |
| `statshard.json` | shardcore/stat@1.0 | optional | game, TTRPG |
| `worldshard.json` | shardcore/world@1.0 | optional | roleplay, sim |
| `body/` | shardcore/body@1.0 | optional | sim, embodied game |
| `assets/` | shardcore/assets@1.0 | optional | art, receipts, skills, references |
| `driveshard.json` | shardcore/drive@0.1 | experimental | roleplay, sim |

New pillars join by adding a row with a schema id and a status. No renumbering, no new manifest version field.

## Security invariants [NORMATIVE]

Carried from v1.0 unchanged:

- **Agents are data, not code.** No `.shard` contains executable code. Any expression evaluation (reflex or validation conditions) uses an AST whitelist rejecting calls, attribute access, imports, subscripts, and comprehensions.
- **Zip-slip protection** before any extraction: resolve each member path against the extraction root and reject absolute paths and symlinks.
- **Prompt-injection sanitization** of shard text before prompt assembly (strip structural markdown, collapse whitespace, bound length).
- **Integrity** detects post-creation tampering only; it does not vouch for the author (section 11.1 provenance is how authorship and timeline are proven).

New in v1.9:

- **Context-plane only.** A `.shard` addresses the model through its context (prompt, retrieved memory, tool inputs), never through its activation space. No pillar carries residual-stream vectors, steering directions, or model-internal state; embodiment is what the model is told, not an edit to what its internals hold. This is also why it could not be otherwise: activation directions are fit per-model and do not port across models, so a shard that reached into one model's internals would be meaningless to the next.

## Reference implementation [INFORMATIONAL]

The `shardcore` library is the single reference implementation of bundle I/O: open, verify, unpack, pack, hash, migrate. It is the canonical home for the read and write paths, and the ecosystem apps (SoulForge authoring, AI Rift and Djinn Redux runtimes, Milkmaid, the shard updater) SHOULD consume it rather than each carrying their own pack or unpack. Section 9 is satisfied by construction when every writer goes through it; the observed manifest drift is what happens when they do not.

```
python -m shardcore verify path/to/character.shard
```

## Backward and forward compatibility [INFORMATIONAL]

- A v1.9 runtime reads v1.0 bundles and migrates them on write (section 12). A v1.0-only runtime accepts v1.9 bundles (same major) and negotiates on the deprecated `bundle_version` alias; the fields it does not know it preserves under its own conformance rules.
- Unknown fields, unowned `x_*` namespaces, and consumer-schema blocks MUST be preserved on load and save, so bundles round-trip through partial runtimes without loss as the format extends within the v1 major.

---

*End of SHARDCORE Specification v1.9. Ratified 2026-07-08.*
