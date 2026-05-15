# Skills Folder: Design Notes

**Status:** Read-only schema design forthcoming. Targets: v1.1 (read-only)
and v1.2 (learned write-back).
**Spec section:** [SHARDCORE_Spec_v1.0.md §10](../SHARDCORE_Spec_v1.0.md)
**Roadmap:** [ROADMAP.md §1.1.5](../ROADMAP.md) (read-only),
[ROADMAP.md §1.2](../ROADMAP.md) (learned)

The `skills/` folder is reserved at v1.0; v1.0 loaders MAY ignore it
entirely, and a conformant v1.0 bundle MAY include it.

This document will cover, when written:

- **File layout.** One `*.md` file per skill, with YAML frontmatter
  (`name` matching filename stem, `description`, `authored`,
  activation tags).
- **Activation gating.** Retrieval-driven by default; `always_on: true`
  bypasses the gate.
- **Read-only schema (v1.1).** Frontmatter, body, activation tags,
  and the `always_on` flag. Loaders that understand v1.1 MUST treat
  the body as authoritative skill content.
- **Learned write-back (v1.2).** `proficiency`, `xp`, `usage_count`
  fields managed by the runtime. Reserved for v1.0 read-only; loaders
  MUST preserve unknown fields on save.

Contributions welcome.
