"""Turn a BundleState into a Diagnosis: findings plus an overall status.

Migration ids referenced here are the migration chain (SHARDCORE_Spec_v1.12.md
section 12, enumerated in SHARD_UPDATER_PROPOSAL.md section 5). Phase 1 detects
and plans only; it applies nothing.
"""

from __future__ import annotations

from .bundle import CANONICAL_STATS, legacy_asset_members, pillar_variant_members
from .core import OLDEST_KEPT_SPEC
from .document import BundleReadError, read_bundle_document
from .model import (
    SEV_BLOCKED,
    SEV_INFO,
    SEV_OUTDATED,
    STATUS_BEHIND,
    STATUS_BLOCKED,
    STATUS_CURRENT,
    STATUS_OUTDATED,
    BundleState,
    Diagnosis,
    DriftFinding,
)
from .registry import NEURON_SCHEMAS, schema_for_member


def diagnose(state: BundleState, target_spec_version: str) -> Diagnosis:
    findings: list[DriftFinding] = []

    if not state.readable:
        findings.append(
            DriftFinding("unreadable", None, SEV_BLOCKED, state.error or "cannot read bundle")
        )
        return _finish(state, findings)

    _check_blocked(state, target_spec_version, findings)
    _check_outdated(state, target_spec_version, findings)
    _check_strict(state, findings)
    return _finish(state, findings, behind=_is_behind(state, target_spec_version))


def _is_behind(state: BundleState, target: str) -> bool:
    """Whether the bundle conforms to the older version it declares."""
    declared = state.spec_version
    if declared is None or not _is_newer(target, declared) or _is_newer(_OLDEST_KEPT, declared):
        return False
    own: list[DriftFinding] = []
    _check_outdated(state, declared, own)
    _check_strict(state, own)
    return not any(f.severity in (SEV_BLOCKED, SEV_OUTDATED) for f in own)


def _check_strict(state: BundleState, findings: list[DriftFinding]) -> None:
    # "current" has to mean the strict runtime reader accepts the bundle; the
    # lenient read above tolerates things it rejects (a schema-less member, an
    # undeclared one). While migrations are pending the failure stays info,
    # because the chain may repair it and apply re-diagnoses after writing, so
    # an unrepaired bundle fails there and gets its backup back. A bundle
    # already blocked skips the second read.
    if any(f.severity == SEV_BLOCKED for f in findings):
        return
    try:
        read_bundle_document(state.path)
    except BundleReadError as exc:
        pending = any(f.severity == SEV_OUTDATED for f in findings)
        findings.append(
            DriftFinding(
                "strict_read_failed",
                None,
                SEV_INFO if pending else SEV_BLOCKED,
                f"strict reader rejects the bundle: {exc}",
            )
        )


def _check_blocked(state: BundleState, target: str, findings: list[DriftFinding]) -> None:
    # A real hash disagreement blocks. Absent hash data (legacy manifest) does
    # not; that is handled as an outdated finding in _check_outdated.
    if state.has_integrity_data and not state.integrity_ok:
        findings.append(
            DriftFinding("integrity_mismatch", None, SEV_BLOCKED, _integrity_detail(state))
        )
    if state.immutable:
        findings.append(
            DriftFinding(
                "immutable", None, SEV_BLOCKED, "manifest.immutable is true; never written"
            )
        )
    if state.spec_version is not None and _is_newer(state.spec_version, target):
        findings.append(
            DriftFinding(
                "future_spec",
                None,
                SEV_BLOCKED,
                f"spec_version {state.spec_version} is newer than target {target}",
            )
        )
    # An app older than the shard allows saved it and could not know (spec 1.9
    # writers refuse nothing). What it broke is for a person to look at.
    if state.min_writer is not None and _is_newer(
        state.min_writer, state.spec_version or state.bundle_version or "0"
    ):
        findings.append(
            DriftFinding(
                "saved_below_floor",
                None,
                SEV_BLOCKED,
                f"stamped {state.spec_version} by a writer older than min_writer "
                f"{state.min_writer}; restore an earlier copy, or check it and restamp it by hand",
            )
        )
    # A broken identity is fixed by hand, never replaced: replacing it would
    # orphan every lineage entry that already names it.
    if state.shard_id_error is not None:
        findings.append(
            DriftFinding("invalid_shard_id", None, SEV_BLOCKED, f"manifest.{state.shard_id_error}")
        )


