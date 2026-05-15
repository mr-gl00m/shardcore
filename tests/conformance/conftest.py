"""Shared fixtures — builds the reference bundles that the conformance
suite runs against.

Fixtures intentionally live here (not under examples/) so the conformance
tests are self-sufficient and don't depend on the shipped example bundles
existing on disk. Malformed-bundle cases are also constructed in-memory
rather than stored as an on-disk corpus.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from shardcore.neuron import (
    DT_SUBSTEP,
    LIFNetwork,
    build_brain_from_shard,
    neuronshard_from_runtime,
)


# ─── Pillar fixtures ─────────────────────────────────────────

def minimal_soulshard() -> dict:
    """The smallest soulshard that satisfies spec §3.1 required fields."""
    return {
        "name": "Minimal",
        "identity": "A reference character used by the conformance suite.",
        "personality": "Cooperative, deterministic, uncomplicated.",
        "stat_block": {
            "STR": 5, "END": 5, "VIG": 5, "DEX": 5,
            "TMP": 5, "ACU": 5, "INS": 5, "ATT": 5,
            "CNV": 5, "PRS": 5,
        },
        "nature": {
            "label": "balanced",
            "increased_stat": "ACU",
            "decreased_stat": "STR",
        },
        "emotional_states": ["Fierce Loyalty"],
        "trait_tags": ["likes: tests", "hates: flakiness"],
        "friendship": 5,
    }


def standard_shellshard() -> dict:
    return {
        "anatomy_profile": {"height_cm": 170, "body_type": "athletic"},
        "identity_image_path": "images/identity.png",
        "appearance_image_path": "images/appearance.png",
        "character_state": {"posture": "standing", "health": 1.0},
    }


def standard_mindshard() -> dict:
    return {
        "version": "2.1",
        "short_term": [],
        "long_term": [],
        "core": [
            {"id": "core_001", "text": "Conformance tests matter.", "weight": 1.0},
        ],
        "archive": [],
        "dream_log": [],
        "vitality": {"bond": 0.5, "focus": 0.5, "calm": 0.5},
        "session_counter": 0,
    }


# ─── Bundle builder ──────────────────────────────────────────

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_bundle(
    path: Path,
    *,
    soul: dict,
    shell: dict | None = None,
    mind: dict | None = None,
    neuron: dict | None = None,
    bundle_version: str = "1.0",
    shard_name: str = "conformance",
) -> Path:
    """Write a conformant .shard to `path`. Returns the path."""
    pillars: dict[str, bytes] = {}
    pillars["soulshard.json"] = json.dumps(soul, sort_keys=True).encode("utf-8")
    if shell is not None:
        pillars["shellshard.json"] = json.dumps(shell, sort_keys=True).encode("utf-8")
    if mind is not None:
        pillars["mindshard.json"] = json.dumps(mind, sort_keys=True).encode("utf-8")
    if neuron is not None:
        pillars["neuronshard.json"] = json.dumps(neuron, sort_keys=True).encode("utf-8")

    manifest = {
        "bundle_version": bundle_version,
        "shard_name": shard_name,
        "files": {
            name: {"sha256": _sha256_hex(data), "size": len(data)}
            for name, data in pillars.items()
        },
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_bytes)
        for name, data in pillars.items():
            zf.writestr(name, data)

    return path


def build_bundle_with_neuron(
    path: Path,
    *,
    seed: int = 42,
    pre_tick_steps: int = 0,
) -> Path:
    """Build a bundle that includes a neuronshard, optionally pre-ticked."""
    soul = minimal_soulshard()
    graph = build_brain_from_shard(soul, seed=seed)
    W = graph.build_weight_matrix()
    net = LIFNetwork(len(graph.nodes), W)
    if pre_tick_steps > 0:
        np.random.seed(seed)
        noise_mask = graph.get_noise_mask()
        net.tick(
            n_steps=pre_tick_steps,
            dt=DT_SUBSTEP,
            noise_mask=noise_mask,
            noise_rate=100.0,
        )
    neuron_data = neuronshard_from_runtime(graph, net)
    return build_bundle(
        path,
        soul=soul,
        shell=standard_shellshard(),
        mind=standard_mindshard(),
        neuron=neuron_data,
    )


# ─── Pytest fixtures ─────────────────────────────────────────

@pytest.fixture
def minimal_bundle(tmp_path: Path) -> Path:
    return build_bundle(tmp_path / "minimal.shard", soul=minimal_soulshard())


@pytest.fixture
def standard_bundle(tmp_path: Path) -> Path:
    return build_bundle(
        tmp_path / "standard.shard",
        soul=minimal_soulshard(),
        shell=standard_shellshard(),
        mind=standard_mindshard(),
    )


@pytest.fixture
def neuron_bundle(tmp_path: Path) -> Path:
    return build_bundle_with_neuron(tmp_path / "neuron.shard", seed=1, pre_tick_steps=50)


# ─── Bundle mutation helpers ─────────────────────────────────

def rewrite_bundle_file(src: Path, dst: Path, target: str, new_bytes: bytes) -> None:
    """Copy `src` to `dst`, replacing `target`'s contents with `new_bytes`.

    The manifest is NOT updated — so the tampered bundle's manifest
    digest no longer matches the stored bytes. This is the scenario
    the integrity check must catch.
    """
    with zipfile.ZipFile(src, "r") as src_zf, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as dst_zf:
        for info in src_zf.infolist():
            data = new_bytes if info.filename == target else src_zf.read(info.filename)
            dst_zf.writestr(info, data)


def drop_bundle_file(src: Path, dst: Path, target: str) -> None:
    """Copy `src` to `dst`, omitting `target`. Manifest stays intact."""
    with zipfile.ZipFile(src, "r") as src_zf, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as dst_zf:
        for info in src_zf.infolist():
            if info.filename == target:
                continue
            dst_zf.writestr(info, src_zf.read(info.filename))
