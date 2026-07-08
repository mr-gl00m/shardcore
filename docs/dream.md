# Dream consolidation

Status: **reserved** (spec PART II).

Dream consolidation is a between-session pass over short-term memory that
produces long-term entries and writes `mindshard.dream_log`. v1.9 reserves the
`dream_log` slot in the mind pillar; the consolidator itself is a roadmap item.

When written in full, this document will cover:

- **Triggers**: when a consolidation pass runs (session close, idle time, an
  explicit call).
- **Clustering and promotion**: how short-term entries group and which get
  promoted to long-term or core, deterministically given a seed.
- **Neuronshard coupling**: an optional Hebbian update on co-active memory
  clusters, behind a flag.
- **The `dream_log` trace format**: `cluster`, `entries`, `consolidated_text`,
  `promoted_to`.
- **Determinism**: a second pass on unchanged inputs is a no-op.

See the "substrate, in motion" milestone in [../ROADMAP.md](../ROADMAP.md).
