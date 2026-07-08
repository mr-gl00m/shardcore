# The optional defined pillars

Status: **normative, optional** (spec section 11), except drive which is
experimental.

Only the soul is required. Every pillar below is optional and self-describes
through a `schema` id in `manifest.files`. Absence is never a load error. The
spec is authoritative; this note orients.

## Canon (`canonshard.json`, `shardcore/canon@1.0`)

Authored, immutable "fixed point" events: the things about a character that are
true by authorial decision, not by memory drift. Canon is append-only, each
event is individually signable, and canon is injected at maximum priority and
exempt from decay. It is in the projection never-trim set. Use it for origin
facts and hard boundaries you never want a runtime to summarize away.

## Stat (`statshard.json`, `shardcore/stat@1.0`)

Game-system stat blocks (`dnd5e`, `d20`, `custom:<name>`). The core soul's
`stat_block` is closed at exactly ten narrative stats; anything that belongs to
a rules system lives here instead. The pillar validates shape, not rules: it is
a registry, not a rules engine.

## Body (`body/`, `shardcore/body@1.0`)

A live subsystem, not a single file. Per-item sub-shards under `body/items/`,
an `equipped.json` assignment layer, and `status_effects.json` with wall-clock
UTC decay. Each file under `body/` is listed individually in the manifest. The
shell's read-only `body_summary` is regenerated from this folder on save.

## Assets (`assets/`, `shardcore/assets@1.0`)

One folder for every static asset: images, OpenTimestamps receipts, skills, and
references. Everything under `assets/` carries the single `shardcore/assets@1.0`
id. The subfolder layout (`assets/images/`, `assets/skills/`, ...) is a
recommended convention, not a requirement. The separate v1.0 `skills/` and
`references/` folders fold in here; migration `0014` relocates legacy top-level
asset folders under `assets/`.

## World (`worldshard.json`, `shardcore/world@1.0`)

Setting and scene state: where the character is and what is going on around
them. Optional, and projected after active memory.

## Drive (`driveshard.json`, `shardcore/drive@0.1`)

**Experimental.** Drives as named scalars with half-life chemistry, and tiered
goals that mirror the memory tiers. The schema is sketched; the tick engine is
a roadmap item. See [driveshard.md](driveshard.md).
