# Driveshard: Design Notes

**Status:** Design notes forthcoming. Target: v1.1.
**Spec section:** [SHARDCORE_Spec_v1.0.md §9](../SHARDCORE_Spec_v1.0.md)
**Roadmap:** [ROADMAP.md §1.1.1](../ROADMAP.md)

The Driveshard pillar is reserved at v1.0; the schema surface is fixed
so bundles written today remain loadable by the v1.1 reference engine.
The tick engine itself is scheduled for v1.1.

This document will cover, when written:

- **Drives.** Bounded scalar states (hunger, loneliness, curiosity,
  libido, etc.) with per-drive baselines and saturation behavior.
- **Chemistry.** Half-life decay variables (dopamine, cortisol,
  oxytocin, etc.) that modulate drive responsiveness. Distinct from
  drives because chemistry decays on a timer, drives shift on events.
- **Goals.** Three tiers mirroring `mindshard` memory tiers
  (short-term, long-term, core-dream). Goal salience couples back into
  drive saturation.
- **Genome linkage.** Drive baselines and sensitivities derived from
  shellshard genome data; supports breeding semantics.
- **Epigenetic inheritance** (optional). How trauma marks decay
  across generations.

Contributions and design discussion welcome. See `CONTRIBUTING.md` for
the spec RFC flow.
