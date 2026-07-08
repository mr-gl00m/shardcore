# Conformance profiles and model tiers

Status: **normative** (spec section 4).

v1.0 left "which pillars does this use case need" implicit. v1.9 writes it
down as a small set of profiles, plus model tiers that describe how a bundle
projects into different context budgets. Both are optional and recorded in
`manifest.conformance`. The spec is authoritative; this note orients.

## Profiles

A profile is a required-pillar set plus a tier floor. A runtime that claims to
support a profile MUST load every bundle valid for it.

| Profile     | Required pillars            |
|-------------|-----------------------------|
| `companion` | soul + mind                 |
| `npc`       | soul + mind (with `structured`) |
| `agent`     | soul + mind                 |

The soul is always required. Shell, neuron, canon, stat, world, body, and
assets are common but optional, even inside a profile.

## Model tiers

`min_tier` records the smallest tier at which the author considers the
character faithful. Below it, a runtime SHOULD warn that projection is lossy.

| Tier | Budget      | Projection scope                                  |
|------|-------------|---------------------------------------------------|
| `S`  | up to ~8k   | identity + boundaries + top-K core memory only    |
| `M`  | ~8k to 32k  | plus active memory and world                      |
| `L`  | 32k+        | full memory, plus curiosity and drives            |

## The manifest block

```json
"conformance": { "profile": "companion", "min_tier": "M" }
```

Both keys are optional. A bundle with no `conformance` block is still valid; it
just makes no profile claim, and a runtime falls back to loading whatever
pillars are present.

See [projection.md](projection.md) for how a tier's budget drives trimming.
