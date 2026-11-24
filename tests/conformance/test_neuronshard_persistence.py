"""Conformance: neuronshard persistence (spec sections 6 and 8).

A runtime that reads and writes neuronshards MUST declare its version, keep node
ids equal to their list index, size every state vector to the node count, and
round-trip runtime state byte-identically. The fixture is built inline from
shardcore.neuron, so this test is self-contained and needs no shipped bundle.
"""

from __future__ import annotations

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

CANONICAL_STAT_BLOCK = {
    "STR": 5,
    "END": 6,
    "VIG": 7,
    "DEX": 5,
    "TMP": 4,
    "ACU": 8,
    "INS": 6,
    "ATT": 7,
    "CNV": 5,
    "PRS": 6,
}


def _soul() -> dict:
    return {
        "name": "Neuron Fixture",
        "identity": "A conformance fixture.",
        "personality": "Deterministic.",
        "stat_block": dict(CANONICAL_STAT_BLOCK),
        "nature": {"label": "steady", "increased_stat": "ACU", "decreased_stat": "STR"},
        "emotional_states": ["Fierce Loyalty", "Melancholic Longing"],
        "trait_tags": ["likes: order"],
        "friendship": 6,
    }


def _prewarmed() -> dict:
    graph = build_brain_from_shard(_soul(), seed=1616)
    net = LIFNetwork(len(graph.nodes), graph.build_weight_matrix())
    np.random.seed(1616)
    net.tick(
        n_steps=50,
        dt=DT_SUBSTEP,
        noise_mask=graph.get_noise_mask(),
        noise_rate=100.0,
        hebbian=True,
    )
    return neuronshard_from_runtime(graph, net)


def test_neuronshard_declares_version():
    assert _prewarmed()["version"] == NEURONSHARD_SCHEMA_VERSION


def test_topology_and_state_present():
    data = _prewarmed()
    assert "topology" in data and "state" in data
    nodes = data["topology"]["nodes"]
    assert len(nodes) > 0
    for i, node in enumerate(nodes):
        assert node["id"] == i, "node ids MUST equal their list index (spec 6.3)"
        assert "label" in node and "type" in node


def test_state_vector_lengths_match_node_count():
    data = _prewarmed()
    n = len(data["topology"]["nodes"])
    state = data["state"]
    for vec in ("v", "g", "refractory", "fire_time", "total_spikes"):
        assert len(state[vec]) == n, f"{vec} length {len(state[vec])} != node count {n}"
    w_learned = state["W_learned"]
    assert len(w_learned) == n and all(len(row) == n for row in w_learned), (
        "W_learned MUST be n x n"
    )


def test_roundtrip_preserves_state_exactly():
    data = _prewarmed()
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
    for a, b in zip(graph.edges, graph2.edges, strict=True):
        assert (a.src, a.dst, a.weight) == (b.src, b.dst, b.weight)


def test_runtime_rejects_unknown_version():
    bad = {
        "version": "2.0",
        "topology": {"nodes": [], "edges": []},
        "state": {
            "v": [],
            "g": [],
            "refractory": [],
            "fire_time": [],
            "total_spikes": [],
            "W_learned": [],
            "sim_time": 0.0,
        },
    }
    with pytest.raises(ValueError):
        runtime_from_neuronshard(bad)


def test_rejects_edge_referencing_nonexistent_node():
    """Spec section 6.4: edges MUST NOT reference node ids outside topology."""
    bad = {
        "version": NEURONSHARD_SCHEMA_VERSION,
        "topology": {
            "nodes": [
                {
                    "id": 0,
                    "label": "A",
                    "type": "EMOTION",
                    "x": 0.0,
                    "y": 0.0,
                    "receives_noise": False,
                },
            ],
            "edges": [{"src": 0, "dst": 99, "weight": 1.0}],
        },
        "state": {
            "v": [-52.0],
            "g": [0.0],
            "refractory": [0.0],
            "fire_time": [-1000.0],
            "total_spikes": [0],
            "W_learned": [[0.0]],
            "sim_time": 0.0,
        },
    }
    with pytest.raises((ValueError, IndexError, KeyError)):
        graph, net = runtime_from_neuronshard(bad)
        _ = net.W[0, 99]  # touch the out-of-range index if a silent load let it through
