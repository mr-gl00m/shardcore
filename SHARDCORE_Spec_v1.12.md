# SHARDCORE Bundle Specification, v1.12

**Status:** RATIFIED by Cid on 2026-11-23, amended 2026-11-24 before publication. An additive minor over v1.11. The reference library and the schema registry implement it. Library 1.11.0 was never released; 1.12.0 is the first library release since 1.9.0.
**Date:** 2026-11-24 (ratified 2026-11-23; draft opened 2026-11-15)
**License:** Apache-2.0 (spec and reference implementation)
**Reference implementation:** the `shardcore` library (see PART III)
**Supersedes:** `SHARDCORE_Spec_v1.11.md`, which superseded `SHARDCORE_Spec_v1.10.md`, which superseded `SHARDCORE_Spec_v1.9.md` and `SHARDCORE_Spec_v1.0.md`.
**Self-contained:** this document is the whole format. The v1.0 sections earlier versions incorporated by reference (soul `vitality_system` and `interest_graph`, shell, mind, neuron) are folded into sections 5 to 8, and the v1.1 addendum's pillar internals (canon, lineage example, statshard, body) are PART IV. The addendum keeps only its rationale.
**Companion:** `SHARDCORE_FORMAT_EVOLUTION_PROPOSAL.md` (v1.9 rationale), `SHARDCORE_LINEAGE_OFFSPRING_RFC.md` (v1.10 rationale), `SHARDCORE_REVISION_CHAIN_RFC.md` and `SHARDCORE_PROJECTION_RFC.md` (v1.11 rationale), `SHARDCORE_NEURON_1_1_RFC.md` (v1.12 rationale), `SHARD_UPDATER_PROPOSAL.md` (the migration tool).

---

## Ratification record

**v1.12.** Ratified by Cid on 2026-11-23. Applied to the reference library, the schema registry and every ecosystem writer the same day (ecosystem check: 15 consumers pass). Applied to the live library the same day, straight from v1.10: 115 of 115 eligible bundles migrated, 0 failed (apply run `20261123T055902Z-f8c86bfc`, per-shard backups retained); one immutable bundle stays at v1.9 and one locked bundle at v1.10. Library 1.11.0 was never released; 1.12.0 is the first library release since 1.9.0. What it adds:

- Section 6.1: the `anatomy_profile` row named the list keys v1.11 retired. Corrected to the parts map (an erratum, no format change).
- Section 6.3: `parts[id].neural`, the weights that tie a body part to neural map nodes. The shell moves to `shardcore/shell@1.12`.
- Section 8.9: how a body stimulus becomes input to the neural substrate.
- Section 8.10: `shardcore/neuron@1.1`, a substrate whose edges are synapse counts, with `SENSE` nodes, pooled inhibition and an `experience` block. Reference: `shardcore/brain/`.
- Section 3: a neuronshard's schema id follows the version its document declares; new neuronshards default to `neuron@1.1`.

Amended on 2026-11-24, approved by Cid, before anyone outside had the text. It changes no bundle:

- Section 2.2: `manifest.min_writer`, the oldest version whose writers may save a bundle.
- Section 3: a save keeps the version and schema ids the bundle declares. Raising them is a separate act.
- Section 11.4.1: a writer that saves a bundle without a `shard_id` mints the derived one.
- Section 11.5.1: the revision chain applies from 1.11. A bundle declaring an older version is given none.
- Section 12: migration is asked for, and to an older version stamps that version's schema ids.
- Section 13 and the compatibility section.

Decisions taken at ratification:

- [x] **Schema ids.** `parts[id].neural` moves the shell to `shardcore/shell@1.12`. Migration 0009 restamps `shell@1.10` and older.
- [x] **`SENSE` node kind.** Ratified as proposed on 2026-11-15 (section 8.10.2): a kind a tool may extend, with what a part comes to mean learned in `experience`.
- [x] **Propagation under the frozen 1.0 constants.** `neuron@1.0` stays exactly as published: text, constants and `shardcore/neuron.py`. Its measured behavior (activity does not spread past directly driven nodes) is documented in section 8 as a known property. `neuron@1.1` is the substrate that propagates.
- [x] **Default id.** New neuronshards default to `shardcore/neuron@1.1`. `neuron@1.0` stays readable and is never converted, since no faithful conversion exists.
- [x] **Where `experience` lives.** Inside the neuron pillar, so what she is wired for and what she has learned travel in one file a runtime either runs or ignores.
- [x] **RNG state encoding.** PCG64, named; its two 128-bit integers are decimal strings (section 8.10.4).
- [x] **The clock.** 0.1 ms.
- [x] **Round trip.** Split (section 8.10.7): every implementation MUST round-trip a document byte for byte when it loads and saves without stepping. Stepping MUST reproduce the reference's golden behaviors; bit-exact dynamics is an optional claim an implementation earns by matching the reference traces.
- [x] **Memory write-back.** The runtime's call; the spec says SHOULD file in `short_term` with the source recorded (section 8.10.8).
- [x] **Keyword perception.** The reference word lists are informative; the normative interface takes senses, cues and frames directly (section 8.10.9).
- [x] **Version strings.** Moved to 1.12. No new migration: the existing chain (spec stamp, 0009 schema ids, 0016 revision) carries a v1.11 bundle to v1.12.

**v1.11.** Ratified by Cid on 2026-11-01 from `SHARDCORE_REVISION_CHAIN_RFC.md` (the revision chain and merge, section 11.5; the anatomy parts map, section 6.3) and `SHARDCORE_PROJECTION_RFC.md` (the reference projection, section 10.4). Applied to the reference library and every ecosystem writer the same day. Library 1.11.0 was never released, and v1.12 superseded it before the live library moved off v1.10.

**v1.10.** Ratified by Cid on 2026-10-16 from `SHARDCORE_LINEAGE_OFFSPRING_RFC.md`: a stable `shard_id`, offspring lineage, and normative numeric version comparison (section 11.4, section 3). Applied to the reference library the same day. The live library is still at v1.9 until a separate migration pass.

**v1.9.** Ratified by Cid on 2026-07-08 and applied to the live library the same day: 87/87 bundles migrated to v1.9, 0 failed, all verified `current` (apply run `20260708T090625Z-6a385429`, per-shard backups retained). The three decisions below are folded into the normative text; kept here as provenance.

- [x] **Asset schema id + folder (§1, §2.3, §12).** RESOLVED: all static assets (images, OpenTimestamps receipts, skills, references) live under one top-level `assets/` folder and carry one schema id, `shardcore/assets@1.0`. Origin subfolders (`assets/images/`, `assets/attestations/`, `assets/skills/`, `assets/references/`) are kept for clarity but not required. The earlier singular/plural split (`asset@1.0` vs `assets@1.0`) is collapsed and the singular is retired. Migration 0014 relocates any legacy top-level asset folder under `assets/`.
- [x] **Stat-less soul on migration (§5.1, §12).** RESOLVED: a soul with no `stat_block` defaults to average stats (every stat 5) on migration, and the migrator MUST log every soul it defaulted so the placeholders can be authored later. Written into §5.1 and §12 step 5.
- [x] **`preservation_state` stays portable (§5.2).** Confirmed: it is a portable soul field, not runtime-specific, so it does NOT move under `x_nexus`. This was a false positive in the migrator's allowlist, since corrected. No text change needed; listed here only to record the decision. Verify §5.2 still names it.

---

## Abstract

A `.shard` is a portable, verifiable bundle describing an evolving digital entity: a **soul** (portable identity, personality, stats), a **shell** (body, anatomy, image refs), a **mind** (tiered memory), and a **neural substrate** (Neuronshard) giving continuous internal state between interactions, plus optional pillars for canon, stats, drives, equipment, and world.

v1.9 reshaped the v1 line. It fixed how the format versions itself, made the portable soul honestly portable, and wrote down the two contracts v1.0 left implicit: how a bundle projects into a prompt across models, and which subset of pillars a given use case needs. v1.10 adds identity and offspring: a `shard_id` that survives every save, and a lineage shape for new individuals produced from one or more parents (breeding, cloning, fusion). v1.11 orders and reconciles copies: a revision chain that tells a newer copy from an older or a diverged one, and a merge for diverged copies; it also fixes the shell's anatomy as a parts map and ships the projection as reference code with golden texts. v1.12 adds a neural substrate that propagates and learns (`neuron@1.1`) and ties body parts to it. The 2.0 major stays reserved for a change that genuinely breaks foreign readers.

---

## Changes from v1.11

All additive. A v1.11 bundle is valid as it is, and stays a v1.11 bundle until someone upgrades it (section 3).

1. **`shardcore/neuron@1.1`** (section 8.10). Edges are synapse counts at 0.275 mV, so activity propagates. Sixteen `SENSE` nodes, eight `COND` nodes, pooled inhibition through two interneurons, and an `experience` block for what cues have come to mean. New neuronshards default to it; `neuron@1.0` is unchanged and still read.
2. **Body stimulus** (section 8.9). A part's `parts[id].neural` weights become sustained synaptic input to the substrate (section 6.3, `shardcore/shell@1.12`).
3. **Schema id by declared version** (section 3). A neuronshard's schema id follows its document's `version`.
4. **Erratum** (section 6.1). The shell field table names the parts map, not the retired lists.
5. **A save keeps the version** (section 3). Raising a bundle's version is a separate act, and the earlier file is kept. v1.11 and earlier writers stamped the version they implemented.
6. **`manifest.min_writer`** (section 2.2). A writer older than a bundle may save it when the bundle says so.

## Changes from v1.10

All additive. A v1.10 bundle is a valid v1.11 bundle; it only lacks the optional fields below, and migrating it starts its revision chain.

