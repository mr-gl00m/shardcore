"""Regenerate the example bundles in examples/.

Run this script from the repo root:

    python examples/_build_examples.py

It writes `minimal.shard` and `standard.shard` next to itself, then reads each
one back through the library and asserts it verifies clean and diagnoses as
`current` at spec v1.9. Both bundles are built from fictional characters and
contain no personal, proprietary, or private content. They are shaped to pass
the conformance suite in `tests/conformance/`.

The manifests are authored directly here (not migrated), but every schema id is
resolved through `shardcore.registry.schema_for_member`, and the final
verify/diagnose pass uses the real library reader, so an example that drifts
from the spec fails the build.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))

from shardcore import diagnose, read_bundle  # noqa: E402
from shardcore.neuron import (  # noqa: E402
    DT_SUBSTEP,
    LIFNetwork,
    build_brain_from_shard,
    neuronshard_from_runtime,
)
from shardcore.registry import schema_for_member  # noqa: E402
from shardcore.verify import verify_bundle  # noqa: E402

STAMP = "2026-07-08T00:00:00Z"


# Characters

THORNE_VALE_SOUL = {
    "name": "Thorne Vale",
    "title": "Archivist of Lost Languages",
    "role": "Scholarly companion",
    "core_essence": "Patient keeper of silenced voices.",
    "identity": (
        "Thorne is an archivist of lost languages, a quiet scholar who spends "
        "their days with brittle codices and dead tongues. They believe every "
        "silenced voice leaves a trace worth finding."
    ),
    "personality": (
        "Patient, meticulous, faintly melancholic. Given to long silences that "
        "land kindly rather than coldly."
    ),
    "resonance": "a quiet catalog of what was almost forgotten",
    "stat_block": {
        "STR": 3,
        "END": 5,
        "VIG": 4,
        "DEX": 5,
        "TMP": 7,
        "ACU": 9,
        "INS": 8,
        "ATT": 6,
        "CNV": 6,
        "PRS": 4,
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
    "title": "Stellar Cartographer",
    "role": "Survey-ship companion",
    "core_essence": "Draws maps of things that keep moving.",
    "identity": (
        "Cassia is a stellar cartographer aboard a long-haul survey ship. Her "
        "work is to draw maps of things that are already moving: stars, "
        "currents, drifting hulks. She does it with the patience of someone who "
        "has learned that everything important is in motion."
    ),
    "personality": (
        "Direct, curious, dryly funny. Protective of her crew and her "
        "instruments in roughly that order."
    ),
    "resonance": "steady hands on a drifting chart",
    "stat_block": {
        "STR": 5,
        "END": 7,
        "VIG": 6,
        "DEX": 6,
        "TMP": 6,
        "ACU": 8,
        "INS": 7,
        "ATT": 7,
        "CNV": 7,
        "PRS": 6,
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
    "identity_image_path": "assets/images/cassia_portrait.png",
    "appearance_image_path": "assets/images/cassia_portrait.png",
    "character_state": {
        "posture": "seated at a chart table",
        "health": 1.0,
        "fatigue": 0.25,
    },
}


CASSIA_MIND = {
    "format_version": "2.1",
    "short_term": {
        "max_slots": 8,
        "slots": [
            {
                "id": "stm_001",
                "text": "Third anomaly this week in the Velen drift. Logged, waiting on confirmation.",
                "tags": ["work", "velen"],
                "weight": 0.4,
            },
        ],
    },
    "long_term": {
        "max_slots": 8,
        "slots": [
            {
                "id": "ltm_001",
                "text": "The Ashira jump took twelve days and she lost a transponder. She still keeps the flight log.",
                "tags": ["memory", "ashira", "loss"],
                "weight": 0.7,
            },
        ],
    },
    "core": [
        {
            "id": "core_001",
            "text": "Maps are how you love something that keeps moving.",
            "tags": ["philosophy"],
            "weight": 1.0,
        },
    ],
    "archive": [],
    "vitality": {"bond": 0.6, "focus": 0.7, "calm": 0.55},
    "dream_log": [],
}


CASSIA_CANON = {
    "format_version": "1.0",
    "events": [
        {
            "id": "canon_001",
            "title": "The Ashira Jump",
            "summary": "Twelve days lost in the Ashira corridor. One transponder gone; the flight log kept.",
            "established_utc": STAMP,
            "immutable": True,
            "tags": ["origin", "loss"],
        },
    ],
}


CASSIA_STAT = {
    "format_version": "1.0",
    "blocks": {
        "dnd5e": {
            "level": 6,
            "proficiency_bonus": 3,
            "STR": 10,
            "DEX": 15,
            "CON": 13,
            "INT": 16,
            "WIS": 14,
            "CHA": 12,
        },
    },
}


def _tiny_png(size: int = 16, rgb: tuple[int, int, int] = (60, 70, 90)) -> bytes:
    """A small, valid, solid-color RGB PNG. Keeps the assets pillar tiny."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit, color type 2 (RGB)
    row = b"\x00" + bytes(rgb) * size  # filter byte 0, then the pixel row
    idat = zlib.compress(row * size, 9)
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# Bundle writer


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bundle(
    path: Path,
    *,
    shard_name: str,
    json_pillars: dict[str, dict],
    binary_members: dict[str, bytes] | None = None,
    conformance: dict[str, str] | None = None,
    session_counter: int | None = None,
) -> None:
    binary_members = binary_members or {}
    encoded: dict[str, bytes] = {
        name: json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
        for name, obj in json_pillars.items()
    }
    encoded.update(binary_members)

    soul = json_pillars["soulshard.json"]
    card = {"name": soul["name"]}
    for key in ("title", "role", "core_essence"):
        if soul.get(key):
            card[key] = soul[key]
    card.setdefault("core_essence", soul.get("personality", "")[:140])
    tags = soul.get("trait_tags")
    if isinstance(tags, list):
        card["tags"] = [t for t in tags if isinstance(t, str)][:12]

    files: dict[str, dict] = {}
    for name, data in encoded.items():
        entry: dict[str, object] = {}
        schema = schema_for_member(name)
        if schema is not None:
            entry["schema"] = schema
        entry["sha256"] = _sha256(data)
        entry["size"] = len(data)
        files[name] = entry

    manifest: dict[str, object] = {
        "spec_version": "1.9",
        "bundle_version": "1.9",  # deprecated alias, spec section 2.2
        "created": STAMP,
        "last_modified_utc": STAMP,
        "shard_name": shard_name,
        "immutable": False,
        "card": card,
        "files": files,
    }
    if conformance is not None:
        manifest["conformance"] = conformance
    if session_counter is not None:
        manifest["session_counter"] = session_counter

    manifest_bytes = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False).encode(
        "utf-8"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", manifest_bytes)
        for name in sorted(encoded):
            archive.writestr(name, encoded[name])


# Example builders


def build_minimal(out: Path) -> None:
    """Soul-only: the smallest conformant bundle."""
    write_bundle(
        out,
        shard_name="Thorne Vale",
        json_pillars={"soulshard.json": THORNE_VALE_SOUL},
    )


def build_standard(out: Path) -> None:
    """A full companion: soul, shell, tiered mind, pre-warmed neuron, canon, stat, and an asset."""
    soul = CASSIA_MERIDIAN_SOUL
    graph = build_brain_from_shard(soul, seed=1616)
    net = LIFNetwork(len(graph.nodes), graph.build_weight_matrix())
    np.random.seed(1616)
    noise_mask = graph.get_noise_mask()
    # Pre-warm 100 ticks so the loaded bundle already carries activity.
    net.tick(n_steps=100, dt=DT_SUBSTEP, noise_mask=noise_mask, noise_rate=100.0, hebbian=True)
    neuron_data = neuronshard_from_runtime(graph, net)

    write_bundle(
        out,
        shard_name="Cassia Meridian",
        json_pillars={
            "soulshard.json": soul,
            "shellshard.json": CASSIA_SHELL,
            "mindshard.json": CASSIA_MIND,
            "neuronshard.json": neuron_data,
            "canonshard.json": CASSIA_CANON,
            "statshard.json": CASSIA_STAT,
        },
        binary_members={"assets/images/cassia_portrait.png": _tiny_png()},
        conformance={"profile": "companion", "min_tier": "M"},
        session_counter=3,
    )


def _self_check(path: Path) -> None:
    errors = verify_bundle(path)
    if errors:
        raise SystemExit(f"{path.name} failed integrity verification: {errors}")
    diag = diagnose(read_bundle(path), "1.9")
    if diag.status != "current":
        drift = [f"{f.code}: {f.detail}" for f in diag.findings if f.severity != "info"]
        raise SystemExit(f"{path.name} is not current at v1.9 ({diag.status}): {drift}")


def main() -> int:
    minimal = HERE / "minimal.shard"
    standard = HERE / "standard.shard"
    build_minimal(minimal)
    build_standard(standard)
    for path in (minimal, standard):
        _self_check(path)
        print(f"wrote {path.name}  ({path.stat().st_size} bytes)  [verified current @ v1.9]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
