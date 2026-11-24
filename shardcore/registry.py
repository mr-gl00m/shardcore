"""Spec version and schema-id registry (spec section 3, PART III pillar registry).

SPEC_VERSION is the newest spec this library implements and migrates to;
NEW_SHARD_SPEC is what it stamps on a new shard. A save keeps a shard's own.
The values live in core.py (the vendorable implementation); this module is
the registry's name inside the package. schema_for_member answers "what schema
id does this archive member carry", or None for members the registry cannot
map (unknown vendor files).

Every static asset (images, OpenTimestamps receipts, skills, references)
lives under one `assets/` folder and carries one schema id,
`shardcore/assets@1.0` (spec 2.3). There is no singular `asset` id. The
legacy top-level folders (`images/`, `skills/`, ...) still map here so a
pre-migration bundle stamps consistently before migration 0014 relocates
them under `assets/`.
"""

from __future__ import annotations

from .core import (
    ASSETS_SCHEMA,
    NEURON_SCHEMAS,
    NEW_SHARD_SPEC,
    PILLAR_SCHEMAS,
    SPEC_VERSION,
    schema_for_member,
)

__all__ = [
    "ASSETS_SCHEMA",
    "NEURON_SCHEMAS",
    "NEW_SHARD_SPEC",
    "PILLAR_SCHEMAS",
    "SPEC_VERSION",
    "schema_for_member",
]
