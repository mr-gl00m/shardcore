"""SHARDCORE reference implementation.

The single reference library for the .shard bundle format (SHARDCORE spec
PART III): read, verify, diagnose, migrate, and repack bundles, plus the
Neuronshard tick engine. A writer that goes through this library produces a
spec-conformant bundle by construction, so the integrity and save rules of
spec section 9 are satisfied without every app re-deriving them.

Spec: SHARDCORE_Spec_v1.12.md

The bundle I/O surface is stdlib-only; the Neuronshard runtime under
`shardcore.neuron` additionally needs numpy and is imported on demand.
"""

from __future__ import annotations

from .builder import BundleBuildError, build_bundle, json_member_bytes
from .bundle import read_bundle
from .core import (
    anatomy_parts_map,
    common_ancestor,
    compare_revisions,
    merge_bundles,
    merge_members,
    next_revision,
    read_bundle_members,
    revision_errors,
    revision_history,
    write_merge,
)
from .diagnose import diagnose
from .document import BundleDocument, BundleReadError, read_bundle_document
from .lineage import (
    derived_shard_id,
    lineage_errors,
    manifest_digest,
    new_shard_id,
    offspring_lineage,
    shard_id_error,
)
from .migrate import migrate_bundle
from .model import (
    STATUS_BEHIND,
    STATUS_BLOCKED,
    STATUS_CURRENT,
    STATUS_OUTDATED,
    BundleState,
    Diagnosis,
    DriftFinding,
    PillarInfo,
)
from .mutable import MigrationError, MutableBundle, repack_atomic
from .registry import SPEC_VERSION, schema_for_member
from .verify import verify_bundle

__version__ = "1.12.0"
__spec_version__ = SPEC_VERSION

__all__ = [
    "__version__",
    "__spec_version__",
    "read_bundle",
    "read_bundle_document",
    "build_bundle",
    "json_member_bytes",
    "verify_bundle",
    "diagnose",
    "migrate_bundle",
    "MutableBundle",
    "repack_atomic",
    "MigrationError",
    "BundleReadError",
    "BundleBuildError",
    "schema_for_member",
    "new_shard_id",
    "derived_shard_id",
    "manifest_digest",
    "shard_id_error",
    "lineage_errors",
    "offspring_lineage",
    "revision_errors",
    "revision_history",
    "next_revision",
    "compare_revisions",
    "common_ancestor",
    "read_bundle_members",
    "merge_members",
    "merge_bundles",
    "write_merge",
    "anatomy_parts_map",
    "BundleState",
    "BundleDocument",
    "PillarInfo",
    "Diagnosis",
    "DriftFinding",
    "STATUS_CURRENT",
    "STATUS_BEHIND",
    "STATUS_OUTDATED",
    "STATUS_BLOCKED",
]
