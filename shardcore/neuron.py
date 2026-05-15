"""Neuronshard reference runtime — Leaky Integrate-and-Fire dynamics.

Pure-numpy extraction of the LIF network prototyped in shard_brain_viz.py.
No Qt/visualization dependencies. Provides:

- LIFNetwork: vectorized LIF simulation with Poisson noise + Hebbian learning.
- ShardBrainGraph: topology (nodes + weighted edges).
- build_brain_from_shard(): derive a graph from a soulshard.json dict.
- neuronshard_from_runtime / runtime_from_neuronshard: serialize to/from
  neuronshard.json per the v1.0 schema.
- main(): `python -m shardcore.neuron <bundle.shard> --ticks N` CLI.

Spec: see SHARDCORE_Spec_v1.0.md §Neuronshard.
"""
from __future__ import annotations

import json
import math
import random
import sys
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

import numpy as np


# ─────────────────────────────────────────────
#  Constants (from Drosophila connectome model)
# ─────────────────────────────────────────────
V_REST = -52.0        # mV, resting potential
V_THRESHOLD = -45.0   # mV, spike threshold
V_RESET = -52.0       # mV, post-spike reset
TAU_MEMBRANE = 20.0   # ms, membrane time constant
TAU_SYNAPSE = 5.0     # ms, synaptic input decay
T_REFRACTORY = 2.2    # ms, refractory period after spike
T_DELAY = 1.8         # ms, synaptic transmission delay
W_SYN_BASE = 0.275    # mV, base weight per synapse

DT_SUBSTEP = 0.5      # ms, default integration substep

# Hebbian
HEBBIAN_WINDOW = 20.0 # ms, co-firing window
HEBBIAN_ETA = 0.005   # learning rate
W_MAX = 2.0           # mV, max absolute weight

# Poisson
DEFAULT_POISSON_RATE = 150.0  # Hz
POISSON_WEIGHT = W_SYN_BASE * 250  # mV (w_syn * f_poi from fly model)


# ─────────────────────────────────────────────
#  Neuron Types
# ─────────────────────────────────────────────
class NeuronType(str, Enum):
    IDENTITY_ANCHOR = "IDENTITY_ANCHOR"
    MEMORY_CORE = "MEMORY_CORE"
    MEMORY_LTM = "MEMORY_LTM"
    MEMORY_STM = "MEMORY_STM"
    EMOTION = "EMOTION"
    DRIVE = "DRIVE"
    IMPULSE = "IMPULSE"


STAT_LABELS = {
    "STR": "Strength", "END": "Endurance", "VIG": "Vigor", "DEX": "Dexterity",
    "TMP": "Temperament", "ACU": "Acuity", "INS": "Insight", "ATT": "Attunement",
    "CNV": "Conviction", "PRS": "Presence",
}

EMOTIONAL_STATE_BIASES: dict[str, dict[str, float]] = {
    "Defensive Sarcasm":   {"Anger": 0.4, "Disgust": 0.2},
    "Melancholic Longing": {"Sadness": 0.5, "Curiosity": 0.2},
    "Raw Vulnerability":   {"Fear": 0.4, "Sadness": 0.3, "Trust": 0.2},
    "Fierce Loyalty":      {"Trust": 0.6, "Anger": 0.2},
    "Playful Menace":      {"Joy": 0.3, "Anger": 0.2, "Surprise": 0.3},
    "resigned":            {"Sadness": 0.3, "Trust": 0.1},
    "grateful":            {"Joy": 0.3, "Trust": 0.4},
    "submissive":          {"Fear": 0.2, "Trust": 0.3},
    "devoted":             {"Trust": 0.5, "Joy": 0.2},
    "accepting":           {"Trust": 0.3, "Sadness": 0.1},
    "purposeful":          {"Joy": 0.2, "Trust": 0.2, "Anger": 0.1},
}


# ─────────────────────────────────────────────
#  Topology (pure data — no rendering)
# ─────────────────────────────────────────────
@dataclass
class NodeInfo:
    index: int
    label: str
    ntype: NeuronType
    x: float = 0.0
    y: float = 0.0
    receives_noise: bool = False


@dataclass
class EdgeInfo:
    src: int
    dst: int
    weight: float  # positive = excitatory, negative = inhibitory


