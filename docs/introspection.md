# Introspection Surface: Design Notes

**Status:** Design notes forthcoming. Target: v1.1.
**Spec section:** [SHARDCORE_Spec_v1.0.md §13](../SHARDCORE_Spec_v1.0.md)
**Roadmap:** [ROADMAP.md §1.1](../ROADMAP.md)

The introspection surface is a structured, grounded self-report
function (`shardcore.introspect()`) for LLMs running a shard. Because
the data causally depends on real internal state (drive ticker,
chemistry, Neuronshard activation), any LLM statement grounded in it
satisfies the accuracy / grounding / internality criteria from the
Anthropic introspection paper cited in spec §16.

This document will cover, when written:

- **Output shape.** Top-N drives, chemistry levels, currently firing
  Neuronshard nodes, currently inhibited nodes, active goals.
- **Sampling and stability.** How snapshot semantics interact with
  the running tick loop; whether introspect() pauses ticks.
- **Privacy and scoping.** What's exposed by default vs.
  opt-in (e.g. arousal, trauma, contradiction structure).
- **Format.** JSON for machine consumers, human-readable text block
  for prompt injection.
- **Example output.** A worked example with all fields populated.

Reserved for v1.1; do not call `shardcore.introspect()` against v1.0
bundles in production paths.
