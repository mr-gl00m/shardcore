# Examples

Two reference `.shard` bundles that exercise the v1.0 format surface.
Both are built from fictional characters with no personal, proprietary,
or project-private content. Both are shaped to pass the full
conformance suite.

Regenerate with:

```sh
python examples/_build_examples.py
```

---

## `minimal.shard`: Thorne Vale

**What it demonstrates:** the smallest valid SHARDCORE bundle.

- Only `soulshard.json` and `manifest.json` (soulshard is the single
  required pillar per §3).
- No shell, no mind, no neuron.
- ~1 KB total.

**Persona:** Thorne Vale, an archivist of lost languages. Meticulous,
quietly melancholic, carries their late mentor's silver pen. Stats lean
on ACU and TMP; PRS is low. Built to exercise the minimum-viable load
path in a runtime.

**Try it:**

```sh
python -m shardcore verify examples/minimal.shard
```

Should print `OK: examples/minimal.shard conforms to SHARDCORE v1.0`.

---

## `standard.shard`: Cassia Meridian

**What it demonstrates:** a full four-pillar bundle with a pre-warmed
neural substrate.

- `soulshard.json`: soul fields including `appearance_profile`.
- `shellshard.json`: anatomy, image paths, physical state.
- `mindshard.json`: v2.1 memory with one entry in each of short-term,
  long-term, and core tiers.
- `neuronshard.json`: topology (48 nodes, 104 edges) plus state
  vectors from 100 ticks of pre-warming with Hebbian learning on.

**Persona:** Cassia Meridian, stellar cartographer aboard a long-haul
survey ship. Direct, dryly funny, protective of her crew and her
instruments. Remembers losing a transponder on the Ashira jump; holds
"maps are how you love something that keeps moving" as a core belief.

**Try it:**

```sh
# Validate
python -m shardcore verify examples/standard.shard

# Resume the neural substrate and tick 200 more ms
python -m shardcore neuron examples/standard.shard --ticks 200 --save resumed.json
```

The bundle's Neuronshard picks up mid-activity, so the first output
tick will already carry dynamics left over from the pre-warm. This is
the point: a `.shard` you loaded today is not the same `.shard` you
loaded yesterday, even if no prompt was ever sent to an LLM in
between.

---

## Conformance note

Both bundles are covered by the conformance suite under
`tests/conformance/`. Specifically, the fixture generators in
`conftest.py` produce bundles of the same shape. If you modify
`_build_examples.py` and it stops matching the fixtures, either fix
the builder or extend the suite.
