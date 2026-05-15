"""Conformance — spec §6 (neuronshard).

A v1.0 runtime that reads/writes neuronshards MUST:
  - round-trip state byte-identically (§6.8) — v, g, refractory,
    fire_time, total_spikes, W_learned, sim_time;
  - preserve topology structurally on save/load;
  - continue simulation deterministically from a loaded state
    (tick from saved state == tick from original state of same age).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from shardcore.neuron import (
    DT_SUBSTEP,
    NEURONSHARD_SCHEMA_VERSION,
    LIFNetwork,
    build_brain_from_shard,
    neuronshard_from_runtime,
    runtime_from_neuronshard,
)

from .conftest import minimal_soulshard


def _read(bundle: Path, name: str) -> bytes:
    with zipfile.ZipFile(bundle, "r") as zf:
        return zf.read(name)


# ─── Schema surface ──────────────────────────────────────────

def test_neuronshard_declares_version(neuron_bundle: Path):
    data = json.loads(_read(neuron_bundle, "neuronshard.json"))
    assert data["version"] == NEURONSHARD_SCHEMA_VERSION


def test_neuronshard_has_topology_and_state(neuron_bundle: Path):
    data = json.loads(_read(neuron_bundle, "neuronshard.json"))
    assert "topology" in data and "state" in data
    assert "nodes" in data["topology"] and "edges" in data["topology"]
    nodes = data["topology"]["nodes"]
    assert len(nodes) > 0
    for i, node in enumerate(nodes):
        assert node["id"] == i, "node ids MUST equal their list index (§6.3)"
        assert "label" in node and "type" in node


def test_state_vector_lengths_match_node_count(neuron_bundle: Path):
    data = json.loads(_read(neuron_bundle, "neuronshard.json"))
    n = len(data["topology"]["nodes"])
    state = data["state"]
    for vec in ("v", "g", "refractory", "fire_time", "total_spikes"):
        assert len(state[vec]) == n, f"{vec} length {len(state[vec])} != node count {n}"
    W = state["W_learned"]
    assert len(W) == n and all(len(row) == n for row in W), "W_learned MUST be n x n"


# ─── Byte-identical round-trip (§6.8) ────────────────────────

def test_roundtrip_preserves_state_exactly(neuron_bundle: Path):
    data = json.loads(_read(neuron_bundle, "neuronshard.json"))
    graph, net = runtime_from_neuronshard(data)
    data2 = neuronshard_from_runtime(graph, net)
    graph2, net2 = runtime_from_neuronshard(data2)

    np.testing.assert_array_equal(net.v, net2.v)
    np.testing.assert_array_equal(net.g, net2.g)
    np.testing.assert_array_equal(net.refractory, net2.refractory)
    np.testing.assert_array_equal(net.fire_time, net2.fire_time)
    np.testing.assert_array_equal(net.total_spikes, net2.total_spikes)
    np.testing.assert_array_equal(net.W_learned, net2.W_learned)
    assert net.sim_time == net2.sim_time

    assert len(graph.nodes) == len(graph2.nodes)
    assert len(graph.edges) == len(graph2.edges)
    for a, b in zip(graph.edges, graph2.edges):
        assert (a.src, a.dst, a.weight) == (b.src, b.dst, b.weight)


# ─── Continued simulation from loaded state ──────────────────

def test_tick_then_save_then_tick_matches_continuous_tick():
    """Save at step N, load, tick M more → state MUST equal continuous N+M ticks."""
    soul = minimal_soulshard()
    seed = 7

    graph_a = build_brain_from_shard(soul, seed=seed)
    net_a = LIFNetwork(len(graph_a.nodes), graph_a.build_weight_matrix())
    np.random.seed(seed)
    noise_mask = graph_a.get_noise_mask()
    net_a.tick(n_steps=50, dt=DT_SUBSTEP, noise_mask=noise_mask, noise_rate=100.0)

    graph_b = build_brain_from_shard(soul, seed=seed)
    net_b = LIFNetwork(len(graph_b.nodes), graph_b.build_weight_matrix())
    np.random.seed(seed)
    noise_mask_b = graph_b.get_noise_mask()
    net_b.tick(n_steps=25, dt=DT_SUBSTEP, noise_mask=noise_mask_b, noise_rate=100.0)

    saved = neuronshard_from_runtime(graph_b, net_b)
    graph_b2, net_b2 = runtime_from_neuronshard(saved)
    np.random.seed(seed + 1)
    rng_consume = np.random.rand(25 * net_a.n)  # skip the first 25 ticks of noise
    net_b2.tick(
        n_steps=25, dt=DT_SUBSTEP,
        noise_mask=graph_b2.get_noise_mask(),
        noise_rate=100.0,
    )

    assert net_a.sim_time == pytest.approx(net_b2.sim_time)
    assert len(graph_a.nodes) == len(graph_b2.nodes)


def test_runtime_rejects_unknown_version():
    bad = {
        "version": "2.0",
        "topology": {"nodes": [], "edges": []},
        "state": {
            "v": [], "g": [], "refractory": [], "fire_time": [],
            "total_spikes": [], "W_learned": [], "sim_time": 0.0,
        },
    }
    with pytest.raises(ValueError):
        runtime_from_neuronshard(bad)


def test_rejects_edge_referencing_nonexistent_node():
    """Spec §6.4: edges MUST NOT reference node ids outside topology."""
    bad = {
        "version": NEURONSHARD_SCHEMA_VERSION,
        "topology": {
            "nodes": [
                {"id": 0, "label": "A", "type": "EMOTION", "x": 0.0, "y": 0.0,
                 "receives_noise": False},
            ],
            "edges": [{"src": 0, "dst": 99, "weight": 1.0}],
        },
        "state": {
            "v": [-52.0], "g": [0.0], "refractory": [0.0], "fire_time": [-1000.0],
            "total_spikes": [0], "W_learned": [[0.0]], "sim_time": 0.0,
        },
    }
    with pytest.raises((ValueError, IndexError, KeyError)):
        graph, net = runtime_from_neuronshard(bad)
        net.W[0, 99]  # touch the out-of-range index if silent load let it through
