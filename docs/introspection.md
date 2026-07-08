# Introspection surface

Status: **reserved** (spec PART II).

The introspection surface is a structured self-report a runtime can generate
from a character's real internal state, `shardcore.introspect(bundle_or_runtime)
-> IntrospectionReport`. It is reserved in v1.9 and lands as a roadmap item.

When written in full, this document will cover:

- **Report fields**: `active_drives`, `chemistry`, `firing_now`, `inhibited`,
  `active_goals`, plus raw-state pointers for grounding an LLM.
- **Causal sourcing**: every value comes from neuronshard and driveshard state.
  No template strings, no invented numbers.
- **Format and stability**: JSON-serializable, stable ordering, documented
  precision and units.

The point of the surface is that a character can report on itself from what is
actually true in its state, not from a prompt describing what it should feel.
See the "substrate, in motion" milestone in [../ROADMAP.md](../ROADMAP.md).
