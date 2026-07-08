# Skills

Status: **experimental** (spec PART II; under `assets/`, `shardcore/assets@1.0`).

Skills are retrieval-gated abilities carried as markdown under the bundle's
`assets/` folder. v1.9 folds skills into the single `assets/` folder alongside
images, receipts, and references; the activation and write-back semantics stay
experimental.

When written in full, this document will cover:

- **File layout and frontmatter**: the schema validated on load.
- **Activation**: always-on versus retrieval-gated, expressed as
  mindshard and driveshard queries.
- **Learned fields**: `proficiency`, `xp`, `usage_count`, read-only for now.
  Any sanctioned write-back path (with a locking and atomic-write contract) is
  a later milestone.

Security note: a skill can declare behavior a runtime may execute. Treat skills
from untrusted bundles as code and sandbox them accordingly. See
[../SECURITY.md](../SECURITY.md) and [pillars.md](pillars.md).
