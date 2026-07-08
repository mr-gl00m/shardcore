"""Schema-id registry for v1.9 (spec PART III pillar registry).

schema_for_member answers "what schema id does this archive member carry at
v1.9", or None for members the registry cannot map (unknown vendor files).

Every static asset (images, OpenTimestamps receipts, skills, references)
lives under one `assets/` folder and carries one schema id,
`shardcore/assets@1.0` (spec 2.3). There is no singular `asset` id. The
legacy top-level folders (`images/`, `skills/`, ...) still map here so a
pre-migration bundle stamps consistently before migration 0014 relocates
them under `assets/`.
"""

from __future__ import annotations

# The one asset schema (spec 2.3): everything under assets/. Integrity by
# hash is the baseline contract; JSON assets may carry their own structure.
ASSETS_SCHEMA = "shardcore/assets@1.0"

PILLAR_SCHEMAS: dict[str, str] = {
    "soulshard.json": "shardcore/soul@1.9",
    "shellshard.json": "shardcore/shell@1.9",
    "mindshard.json": "shardcore/mind@2.1",
    "memoryshard.json": "shardcore/mind@2.1",
    "neuronshard.json": "shardcore/neuron@1.0",
    "canonshard.json": "shardcore/canon@1.0",
    "statshard.json": "shardcore/stat@1.0",
    "driveshard.json": "shardcore/drive@0.1",
    "worldshard.json": "shardcore/world@1.0",
}

_PREFIX_SCHEMAS: tuple[tuple[str, str], ...] = (
    ("body/", "shardcore/body@1.0"),
    ("assets/", ASSETS_SCHEMA),
    # Legacy top-level asset folders, still mapped pre-consolidation (0014).
    ("images/", ASSETS_SCHEMA),
    ("attestations/", ASSETS_SCHEMA),
    ("skills/", ASSETS_SCHEMA),
    ("references/", ASSETS_SCHEMA),
)

# Loose binaries not under a known prefix still map to the asset schema by
# extension, so a stray portrait or receipt is never left without an id.
_ASSET_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".ots",
)


def schema_for_member(name: str) -> str | None:
    """The v1.9 schema id for an archive member, or None when unmappable."""
    direct = PILLAR_SCHEMAS.get(name)
    if direct is not None:
        return direct
    for prefix, schema in _PREFIX_SCHEMAS:
        if name.startswith(prefix):
            return schema
    if name.lower().endswith(_ASSET_EXTENSIONS):
        return ASSETS_SCHEMA
    return None