def _check_outdated(state: BundleState, target: str, findings: list[DriftFinding]) -> None:
    present = {p.name for p in state.pillars if p.present}

    if (
        _version_tuple(target) >= _IDENTITY_SINCE
        and state.shard_id is None
        and state.shard_id_error is None
    ):
        findings.append(
            DriftFinding("no_shard_id", "0015", SEV_OUTDATED, "manifest has no shard_id")
        )

    # Lineage is provenance, not load state (spec 11.4.2 rule 6): a malformed
    # block is reported for context and never blocks or migrates the bundle.
    if state.lineage_errors:
        shown = "; ".join(state.lineage_errors[:3])
        more = f" (+{len(state.lineage_errors) - 3} more)" if len(state.lineage_errors) > 3 else ""
        findings.append(
            DriftFinding(
                "invalid_lineage",
                None,
                SEV_INFO,
                f"lineage departs from spec 11.4: {shown}{more}",
            )
        )

    # The revision chain is provenance too (spec 11.5): reported, never blocking.
    if state.revision_errors:
        findings.append(
            DriftFinding(
                "invalid_revision",
                None,
                SEV_INFO,
                "revision departs from spec 11.5: " + "; ".join(state.revision_errors[:3]),
            )
        )

    if _version_tuple(target) >= _PARTS_MAP_SINCE and state.anatomy_needs_map:
        findings.append(
            DriftFinding(
                "anatomy_list_shape",
                "0017",
                SEV_OUTDATED,
                "shell anatomy_profile is not the spec 6 parts map",
            )
        )

    if state.spec_version is None:
        findings.append(
            DriftFinding("no_spec_version", "0005", SEV_OUTDATED, "manifest has no spec_version")
        )
    elif _is_newer(target, state.spec_version):
        findings.append(
            DriftFinding(
                "stale_spec_version",
                "0005",
                SEV_OUTDATED,
                f"spec_version {state.spec_version} is behind target {target}",
            )
        )

    if state.bundle_version is not None and state.spec_version is None:
        findings.append(
            DriftFinding(
                "legacy_bundle_version",
                "0005",
                SEV_OUTDATED,
                f"uses legacy bundle_version {state.bundle_version} instead of spec_version",
            )
        )

    if (
        state.bundle_version is not None
        and state.spec_version is not None
        and state.bundle_version != state.spec_version
    ):
        findings.append(
            DriftFinding(
                "stale_bundle_alias",
                "0005",
                SEV_OUTDATED,
                f"deprecated bundle_version alias {state.bundle_version} disagrees with "
                f"spec_version {state.spec_version}",
            )
        )

    if "memoryshard.json" in present and "mindshard.json" not in present:
        findings.append(
            DriftFinding(
                "uses_memoryshard", "0002", SEV_OUTDATED, "memory pillar is memoryshard.json"
            )
        )

    if "memoryshard.json" in present and "mindshard.json" in present:
        findings.append(
            DriftFinding(
                "dual_memory_pillars",
                "0002",
                SEV_OUTDATED,
                "both memoryshard.json and mindshard.json present; mindshard is canonical",
            )
        )

    # Shell and mind are optional pillars (spec sections 6 and 7); bare absence is
    # not drift. A missing shellshard is only a finding when the soul still
    # carries the shell fields migration 0001 would split out.
    if "shellshard.json" not in present and state.soul_has_shell_fields:
        findings.append(
            DriftFinding(
                "missing_shellshard",
                "0001",
                SEV_OUTDATED,
                "soul carries shell fields but no shellshard.json exists",
            )
        )

    if "mindshard.json" not in present and "memoryshard.json" not in present:
        findings.append(
            DriftFinding(
                "missing_mindshard",
                None,
                SEV_INFO,
                "no memory pillar (mind is optional; context only)",
            )
        )

    if state.soul_has_shell_fields:
        findings.append(
            DriftFinding(
                "soul_carries_shell_fields",
                "0001",
                SEV_OUTDATED,
                "soulshard still carries shell fields (anatomy or physical character_state)",
            )
        )

    if state.memory_is_flat:
        findings.append(
            DriftFinding(
                "flat_memory", "0003", SEV_OUTDATED, "memory is flat, not tiered STM/LTM/core"
            )
        )

    if state.manifest_memory_format is not None:
        findings.append(
            DriftFinding(
                "manifest_has_memory_format",
                "0004",
                SEV_OUTDATED,
                "manifest carries memory_format (to be dropped)",
            )
        )

    if (
        state.manifest_memory_format is not None
        and state.mind_format_version is not None
        and state.manifest_memory_format != state.mind_format_version
    ):
        findings.append(
            DriftFinding(
                "memory_format_mismatch",
                "0006",
                SEV_OUTDATED,
                f"manifest memory_format {state.manifest_memory_format} disagrees with "
                f"mindshard format_version {state.mind_format_version}",
            )
        )

    if not state.has_integrity_data:
        findings.append(
            DriftFinding(
                "no_integrity_data", "0011", SEV_OUTDATED, "manifest carries no per-file hashes"
            )
        )
    if not _has_schema_ids(state):
        findings.append(
            DriftFinding("no_schema_ids", "0009", SEV_OUTDATED, "manifest files lack schema ids")
        )
    stale = _stale_schema_members(state, target)
    if stale:
        findings.append(
            DriftFinding(
                "stale_schema_ids",
                "0009",
                SEV_OUTDATED,
                "schema ids behind the registry: " + ", ".join(stale[:5]),
            )
        )

    if state.has_naive_timestamp:
        findings.append(
            DriftFinding(
                "non_utc_timestamps", "0007", SEV_OUTDATED, "manifest timestamps are not UTC"
            )
        )

    if state.soul_has_x_nexus:
        findings.append(
            DriftFinding(
                "soul_runtime_extensions",
                "0010",
                SEV_OUTDATED,
                "soulshard carries recursion-runtime fields; re-nest under x_nexus",
            )
        )

    if state.soul_stat_keys is not None:
        keys = set(state.soul_stat_keys)
        if not keys:
            findings.append(
                DriftFinding(
                    "no_stat_block", "0013", SEV_OUTDATED, "soulshard has no ten-stat stat_block"
                )
            )
        elif keys != CANONICAL_STATS:
            parts: list[str] = []
            extra = sorted(keys - CANONICAL_STATS)
            missing = sorted(CANONICAL_STATS - keys)
            if extra:
                parts.append("extra: " + ", ".join(extra))
            if missing:
                parts.append("missing: " + ", ".join(missing))
            findings.append(
                DriftFinding(
                    "nonstandard_stat_block",
                    "0013",
                    SEV_OUTDATED,
                    "stat_block deviates from the canonical ten (" + "; ".join(parts) + ")",
                )
            )

    assets = legacy_asset_members(state.members)
    if assets:
        shown = ", ".join(assets[:5])
        more = f" (+{len(assets) - 5} more)" if len(assets) > 5 else ""
        findings.append(
            DriftFinding(
                "legacy_asset_layout",
                "0014",
                SEV_OUTDATED,
                f"assets in legacy top-level folders; consolidate under assets/: {shown}{more}",
            )
        )

    variants = pillar_variant_members(state.members)
    if variants:
        shown = ", ".join(variants[:5])
        more = f" (+{len(variants) - 5} more)" if len(variants) > 5 else ""
        findings.append(
            DriftFinding(
                "duplicate_pillar_variants",
                "0012",
                SEV_OUTDATED,
                f"duplicate or mislabeled pillar members to consolidate: {shown}{more}",
            )
        )