class ShardBrainGraph:
    def __init__(self) -> None:
        self.nodes: list[NodeInfo] = []
        self.edges: list[EdgeInfo] = []

    def add_node(self, label: str, ntype: NeuronType,
                 receives_noise: bool = False) -> int:
        idx = len(self.nodes)
        self.nodes.append(NodeInfo(idx, label, ntype, receives_noise=receives_noise))
        return idx

    def add_edge(self, src: int, dst: int, weight: float) -> None:
        self.edges.append(EdgeInfo(src, dst, weight))

    def build_weight_matrix(self) -> np.ndarray:
        n = len(self.nodes)
        W = np.zeros((n, n))
        for e in self.edges:
            W[e.src, e.dst] = e.weight
        return W

    def get_noise_mask(self) -> np.ndarray:
        mask = np.zeros(len(self.nodes))
        for n in self.nodes:
            if n.receives_noise:
                mask[n.index] = 1.0
        return mask

    def layout_rings(self) -> None:
        """Position nodes in concentric rings by type (deterministic given RNG state)."""
        groups = {
            NeuronType.IDENTITY_ANCHOR: (0, 70),
            NeuronType.MEMORY_CORE:     (1, 150),
            NeuronType.EMOTION:         (1, 160),
            NeuronType.MEMORY_LTM:      (2, 250),
            NeuronType.DRIVE:           (2, 260),
            NeuronType.MEMORY_STM:      (3, 350),
            NeuronType.IMPULSE:         (4, 430),
        }
        rings: dict[int, list[tuple[NodeInfo, float]]] = {}
        for node in self.nodes:
            ring_id, radius = groups[node.ntype]
            rings.setdefault(ring_id, []).append((node, radius))
        for ring_id, items in rings.items():
            count = len(items)
            for i, (node, radius) in enumerate(items):
                angle = (2 * math.pi * i / count) + (ring_id * 0.3)
                jitter_r = random.uniform(-12, 12)
                jitter_a = random.uniform(-0.08, 0.08)
                node.x = (radius + jitter_r) * math.cos(angle + jitter_a)
                node.y = (radius + jitter_r) * math.sin(angle + jitter_a)


# ─────────────────────────────────────────────
#  LIF Network (pure numpy simulation)
# ─────────────────────────────────────────────
class LIFNetwork:
    """Vectorized Leaky Integrate-and-Fire network."""

    def __init__(self, n_nodes: int, W: np.ndarray):
        if W.shape != (n_nodes, n_nodes):
            raise ValueError(f"weight matrix shape {W.shape} != ({n_nodes}, {n_nodes})")
        self.n = n_nodes
        self.v = np.full(n_nodes, V_REST, dtype=np.float64)
        self.g = np.zeros(n_nodes, dtype=np.float64)
        self.refractory = np.zeros(n_nodes, dtype=np.float64)
        self.fired = np.zeros(n_nodes, dtype=bool)
        self.fire_time = np.full(n_nodes, -1000.0, dtype=np.float64)
        self.sim_time = 0.0

        self.W = W.astype(np.float64, copy=True)
        self.W_initial = W.astype(np.float64, copy=True)
        self.W_learned = np.zeros_like(self.W)

        self.delay_slots = max(1, int(np.ceil(T_DELAY / DT_SUBSTEP)))
        self.delay_queue = np.zeros((self.delay_slots, n_nodes), dtype=np.float64)
        self.current_slot = 0

        self.total_spikes = np.zeros(n_nodes, dtype=np.int64)

    def step(self, dt: float, external_input: np.ndarray | None = None) -> np.ndarray:
        """Single Euler integration step. Returns boolean fire vector."""
        active = self.refractory <= 0
        dv = (V_REST - self.v + self.g) / TAU_MEMBRANE * dt
        self.v[active] += dv[active]

        self.g += -self.g / TAU_SYNAPSE * dt
        if external_input is not None:
            self.g += external_input

        self.g += self.delay_queue[self.current_slot]
        self.delay_queue[self.current_slot] = 0.0

        self.fired = self.v > V_THRESHOLD
        fired_indices = np.where(self.fired)[0]

        if len(fired_indices) > 0:
            self.v[fired_indices] = V_RESET
            self.g[fired_indices] = 0.0
            self.refractory[fired_indices] = T_REFRACTORY
            self.fire_time[fired_indices] = self.sim_time
            self.total_spikes[fired_indices] += 1

            future_slot = (self.current_slot + self.delay_slots) % self.delay_slots
            outgoing = self.W[fired_indices].sum(axis=0)
            self.delay_queue[future_slot] += outgoing

        self.current_slot = (self.current_slot + 1) % self.delay_slots
        self.refractory = np.maximum(0, self.refractory - dt)
        self.sim_time += dt
        return self.fired.copy()

    def tick(self, n_steps: int, dt: float = DT_SUBSTEP,
             noise_mask: np.ndarray | None = None,
             noise_rate: float = 0.0,
             hebbian: bool = False,
             hebbian_eta: float = HEBBIAN_ETA) -> np.ndarray:
        """Advance the network by n_steps of size dt (ms). Returns spike counts this call."""
        spikes_before = self.total_spikes.copy()
        for _ in range(n_steps):
            if noise_mask is not None and noise_rate > 0:
                self.inject_poisson(noise_mask, noise_rate, dt, POISSON_WEIGHT)
            self.step(dt)
            if hebbian:
                self.apply_hebbian(hebbian_eta)
        return self.total_spikes - spikes_before

    def inject_poisson(self, node_mask: np.ndarray, rate: float,
                       dt: float, weight: float) -> None:
        if rate <= 0:
            return
        lam = rate * dt / 1000.0
        counts = np.random.poisson(lam, size=self.n) * node_mask
        self.g += counts * weight

    def apply_hebbian(self, eta: float) -> None:
        fired_now = np.where(self.fired)[0]
        if len(fired_now) == 0:
            return
        recent = (self.sim_time - self.fire_time) < HEBBIAN_WINDOW
        recent[fired_now] = False
        for j in fired_now:
            pre_mask = recent & (self.W[:, j] != 0)
            if np.any(pre_mask):
                delta = eta * np.sign(self.W_initial[pre_mask, j])
                self.W_learned[pre_mask, j] += delta
                self.W[pre_mask, j] = np.clip(
                    self.W_initial[pre_mask, j] + self.W_learned[pre_mask, j],
                    -W_MAX, W_MAX,
                )

    def get_activation(self) -> np.ndarray:
        raw = (self.v - V_REST) / (V_THRESHOLD - V_REST)
        return np.clip(raw, 0.0, 1.0)


