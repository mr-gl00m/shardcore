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

## The 0.1 shape in use

First written 2026-11-01 by a game whose opponent carries three drives
(temper, hunger, pride) between play sessions. Still experimental: this
records what one consumer writes so others can read it, and it may change
before `drive@0.1` goes normative.

```json
{
  "format_version": "0.1",
  "drives": {
    "temper": {"value": 0.71, "rest": 0.0, "half_life_h": 8.0, "updated_utc": "2026-11-01T03:12:00Z"},
    "hunger": {"value": 0.35, "rest": 0.6, "half_life_h": 24.0, "updated_utc": "2026-11-01T03:12:00Z"}
  }
}
```

- **A drive** is a named scalar: `value` and `rest` in 0 to 1, `half_life_h`
  in wall-clock hours, `updated_utc` (ISO-8601 UTC with a trailing `Z`) the
  moment `value` was last written.
- **Decay** is one rule for every drive: at time `t`, the value reads
  `rest + (value - rest) * 0.5 ^ (hours since updated_utc / half_life_h)`.
  Elapsed time is clamped at zero for clock skew, as for body status effects
  (spec 11.3). A `half_life_h` of 0 reads as `rest`. Because the rest and
  half-life travel with the value, a runtime that knows nothing about the game
  can still say how the character feels right now.
- **Ownership** follows `structured` (spec 7.3): a runtime writes only the
  drives it owns, and every other drive and top-level key rides through a load
  and save untouched. A drive whose fields don't check out resets only that
  drive, never the pillar.
- **What a drive means** (what pushes it, what it does) is the owning
  runtime's business.
