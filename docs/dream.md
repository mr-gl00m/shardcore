# Dream Consolidation: Design Notes

**Status:** Design notes forthcoming. Target: v1.1.
**Spec section:** [SHARDCORE_Spec_v1.0.md §12](../SHARDCORE_Spec_v1.0.md)
**Roadmap:** [ROADMAP.md §1.1](../ROADMAP.md)

Dream consolidation is a between-session pass. v1.0 reserves the surface
so that bundles produced by the eventual reference implementation remain
v1.0-spec-compatible.

This document will cover, when written:

- **Trigger conditions.** Session count, idle time, explicit
  `dream()` calls.
- **Clustering.** Tag overlap and embedding similarity over recent
  short-term entries.
- **Promotion rules.** When a long-term cluster is promoted to a
  core memory, when a core memory is allowed to fade, how
  identity-defining patterns are detected.
- **Hebbian application.** How Neuronshard edge weights are updated
  for memories that co-activated during the session.
- **Trace format.** The human-readable lines written to
  `mindshard.dream_log` (capped list, ~20 entries).
- **Determinism and reproducibility.** Whether dream is required to
  be deterministic given identical input bundles.

Contributions welcome.
