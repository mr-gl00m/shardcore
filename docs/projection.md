# The projection contract

Status: **normative** (spec section 10).

Projection is the deterministic mapping from a bundle to a system prompt.
Two runtimes that project the same bundle at the same model tier produce the
same section order and the same trim decisions, so a character reads the same
way wherever it loads. The spec is authoritative; this note orients.

## Section order

The reference projection assembles sections in this fixed order:

1. identity
2. personality
3. boundaries
4. voice
5. canon
6. core memory
7. active memory (short-term, then long-term)
8. world

A runtime SHOULD follow this order. It MUST NOT reorder sections based on a
model's guess about relevance.

## The never-trim set

When the context budget is tight, a runtime trims from the bottom of the
active-memory and world sections first. Three sections are never trimmed while
the bundle is at or above its `min_tier`: **canon**, **core memory**, and
**boundaries**. If a tier is so small that even these do not fit, the runtime
SHOULD warn that the projection is lossy rather than silently drop them.

## Author hints

`soulshard.projection_hints` is advisory and lets an author steer projection
without breaking determinism:

- `never_trim`: additional sections to protect.
- `section_priority`: a partial ordering hint within the trimmable tail.
- `max_tokens`: a soft ceiling.
- `model_notes`: free-form notes a runtime MAY surface to an operator.

## Where the LLM fits

An LLM MAY condense a section that a runtime has already selected, or generate
curiosity as an escalation step. It MUST NOT decide the section order or the
trim set. Those are the runtime's, so the same bundle projects the same way
regardless of which model is behind it.

See also [conformance.md](conformance.md) for the model tiers that set the
budget.