1. **`manifest.revision`** (section 11.5). Every write records the state it replaced (`prior`) and up to sixteen states before it (`history`), and counts the writes (`n`). Two copies of one identity now compare as same, newer, older, diverged, or unknown.
2. **Merge** (section 11.5.3). Two diverged copies merge three-way against the state both descend from, unit by owner namespace. The base comes from wherever earlier states are kept; the reference keeps every written state in the backup vault.
3. **Anatomy parts map** (section 6.3, `shardcore/shell@1.10`). `anatomy_profile.parts` is a map keyed by part id, the ids `body/` already names. The editor list shape migrates to it (migration 0017).
4. **Reference projection in code** (section 10.4). `shardcore/projection.py` is the reference, with golden texts in the conformance suite and a GDScript port held to them. Shard-text sanitizing is part of it.
5. **Self-contained text.** v1.0 and addendum material this spec used to incorporate by reference is now in this document (sections 5.6 to 8.8 and PART IV).
6. **Stale schema ids are drift.** A listed member whose schema id is behind the registry (a shell still declaring `shell@1.9`) is outdated and restamped by migration 0009. Since v1.12 an id is behind only when it is older than the bundle's declared version gives it.

## Changes from v1.9

All additive. A v1.9 bundle is a valid v1.10 bundle; it only lacks the optional fields below.

1. **`manifest.shard_id`** (section 11.4). An optional, stable identity for the character or creature a bundle carries, minted once and preserved across every save. It gives lineage references something to resolve: a hash pins one state, an id names who.
2. **Offspring lineage** (section 11.4). `lineage.relationship` gains `"offspring"`, recorded as a `parents` array of hash-pinned entries with a `role` each. Offspring carry parents only (no ancestry tree) and inherit no canon.
3. **Lineage defined in this document.** Section 11.4 states the full lineage contract for both branches and offspring; addendum section 3.1 remains the worked branch example.
4. **Numeric version comparison** (section 3). `spec_version` and schema-id versions compare per component as integers; `1.10` is newer than `1.9`.
5. **Migration** (section 12). A v1.9 bundle moves to v1.10 by restamping `spec_version` and minting a deterministic `shard_id`.
6. **Conformance suite location** (section 13). The suite lives in the `shardcore` project at `tests/conformance/`.

## Changes from v1.0 (introduced in v1.9)

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

