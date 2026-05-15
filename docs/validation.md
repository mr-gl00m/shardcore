# Neuro-Symbolic Validation Rules: Design Notes

**Status:** Design notes forthcoming. Target: v1.1.
**Spec section:** [SHARDCORE_Spec_v1.0.md §14](../SHARDCORE_Spec_v1.0.md)
**Roadmap:** [ROADMAP.md §1.1](../ROADMAP.md)

Validation rules extend the existing AST-whitelisted reflex parser to
enforce shard invariants at load and save time. v1.0 reserves the
surface; v1.0 loaders do not evaluate `validation_rules`.

This document will cover, when written:

- **Grammar.** The closed expression grammar (boolean ops,
  comparisons, attribute access, `len()`, arithmetic). No imports,
  no calls beyond a fixed builtin set.
- **Evaluation context.** Which pillars are merged into the namespace
  visible to a rule (e.g. `stat_block.STR`, `evolution_flags.x`,
  `core_essence_lock`).
- **Failure policy.** `policy: warn` vs. `policy: refuse` vs.
  `policy: log`; default behavior when `policy` is absent.
- **Performance.** Rules are evaluated on every load and every save;
  the parser MUST short-circuit and MUST NOT spawn subprocesses.
- **Cited influence.** Amazon Nova 2 Lite's neuro-symbolic
  combination of fluid LLM reasoning with Lean4 symbolic verification
  (spec §16). The shard analogue is much narrower: a small typed
  expression evaluator over merged pillar state.

Reserved for v1.1.
