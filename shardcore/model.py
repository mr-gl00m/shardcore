"""Immutable data structures shared across the read-only pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Status values a diagnosed shard can carry.
STATUS_CURRENT = "current"
STATUS_OUTDATED = "outdated"
STATUS_BLOCKED = "blocked"

# Finding severities. "blocked" means do-not-touch (manual attention). "outdated"
# means a v1 migration would run. "deferred" means a migration exists but is held
# back pending a format decision. "info" is context only.
SEV_BLOCKED = "blocked"
SEV_OUTDATED = "outdated"
SEV_DEFERRED = "deferred"
SEV_INFO = "info"


@dataclass(frozen=True)
class PillarInfo:
    """Per-file integrity and version view inside one bundle."""

    name: str
    present: bool
    declared_schema: str | None
    declared_version: str | None
    manifest_sha256: str | None
    computed_sha256: str | None
    manifest_size: int | None
    actual_size: int | None
    integrity_ok: bool


@dataclass(frozen=True)
class BundleState:
    """Everything the reader could learn about a bundle without modifying it."""

    path: Path
    readable: bool
    is_zip: bool
    manifest_present: bool
    identity: str
    spec_version: str | None
    bundle_version: str | None
    manifest_memory_format: str | None
    mind_format_version: str | None
    soul_version: str | None
    immutable: bool
    pillars: tuple[PillarInfo, ...]
    members: tuple[str, ...]
    has_integrity_data: bool
    integrity_ok: bool
    soul_has_shell_fields: bool
    soul_has_x_nexus: bool
    soul_stat_keys: tuple[str, ...] | None
    memory_is_flat: bool
    has_naive_timestamp: bool
    error: str | None


@dataclass(frozen=True)
class DriftFinding:
    """One reason a shard is not at the target format."""

    code: str
    migration: str | None
    severity: str
    detail: str


@dataclass(frozen=True)
class Diagnosis:
    """A bundle plus the findings and overall status derived from it."""

    path: Path
    identity: str
    status: str
    findings: tuple[DriftFinding, ...]
    state: BundleState
