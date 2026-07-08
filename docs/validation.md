# Neuro-symbolic validation rules

Status: **reserved** (spec PART II).

Validation rules are declarative conditions over the merged pillar state that a
runtime evaluates through a closed, AST-whitelisted grammar. v1.9 reserves the
surface; the evaluator lands as a roadmap item.

When written in full, this document will cover:

- **The rule language**: allowed operators, allowed paths, maximum expression
  depth, and an evaluation timeout.
- **The evaluation context**: what pillar state a rule can read.
- **Policy**: each rule declares `warn`, `refuse`, or `log`.
- **Structured violations**: `{rule, path, expected, actual}`, never untyped
  strings.

Security is the whole point of the closed grammar: a rule cannot call, import,
exec, access attributes, subscript, open files, or allocate unbounded memory. A
malicious rule from an untrusted bundle stays inert. See [../SECURITY.md](../SECURITY.md)
and the "substrate, in motion" milestone in [../ROADMAP.md](../ROADMAP.md).