def _integrity_detail(state: BundleState) -> str:
    bad = [p.name for p in state.pillars if p.present and p.manifest_sha256 and not p.integrity_ok]
    missing = [p.name for p in state.pillars if not p.present and p.manifest_sha256]
    parts: list[str] = []
    if bad:
        parts.append("hash or size mismatch: " + ", ".join(bad))
    if missing:
        parts.append("listed but missing: " + ", ".join(missing))
    return "; ".join(parts) if parts else "manifest integrity check failed"


def _has_schema_ids(state: BundleState) -> bool:
    """Schema ids are required on every listed member the registry can map.

    Images and attestation receipts now map to shardcore/assets@1.0 (spec 2.3),
    so they are no longer exempt. Only members with no registry mapping at all
    (unknown vendor files) are skipped: the library never invents a schema id.
    """
    listed = [p for p in state.pillars if p.manifest_sha256 is not None]
    mappable = [p for p in listed if schema_for_member(p.name) is not None]
    if not mappable:
        return False
    return all(p.declared_schema is not None for p in mappable)


def _stale_schema_members(state: BundleState, target: str) -> list[str]:
    """Listed members whose declared schema id is not the one a bundle of the
    target version carries (a shell still declaring shell@1.9 at spec 1.11).
    0009 restamps."""
    stale: list[str] = []
    for pillar in state.pillars:
        expected = schema_for_member(pillar.name, spec=target)
        if pillar.name == "neuronshard.json":
            # A neuronshard is stamped by the version its document declares.
            expected = NEURON_SCHEMAS.get(pillar.declared_version or "", expected)
        if (
            pillar.manifest_sha256 is not None
            and pillar.declared_schema is not None
            and expected is not None
            and pillar.declared_schema != expected
        ):
            stale.append(f"{pillar.name} ({pillar.declared_schema} -> {expected})")
    return stale


# Before this no current writer produces a bundle's form, so it is never just behind.
_OLDEST_KEPT = OLDEST_KEPT_SPEC
# manifest.shard_id joined the format at spec 1.10 and the anatomy parts map
# at 1.11; diagnosing against an older target must not demand either.
_IDENTITY_SINCE = (1, 10)
_PARTS_MAP_SINCE = (1, 11)


def _is_newer(candidate: str, target: str) -> bool:
    return _version_tuple(candidate) > _version_tuple(target)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in value.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _finish(state: BundleState, findings: list[DriftFinding], *, behind: bool = False) -> Diagnosis:
    severities = {f.severity for f in findings}
    if SEV_BLOCKED in severities:
        status = STATUS_BLOCKED
    elif SEV_OUTDATED in severities:
        status = STATUS_BEHIND if behind else STATUS_OUTDATED
    else:
        status = STATUS_CURRENT
    return Diagnosis(
        path=state.path,
        identity=state.identity,
        status=status,
        findings=tuple(findings),
        state=state,
    )
