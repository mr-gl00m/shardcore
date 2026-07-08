# Driveshard

Status: **experimental** (spec PART II; `driveshard.json`, `shardcore/drive@0.1`).

The driveshard carries drives, chemistry, and goals. It is defined but
experimental: the schema is sketched, the tick engine is a roadmap item, and
the `@0.1` schema id signals that the shape may change before it goes normative.

When written in full, this document will cover:

- **Drives** as named scalars with a half-life, and the chemistry that decays
  between sessions.
- **Goals** tiered like memory (short-term, long-term, core), inheriting and
  expiring with the mindshard tiers.
- **Genome linkage**: base rates read from shell genome data when present.
- **Epigenetic inheritance**: how marks transfer to offspring at reduced
  intensity and fade across generations.

Until the tick engine lands, treat a driveshard as authored data a runtime may
read but is not required to simulate. See the "substrate, in motion" milestone
in [../ROADMAP.md](../ROADMAP.md) and [pillars.md](pillars.md).