# ─────────────────────────────────────────────
#  Topology builder from a soulshard
# ─────────────────────────────────────────────
def build_brain_from_shard(shard: dict, seed: int | None = None) -> ShardBrainGraph:
    """Derive a neural fingerprint graph from a soulshard's stat block.

    Maps stat_block → identity anchor weights, emotional_states → Poisson noise
    biases, nature → stat modifiers on edge weights, trait_tags → drive biases.
    """
    if seed is not None:
        random.seed(seed)

    g = ShardBrainGraph()
    stats = shard.get("stat_block", {})
    nature = shard.get("nature", {})
    emotional_states = shard.get("emotional_states", [])
    trait_tags = shard.get("trait_tags", [])
    friendship = shard.get("friendship", 5)

    stat_vals: dict[str, float] = {}
    for k, v in stats.items():
        key = k.upper()
        if key in STAT_LABELS and isinstance(v, (int, float)):
            stat_vals[key] = float(v)

    inc_stat = (nature.get("increased_stat") or "").upper()
    dec_stat = (nature.get("decreased_stat") or "").upper()

    def nature_boost(stat: str) -> float:
        if stat == inc_stat:
            return 1.2
        if stat == dec_stat:
            return 0.7
        return 1.0

    def w(stat: str, base: float = 0.5) -> float:
        sv = stat_vals.get(stat, 5.0)
        return base * (sv / 10.0) + random.uniform(-0.04, 0.04)

    def wi(stat: str, base: float = -0.4) -> float:
        sv = stat_vals.get(stat, 5.0)
        return base * (sv / 10.0) + random.uniform(-0.025, 0.025)

    # Identity anchors (one per stat)
    id_nodes: dict[str, int] = {}
    for key in ("STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS"):
        sv = stat_vals.get(key, 5.0)
        id_nodes[key] = g.add_node(
            STAT_LABELS[key], NeuronType.IDENTITY_ANCHOR,
            receives_noise=sv >= 7,
        )

    # Emotions
    emotion_names = ["Joy", "Fear", "Sadness", "Curiosity", "Anger", "Trust", "Disgust", "Surprise"]
    em_noise = {name: (name in ("Curiosity", "Surprise")) for name in emotion_names}
    for state in emotional_states:
        biases = EMOTIONAL_STATE_BIASES.get(state)
        if not biases:
            for known, b in EMOTIONAL_STATE_BIASES.items():
                if state.lower().startswith(known.lower()):
                    biases = b
                    break
        if biases:
            for emo in biases:
                if emo in em_noise:
                    em_noise[emo] = True
    em_nodes: dict[str, int] = {}
    for name in emotion_names:
        em_nodes[name] = g.add_node(name, NeuronType.EMOTION, receives_noise=em_noise[name])

    # Drives
    nature_label = (nature.get("label") or "").lower()
    is_lonely = "lonely" in nature_label or "longing" in nature_label
    drive_defs = [
        ("Loneliness",      is_lonely),
        ("Validation",      False),
        ("Creative Drive",  False),
        ("Rest",            True),
        ("Curiosity Drive", True),
    ]
    dr_nodes: dict[str, int] = {
        name: g.add_node(name, NeuronType.DRIVE, receives_noise=noise)
        for name, noise in drive_defs
    }

    # Memories
    stm = [g.add_node(f"STM_{i+1:02d}", NeuronType.MEMORY_STM, receives_noise=True)
           for i in range(8)]
    ltm = [g.add_node(f"LTM_{i+1:02d}", NeuronType.MEMORY_LTM) for i in range(6)]
    core_mem = [g.add_node(f"Core_{i+1}", NeuronType.MEMORY_CORE) for i in range(3)]

    # Impulses
    impulse_names = ["Speak", "Withdraw", "Approach", "Create", "Fight", "Flee", "Observe", "Comfort"]
    imp_nodes: dict[str, int] = {
        name: g.add_node(name, NeuronType.IMPULSE) for name in impulse_names
    }

    # Identity → Emotion
    g.add_edge(id_nodes["ATT"], em_nodes["Trust"],     w("ATT", 0.6) * nature_boost("ATT"))
    g.add_edge(id_nodes["ATT"], em_nodes["Sadness"],   w("ATT", 0.35))
    g.add_edge(id_nodes["INS"], em_nodes["Fear"],      w("INS", 0.5) * nature_boost("INS"))
    g.add_edge(id_nodes["INS"], em_nodes["Sadness"],   w("INS", 0.4) * nature_boost("INS"))
    g.add_edge(id_nodes["INS"], em_nodes["Curiosity"], w("INS", 0.35))
    g.add_edge(id_nodes["TMP"], em_nodes["Anger"],     w("TMP", 0.55))
    g.add_edge(id_nodes["TMP"], em_nodes["Surprise"],  w("TMP", 0.3))
    g.add_edge(id_nodes["TMP"], em_nodes["Fear"],      w("TMP", 0.25))
    g.add_edge(id_nodes["ACU"], em_nodes["Curiosity"], w("ACU", 0.6))
    g.add_edge(id_nodes["ACU"], em_nodes["Surprise"],  w("ACU", 0.3))
    g.add_edge(id_nodes["PRS"], em_nodes["Trust"],     w("PRS", 0.45))
    g.add_edge(id_nodes["PRS"], em_nodes["Joy"],       w("PRS", 0.35))
    g.add_edge(id_nodes["CNV"], em_nodes["Anger"],     w("CNV", 0.3))
    g.add_edge(id_nodes["CNV"], em_nodes["Trust"],     w("CNV", 0.3))
    g.add_edge(id_nodes["END"], em_nodes["Trust"],     w("END", 0.4))
    g.add_edge(id_nodes["END"], em_nodes["Joy"],       w("END", 0.25))
    g.add_edge(id_nodes["VIG"], em_nodes["Joy"],       w("VIG", 0.5) * nature_boost("VIG"))
    g.add_edge(id_nodes["VIG"], em_nodes["Surprise"],  w("VIG", 0.3) * nature_boost("VIG"))
    g.add_edge(id_nodes["STR"], em_nodes["Anger"],     w("STR", 0.4))
    g.add_edge(id_nodes["DEX"], em_nodes["Surprise"],  w("DEX", 0.35))

    # Emotion ↔ Emotion (inhibitory)
    g.add_edge(em_nodes["Joy"],       em_nodes["Sadness"],   wi("VIG", -0.45))
    g.add_edge(em_nodes["Sadness"],   em_nodes["Joy"],       wi("INS", -0.4))
    g.add_edge(em_nodes["Fear"],      em_nodes["Trust"],     wi("INS", -0.35))
    g.add_edge(em_nodes["Trust"],     em_nodes["Fear"],      wi("ATT", -0.3))
    g.add_edge(em_nodes["Anger"],     em_nodes["Fear"],      wi("TMP", -0.3))
    g.add_edge(em_nodes["Curiosity"], em_nodes["Disgust"],   wi("ACU", -0.3))
    g.add_edge(em_nodes["Disgust"],   em_nodes["Curiosity"], wi("CNV", -0.2))

    # Drive → Emotion
    g.add_edge(dr_nodes["Loneliness"],      em_nodes["Sadness"],   w("INS", 0.55))
    g.add_edge(dr_nodes["Loneliness"],      em_nodes["Fear"],      w("INS", 0.25))
    g.add_edge(dr_nodes["Curiosity Drive"], em_nodes["Curiosity"], w("ACU", 0.5))
    g.add_edge(dr_nodes["Creative Drive"],  em_nodes["Joy"],       w("PRS", 0.4))
    g.add_edge(dr_nodes["Validation"],      em_nodes["Joy"],       w("ATT", 0.35))
    g.add_edge(dr_nodes["Rest"],            em_nodes["Sadness"],   w("END", 0.2))
    g.add_edge(dr_nodes["Rest"],            em_nodes["Anger"],     wi("END", -0.3))

    # Memory → Emotion
    g.add_edge(core_mem[0], em_nodes["Trust"],     0.55)
    g.add_edge(core_mem[0], em_nodes["Sadness"],   0.35)
    g.add_edge(core_mem[1], em_nodes["Curiosity"], 0.45)
    g.add_edge(core_mem[1], em_nodes["Joy"],       0.30)
    g.add_edge(core_mem[2], em_nodes["Fear"],      0.40)
    g.add_edge(core_mem[2], em_nodes["Anger"],     0.30)
    for i, l in enumerate(ltm):
        g.add_edge(l, em_nodes[emotion_names[i % len(emotion_names)]], 0.30)
    for i, s in enumerate(stm):
        g.add_edge(s, em_nodes[["Curiosity", "Surprise", "Joy", "Fear"][i % 4]], 0.18)

    # Emotion → Impulse
    g.add_edge(em_nodes["Joy"],       imp_nodes["Approach"], w("PRS", 0.55))
    g.add_edge(em_nodes["Joy"],       imp_nodes["Speak"],    w("PRS", 0.35))
    g.add_edge(em_nodes["Fear"],      imp_nodes["Flee"],     w("INS", 0.6))
    g.add_edge(em_nodes["Fear"],      imp_nodes["Withdraw"], w("INS", 0.45))
    g.add_edge(em_nodes["Sadness"],   imp_nodes["Withdraw"], w("INS", 0.55))
    g.add_edge(em_nodes["Sadness"],   imp_nodes["Comfort"],  w("ATT", 0.3))
    g.add_edge(em_nodes["Curiosity"], imp_nodes["Observe"],  w("ACU", 0.55))
    g.add_edge(em_nodes["Curiosity"], imp_nodes["Approach"], w("ACU", 0.35))
    g.add_edge(em_nodes["Anger"],     imp_nodes["Fight"],    w("TMP", 0.6))
    g.add_edge(em_nodes["Anger"],     imp_nodes["Speak"],    w("TMP", 0.35))
    g.add_edge(em_nodes["Trust"],     imp_nodes["Approach"], w("ATT", 0.5))
    g.add_edge(em_nodes["Trust"],     imp_nodes["Comfort"],  w("ATT", 0.45))
    g.add_edge(em_nodes["Disgust"],   imp_nodes["Withdraw"], w("CNV", 0.45))
    g.add_edge(em_nodes["Surprise"],  imp_nodes["Observe"],  w("ACU", 0.4))

    # Drive → Impulse
    g.add_edge(dr_nodes["Loneliness"],      imp_nodes["Approach"], w("ATT", 0.45))
    g.add_edge(dr_nodes["Creative Drive"],  imp_nodes["Create"],   w("PRS", 0.6))
    g.add_edge(dr_nodes["Curiosity Drive"], imp_nodes["Observe"],  w("ACU", 0.4))
    g.add_edge(dr_nodes["Validation"],      imp_nodes["Speak"],    w("PRS", 0.35))
    g.add_edge(dr_nodes["Rest"],            imp_nodes["Withdraw"], w("END", 0.35))

    # Impulse cross-inhibition
    g.add_edge(imp_nodes["Fight"],    imp_nodes["Flee"],     -0.45)
    g.add_edge(imp_nodes["Flee"],     imp_nodes["Fight"],    -0.40)
    g.add_edge(imp_nodes["Approach"], imp_nodes["Withdraw"], -0.50)
    g.add_edge(imp_nodes["Withdraw"], imp_nodes["Approach"], -0.40)
    g.add_edge(imp_nodes["Speak"],    imp_nodes["Withdraw"], -0.30)

    # Feedback loops
    friend_scale = max(0.1, friendship / 10.0) if isinstance(friendship, (int, float)) else 0.5
    g.add_edge(em_nodes["Trust"],     id_nodes["ATT"], 0.15 * friend_scale)
    g.add_edge(em_nodes["Anger"],     id_nodes["TMP"], 0.15)
    g.add_edge(em_nodes["Curiosity"], id_nodes["ACU"], 0.12)
    g.add_edge(em_nodes["Sadness"],   id_nodes["INS"], 0.12 * nature_boost("INS"))
    g.add_edge(em_nodes["Joy"],       id_nodes["PRS"], 0.10)

    # Inter-memory connections
    for i, cm in enumerate(core_mem):
        if i < len(ltm):
            g.add_edge(cm, ltm[i], 0.35)
            g.add_edge(cm, ltm[min(i + 1, len(ltm) - 1)], 0.20)
    for i in range(len(ltm) - 1):
        g.add_edge(ltm[i], ltm[i + 1], 0.15)
    for i, s in enumerate(stm):
        g.add_edge(s, ltm[i % len(ltm)], 0.10)

    # Trait tags → drive biases
    for tag in trait_tags:
        tag_lower = tag.lower()
        if tag_lower.startswith("likes:"):
            g.add_edge(dr_nodes["Curiosity Drive"], em_nodes["Joy"], 0.15)
        elif tag_lower.startswith("hates:"):
            g.add_edge(dr_nodes["Validation"], em_nodes["Anger"], 0.12)
            g.add_edge(dr_nodes["Validation"], em_nodes["Disgust"], 0.10)

    g.layout_rings()
    return g


