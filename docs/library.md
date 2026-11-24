# Using the reference library

Status: **reference implementation** (spec PART III).

`shardcore` is the single reference implementation of bundle I/O: open, verify,
diagnose, build, migrate, and repack. A writer that goes through it produces a
spec-conformant bundle by construction, so the integrity and save rules of
spec section 9 hold without every app re-deriving them. The bundle I/O surface
is standard-library only; `numpy` is needed only for the neuron substrate.

## Read and verify

```python
from shardcore import read_bundle, verify_bundle

state = read_bundle("character.shard")   # BundleState, never raises on bad input
print(state.readable, state.spec_version, state.integrity_ok)

errors = verify_bundle("character.shard")  # [] means valid
```

`read_bundle` reads every member into memory and hashes it; it never extracts
to disk, so there is no zip-slip surface. `verify_bundle` keeps its v1.0
signature (a list of violation strings, empty means valid).

## Diagnose drift

```python
import shardcore
from shardcore import read_bundle, diagnose

diag = diagnose(read_bundle("character.shard"), shardcore.__spec_version__)
print(diag.status)   # "current" | "behind" | "outdated" | "blocked"
for f in diag.findings:
    print(f.severity, f.code, f.migration, f.detail)
```

`behind` is a choice, not a defect: the bundle keeps the rules of the version it
declares, and a newer one exists. `outdated` departs from its own version's rules.

`current` means the strict reader below accepts the bundle too. When it does
not, `diagnose` adds `strict_read_failed`: `blocked` if nothing is left to
migrate, `info` while migrations are pending.

## Verified runtime document access

```python
from shardcore import read_bundle_document

document = read_bundle_document("character.shard")
soul = document.json_member("soulshard.json")
profile = document.json_member("extensions/nexus/profile.json")
print(document.manifest_sha256, soul["name"], profile["schema"])
```

The strict runtime reader rejects duplicate or unsafe member names, missing or
undeclared files, invalid sizes and hashes, invalid UTF-8 JSON, and archives
past the configured compressed or uncompressed size caps. Member selection
controls retained bytes only. Integrity verification still covers every file
declared by the manifest.

## Build a fresh bundle

```python
from shardcore import build_bundle, json_member_bytes

document = build_bundle(
    "character.shard",
    shard_name="Aria",
    members={
        "soulshard.json": json_member_bytes({"name": "Aria"}),
        "extensions/nexus/profile.json": json_member_bytes(
            {"schema": "nexus/profile@1.0"}
        ),
    },
    schemas={"extensions/nexus/profile.json": "nexus/profile@1.0"},
    immutable=True,
)
```

The fresh builder computes every member hash and size, writes the manifest
first, verifies the temporary bundle through the strict reader, and places the
verified result at the target with an atomic replacement. A fresh bundle is a
new identity, so the builder mints a random `shard_id` unless you pass one
(pass the existing id when rebuilding a bundle that has one, or a fixed id when
byte-identical output matters).

## Breed, clone, or fuse (offspring lineage)

```python
from shardcore import build_bundle, offspring_lineage, read_bundle_document

dam = read_bundle_document("akane.shard")     # verified, or BundleReadError
sire = read_bundle_document("hebiko.shard")

child = build_bundle(
    "kit.shard",
    shard_name="Kit",
    members={"soulshard.json": child_soul_bytes},
    manifest_fields={"lineage": offspring_lineage([("dam", dam), ("sire", sire)])},
)
```

`offspring_lineage` only takes `BundleDocument`s, which exist only after every
member verified, so a parent is never pinned in an unverified state (spec
11.4.2 rule 3). Each entry records the parent's role, `manifest_sha256`,
`shard_id`, and card name. One parent with role `source` records a clone or a
bud. The builder validates the block and refuses a child that reuses a parent's
`shard_id`. What the child inherited (alleles, IVs, traits) is game data: put it
in `statshard.json`, `mindshard.structured`, or an `x_<vendor>` namespace.

