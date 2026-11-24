"""Shard identity and lineage (spec section 11.4).

`shard_id` names an identity across every save; `lineage` records where a
bundle came from. One block holds two shapes: a branch (the same character
retold, one `parent`) and an offspring (a new individual, one or more
`parents`).

The identity primitives (canonical form, digest, id minting) live in core.py
and are re-exported here. Validation returns problems instead of raising. A
reader must tolerate malformed lineage (spec 11.4.2 rule 6) while a writer or
breeder must refuse it, so each caller decides what a problem means for it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from .core import (
    BRANCH_RELATIONSHIPS,
    IDENTITY_NAMESPACE,
    MAX_SHARD_ID_LENGTH,
    SHA256_HEX,
    canonical_json_bytes,
    derived_shard_id,
    manifest_digest,
    new_shard_id,
    shard_id_error,
)

if TYPE_CHECKING:
    from .document import BundleDocument

__all__ = [
    "BRANCH_RELATIONSHIPS",
    "IDENTITY_NAMESPACE",
    "MAX_SHARD_ID_LENGTH",
    "OFFSPRING",
    "ORIGINAL",
    "RELATIONSHIPS",
    "canonical_json_bytes",
    "derived_shard_id",
    "lineage_errors",
    "lineage_parent_ids",
    "manifest_digest",
    "new_shard_id",
    "offspring_lineage",
    "shard_id_error",
]

ORIGINAL = "original"
OFFSPRING = "offspring"
RELATIONSHIPS = BRANCH_RELATIONSHIPS | {ORIGINAL, OFFSPRING}


def lineage_errors(lineage: Any) -> list[str]:
    """Every way `lineage` departs from spec 11.4.2. Empty means valid."""
    if not isinstance(lineage, Mapping):
        return ["lineage must be an object"]
    relationship = lineage.get("relationship")
    if not isinstance(relationship, str) or relationship not in RELATIONSHIPS:
        # The rest of the shape depends on the relationship; stop here.
        return [f"lineage.relationship must be one of: {', '.join(sorted(RELATIONSHIPS))}"]
    if relationship == OFFSPRING:
        return _offspring_errors(lineage)
    if relationship == ORIGINAL:
        return [
            f"lineage.{key} is not allowed for an original"
            for key in ("parent", "parents")
            if key in lineage
        ]
    return _branch_errors(lineage)


def lineage_parent_ids(lineage: Any) -> set[str]:
    """The parent shard_ids a lineage block names, whatever its shape."""
    if not isinstance(lineage, Mapping):
        return set()
    entries: list[Any] = [lineage.get("parent")]
    parents = lineage.get("parents")
    if isinstance(parents, list):
        entries.extend(parents)
    return {
        entry["shard_id"]
        for entry in entries
        if isinstance(entry, Mapping) and isinstance(entry.get("shard_id"), str)
    }


def offspring_lineage(parents: Sequence[tuple[str, BundleDocument]]) -> dict[str, Any]:
    """Build an offspring lineage block from `(role, document)` pairs.

    A BundleDocument exists only after read_bundle_document verified every
    member, so spec 11.4.2 rule 3 (verify a parent before pinning it) holds by
    construction. Parents are listed in the order given. A parent whose
    shard_id is present but invalid is refused rather than silently unnamed.
    """
    if not parents:
        raise ValueError("offspring needs at least one parent")
    entries: list[dict[str, Any]] = []
    for role, document in parents:
        if not isinstance(role, str) or not role.strip():
            raise ValueError("every parent needs a non-empty role")
        manifest = document.manifest()
        entry: dict[str, Any] = {"role": role, "manifest_sha256": document.manifest_sha256}
        if "shard_id" in manifest:
            problem = shard_id_error(manifest["shard_id"])
            if problem is not None:
                raise ValueError(f"parent {document.path.name}: {problem}")
            entry["shard_id"] = manifest["shard_id"]
        label = _label(manifest)
        if label is not None:
            entry["label"] = label
        entries.append(entry)
    return {"relationship": OFFSPRING, "parents": entries}


def _offspring_errors(lineage: Mapping[str, Any]) -> list[str]:
    errors = [
        f"lineage.{key} is not allowed for offspring"
        for key in ("parent", "ancestry", "branch_point")
        if key in lineage
    ]
    parents = lineage.get("parents")
    if not isinstance(parents, list) or not parents:
        errors.append("lineage.parents must be a non-empty array")
        return errors
    for index, entry in enumerate(parents):
        where = f"lineage.parents[{index}]"
        if not isinstance(entry, Mapping):
            errors.append(f"{where} must be an object")
            continue
        role = entry.get("role")
        if not isinstance(role, str) or not role.strip():
            errors.append(f"{where}.role must be a non-empty string")
        errors.extend(_pin_errors(entry, where))
    return errors


def _branch_errors(lineage: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if "parents" in lineage:
        errors.append("lineage.parents is only allowed for offspring")
    parent = lineage.get("parent")
    if isinstance(parent, Mapping):
        errors.extend(_pin_errors(parent, "lineage.parent"))
    else:
        errors.append("lineage.parent must be an object")
    ancestry = lineage.get("ancestry")
    if ancestry is not None and not _is_string_list(ancestry):
        errors.append("lineage.ancestry must be an array of strings")
    branch_point = lineage.get("branch_point")
    if branch_point is not None:
        if isinstance(branch_point, Mapping):
            for key in ("inherited_canon", "dropped_canon"):
                value = branch_point.get(key)
                if value is not None and not _is_string_list(value):
                    errors.append(f"lineage.branch_point.{key} must be an array of strings")
        else:
            errors.append("lineage.branch_point must be an object")
    origin = lineage.get("origin_appearance")
    if origin is not None and not isinstance(origin, Mapping):
        errors.append("lineage.origin_appearance must be an object")
    return errors


def _pin_errors(entry: Mapping[str, Any], where: str) -> list[str]:
    errors: list[str] = []
    digest = entry.get("manifest_sha256")
    if not isinstance(digest, str) or not SHA256_HEX.fullmatch(digest):
        errors.append(f"{where}.manifest_sha256 must be 64 lowercase hex characters")
    if "shard_id" in entry:
        problem = shard_id_error(entry["shard_id"])
        if problem is not None:
            errors.append(f"{where}.{problem}")
    label = entry.get("label")
    if label is not None and not isinstance(label, str):
        errors.append(f"{where}.label must be a string")
    return errors


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _label(manifest: Mapping[str, Any]) -> str | None:
    card = manifest.get("card")
    if isinstance(card, Mapping):
        name = card.get("name")
        if isinstance(name, str) and name.strip():
            return name
    name = manifest.get("shard_name")
    if isinstance(name, str) and name.strip():
        return name
    return None