# ─────────────────────────────────────────────
#  neuronshard.json (de)serialization — schema v1.0
# ─────────────────────────────────────────────
NEURONSHARD_SCHEMA_VERSION = "1.0"


def neuronshard_from_runtime(graph: ShardBrainGraph, net: LIFNetwork) -> dict:
    """Serialize graph + runtime state into a neuronshard.json-shaped dict."""
    return {
        "version": NEURONSHARD_SCHEMA_VERSION,
        "topology": {
            "nodes": [
                {
                    "id": n.index,
                    "label": n.label,
                    "type": n.ntype.value,
                    "x": n.x,
                    "y": n.y,
                    "receives_noise": n.receives_noise,
                }
                for n in graph.nodes
            ],
            "edges": [
                {"src": e.src, "dst": e.dst, "weight": e.weight}
                for e in graph.edges
            ],
        },
        "state": {
            "sim_time": net.sim_time,
            "v": net.v.tolist(),
            "g": net.g.tolist(),
            "refractory": net.refractory.tolist(),
            "fire_time": net.fire_time.tolist(),
            "total_spikes": net.total_spikes.tolist(),
            "W_learned": net.W_learned.tolist(),
        },
    }


def runtime_from_neuronshard(data: dict) -> tuple[ShardBrainGraph, LIFNetwork]:
    """Rebuild graph + LIF network from a neuronshard.json-shaped dict."""
    version = data.get("version")
    if version != NEURONSHARD_SCHEMA_VERSION:
        raise ValueError(f"unsupported neuronshard version: {version!r}")

    topology = data["topology"]
    graph = ShardBrainGraph()
    for raw in topology["nodes"]:
        node = NodeInfo(
            index=raw["id"],
            label=raw["label"],
            ntype=NeuronType(raw["type"]),
            x=raw.get("x", 0.0),
            y=raw.get("y", 0.0),
            receives_noise=raw.get("receives_noise", False),
        )
        graph.nodes.append(node)
    for raw in topology["edges"]:
        graph.add_edge(raw["src"], raw["dst"], raw["weight"])

    W = graph.build_weight_matrix()
    net = LIFNetwork(len(graph.nodes), W)

    state = data.get("state") or {}
    if state:
        net.sim_time = float(state.get("sim_time", 0.0))
        if "v" in state:
            net.v = np.asarray(state["v"], dtype=np.float64)
        if "g" in state:
            net.g = np.asarray(state["g"], dtype=np.float64)
        if "refractory" in state:
            net.refractory = np.asarray(state["refractory"], dtype=np.float64)
        if "fire_time" in state:
            net.fire_time = np.asarray(state["fire_time"], dtype=np.float64)
        if "total_spikes" in state:
            net.total_spikes = np.asarray(state["total_spikes"], dtype=np.int64)
        if "W_learned" in state:
            net.W_learned = np.asarray(state["W_learned"], dtype=np.float64)
            net.W = np.clip(net.W_initial + net.W_learned, -W_MAX, W_MAX)

    return graph, net


