# Examples

Two reference `.shard` bundles that exercise the v1.9 format surface. Both are
built from fictional characters with no personal, proprietary, or
project-private content, and both are shaped to pass the conformance suite.

Regenerate with:

```sh
python examples/_build_examples.py
```

The builder authors each manifest directly, then reads the result back through
the library and asserts it verifies clean and diagnoses as `current` at spec
v1.9. If an example drifts from the spec, the build fails.

---

## `minimal.shard`: Thorne Vale

**What it demonstrates:** the smallest valid SHARDCORE bundle.

- Only `manifest.json` and `soulshard.json` (the soul is the one required
  pillar, spec section 5).
- No shell, mind, or any optional pillar.
- ~1 KB total.

**Persona:** Thorne Vale, an archivist of lost languages. Meticulous, quietly
melancholic, carries their late mentor's silver pen. Stats lean on ACU and TMP;
PRS is low. Built to exercise the minimum-viable load path in a runtime.

**Try it:**

```sh
python -m shardcore verify examples/minimal.shard
```

Prints `OK: examples/minimal.shard passes integrity verification`.

---

## `standard.shard`: Cassia Meridian

**What it demonstrates:** a full companion bundle that touches most of the v1.9
optional pillars, with a pre-warmed neural substrate.

- `soulshard.json`: core soul (ten-stat `stat_block`, `identity`,
  `personality`) plus portable `appearance_profile` and a soul-level
  `resonance`.
- `shellshard.json`: anatomy, `assets/`-relative image paths, physical state.
- `mindshard.json`: `format_version` 2.1 memory with one entry in each of the
  short-term, long-term, and core tiers.
- `neuronshard.json`: topology derived from the soul plus state vectors from
  100 ticks of pre-warming with Hebbian learning on.
- `canonshard.json`: one authored, immutable canon event.
- `statshard.json`: a D&D 5e game-system block, kept out of the closed
  ten-stat core soul.
- `assets/images/cassia_portrait.png`: a small asset under the single
  `assets/` folder (`shardcore/assets@1.0`).
- `manifest.conformance`: declared `companion` profile, `min_tier` `M`.

**Persona:** Cassia Meridian, stellar cartographer aboard a long-haul survey
ship. Direct, dryly funny, protective of her crew and her instruments.
Remembers losing a transponder on the Ashira jump; holds "maps are how you love
something that keeps moving" as a core belief.

**Try it:**

```sh
# Integrity check
python -m shardcore verify examples/standard.shard

# Drift check against the current spec
python -m shardcore diagnose examples/standard.shard

# Resume the neural substrate and tick 200 more steps
python -m shardcore neuron examples/standard.shard --ticks 200 --save resumed.json
```

The Neuronshard picks up mid-activity, so the first output tick already carries
dynamics left over from the pre-warm. That is the point: a `.shard` you loaded
today is not the same `.shard` you loaded yesterday, even if no prompt was ever
sent to an LLM in between.

To see the migration path, copy any older bundle and run:

```sh
python -m shardcore migrate path/to/old.shard --out migrated.shard
```

---

## Conformance note

Both bundles share the shape the conformance suite builds under
`tests/conformance/`. If you modify `_build_examples.py` and it stops matching
the fixtures, either fix the builder or extend the suite.
