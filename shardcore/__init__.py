"""SHARDCORE reference implementation.

The single reference library for the .shard bundle format (SHARDCORE spec
PART III): read, verify, diagnose, migrate, and repack bundles, plus the
Neuronshard tick engine. A writer that goes through this library produces a
spec-conformant v1.9 bundle by construction, so the integrity and save rules
of spec section 9 are satisfied without every app re-deriving them.

Spec: SHARDCORE_Spec_v1.9.md

The bundle I/O surface is stdlib-only; the Neuronshard runtime under
`shardcore.neuron` additionally needs numpy and is imported on demand.
"""

from __future__ import annotations

from .bundle import read_bundle
from .diagnose import diagnose
from .migrate import migrate_bundle
from .model import (
    STATUS_BLOCKED,
    STATUS_CURRENT,
    STATUS_OUTDATED,
    BundleState,
    Diagnosis,
    DriftFinding,
    PillarInfo,
)
from .mutable import MigrationError, MutableBundle, repack_atomic
from .registry import schema_for_member
from .verify import verify_bundle

__version__ = "1.9.0"
__spec_version__ = "1.9"

__all__ = [
    "__version__",
    "__spec_version__",
    "read_bundle",
    "verify_bundle",
    "diagnose",
    "migrate_bundle",
    "MutableBundle",
    "repack_atomic",
    "MigrationError",
    "schema_for_member",
    "BundleState",
    "PillarInfo",
    "Diagnosis",
    "DriftFinding",
    "STATUS_CURRENT",
    "STATUS_OUTDATED",
    "STATUS_BLOCKED",
]