# ─────────────────────────────────────────────
#  Bundle I/O
# ─────────────────────────────────────────────
def load_soulshard(path: str | Path) -> dict:
    """Load a soulshard dict from a .shard bundle or a raw soulshard.json."""
    p = Path(path)
    if p.suffix == ".shard":
        with zipfile.ZipFile(p, "r") as zf:
            if "soulshard.json" in zf.namelist():
                return json.loads(zf.read("soulshard.json"))
            for name in zf.namelist():
                if "soulshard" in name.lower() and name.endswith(".json"):
                    return json.loads(zf.read(name))
            raise FileNotFoundError(f"no soulshard.json in {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def load_neuronshard_if_present(path: str | Path) -> dict | None:
    """Return the neuronshard.json contents from a bundle, or None if absent."""
    p = Path(path)
    if p.suffix != ".shard":
        return None
    with zipfile.ZipFile(p, "r") as zf:
        if "neuronshard.json" in zf.namelist():
            return json.loads(zf.read("neuronshard.json"))
    return None


# ─────────────────────────────────────────────
#  CLI entry point
# ─────────────────────────────────────────────
def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="shardcore.neuron",
        description="Tick the Neuronshard runtime on a .shard bundle or soulshard JSON.",
    )
    parser.add_argument("shard", help="path to .shard bundle or soulshard.json")
    parser.add_argument("--ticks", type=int, default=200,
                        help="number of integration steps to run (default: 200)")
    parser.add_argument("--dt", type=float, default=DT_SUBSTEP,
                        help=f"substep size in ms (default: {DT_SUBSTEP})")
    parser.add_argument("--noise", type=float, default=DEFAULT_POISSON_RATE,
                        help="Poisson noise rate in Hz (default: %(default)s)")
    parser.add_argument("--hebbian", action="store_true",
                        help="enable Hebbian learning during ticks")
    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed for reproducible topology + noise")
    parser.add_argument("--save", type=str, default=None,
                        help="write final neuronshard.json state to this path")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    existing = load_neuronshard_if_present(args.shard)
    if existing is not None:
        graph, net = runtime_from_neuronshard(existing)
        source = "resumed from embedded neuronshard.json"
    else:
        shard = load_soulshard(args.shard)
        graph = build_brain_from_shard(shard, seed=args.seed)
        W = graph.build_weight_matrix()
        net = LIFNetwork(len(graph.nodes), W)
        source = "built from soulshard.json"

    noise_mask = graph.get_noise_mask()
    spikes = net.tick(
        n_steps=args.ticks,
        dt=args.dt,
        noise_mask=noise_mask,
        noise_rate=args.noise,
        hebbian=args.hebbian,
    )

    print(f"[neuronshard] {source}")
    print(f"  nodes: {len(graph.nodes)}  edges: {len(graph.edges)}")
    print(f"  ticks: {args.ticks}  dt: {args.dt} ms  sim_time: {net.sim_time:.2f} ms")
    print(f"  spikes this run: {int(spikes.sum())}  total: {int(net.total_spikes.sum())}")

    # Top-active nodes this run
    top = np.argsort(spikes)[::-1][:5]
    for idx in top:
        if spikes[idx] == 0:
            break
        n = graph.nodes[int(idx)]
        print(f"    {n.label:<22} ({n.ntype.value:<17}) {int(spikes[idx])} spikes")

    if args.save:
        out = neuronshard_from_runtime(graph, net)
        Path(args.save).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"[neuronshard] wrote {args.save}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