`lineage_errors(block)` and `shard_id_error(value)` return problems instead of
raising, for tools that consume lineage (a pedigree view) and decide for
themselves what a problem means.

## Save without changing the version

```python
import json
from shardcore import core

manifest, members = core.read_bundle_members("character.shard")
soul = json.loads(members["soulshard.json"])
soul["summary"] = "Edited."
members["soulshard.json"] = json.dumps(soul, indent=2, ensure_ascii=False).encode()

# keeps spec_version, schema ids, shard_id and every key it does not know
core.pack_bundle("character.shard", members, soul=soul, prior_manifest=manifest)

# raises it, and keeps character.shard.v1.10.bak (or the backup vault's copy)
core.pack_bundle(
    "character.shard", members, soul=soul, prior_manifest=manifest, upgrade_to="1.12"
)
```

Pass the manifest as loaded, or the one the last save returned. A save that needs
something the declared version cannot hold raises `UpgradeNeededError`: leave it
out, or ask and write again with `upgrade_to`.

`manifest.min_writer` names the oldest version whose writers may save a bundle.
`pack_bundle` raises `NewerSpecError` below it, and for a newer bundle that names
none. At or above it, a newer bundle is saved whole and stays at its version.

## Migrate and repack

```python
from shardcore import migrate_bundle

notes = migrate_bundle("old.shard", out="migrated.shard")  # target defaults to the current spec
```

The lower-level pieces are public too: `MutableBundle` (an in-memory mutable
view), `repack_atomic` (the atomic writer), and `schema_for_member` (the
per-member schema-id registry).

## The substrate

```python
from shardcore.neuron import build_brain_from_shard, LIFNetwork
```

`shardcore.neuron` carries the LIF tick engine and Neuronshard I/O forward from
v1.0 unchanged, including the byte-identical state round-trip.

## CLI

```bash
python -m shardcore verify   <bundle>
python -m shardcore diagnose <bundle>
python -m shardcore migrate  <bundle> [--out OUT] [--target 1.12]
python -m shardcore compare  <a> <b>
python -m shardcore merge    <ours> <theirs> --out OUT
python -m shardcore neuron   <bundle> [--ticks N] [--save STATE.json]
```

All commands exit 0 on success, non-zero on any violation.

## What the library is not

It is not a batch migration tool. `migrate_bundle` is atomic but keeps no
backup and no run-log; the full backup / verify / restore-on-failure envelope
belongs to a tool that wraps it. See [migration.md](migration.md).

## Compare and merge copies (spec 11.5)

```python
from shardcore import compare_revisions, merge_bundles, read_bundle_members, write_merge

a, _ = read_bundle_members("editor_copy.shard")
b, _ = read_bundle_members("runtime_copy.shard")
compare_revisions(a, b)        # "same" | "a_newer" | "b_newer" | "diverged" | "unknown"

result = merge_bundles("editor_copy.shard", "runtime_copy.shard")
if result["status"] == "merged":
    write_merge("merged.shard", result)
elif result["status"] == "conflicts":
    print(result["conflicts"])  # e.g. ["soulshard.json#nature"]; pass prefer={unit: "theirs"}
```

Every write through `core.pack_bundle` stamps `manifest.revision` from the
manifest it replaces, so pass the manifest the file was loaded with (or the
one the last save returned) as `prior_manifest`. The merge base comes from the
backup vault, which records every state a writer saves.

## Project a bundle into a prompt (spec 10)

```python
from shardcore import read_bundle_members
from shardcore.projection import project

manifest, members = read_bundle_members("character.shard")
p = project(manifest, members, tier="M")
system_prompt = my_runtime_preamble + "\n\n" + p.text
if p.lossy:
    print(p.warnings)
```

`shardcore/projection.py` is one stdlib file; a runtime that does not import
the library vendors it (the ecosystem check keeps the copy identical).