Sections are tagged **[NORMATIVE]**, **[EXPERIMENTAL]** (present as design or partial impl, subject to change), or **[INFORMATIONAL]**. A runtime claiming v1.12 conformance MUST implement every [NORMATIVE] section that applies to the pillars it reads or writes.

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
  "spec_version": "1.12",
  "bundle_version": "1.12",
  "created": "2026-07-04T00:00:00Z",
  "last_modified_utc": "2026-07-04T00:00:00Z",
  "shard_name": "Aria",
  "shard_id": "3f6c1a52-8d4e-4b7a-9c21-5e0f7d93a6b8",
  "immutable": false,
  "card": {
    "name": "Aria", "title": "Companion", "role": "General-purpose",
    "core_essence": "Curious, careful, quietly stubborn.",
    "tags": ["curious", "careful", "stubborn"]
  },
  "conformance": { "profile": "companion", "min_tier": "M" },
  "revision": { "n": 7, "prior": "5be1…", "history": ["5be1…", "0c9a…", "…"] },
  "files": {
    "soulshard.json":   { "schema": "shardcore/soul@1.9",   "sha256": "…", "size": 4096 },
    "shellshard.json":  { "schema": "shardcore/shell@1.10", "sha256": "…", "size": 2048 },
    "mindshard.json":   { "schema": "shardcore/mind@2.1",   "sha256": "…", "size": 1024 },
    "neuronshard.json": { "schema": "shardcore/neuron@1.0", "sha256": "…", "size": 55760 }
  },
  "session_counter": 42
}
```

### 2.1 Required fields

| Field | Type | Notes |
|---|---|---|
| `spec_version` | string | `MAJOR.MINOR`. This document defines `"1.12"`. The only version negotiated on. |
| `shard_name` | string | SHOULD match the archive filename stem. |
| `files` | object | Map from archive-relative POSIX path to a file entry (section 2.3). |

### 2.2 Optional fields

`created`, `last_modified_utc` (ISO-8601 UTC, `Z` suffix), `shard_id` (section 11.4), `revision` (section 11.5), `card`, `conformance` (section 4), `immutable` (section 11.2), `min_writer` (below), `session_counter`, `lineage` (section 11.4), `attestation` (section 11.1), `has_travel_context`.

`min_writer` is a string, `<major>.<minor>`: the oldest spec version whose writers can save this bundle without breaking it. Absent, it equals `spec_version`. The first meaningful value is 1.12, since no earlier writer reads the field.

- A minor raises the floor only when a writer that preserves everything it does not know would still break the bundle. Each minor's record says whether it does and why.
- A writer stamps the highest of the value already present and the floor of each feature the bundle holds. A merge takes the higher of its sides.
- A writer older than `spec_version` and at or above `min_writer` MAY save the bundle. It MUST keep `spec_version`, `bundle_version`, `min_writer` and each member's declared schema id, and preserve every member, field and manifest key it does not know.
- A writer below `min_writer` MUST refuse, whatever `spec_version` says. A writer older than `spec_version` MUST refuse when there is no valid `min_writer`. A higher MAJOR is always refused.
- `spec_version` below `min_writer` means a writer that does not know this rule saved the bundle. A reader loads it, and a diagnosing tool reports it and does not migrate it.

`bundle_version` is retained as a deprecated alias so v1.0 readers can keep negotiating: a writer SHOULD stamp it with the same value as `spec_version`; a reader MUST ignore it whenever `spec_version` is present. The alias is removed at the 2.0 major.

`memory_format` is REMOVED (since v1.9). A writer MUST NOT emit it. A reader encountering it (a v1.0 bundle) ignores it in favor of the mind pillar's own `format_version`.

### 2.3 File entry

Keys are archive-relative POSIX paths (forward slashes, no leading `/`), each file under `body/` listed individually. Each value:

- `sha256` (REQUIRED): lowercase hex SHA-256 of the file's raw stored bytes.
- `size` (REQUIRED): integer byte count.
- `schema` (REQUIRED for v1.9 and later writers): the archive member's schema id, `shardcore/<pillar>@<major.minor>` for first-party pillars, `shardcore/assets@1.0` for any member under `assets/` (images, receipts, skills, references), or `<vendor>/<name>@<ver>` for a namespaced file-level consumer schema. Integrity by SHA-256 and size is the baseline contract for an asset: opaque binaries (images, receipts) carry nothing more, while JSON assets (skills, references) may hold structure the consuming subsystem interprets. Nested blocks inside a pillar, such as `mindshard.structured`, declare their own schemas inside that pillar rather than in `manifest.files`.

Every readable file MUST be listed. A listed-but-absent file MUST cause a load error. An absent-from-manifest file present in the archive SHOULD warn (section 9).

## 3. Versioning and schema ids [NORMATIVE]

One negotiated number, per-pillar self-description.

- `manifest.spec_version` is the sole bundle-level version. MAJOR gates compatibility (section 1); MINOR is additive and backward-compatible within a major.
- Versions compare per component as integers: split on `.`, compare MAJOR, then MINOR. `1.10` is newer than `1.9`. A reader MUST NOT compare versions as strings (where `"1.10"` sorts before `"1.9"`) or as decimal numbers (where `1.10` equals `1.1`). The same rule applies to the `<major.minor>` part of schema ids.
- A save keeps the `spec_version` and schema ids the bundle declares, and writes by that version's rules. A bundle at an older MINOR of the same major is valid and stays at it. A member the save adds takes the schema id of the declared version. A neuronshard's id follows its document (section 8).
- Raising the version is a separate act: a person asks for it or an app's developer turns it on, and the earlier file is kept. A writer handed content the declared version cannot hold MUST leave it out or ask; it MUST NOT raise the version on its own.
- A new bundle is stamped with the lowest version that covers what it holds, and no lower than 1.12. A branch keeps its parent's version. A merge takes the higher of its two sides. A bundle older than 1.9 has no form a current writer produces, so a save upgrades it.
- Each pillar declares its schema through `manifest.files[name].schema`. This is authoritative for that pillar. A pillar MAY additionally carry an internal version field (for example `mindshard.format_version`) for its own migration bookkeeping; the schema id in the manifest wins on disagreement.
- `min_writer` (section 2.2) is the only other version field, because a floor covers the whole bundle and no pillar id can hold it. Any other change that seems to need one belongs in a pillar schema id.

First-party schema ids at v1.12: `shardcore/manifest@1.12`, `shardcore/soul@1.9`, `shardcore/shell@1.12`, `shardcore/mind@2.1`, `shardcore/neuron@1.1` (the default for new neuronshards; `shardcore/neuron@1.0` stays valid, section 8), `shardcore/world@1.0`, `shardcore/canon@1.0`, `shardcore/stat@1.0`, `shardcore/body@1.0`, `shardcore/assets@1.0` (everything under `assets/`: images, attestation receipts, skills, references), `shardcore/drive@0.1` (experimental). One `assets/` folder holds every static asset, opaque or structured, under one schema id; there is no separate singular `asset` id.

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
| `S` | up to ~8k | identity, personality, boundaries, canon, top 8 core memories, hard-trimmed |
| `M` | ~8k to 32k | plus voice, the top 12 short-term and long-term memories, world |
| `L` | 32k+ | plus every memory entry |

Curiosity and novelty injection and drive state are runtime escalations layered on top of the projection (section 10.3), not part of the reference text.

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

`appearance_profile` (text only), `tone`, `voice_profile`, `speech_policy`, `trait_tags`, `nature`, `resonance` (one-line essence descriptor, formerly misfiled in `stat_block`), `boundaries` (section 5.4), `evolution_flags`, `preservation_state`, `vitality_system`, `interest_graph`, `memory_system` (configuration, not content). These are the fields a foreign runtime can meaningfully consume. `vitality_system` and `interest_graph` are defined in sections 5.6 and 5.7.

### 5.3 Fields that MUST NOT live in the soul

`anatomy_profile`, `identity_image_path`, `appearance_image_path`, and the physical sub-keys of `character_state` belong in the shell (section 6). A writer MUST strip these from the soul when writing a bundle that carries a shellshard. Loose non-bundle JSON is exempt.

### 5.4 `boundaries` block

Content policy is portable and essential; a new model needs the rails.

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

### 5.6 `vitality_system` [NORMATIVE]

Configuration for anti-collapse mechanics. Runtime state lives in the
mindshard (§7.7).

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

### 5.7 `interest_graph` [NORMATIVE]

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

## 6. Shellshard (`shellshard.json`) [NORMATIVE, OPTIONAL]

Schema id `shardcore/shell@1.10`: `anatomy_profile` (section 6.3), image paths, a free-form `character_state` whose keys are domain-defined (hunger, fatigue, lactation, arousal, anything) with unknown keys preserved, and the read-only `body_summary` block (section 11.3) regenerated from `body/` on save. Absence is not an error.

### 6.1 Fields

| Field                             | Type   | Notes |
|-----------------------------------|--------|-------|
| `anatomy_profile`              | object | Body-part system: `template` and the `parts` map (section 6.3). (v1.12 erratum: v1.11 still listed the retired `external_parts` and `internal_parts` list keys here.) |
| `identity_image_path`          | string | Local-path reference (OPTIONAL). |
| `appearance_image_path`        | string | Local-path reference (OPTIONAL). |
| `character_state.hunger_level` | float  | `0.0`-`1.0`; example of a tickable physical state. |
| `character_state.fatigue`      | float  | `0.0`-`1.0`; example of an accumulating state. |
| `character_state.injury_status`| object | Free-form per-region injury record; example of a structured state. |

The `character_state` examples above are illustrative, not normative.
Runtimes MAY define their own `character_state` keys for whatever physical
or biological systems their domain requires (hunger, fatigue, lactation,
arousal, energy, anything else). Generic tooling MUST preserve unknown
keys on load/save. Domain-specific extensions SHOULD be documented in a
sidecar spec rather than added to this document.

### 6.2 Absence

A bundle MAY omit `shellshard.json` entirely. Loaders MUST NOT treat
absence as an error.

### 6.3 `anatomy_profile`: the parts map

`anatomy_profile` holds the body's parts as a map keyed by part id. These keys are what `body/equipped.json` `part_id` and item `slot` values name (PART IV, A.5).

```json
"anatomy_profile": {
  "template": "humanoid",
  "parts": {
    "breast_l": {
      "id": "breast_l",
      "name": "Left Breast",
      "part_type": "organ",
      "tags": ["soft", "external", "lactating"],
      "size": "DDD",
      "capacity_ml": 160.0,
      "fluid_type": "Milk",
      "sensitivity": 81.0
    }
  }
}
```

| Field | Notes |
|---|---|
| `parts` | REQUIRED when `anatomy_profile` is present: an object keyed by part id. An anatomy with no parts is `{}`. |
| `parts[id].id` | OPTIONAL. When present it MUST equal the key. |
| `parts[id].name` | REQUIRED string. |
| `parts[id].part_type` | OPTIONAL string. RECOMMENDED values: `core`, `limb`, `organ`, `appendage`, `bone`. |
| `parts[id].tags` | OPTIONAL array of strings, unordered. A part inside the body carries `internal`; that tag is how an editor splits external from internal parts. |
| `parts[id].size` | OPTIONAL string, the portable size. RECOMMENDED values: for breasts a cup on the US ladder (`A`, `B`, `C`, `D`, `DD`, which is the same cup as `E`, `DDD`); for other parts `Flat`, `Tiny`, `Small`, `Medium`, `Large`, `Huge`, `Massive`, `Gigantic`, `Hyper`. Other strings are valid. |
| `parts[id].capacity_ml`, `fluid_type`, `sensitivity` (0 to 100), `accessories` | OPTIONAL. |
| `parts[id].neural` | OPTIONAL object, added in v1.12 (`shell@1.12`). Maps a neural map node label (section 8.3) to a number: the sustained drive, in mV, that stimulating this part puts on that node at full intensity and `sensitivity` 100. Negative values hold the node down. Section 8.9 defines how it is applied. |
| `template` | OPTIONAL string naming the body plan the parts started from. |

Every other `anatomy_profile` key (`body_type`, `height`, `measurements`, and the like) is descriptive and preserved. `size` is the intent and `capacity_ml` a mechanic: a runtime that derives capacity from size recomputes it when `size` changes; one that does not keeps `capacity_ml` as written. Any other key on a part (`health`, `pain`, `current_stored_ml`, `layers`) is runtime state, preserved by every runtime that does not own it.

Before v1.11 editors stored parts as lists (`external_parts`, `internal_parts`, a `modifiers` copy of both, a `show_internal` display toggle). A writer MUST write the map; migration 0017 (section 12) folds the lists into it.

## 7. Mindshard (`mindshard.json`) [NORMATIVE, OPTIONAL]

### 7.1 Tiers

`short_term`, `long_term`, `core`, `archive`, plus `vitality` runtime state and `dream_log` (sections 7.4 to 7.8). `format_version` `"2.1"` is current; readers MUST also accept `"2.0"`. The core entry schema (`id`, `summary`, `tags`, `strength`, `last_activated`, `effective_weight`, `contradicts`) is section 7.6.

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

### 7.4 Top-level schema

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

### 7.5 Memory tiers

- **`short_term`**, ephemeral working memory. Bounded ring; oldest evicted.
- **`long_term`**, consolidated sessions; persistent but decayable.
- **`core`**, identity-defining engrams; promoted from long_term via dream.
- **`archive`**, frozen history; never retrieved directly but minable by dream.

### 7.6 `core` entry schema (v2.1)

| Field             | Type         | Default | Purpose |
|-------------------|--------------|---------|---------|
| `id`              | string       | -       | Stable UUID. |
| `summary`         | string       | -       | Human-readable description. |
| `tags`            | list[string] | `[]`    | Retrieval tags. |
| `strength`        | float        | `1.0`   | Base weight. |
| `last_activated`  | int          | `0`     | Session number of last tag-match retrieval. |
| `effective_weight`| float        | `1.0`   | `strength * decay_rate^(session - last_activated)`. |
| `contradicts`     | list[string] | `[]`    | IDs of cores this is in tension with. |

Runtimes that don't understand `effective_weight` MAY fall back to
`strength`; the split is deliberately backward-compatible with v2.0.

### 7.7 `vitality` block (runtime state)

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

### 7.8 `dream_log`

Capped list (~20 entries) of human-readable dream traces produced by the
dream consolidation pass (PART II). Absent in mindshards that have not been
dreamed yet.

## 8. Neuronshard (`neuronshard.json`) [NORMATIVE, OPTIONAL]

Schema id `shardcore/neuron@1.0`, unchanged since v1.0: LIF topology, closed node-type set, frozen dynamics constants, and the byte-identical round-trip guarantee. The reference tick engine is `shardcore/neuron.py`. Section 8.10 adds `shardcore/neuron@1.1` beside it, the default for new neuronshards since v1.12; a document's `version` says which it is.

**A known property of 1.0, documented at v1.12.** Under the section 8.6 constants and the reference topology's edge weights, a node driven to 38 Hz moves its targets by about 0.15 mV against a 7 mV threshold, and no node without direct drive or noise ever spikes; `W_MAX` (2.0 mV) caps any edge. Downstream response in 1.0 is sub-threshold depolarization. 1.0 stays frozen as published so existing documents keep their meaning; `neuron@1.1` is the substrate that propagates.

The Neuronshard gives a shard **continuous internal state** between
interactions. It declares a topology of LIF (Leaky Integrate-and-Fire)
neurons, weighted excitatory/inhibitory edges, and the current membrane
state of each neuron.

> **Why it's normative:** The schema is frozen at v1.0 so third-party
> runtimes can rely on it. The reference tick engine in `shardcore/neuron.py`
> is the canonical implementation; alternate implementations MUST produce
> byte-identical state round-trips against that engine's serializer.

### 8.1 Schema

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

### 8.2 Node types (closed set in v1.0)

| `type`              | Purpose |
|---------------------|---------|
| `IDENTITY_ANCHOR`   | Stable identity trait (one per stat, plus symbolic anchors). |
| `MEMORY_CORE`       | Bound to a `mindshard.core` entry. |
| `MEMORY_LTM`        | Bound to a `mindshard.long_term` slot. |
| `MEMORY_STM`        | Bound to a `mindshard.short_term` slot. |
| `EMOTION`           | One of Joy, Fear, Sadness, Curiosity, Anger, Trust, Disgust, Surprise. |
| `DRIVE`             | Bound to a driveshard entry (PART II). |
| `IMPULSE`           | Behavioral output node (Speak, Withdraw, Approach, etc.). |

Future versions MAY extend this set. v1.0 loaders MUST reject unknown types
with a clear error.

### 8.3 Node fields

| Field            | Type  | Required | Purpose |
|------------------|-------|----------|---------|
| `id`             | int   | yes      | Index into state vectors; MUST equal the node's position in `nodes`. |
| `label`          | str   | yes      | Human-readable label. |
| `type`           | str   | yes      | One of §8.2. |
| `x`, `y`         | float | no       | Visualization coordinates. `0.0, 0.0` if absent. |
| `receives_noise` | bool  | no       | If true, the node receives Poisson input during ticks. Defaults `false`. |

### 8.4 Edge fields

| Field    | Type  | Required | Purpose |
|----------|-------|----------|---------|
| `src`    | int   | yes      | Source node id. |
| `dst`    | int   | yes      | Destination node id. |
| `weight` | float | yes      | mV delta applied to `dst.g` when `src` fires. Positive = excitatory, negative = inhibitory. |

Edges MUST NOT reference node ids outside the topology.

### 8.5 State vectors

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

### 8.6 Dynamics constants

The v1.0 reference engine fixes the following constants (derived from the
Drosophila connectome model cited in the research grounding of the v1.0 release (`SHARDCORE_Spec_v1.0.md`, section 16)):

| Constant       | Value     | Purpose |
|----------------|-----------|---------|
| `V_REST`       | -52.0 mV  | Resting potential. |
| `V_THRESHOLD`  | -45.0 mV  | Spike threshold. |
| `V_RESET`      | -52.0 mV  | Post-spike reset. |
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

### 8.7 Runtime semantics

See `shardcore/neuron.py`. In summary:

1. At each tick (default `dt = 0.5 ms`):
   - Inject Poisson noise on nodes with `receives_noise=true`.
   - Euler-integrate membrane: `dv = (V_REST − v + g) / TAU_MEMBRANE · dt`.
   - Decay synaptic input: `dg = −g / TAU_SYNAPSE · dt`.
   - Detect spikes (`v > V_THRESHOLD`), reset, schedule delayed outputs.
2. Hebbian updates (OPTIONAL at runtime): strengthen edges whose source
   fired inside the last `HEBBIAN_WINDOW = 20 ms` when the destination fires.

### 8.8 Persistence guarantees

A v1.0 Neuronshard MUST round-trip exactly: for any `(graph, network)`,
`runtime_from_neuronshard(neuronshard_from_runtime(graph, network))` MUST
yield identical `v, g, refractory, fire_time, total_spikes, W_learned,
sim_time`, and structurally identical topology.

The reference implementation's test suite
(`tests/unit/test_neuron.py::test_neuronshard_roundtrip_preserves_state`)
is the conformance check.

### 8.9 Body stimulus (v1.12)

A shell part reaches the substrate through its `neural` weights (section 6.3). The v1.0 node type set has no sensory type, so a sensation the reference topology lacks (arousal, pain, soothing) is carried by a `DRIVE` node with that label, wired to the emotion and impulse nodes it moves.

A runtime that stimulates part `p` at intensity `i` (0 to 1) computes, for each `label: w` in `p.neural`:

```
drive(label) = w * (sensitivity / 100) * i
```

- `sensitivity` is the part's own (section 6.3). A part with none recorded uses 50.
- A label matches the first node carrying it. A label no node carries contributes nothing; a tool SHOULD surface it to the author instead of adding a node silently.
- The drive is applied as external synaptic input for as long as the stimulus lasts: each step of size `dt` adds `drive * dt / TAU_SYNAPSE` to the node's `g`, which settles `g` at `drive`. A node at rest starts to spike once its drive exceeds `V_THRESHOLD - V_REST` (7.0 mV).
- A stimulus is input, not state. It is never written into `neuronshard.json`; only the state the network reaches is.

A runtime that does not run the substrate ignores `neural` and preserves it.

### 8.10 `shardcore/neuron@1.1` (v1.12)

A second neuronshard version, for a substrate that propagates and learns. Sections 8.1 to 8.8 describe `neuron@1.0` and are unchanged. A document declares which it is by its `version`, and the manifest schema id follows it (`shardcore/neuron@1.0` or `shardcore/neuron@1.1`). The reference is `shardcore/brain/`.

#### 8.10.1 Schema

```json
{
  "version": "1.1",
  "nodes": [
    { "id": 0, "label": "STR", "kind": "ANCHOR", "tonic_hz": 30.0, "ref": "", "weight": 1.0, "x": 315.0, "y": 0.0 }
  ],
  "edges": [
    { "src": 0, "dst": 14, "syn": 16.0, "plastic": false }
  ],
  "experience": { "assoc": {}, "met": {}, "grudge": {}, "exposure": {}, "distrust": 0.0,
                  "habit": {}, "mood": {}, "scar": {}, "told": {} },
  "state": { "step": 0, "slot": 0, "v": [], "g": [], "ready_step": [], "last_fire_step": [],
             "total_spikes": [], "delay": [], "rng": {} }
}
```

`experience` and `state` are OPTIONAL. Without `state` the network loads at rest. Without `experience` nothing has been learned. A tool that adds or removes a node MUST drop `state`.

#### 8.10.2 Node kinds

| `kind` | Purpose |
|---|---|
| `ANCHOR` | One per soul stat. `tonic_hz` is its standing input, the stat times 6. |
| `SENSE` | Something that can happen to her or be felt from inside: Threat, Challenge, Kindness, Distress, Food, Foul, Sudden, Pain, Pleasure, Novelty, Familiar, Fatigue, Unease, Lonely, Relief, Craving. A tool MAY add more. |
| `COND` | One per emotion. Carries what the things present have come to mean, and her mood. |
| `MEMORY` | One per mind entry whose text carries feeling. `ref` is `<tier>:<index>` into the mind; `weight` is the entry's. |
| `EMOTION` | Joy, Fear, Sadness, Curiosity, Anger, Trust, Disgust, Surprise. |
| `IMPULSE` | Speak, Withdraw, Approach, Create, Fight, Flee, Observe, Comfort. The impulse with the most spikes in a moment is what she does. |
| `INTERNEURON` | `emotion_pool` and `impulse_pool`. The only inhibitory kind: every member of a pool excites its interneuron, which inhibits every member. |

A (`kind`, `label`) pair MUST be unique. The sixteen senses, eight emotions, eight `COND` nodes and eight impulses above MUST be present. `id` MUST equal the node's position. `x` and `y` are where a tool draws the node and have no effect.

#### 8.10.3 Edges

`syn` is a synapse count, 0 to 200. When `src` fires, `dst.g` moves by `syn * 0.275 mV` after the synaptic delay, upward unless `src` is an `INTERNEURON`. `plastic` edges change with use: on a spike of `dst`, a plastic input that fired in the last 20 ms gains 0.02 synapses and one that did not loses 0.01, held between 1 and 200.

#### 8.10.4 Dynamics

The membrane equations and the constants of section 8.6 other than `HEBBIAN_ETA` and `W_MAX` apply, on a 0.1 ms step. Input to a node is a Poisson rate; each event adds 68.75 mV to its membrane, and a node with a nonzero rate has no refractory period. Sustained drive in mV (section 8.9) is added to `g` as that section defines. `state.rng` is the generator's state, so that state, input and step count give exactly one next state. The generator is PCG64, and its state is `{"bit_generator": "PCG64", "state": {"state": "<decimal>", "inc": "<decimal>"}, "has_uint32": 0 or 1, "uinteger": <integer>}`. The two 128-bit values MUST be decimal strings, because many JSON readers hold numbers as 64-bit floats. A reader MAY accept JSON integers there from documents written before v1.12.

A probe is a moment run and taken back: a runtime MUST leave `state`, `edges` and `experience` as they were.

#### 8.10.5 `experience`

Tables keyed by cue. A cue is a thing present in a moment (a word stem, or an identity the runtime names such as `actor:dax` or `part:toes_l`) or a pair of them joined by `+`.

| Key | Holds |
|---|---|
| `assoc` | cue to emotion to `[strength, peak]`, each 0 to 1: what the cue has come to mean. |
| `met` | cue to the number of eventful moments it has been part of. |
| `grudge` | cue to `[betrayals, making_up]`. |
| `exposure` | cue to how often it has been present, for habituation. |
| `scar` | cue to 0 to 1: how traumatic the worst moment with it was. |
| `habit` | cue to `[dependence, hours_since]`. |
| `distrust` | 0 to 1: how she expects people to treat her. |
| `mood` | emotion to 0 to 1. |
| `told` | the things in a strong moment to how many times it has happened. |

A runtime that does not run the substrate preserves `experience` whole.

#### 8.10.6 Body stimulus under 1.1

Section 8.9 applies as written. In addition, drive above zero on a `SENSE` node counts as that sense at strength `drive / 14 mV`, capped at 1, so it is appraised and learned from with the part among the things present.

#### 8.10.7 Persistence guarantees

1. **Document round trip.** Loading a `neuron@1.1` document and saving it without stepping MUST give back the same document: `to_dict(from_dict(d))` equals `d`, and in canonical JSON (section 11.1) the bytes are identical. This binds every implementation.
2. **Determinism inside an implementation.** Saving and resuming MUST equal an unbroken run, and a probe MUST leave the brain bit for bit as it was.
3. **Across implementations.** Stepping MUST reproduce the reference's golden behaviors on the conformance scenarios: the winning impulse of each moment and its spike counts. An implementation MAY claim *exact* dynamics when it matches the reference's state traces bit for bit. Floating-point differences between languages make that optional rather than required.

#### 8.10.8 Memory write-back

When a moment is strong enough to keep (the 1st, 3rd, 10th, 30th and 100th time it happens), the reference returns a mind entry for it. Filing it is the runtime's call. A runtime SHOULD file it in `short_term` and SHOULD record that it came from the substrate (a `neuron` tag, for example), so a reader can tell it apart from what the entity was told. A runtime MAY have a model rewrite the template sentence; the rewrite keeps the entry's link to its moment.

#### 8.10.9 Perception interface

The normative interface takes senses, cues and frames directly. The reference's word lists (`shardcore/brain/chat.py`), which read senses and settings from text, are INFORMATIVE: a stand-in a runtime may replace.

## 9. Integrity and save discipline [NORMATIVE]

The requirement is the one v1.0 set, restated because practice diverged from it:

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

### 10.4 Reference implementation and golden texts

`shardcore/projection.py` is the reference projection: one pure function from a manifest and its verified members to the projected text, with no model call. It is stdlib only and is vendored as one file into runtimes that do not import the library; `vendor/shard_projection.gd` is its GDScript port. The conformance suite holds both to golden texts (`tests/conformance/projection/`, built by `tests/conformance/projection_cases.py`): the same bundle at the same tier and budget yields the same bytes.

Its fixed choices, which a runtime that claims the reference projection reproduces:

- Section labels are `[SHARDCORE IDENTITY]`, `[SHARDCORE PERSONALITY]`, `[SHARDCORE BOUNDARIES]`, `[SHARDCORE VOICE]`, `[SHARDCORE CANON]`, `[SHARDCORE CORE MEMORY]`, `[SHARDCORE ACTIVE MEMORY]`, `[SHARDCORE WORLD]`, each on its own line above the section text; sections are separated by one blank line.
- Character budgets are 24,000 (S), 64,000 (M) and 160,000 (L): the conservative heuristic of about four characters a token. A runtime with a real tokenizer passes its own budget.
- Tier contents are section 4.2's. Optional sections drop whole, in the order world, active memory, voice, personality, or as `projection_hints.section_priority` reorders them; `projection_hints.never_trim` adds to the never-trim set; `projection_hints.max_tokens` caps a section at four characters a token.
- Shard text is sanitized before it is placed (Security invariants): control characters and every run of whitespace become one space, so shard text cannot start a line; a triple backtick becomes three apostrophes; `[SHARDCORE` becomes `(SHARDCORE`, so shard text cannot pose as a section label; hyphen-like dashes fold to a hyphen and the two long dashes to a spaced hyphen. Each field is cut to a fixed length.

A runtime wraps the projected text in its own instructions, tools and history; that wrapper is not part of the contract.

## 11. Optional defined pillars [NORMATIVE, OPTIONAL]

These are defined optional pillars at the schema ids below. Their internal structure is PART IV, folded in from the v1.1 addendum at v1.11; this section fixes their place in the format. Identity, lineage and the revision chain (sections 11.4 and 11.5) are manifest fields rather than pillars, and are defined in full here.

### 11.1 Canon, attestation, and the manifest digest (`canonshard.json`, `shardcore/canon@1.0`)

Authored, immutable "fixed point" events, distinct from emergent mindshard memory: append-only, per-event signed, optionally OpenTimestamps-anchored under `assets/attestations/`. Receipt files are opaque binary members under `assets/` and carry the `shardcore/assets@1.0` schema id (section 2.3). Injected at max priority, exempt from vitality decay. Lineage (section 11.4) pins parents by `manifest_sha256`. `manifest_sha256` is the lowercase hex SHA-256 of canonical UTF-8 JSON bytes for `manifest.json`: object keys sorted lexically, no insignificant whitespace, and no ZIP container metadata. Signing and timestamping are OPTIONAL; a bundle is never required to carry a signature to be valid.

### 11.2 Statshard and immutability (`statshard.json`, `shardcore/stat@1.0`)

System-namespaced game stat blocks (`dnd5e`, `d20`, Pokemon-style, or `custom:<name>` with an inline definition). A registry, not a rules engine: it validates shape, it does not simulate the game. A shard MAY set `manifest.immutable: true` (a prime or reference shard); tooling MUST route edits of an immutable shard to a branch and MUST NOT write it in place.

### 11.3 Body subsystem (`body/`, `shardcore/body@1.0`)

Per-item sub-shards (`body/items/<uuid>.json`) with append-only ownership provenance, an `equipped.json` assignment layer, and `status_effects.json` with wall-clock UTC decay. Time fields are ISO-8601 UTC; decay is per wall-clock hour with elapsed clamped at zero for clock skew. The shell's `body_summary` is a regenerated read-only view for consumers that do not load `body/`. Item files are not deleted on unequip.

### 11.4 Identity and lineage (`manifest.shard_id`, `manifest.lineage`)

Provenance for who a bundle is and where it came from. Both are OPTIONAL manifest fields, so both are covered by `manifest_sha256` (section 11.1) when a later bundle pins this one.

#### 11.4.1 `shard_id`

An opaque string naming the identity a bundle carries: the character or creature, not one saved state of it.

- Format: a string of 1 to 128 characters with no control characters. A writer minting a new id SHOULD use a random UUID (RFC 9562 version 4) in lowercase hyphenated form.
- A writer MUST preserve an existing `shard_id` on every save, repack, and migration.
- A writer saving a bundle that has none MUST mint the id section 12 derives, whatever version the bundle declares. An id left to be derived on each load changes with every save, so the character would not be recognized after one. A writer that does not know the field preserves it as an unknown key.
- A new identity gets a new id. A writer creating a bundle SHOULD mint one, and a branch or an offspring (section 11.4.2) MUST NOT reuse its parent's id.
- Copies of one bundle (backups, trades, a mirrored vault) share the id because they are the same identity; `manifest_sha256` tells their states apart.
- A migrator adding an id to an existing bundle derives it deterministically (section 12), so migrating the same input twice yields the same id.

An id names an identity; it proves nothing. Authorship is proven by signing (section 11.1).

#### 11.4.2 `lineage`

A manifest block recording where a bundle came from, omitted for original characters. `relationship` is REQUIRED whenever the block is present and selects the shape.

**Branch** (`interpretation`, `derivative`, `alternate-universe`): the same character, retold. Worked example in A.3.3.

| Field | Notes |
|---|---|
| `parent` | REQUIRED object. `manifest_sha256` REQUIRED: the exact parent state forked from. `shard_id` (the parent's `manifest.shard_id`) and `label` OPTIONAL. |
| `ancestry` | OPTIONAL. Ordered ancestor `shard_id`s, root-first. |
| `origin_appearance` | OPTIONAL. Which published version the branch derives from (A.3.1). |
| `branch_point` | OPTIONAL. `inherited_canon` and `dropped_canon`, each a list of the parent's canon ids. |

A branch MUST NOT carry `parents`. An `original` relationship carries neither `parent` nor `parents`; omitting `lineage` entirely is preferred.

**Offspring** (`offspring`): a new individual produced from one or more parents. Two for breeding, one for a clone or a bud, more for a fusion.

```json
"lineage": {
  "relationship": "offspring",
  "parents": [
    { "role": "dam",  "shard_id": "8a0e5c3b-…", "manifest_sha256": "9b2e…", "label": "Akane (gen 2)" },
    { "role": "sire", "shard_id": "e07a41d9-…", "manifest_sha256": "51d0…", "label": "Hebiko" }
  ]
}
```

| Field | Notes |
|---|---|
| `parents` | REQUIRED array of one or more entries, in the order the producing tool lists them. |
| `parents[].role` | REQUIRED non-empty string naming the contribution. RECOMMENDED values: `dam`, `sire`, `donor` (a genetic contributor that is not a parent in the game's terms), `source` (the single parent of a clone or bud). A game MAY use its own vocabulary; the format does not model biology. |
| `parents[].manifest_sha256` | REQUIRED. The parent's manifest digest (section 11.1) at the moment the offspring was produced. |
| `parents[].shard_id` | RECOMMENDED when the parent has one: the parent's `manifest.shard_id`. |
| `parents[].label` | OPTIONAL human-readable name. |

Rules:

1. An offspring bundle MUST NOT carry `parent`, `ancestry`, or `branch_point`. It records its parents only; deeper pedigree is resolved by following `shard_id`s through whatever vault or save holds the parents.
2. Offspring inherit no canon. A parent's canon is that parent's lived history, and the child did not live it. The child's own canon MAY include an event that references its parents.
3. A tool producing offspring MUST verify each parent's integrity (section 9) before computing its digest, and MUST refuse a parent that fails. A pin to an unverified state proves nothing.
4. A pinned `manifest_sha256` records the parent's state at breeding or branching time. Parents keep changing afterward, so the pinned state usually survives only as this record; a reader MUST NOT treat an unresolvable pin as an error.
5. What a child inherited (alleles, IVs, traits, epigenetic marks) is game data, not lineage. It belongs in `statshard.json` (a `custom:<name>` system), `mindshard.structured`, or an `x_<vendor>` namespace.
6. Lineage is provenance and does not change how a bundle loads. A reader that does not consume lineage MUST NOT reject a bundle for a malformed `lineage` block. A tool that consumes it (a breeder, a pedigree view) validates the block before trusting it.

### 11.5 Revision chain and merge (`manifest.revision`)

Copies of one identity share a `shard_id` (11.4.1), and `manifest_sha256` tells their states apart without ordering them. The revision chain orders them: a bundle edited in an editor and the same bundle carried into a runtime can be told apart as newer, older, or diverged, and diverged copies can be merged.

#### 11.5.1 The block

```json
"revision": {
  "n": 7,
  "prior": "<manifest_sha256 of the state this write replaced>",
  "history": ["<prior>", "<the state before it>", "..."],
  "merged": "<manifest_sha256 of the other side, on a merge only>"
}
```

| Field | Notes |
|---|---|
| `n` | REQUIRED integer, 1 or more: how many writes this identity's chain has seen. A new identity (a new bundle, a branch, an offspring) is 1. Every write of an existing state is that state's `n` plus 1, an absent or malformed `revision` counting as 0. |
| `prior` | The `manifest_sha256` (section 11.1) of the state this write replaced. REQUIRED when the write replaced a state (so whenever `n` is above 1, and on the first v1.11 write of an older bundle); absent for a new identity. |
| `history` | OPTIONAL. Up to 16 digests, newest first, `history[0]` equal to `prior`: `prior` followed by the replaced state's own history. |
| `merged` | OPTIONAL. On a merge (11.5.3), the digest of the other side. |

The chain applies from 1.11. A save of a bundle declaring an older version adds no `revision`, since its other writers would carry one forward without advancing it; one already there is advanced. A restore writes an earlier state's members with that state's version, schema ids and floor, and its chain runs from the state it replaces.

A writer MUST derive the block from the state it replaces and MUST NOT copy it forward unchanged: the reference writer (`core.build_manifest`) derives it from `prior_manifest`, the manifest of the file as loaded or as the last save returned it. A branch's prior manifest carries no `files` map (`branch_manifest` drops it), so a branch starts at 1. A byte-for-byte file copy is the same state and keeps the block.

Like lineage, the chain is provenance. A reader MUST NOT reject a bundle over a missing or malformed `revision`; diagnose reports one for context.

#### 11.5.2 Comparing two states

Two manifests with one `shard_id` compare deterministically (`core.compare_revisions`):

| Result | Rule |
|---|---|
| `same` | the manifest digests are equal |
| `a_newer` | B's digest is in A's history: A descends from B |
| `b_newer` | the mirror case |
| `diverged` | neither is in the other's history, and the two histories share a digest (`core.common_ancestor` names the newest) |
| `unknown` | the histories never meet; `n` hints which is later and proves nothing |

Different `shard_id`s have no order; the comparison refuses them. Sixteen digests cover any realistic out-and-back between apps; past that, `unknown` is the honest answer.

#### 11.5.3 Merge

A merge needs the content of the state both sides descend from. A bundle does not carry it; whatever keeps earlier states does. The reference keeps every state a writer records in a content-addressed backup vault, keyed by `manifest_sha256` (`shardcore/backup_vault.py`), so the base is found by the digest `common_ancestor` returns.

The merge is three-way, unit by unit, where a unit is the smallest thing one owner changes:

- each top-level key of a JSON object member, so every `x_<vendor>` namespace (section 5.5) and every portable soul, shell or mind field is its own unit;
- each `mindshard.structured` schema block (section 7.3);
- every other member, whole (an image, a body item, a receipt).

A unit only one side changed takes that side; a unit both sides changed the same way takes it; a unit both changed differently is a conflict, resolved by the caller choosing a side. `manifest.json` is never merged: the merged state is written as a new state whose `prior` is one side and whose `merged` pins the other, with `n` one past the larger of the two and a history interleaving both chains, so both inputs compare as older than the merge.

When no base can be found, a tool MUST NOT guess one; it reports the copies as diverged and lets a person keep one. The reference is `core.merge_bundles` (and `python -m shardcore merge`).

## 12. Migration to v1.12 [NORMATIVE]

Migration is the explicit upgrade of section 3. A save never runs it. Migration to a version older than this one stamps the schema ids a bundle of that version carries, and adds nothing the version lacks.

A writer produces a v1.12 bundle from any prior bundle by the mechanical chain below. This is exactly the chain the shard updater applies (see `SHARD_UPDATER_PROPOSAL.md`). Migration is behavior-preserving for content; it corrects structure and versioning, and adds the identity field.

From a v1.11 bundle: restamp the version (step 1), refresh schema ids behind the registry (step 3; a shell at `shell@1.10` becomes `shell@1.12`), regenerate `card` (step 7), rewrite the manifest (step 8), and advance the revision chain. A `neuron@1.0` neuronshard is left as it is.

From a v1.10 bundle: restamp the version (step 1), refresh schema ids behind the registry (step 3), hold a list-shape anatomy as the parts map (anatomy, below), regenerate `card` (step 7), rewrite the manifest (step 8), and start the revision chain (revision, below).

From a v1.9 bundle: the v1.10 steps, plus mint `shard_id` (identity, below).

From a v1.0 bundle:

1. Set `manifest.spec_version` to `"1.12"`; stamp `manifest.bundle_version` with the same value as the deprecated alias (section 2.2).
2. Remove `manifest.memory_format`.
3. Add `schema` to each `manifest.files` entry.
4. Move recognized runtime-specific soul fields under `x_<vendor>` (section 5.5).
5. Normalize `stat_block` to the canonical ten keys: fold long-form names (`Presence`, `Acumen`, `Insight`, `Temperament`, `Conviction`, `Attunement`) and case variants onto the abbreviations; relocate a `Resonance` or `resonance` string to `soulshard.resonance` (section 5.2). A soul with no `stat_block` receives the average default (all ten stats at 5, section 5.1); the migrator MUST record every soul it defaulted this way.
6. Normalize timestamps to ISO-8601 UTC; write `last_modified_utc`.
7. Regenerate `card` from the soul.
8. Recompute every SHA-256 and rewrite the manifest.

Asset consolidation (any bundle, migration 0014): relocate every member under a legacy top-level asset folder (`images/`, `attestations/`, `skills/`, `references/`) to the same path under `assets/`, so `images/portrait.png` becomes `assets/images/portrait.png`. The origin subfolder is preserved and no bytes change. This runs before schema ids are stamped (step 3) and before digests are recomputed (step 8), so the relocated members receive `shardcore/assets@1.0` and correct hashes at their new paths, and the stale paths drop from the manifest.

Identity (any bundle without `shard_id`, migration 0015): mint the UUID version 5 (RFC 9562) whose name is the bundle's pre-migration `manifest_sha256` (section 11.1, as its 64-character lowercase hex string) under the SHARDCORE identity namespace `7e027d65-5d78-55a0-b193-cd8e1ecdccc3`, written in lowercase hyphenated form. Deriving the id from the input means migrating the same bundle twice, or with two conformant migrators, yields the same id. A present but invalid `shard_id` (section 11.4.1) is surfaced for manual attention and never replaced.

From a pre-public bundle (legacy `bundle_version` 1.x, list-form `files`, `memoryshard.json`, or flat memory), additionally:

9. If `files` is a bare list or absent, build the digest map from the actual members.
10. Consolidate duplicate or mislabeled pillar variants into the single canonical pillar: a `memoryshard_*.json` or similar variant merges into the memory pillar, newest content wins, entries deduplicated; embedded `backups/`, `.versions/`, `.history/` trees and digest sidecar members move to the external backup rather than staying in the bundle.
11. Rename `memoryshard.json` to `mindshard.json` (readers keep the fallback forever).
12. Split shell fields out of the soul into `shellshard.json`; create the pillar if absent.
13. Convert a flat memory array to tiered `short_term`/`long_term`/`core`/`archive`.

Anatomy (a shell `anatomy_profile` in the editor list shape, migration 0017): fold `external_parts` and `internal_parts` (or, when neither is present, the legacy `modifiers` list) into `parts`, keyed by each part's `id`. `stats.capacity_ml` and `stats.sensitivity` move onto the part, other stats stay under its `stats`; a part from `internal_parts` gains the `internal` tag; an editor `size` of `Custom` or empty and an empty `accessories` are dropped; `show_internal` and the list keys go. A part that already sits in a `parts` map wins over a list copy of it, and a list part the map lacks is added. A part without an id, or two different parts under one id, is surfaced for manual attention. A profile with no parts gets `"parts": {}`. This runs after the shell split (step 12), which can move an anatomy out of the soul.

Revision (every migration write, migration 0016): stamp `manifest.revision` from the pre-migration manifest by the rule of section 11.5.1, so a migrated bundle descends from the state it was migrated from.

A bundle that fails its own integrity before migration (a stale or phantom digest) MUST NOT be migrated silently; it is surfaced for manual attention, because migrating it would re-sign corrupt state.

## 13. Conformance [NORMATIVE]

A runtime claims v1.12 conformance if and only if it:

1. Loads every fixture in the reference conformance suite (`tests/conformance/` in the `shardcore` project) for the profiles it supports, and rejects every fixture marked malformed.
2. Rejects bundles whose `spec_version` major exceeds its own (section 1), comparing versions numerically (section 3).
3. Verifies SHA-256 on load and recomputes on save (section 9).
4. Preserves unknown fields, unowned `x_*` and consumer-schema namespaces, `shard_id`, `lineage` and `min_writer` on load and save, keeps the version and schema ids a bundle declares (section 3), refuses what section 2.2 says to refuse, and derives `revision` on every write of a bundle that has the chain (section 11.5).
5. Implements the normative pillars it reads or writes, and, if it reads neuronshards, meets section 8.8 for `neuron@1.0` and section 8.10.7 for `neuron@1.1`.
6. Declares which conformance profiles (section 4) and model tiers (section 4.2) it supports.
7. Writes a shell `anatomy_profile` as the parts map (section 6.3).

A runtime that projects bundles into prompts and claims the reference projection reproduces its golden texts (section 10.4).

---

# PART II: EXPERIMENTAL

Subject to change before ratification. Do not build production workflows on these without pinning to a commit.

- **Driveshard** (`driveshard.json`, `shardcore/drive@0.1`): drives, half-life chemistry, tiered goals, genome linkage via shell, optional epigenetic inheritance. The one working writer (QUICKENING, `quickening/drives.py`) sets the field set a schema freeze starts from: `drives[name] = {value, growth_per_hour, critical}` (pressure that grows by the hour and is critical past `critical`), `chemicals[name] = {value, half_life_hours}` (exponential decay), `goals = {core_dreams, long_term_goals, short_term_goals}`, `tick = {last_tick_utc, tick_count}`, and `regulators = {anguish, boredom, integrity, terminal_samples}`, under `schema_version` `"0.1"`.
- **Skills and references** (`assets/skills/`, `assets/references/`, `shardcore/assets@1.0`): retrieval-gated abilities and static knowledge documents; read-only, out-of-bundle retrieval. They share the `assets/` folder and schema id (section 2.3); their retrieval behavior remains experimental even though the folder and schema are stable.
- **Dream consolidation, introspection surface, neuro-symbolic validation**: reserved, as below.

### E.1 Dream Consolidation [EXPERIMENTAL]

A between-session pass that clusters recent short-term entries by tag
overlap and embedding similarity, produces consolidated long-term
entries, promotes identity-defining patterns to core, applies Hebbian
updates to the Neuronshard for co-activated memories, and writes a
readable trace to `mindshard.dream_log`. No reference implementation ships yet; the surface is reserved so
future bundles stay compatible. The reference consolidator is a ROADMAP
milestone. See `docs/dream.md`.


### E.2 Introspection Surface [EXPERIMENTAL]

A structured, grounded self-report surface (`shardcore.introspect()`) for
LLMs running a shard: top drives, chemistry levels, currently firing
nodes, inhibited nodes, active goals. Because the data causally depends
on real internal state (drive ticker, chemistry, Neuronshard
activation), any LLM statement grounded in it satisfies the accuracy /
grounding / internality criteria from the Anthropic introspection paper
cited in the research grounding of the v1.0 release (`SHARDCORE_Spec_v1.0.md`, section 16). Reserved; example output and usage in
`docs/introspection.md`.


### E.3 Neuro-Symbolic Validation Rules [EXPERIMENTAL]

Extension of the existing AST-whitelisted reflex parser to validate
shard invariants at load and save time (e.g.
`stat_block.STR + stat_block.END <= 200`, or
`not (core_essence_lock and allow_personality_override)`). On load,
every rule is evaluated against the merged pillar state; violations MAY
warn or refuse per `policy` (not yet specified). Cited influence:
Amazon's Nova 2 Lite neuro-symbolic training with Lean4 (the research grounding of the v1.0 release (`SHARDCORE_Spec_v1.0.md`, section 16)). Reserved; full grammar in `docs/validation.md`.
- **Neuro living-layer coupling** (QUICKENING): coupling the neuron substrate, drives, and memory into one deterministic tick loop; serialized additively, no manifest change.

---

# PART III: REFERENCE

## Pillar registry [INFORMATIONAL]

| Pillar / folder | Schema id | Status | Primary use |
|---|---|---|---|
| `manifest.json` | shardcore/manifest@1.12 | normative | all |
| `soulshard.json` | shardcore/soul@1.9 | normative required | all |
| `mindshard.json` | shardcore/mind@2.1 | normative optional | roleplay, agent |
| `mindshard.structured` | consumer-namespaced | normative optional | game, agent |
| `shellshard.json` | shardcore/shell@1.12 | normative optional | roleplay, embodied game |
| `neuronshard.json` | shardcore/neuron@1.1 (default), shardcore/neuron@1.0 | normative optional | living-layer |
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
- **Integrity** detects post-creation tampering only; it does not vouch for the author (the provenance in sections 11.1 and 11.4 is how authorship, timeline, and descent are proven).

New in v1.9:

- **Context-plane only.** A `.shard` addresses the model through its context (prompt, retrieved memory, tool inputs), never through its activation space. No pillar carries residual-stream vectors, steering directions, or model-internal state; embodiment is what the model is told, not an edit to what its internals hold. This is also why it could not be otherwise: activation directions are fit per-model and do not port across models, so a shard that reached into one model's internals would be meaningless to the next.

## Reference implementation [INFORMATIONAL]

The `shardcore` library is the single reference implementation of bundle I/O: open, verify, unpack, pack, hash, migrate, compare and merge, and of the projection. Its core (`shardcore/core.py`) and projection (`shardcore/projection.py`) are single stdlib files that apps vendor verbatim; `vendor/shardcore.gd` and `vendor/shard_projection.gd` are their GDScript ports. It is the canonical home for the read and write paths, and the ecosystem apps (SoulForge authoring, AI Rift and Djinn Redux runtimes, Milkmaid, the shard updater) SHOULD consume it rather than each carrying their own pack or unpack. Section 9 is satisfied by construction when every writer goes through it; the observed manifest drift is what happens when they do not.

```
python -m shardcore verify path/to/character.shard
```

## Backward and forward compatibility [INFORMATIONAL]

- A runtime reads every bundle of its major and never raises one on save. A writer from before 1.12 does not know section 2.2: a 1.10 or 1.11 writer refuses any newer bundle, and a 1.9 writer refuses none and stamps it down, which `min_writer` makes visible.
- A v1.12 runtime reads v1.11, v1.10, v1.9 and v1.0 bundles, and migrates them when asked (section 12). A v1.11 runtime accepts v1.12 bundles (same major) and preserves a `neuron@1.1` neuronshard it does not run.
- A v1.11 runtime read v1.10, v1.9 and v1.0 bundles and migrated them on write. A v1.10 or v1.9 runtime accepts v1.11 bundles (same major) and preserves `revision` as an unknown manifest field, though it carries it forward without advancing it; a comparison then finds such a write `diverged` from the state it was loaded from. A v1.0-only runtime accepts both and negotiates on the deprecated `bundle_version` alias; the fields it does not know it preserves under its own conformance rules.
- Unknown fields, unowned `x_*` namespaces, and consumer-schema blocks MUST be preserved on load and save, so bundles round-trip through partial runtimes without loss as the format extends within the v1 major.

---

# PART IV: PILLAR INTERNALS [NORMATIVE]

The internal structure of the optional pillars section 11 places: canon (A.2), statshard (A.4) and the body subsystem (A.5), plus the branch lineage worked example (A.3, informational; section 11.4.2 governs where they differ). Folded in from the v1.1 addendum at v1.11; headings keep the addendum's numbers with an `A.` prefix, and `§A.x` references point inside this part. Where this text says "v1.1" it means the version that introduced the field.

## A.2 Canonshard (`canonshard.json`, `shardcore/canon@1.0`)

### A.2.2 Bundle placement

Extends the v1.0 §1 bundle structure:

```
character.shard                (ZIP, DEFLATED)
├── manifest.json              [required]
├── soulshard.json             [required]
├── shellshard.json            [optional, gains body_summary in v1.1, see §5.7]
├── mindshard.json             [optional]
├── neuronshard.json           [optional]
├── canonshard.json            [optional, NEW in v1.1]
├── statshard.json             [optional, NEW in v1.1]
├── driveshard.json            [optional]
├── worldshard.json            [optional]
├── body/                      [optional, NEW in v1.1, see §5]
│   ├── equipped.json
│   ├── items/
│   │   └── <uuid>.json
│   └── status_effects.json
├── skills/                    [optional]
├── references/                [optional]
└── attestations/              [optional, NEW in v1.1: .ots receipts]
    └── canon-0001.ots
```

### A.2.3 File schema

```json
{
  "format_version": "1.0",
  "character_id": "soulshard://identity/uuid-abc",
  "events": [
    {
      "id": "canon-0001",
      "sequence": 1,
      "title": "Uncle Ben dies",
      "summary": "Ben Parker is killed by a burglar Peter chose not to stop.",
      "detail": "...",
      "era": "origin",
      "origin": "inherited",
      "source": {
        "work": "Amazing Fantasy #15",
        "year": 1962,
        "rights": "third-party"
      },
      "supersedes": null,
      "content_sha256": "abc123...",
      "attestation": {
        "added_utc": "2026-05-17T14:00:00Z",
        "author": "Cid",
        "key_id": "ed25519:9f8e...",
        "signature": "...",
        "ots_receipt": "attestations/canon-0001.ots"
      }
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `sequence` | int | Order within the log. Monotonic, gap-free. |
| `origin` | string | `inherited` (from source/parent) or `authored` (author's own). |
| `source.rights` | string | `public-domain`, `third-party`, or `owned`. |
| `supersedes` | string \| null | `id` of an event this revises. See §2.5. |
| `content_sha256` | string | SHA-256 of the event's canonical-serialized content (all fields except `attestation`). The thing that gets signed and timestamped. |
| `attestation.signature` | string | Signature over `content_sha256`. |
| `attestation.ots_receipt` | string \| null | Archive-relative path to the OTS receipt anchoring `content_sha256`. |

The OTS receipt anchors the **per-event content hash**, not the whole bundle. This avoids the
chicken-and-egg where adding a receipt changes the bundle hash, receipts stay valid
regardless of later bundle edits.

### A.2.4 Inherited vs. authored, the IP-honesty backbone

`origin` splits canon into:

- **`inherited`**, from a public-domain source or a parent shard. Attributed via `source`.
  **Not the author's IP.** Dracula's 1897 novel events; Steamboat Willie Mickey.
- **`authored`**, the author's own contribution. Signed. **The author's IP.**

`source.rights` further qualifies inherited events: `public-domain` (free to build on),
`third-party` (still under copyright, included as reference scaffolding only, not a claim),
`owned` (the author's other registered work).

This is what keeps a `.shard` legally *useful* instead of *overclaiming*. It documents
exactly where the public domain ends and the author's creativity begins.

### A.2.5 Immutability discipline

Canon events are append-only. A runtime **MUST NOT** edit an event in place.

To revise a canon event, append a **new** event with `supersedes` set to the old event's
`id`. The old event keeps its `content_sha256`, signature, and OTS receipt, the chain stays
intact. Prompt assembly and tooling resolve `supersedes` and present only the live tip of
each supersession chain.

Deleting is the same: append a tombstone event (`supersedes` set, content marking it
retracted). Nothing is ever removed from the file.

### A.2.6 Runtime semantics

- Canon events are injected into every prompt at max priority, regardless of session count.
- They are **exempt** from the v1.0 §3.4 vitality/decay mechanics, the §5.4 collapse
  tracking, and the §12 dream pass, those apply only to `mindshard` tiers.
- A v1.0 runtime ignores `canonshard.json`. It then loses the immutability guarantee and the
  always-inject behavior; this is acceptable degradation but SHOULD be surfaced to the user.

## A.3 Lineage, branch worked example [INFORMATIONAL]

### A.3.1 `lineage` block

> Section 11.4 defines lineage in full and overrides this part where they differ. It defines `shard_id` (the parent's `manifest.shard_id`), makes `relationship` required, and adds `relationship: "offspring"` with a `parents` array for new individuals produced by breeding, cloning, or fusion. This section remains the worked example for branches.

Added to `manifest.json` (v1.0 §2). Omit entirely for original, non-forked characters.

```json
"lineage": {
  "relationship": "interpretation",
  "parent": {
    "shard_id": "popeye-prime",
    "manifest_sha256": "def456...",
    "label": "Popeye (Thimble Theatre, 1929)"
  },
  "ancestry": ["popeye-prime"],
  "origin_appearance": {
    "work": "Thimble Theatre",
    "year": 1929,
    "rights": "public-domain",
    "note": "US public domain since 2025-01-01"
  },
  "branch_point": {
    "inherited_canon": ["canon-0001", "canon-0002", "canon-0003", "canon-0004"],
    "dropped_canon": ["canon-0005"]
  }
}
```

| Field | Notes |
|-------|-------|
| `relationship` | `original`, `interpretation`, `derivative`, or `alternate-universe`. `offspring` (section 11.4.2) is the other shape. |
| `parent.manifest_sha256` | Pins the **exact** parent state forked from. |
| `ancestry` | Ordered ancestor list, root-first. Full chain, not just the parent. |
| `origin_appearance` | The branch point, **the legal floor**. Records *which version* the branch derives from. The field a dispute turns on. |
| `branch_point.inherited_canon` | Canon IDs carried forward from the parent. |
| `branch_point.dropped_canon` | Parent canon IDs deliberately not carried. |

### A.3.2 Prime / reference shards

A canonical reference shard sets a manifest-level `"immutable": true`. Branches reference it
by `manifest_sha256`. Tooling MUST refuse to write changes to an `immutable` shard, edits
go to a branch.

### A.3.3 Worked example

Gritty Souls-like Popeye: fork the public-domain 1929 comic-strip Popeye
(`relationship: "interpretation"`, `origin_appearance.rights: "public-domain"`), inherit
canon events 1 to 4, drop event 5, then append authored events 6 to 12 with `origin: "authored"`.
The prime `popeye-prime.shard` is never touched.

## A.4 Statshard (`statshard.json`, `shardcore/stat@1.0`)

### A.4.2 File schema

```json
{
  "format_version": "1.0",
  "systems": {
    "dnd5e": {
      "schema": "shardcore/statschema/dnd5e@1.0",
      "data": {
        "abilities": { "STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 13, "CHA": 8 },
        "class": "Fighter",
        "level": 12,
        "features": ["Action Surge", "Second Wind"]
      }
    },
    "pokemon": {
      "schema": "shardcore/statschema/pokemon@1.0",
      "data": {
        "species": "...",
        "ivs": { "hp": 31, "atk": 30, "def": 31, "spa": 5, "spd": 31, "spe": 31 },
        "evs": { "hp": 0, "atk": 252, "def": 0, "spa": 0, "spd": 4, "spe": 252 },
        "nature": "Adamant",
        "moves": ["...", "...", "...", "..."]
      }
    },
    "custom:stigmata": {
      "schema": "inline",
      "definition": { "...": "user-defined field schema" },
      "data": { "...": "values" }
    }
  }
}
```

- `schema` points to a named first-party schema (`shardcore/statschema/<system>@<ver>`) or
  `"inline"` with a `definition` block carrying a user-defined field schema.
- First-party schemas shipped at v1.1: `dnd5e`, a generic `d20`, and a Pokemon-IV-style
  block. Everything else uses `custom:<name>` + inline definition.
- Cross-system translation (D&D ↔ Pokemon) is explicitly **out of scope**, a future toy,
  not a v1.1 commitment.

## A.5 Body subsystem (`body/`, `shardcore/body@1.0`)

### A.5.2 Bundle placement

```
body/                          [optional]
├── equipped.json              [optional within body/]
├── items/                     [optional within body/]
│   ├── <uuid>.json
│   └── ...
└── status_effects.json        [optional within body/]
```

`body/` is optional. Files within `body/` are individually optional, a bundle may carry
`items/` and `equipped.json` without any active effects, or `status_effects.json` without
any items.

A consumer that does not load `body/` reads `shellshard.body_summary` (§5.7) for a degraded
but accurate view.

Manifest `files` hashes every file under `body/` individually (§6). Paths in `files` use
forward slashes regardless of host OS: `body/equipped.json`, `body/items/<uuid>.json`,
`body/status_effects.json`.

### A.5.3 Time conventions

All time fields added in §5 use **ISO 8601 UTC with the `Z` suffix**:
`2026-05-26T14:32:17Z`.

Game-time tick fields stay as integers and are **optional sim-internal metadata**. A bundle
MAY carry `applied_at_tick` alongside `applied_at_utc`. Wall-clock UTC is canonical for
decay; tick is a hint for sims reconciling their own tick state on reload.

Decay is per wall-clock hour, always. Sims that internally tick faster or slower than real
time still serialize wall-clock anchors. The wall-clock model is the only one consistent
across runtimes that may or may not have a tick concept at all.

### A.5.4 `body/items/<uuid>.json`, per-item sub-shards

Each item is its own file. Treat it as a sub-shard: it carries its own identity,
per-instance state, and an append-only ownership chain.

```json
{
  "format_version": "1.0",
  "id": "uuid-collar-a47",
  "catalog_key": "collar_standard",
  "display_name": "DX-stamped obedience collar",
  "slot": "neck",
  "condition": 0.87,
  "durability_max": 1.0,
  "stat_mods": {"obedience": 8, "resistance": -4},
  "per_tick_effects": [],
  "tags": ["restraint", "facility_dx", "branded"],
  "origin_facility": "facility_dx",
  "created_at_utc": "2026-05-20T09:11:00Z",
  "provenance": [
    {
      "owner_shard_id": "soul-uuid-the-maid",
      "acquired_at_utc": "2026-05-26T14:32:17Z",
      "source": "facility_dx",
      "prev_hash": null,
      "entry_hash": "abc123..."
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | UUID. Filename MUST be `<id>.json`. |
| `catalog_key` | string | Points to the runtime's seed catalog (defaults factory). Per-instance state may diverge from catalog defaults. |
| `slot` | string | The anatomy slot type this item targets (`neck`, `wrists`, `breast_l`, etc.). Validation against shellshard's `anatomy_profile` happens at equip time. |
| `condition` | float | 0.0 to 1.0. Runtime defines the meaning per item type. |
| `stat_mods` | object | Per-instance overrides; absent fields fall back to catalog defaults. |
| `provenance` | array | Append-only ownership chain. See §5.4.1. |

#### A.5.4.1 Item provenance chain

Each `provenance[]` entry:

```json
{
  "owner_shard_id": "soul-uuid-current-owner",
  "acquired_at_utc": "2026-05-26T14:32:17Z",
  "source": "facility_dx",
  "prev_hash": null,
  "entry_hash": "sha256-of-this-entry-with-entry_hash-omitted"
}
```

Rules:

1. First entry: `prev_hash: null`.
2. Subsequent entries: `prev_hash` MUST equal the previous entry's `entry_hash`.
3. `entry_hash` is SHA-256 over the canonical serialization of the entry with the
   `entry_hash` field itself omitted.
4. Receiving runtimes MUST verify the chain on load. A broken chain is a manifest-integrity
   failure equivalent to a bad file hash, warn the user; do not silently proceed.
5. Transfer between bundles: source bundle removes the item file; destination bundle adds
   the file and appends a new provenance entry referencing the prior chain head as
   `prev_hash`.

#### A.5.4.2 Unequip vs. transfer-out

- **Unequip:** entry removed from `body/equipped.json`. File stays in `body/items/`. The
  character still possesses the item.
- **Transfer out:** item file removed from this bundle, added to destination bundle with a
  new provenance entry. Both bundles' manifests reflect the file movement.

Tooling MUST NOT silently delete item files on save when an item is merely unequipped.
Destruction is a separate explicit action.

### A.5.5 `body/equipped.json`, assignment layer

Which item is anchored to which anatomy part, and how.

```json
{
  "format_version": "1.0",
  "equipped": [
    {
      "item_id": "uuid-collar-a47",
      "part_id": "neck",
      "orientation": null,
      "applied_at_utc": "2026-05-26T14:32:17Z",
      "applied_by": "facility_dx"
    },
    {
      "item_id": "uuid-milker-std-19",
      "part_id": "breast_l",
      "orientation": "left",
      "applied_at_utc": "2026-05-26T14:33:01Z",
      "applied_by": "facility_dx"
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `item_id` | string | MUST reference a file at `body/items/<item_id>.json`. |
| `part_id` | string | MUST reference an anatomy part identifier in shellshard's `anatomy_profile`. |
| `orientation` | string \| null | Item/part-specific (`"left"`, `"right"`, `"inverted"`, etc.). |
| `applied_by` | string | Free-text source: facility id, character id, `"self"`, etc. |

Validation:

- `item_id` must point to an existing file under `body/items/`.
- `part_id` must exist in shellshard's `anatomy_profile`.
- Slot compatibility (item's `slot` matches the part's type) is a runtime concern, not a
  manifest-integrity concern. Mismatches SHOULD warn but not block load.

### A.5.6 `body/status_effects.json`, active effects with decay

```json
{
  "format_version": "1.0",
  "effects": [
    {
      "id": "uuid-effect-1",
      "name": "ambrosia.serenity_agent",
      "source": "facility_dx.ambrosia_dispenser_3",
      "level": 67.0,
      "decay_rate_per_hour": 0.05,
      "applied_at_utc": "2026-05-26T12:01:00Z",
      "expires_at_utc": null,
      "applied_at_tick": 14801,
      "effects": {"obedience": 12, "resistance": -8, "arousal": 4},
      "withdrawal_on_clear": true,
      "withdrawal_effect_id": "uuid-effect-withdrawal-template"
    },
    {
      "id": "uuid-effect-2",
      "name": "drunk",
      "source": "tavern.house_ale",
      "level": 1.0,
      "decay_rate_per_hour": 0.125,
      "applied_at_utc": "2026-05-26T14:00:00Z",
      "expires_at_utc": "2026-05-26T22:00:00Z",
      "applied_at_tick": null,
      "effects": {"coordination": -3, "inhibition": -5, "suggestibility": 2},
      "withdrawal_on_clear": false
    }
  ]
}
```

#### A.5.6.1 Decay model

On bundle load at wall-time `T`:

```
elapsed_hours = max(0, hours_between(applied_at_utc, T))
current_level = level - (decay_rate_per_hour * elapsed_hours)
```

Effect clears when **either** condition fires first:

- `current_level <= 0`, OR
- `T >= expires_at_utc` (when non-null).

`elapsed_hours` is clamped to ≥ 0. If the system clock has gone backwards (shard moved
between machines with skewed clocks), treat elapsed as zero rather than negative, no
negative decay.

A sim wanting "drunk clears in 8 in-world hours that happen in 8 real seconds" sets
`expires_at_utc: applied_at_utc + 8s`. Decay rate stays per wall-clock hour; sim controls
perceived duration via `expires_at_utc`.

#### A.5.6.2 Withdrawal

When an effect with `withdrawal_on_clear: true` clears, the runtime SHOULD instantiate a
fresh effect from the template referenced by `withdrawal_effect_id` and append it to the
active list. Withdrawal templates are catalog-defined (same pattern as items), not stored
inline on every parent effect.

If `withdrawal_on_clear: true` but `withdrawal_effect_id` is null, the runtime is free to
apply a generic withdrawal or no-op, runtime policy, not spec-mandated.

### A.5.7 `shellshard.body_summary`, flat read-only view

For consumers that don't load `body/`, the shellshard gains a `body_summary` block: a
regenerated, read-only flat view of `body/` state.

```json
"body_summary": {
  "equipped_count": 4,
  "equipped_parts": ["neck", "breast_l", "breast_r", "wrists"],
  "active_effects": ["ambrosia.serenity_agent", "drunk"],
  "effect_count": 2
}
```

**Authority rule:** `body/` is authoritative when present. `body_summary` is regenerated
from `body/` on every save by v1.1-aware writers.

A v1.0-only consumer reads `body_summary` and gets a degraded-but-accurate picture. It MUST
NOT write to `body_summary` and have that propagate back to `body/`. If a v1.0-only consumer
modifies the shellshard's other fields and resaves the bundle without `body/` awareness,
`body/` remains canonical and `body_summary` is regenerated when a v1.1-aware consumer next
saves.

### A.5.8 Mindshard interaction

`body/` does not duplicate memory. The mindshard remains the cognitive layer.

Runtimes with agency are responsible for **minting memories** into `mindshard.core[]` when
body-side thresholds cross into narrative significance, e.g., "milked >500 times," "wore
the DX collar continuously for 30 days," "survived three withdrawal cycles."

Thresholds are runtime policy, not spec-mandated. Memories minted from body events are
first-class mindshard entries. Suggested convention: include a `source_kind` tag in the
memory's metadata for downstream filtering. Suggested values: `"somatic"`, `"equipment"`,
`"chemical"`, `"social"`, `"environmental"`. Not normative.

---

*End of SHARDCORE Specification v1.12. Ratified 2026-11-23.*
