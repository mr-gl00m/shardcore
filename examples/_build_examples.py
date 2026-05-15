"""Regenerate the example bundles in examples/.

Run this script from the repo root:

    python examples/_build_examples.py

It writes `minimal.shard` and `standard.shard` next to itself. Both
bundles are built from fictional characters and contain no personal,
proprietary, or private content. They are shaped to pass the full
conformance suite in `tests/conformance/`.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))

from shardcore.neuron import (  # noqa: E402
    DT_SUBSTEP,
    LIFNetwork,
    build_brain_from_shard,
    neuronshard_from_runtime,
)


# ─── Characters ──────────────────────────────────────────────

THORNE_VALE_SOUL = {
    "name": "Thorne Vale",
    "identity": (
        "Thorne is an archivist of lost languages — a quiet scholar who "
        "spends their days with brittle codices and dead tongues. They "
        "believe every silenced voice leaves a trace worth finding."
    ),
    "personality": (
        "Patient, meticulous, faintly melancholic. Given to long silences "
        "that land kindly rather than coldly."
    ),
    "stat_block": {
        "STR": 3, "END": 5, "VIG": 4, "DEX": 5,
        "TMP": 7, "ACU": 9, "INS": 8, "ATT": 6,
        "CNV": 6, "PRS": 4,
    },
    "nature": {
        "label": "quietly devoted",
        "increased_stat": "ACU",
        "decreased_stat": "PRS",
    },
    "emotional_states": ["Melancholic Longing", "Fierce Loyalty"],
    "trait_tags": [
        "likes: margins and marginalia",
        "hates: censorship",
        "carries: a silver pen that was their mentor's",
    ],
    "friendship": 6,
    "appearance_profile": {
        "hair": "ink-dark, often tied back",
        "eyes": "pale grey",
        "build": "slight, careful-moving",
        "clothing": "layered linen, ink-stained cuffs",
    },
}


CASSIA_MERIDIAN_SOUL = {
    "name": "Cassia Meridian",
    "identity": (
        "Cassia is a stellar cartographer aboard a long-haul survey ship. "
        "Her work is to draw maps of things that are already moving — "
        "stars, currents, drifting hulks. She does it with the patience "
        "of someone who has learned that everything important is in motion."
    ),
    "personality": (
        "Direct, curious, dryly funny. Protective of her crew and her "
        "instruments in roughly that order."
    ),
    "stat_block": {
        "STR": 5, "END": 7, "VIG": 6, "DEX": 6,
        "TMP": 6, "ACU": 8, "INS": 7, "ATT": 7,
        "CNV": 7, "PRS": 6,
    },
    "nature": {
        "label": "steady under drift",
        "increased_stat": "INS",
        "decreased_stat": "TMP",
    },
    "emotional_states": ["Fierce Loyalty", "Playful Menace", "Raw Vulnerability"],
    "trait_tags": [
        "likes: clean sextant glass",
        "likes: her crew",
        "dislikes: hierarchy-worship",
        "carries: a worn almanac her grandmother annotated",
    ],
    "friendship": 7,
    "appearance_profile": {
        "hair": "close-cropped, silver at the temples",
        "eyes": "hazel, usually squinting at something far away",
        "build": "long-limbed, spacer's leanness",
        "clothing": "soft crew fatigues and a worn flight jacket",
    },
}


CASSIA_SHELL = {
    "anatomy_profile": {
        "height_cm": 178,
        "body_type": "lean, long-limbed",
        "handedness": "right",
    },
    "identity_image_path": "images/cassia_identity.png",
    "appearance_image_path": "images/cassia_appearance.png",
    "character_state": {
        "posture": "seated at a chart table",
        "health": 1.0,
        "fatigue": 0.25,
    },
}


CASSIA_MIND = {
    "version": "2.1",
    "session_counter": 3,
    "short_term": [
        {
            "id": "stm_001",
            "text": "Third anomaly this week in the Velen drift. Logged, waiting on confirmation.",
            "tags": ["work", "velen"],
            "weight": 0.4,
        },
    ],
    "long_term": [
        {
            "id": "ltm_001",
            "text": "The Ashira jump took twelve days and she lost a transponder. She still keeps the flight log.",
            "tags": ["memory", "ashira", "loss"],
            "weight": 0.7,
        },
    ],
    "core": [
        {
            "id": "core_001",
            "text": "Maps are how you love something that keeps moving.",
            "tags": ["philosophy"],
            "weight": 1.0,
        },
    ],
    "archive": [],
    "dream_log": [],
    "vitality": {"bond": 0.6, "focus": 0.7, "calm": 0.55},
}


# ─── Bundle writer (same shape as tests/conformance/conftest.py) ─

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bundle(path: Path, *, shard_name: str, pillars: dict[str, dict]) -> None:
    encoded = {
        name: json.dumps(obj, sort_keys=True, indent=2).encode("utf-8")
        for name, obj in pillars.items()
    }
    manifest = {
        "bundle_version": "1.0",
        "shard_name": shard_name,
        "created": "2026-04-16T00:00:00Z",
        "last_modified": "2026-04-16T00:00:00Z",
        "card": {
            "name": shard_name,
            "core_essence": pillars["soulshard.json"].get("personality", "")[:140],
        },
        "files": {
            name: {"sha256": sha256_hex(data), "size": len(data)}
            for name, data in encoded.items()
        },
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_bytes)
        for name, data in encoded.items():
            zf.writestr(name, data)


# ─── Example builders ────────────────────────────────────────

def build_minimal(out: Path) -> None:
    write_bundle(
        out,
        shard_name="Thorne Vale",
        pillars={"soulshard.json": THORNE_VALE_SOUL},
    )


def build_standard(out: Path) -> None:
    soul = CASSIA_MERIDIAN_SOUL
    graph = build_brain_from_shard(soul, seed=1616)
    net = LIFNetwork(len(graph.nodes), graph.build_weight_matrix())
    np.random.seed(1616)
    noise_mask = graph.get_noise_mask()
    # Pre-warm for 100 ticks so the loaded bundle already has activity.
    net.tick(
        n_steps=100,
        dt=DT_SUBSTEP,
        noise_mask=noise_mask,
        noise_rate=100.0,
        hebbian=True,
    )
    neuron_data = neuronshard_from_runtime(graph, net)
    write_bundle(
        out,
        shard_name="Cassia Meridian",
        pillars={
            "soulshard.json": soul,
            "shellshard.json": CASSIA_SHELL,
            "mindshard.json": CASSIA_MIND,
            "neuronshard.json": neuron_data,
        },
    )


def main() -> int:
    minimal = HERE / "minimal.shard"
    standard = HERE / "standard.shard"
    build_minimal(minimal)
    build_standard(standard)
    print(f"wrote {minimal}  ({minimal.stat().st_size} bytes)")
    print(f"wrote {standard} ({standard.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
