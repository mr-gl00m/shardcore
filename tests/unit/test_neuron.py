"""Unit tests for shardcore.neuron: LIF dynamics + neuronshard round-trip."""

from __future__ import annotations

import numpy as np
import pytest

from shardcore.neuron import (
    DT_SUBSTEP,
    HEBBIAN_ETA,
    T_REFRACTORY,
    V_REST,
    LIFNetwork,
    NeuronType,
    ShardBrainGraph,
    build_brain_from_shard,
    neuronshard_from_runtime,
    runtime_from_neuronshard,
)

# ─── LIF dynamics ────────────────────────────────────────────


def test_rests_at_vrest_without_input():
    """With no input, a neuron decays toward V_REST and never fires."""
    W = np.zeros((1, 1))
    net = LIFNetwork(1, W)
    net.tick(n_steps=400, dt=DT_SUBSTEP)
    assert net.v[0] == pytest.approx(V_REST, abs=0.1)
    assert net.total_spikes[0] == 0


def test_fires_on_sustained_drive():
    """Sustained external input above the leak threshold must produce spikes."""
    W = np.zeros((1, 1))
    net = LIFNetwork(1, W)
    drive = np.array([50.0])
    for _ in range(400):
        net.step(DT_SUBSTEP, external_input=drive)
    assert net.total_spikes[0] >= 1


def test_refractory_period_blocks_immediate_refire():
    """No second spike can fire within the refractory window of the first."""
    W = np.zeros((1, 1))
    net = LIFNetwork(1, W)
    drive = np.array([80.0])
    # Drive until the first spike
    for _ in range(800):
        net.step(DT_SUBSTEP, external_input=drive)
        if net.total_spikes[0] >= 1:
            break
    assert net.total_spikes[0] >= 1, "neuron failed to fire under strong drive"
    # Keep driving through the refractory period; no additional spikes allowed
    n_ref_steps = int(T_REFRACTORY / DT_SUBSTEP)
    spikes_at_first = int(net.total_spikes[0])
    for _ in range(n_ref_steps - 1):
        net.step(DT_SUBSTEP, external_input=drive)
    assert int(net.total_spikes[0]) == spikes_at_first


def test_excitatory_edge_propagates_spikes():
    """A strong positive A→B edge should cause B to fire when only A is driven."""
    W = np.zeros((2, 2))
    W[0, 1] = 5.0
    net = LIFNetwork(2, W)
    drive = np.array([80.0, 0.0])  # drive A only; B only sees A's synaptic output
    for _ in range(2000):
        net.step(DT_SUBSTEP, external_input=drive)
    assert net.total_spikes[0] >= 1
    assert net.total_spikes[1] >= 1


def test_inhibitory_edge_reduces_post_firing():
    """An inhibitory A→B edge should reduce B's spike count vs. an unconnected baseline."""
    weak_drive = np.array([4.0])
    baseline = LIFNetwork(1, np.zeros((1, 1)))
    for _ in range(2000):
        baseline.step(DT_SUBSTEP, external_input=weak_drive)
    assert baseline.total_spikes[0] > 0  # sanity: weak drive still spikes

    W_inh = np.zeros((2, 2))
    W_inh[0, 1] = -100.0  # strong inhibition, shunts B's accumulation
    inhibited = LIFNetwork(2, W_inh)
    for _ in range(2000):
        inhibited.step(DT_SUBSTEP, external_input=np.array([80.0, 4.0]))

    assert inhibited.total_spikes[1] < baseline.total_spikes[0]


# ─── Hebbian learning ────────────────────────────────────────


def test_hebbian_strengthens_co_firing_excitatory_edge():
    """Phase-shifted co-firing on an excitatory edge should grow W_learned.

    Drive A hard and let its synaptic output drive B through the edge. The
    synaptic delay means B fires AFTER A, so at B's fire-step A's spike is
    still inside the Hebbian window, so the edge gets reinforced.
    """
    W = np.zeros((2, 2))
    W[0, 1] = 8.0
    net = LIFNetwork(2, W)
    for _ in range(1000):
        net.step(DT_SUBSTEP, external_input=np.array([80.0, 0.0]))
        net.apply_hebbian(HEBBIAN_ETA)
    assert net.total_spikes[0] >= 1
    assert net.total_spikes[1] >= 1
    assert net.W_learned[0, 1] > 0


# ─── Topology + serialization ────────────────────────────────


def _minimal_shard() -> dict:
    return {
        "name": "Test Persona",
        "stat_block": {
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
        },
        "nature": {"label": "curious and kind", "increased_stat": "ACU", "decreased_stat": "STR"},
        "emotional_states": ["Fierce Loyalty", "Melancholic Longing"],
        "trait_tags": ["likes: books", "hates: cruelty"],
        "friendship": 7,
    }


def test_build_brain_from_shard_is_deterministic_with_seed():
    g1 = build_brain_from_shard(_minimal_shard(), seed=42)
    g2 = build_brain_from_shard(_minimal_shard(), seed=42)
    assert len(g1.nodes) == len(g2.nodes)
    assert len(g1.edges) == len(g2.edges)
    for a, b in zip(g1.edges, g2.edges, strict=True):
        assert a.src == b.src and a.dst == b.dst
        assert a.weight == pytest.approx(b.weight)


def test_neuronshard_roundtrip_preserves_state():
    """Save → load should reproduce state + topology exactly."""
    graph = build_brain_from_shard(_minimal_shard(), seed=7)
    W = graph.build_weight_matrix()
    net = LIFNetwork(len(graph.nodes), W)
    np.random.seed(7)
    noise_mask = graph.get_noise_mask()
    net.tick(
        n_steps=50,
        dt=DT_SUBSTEP,
        noise_mask=noise_mask,
        noise_rate=100.0,
        hebbian=True,
        hebbian_eta=HEBBIAN_ETA,
    )

    data = neuronshard_from_runtime(graph, net)
    assert data["version"] == "1.0"
    assert len(data["topology"]["nodes"]) == len(graph.nodes)
    assert len(data["topology"]["edges"]) == len(graph.edges)

    graph2, net2 = runtime_from_neuronshard(data)
    assert len(graph2.nodes) == len(graph.nodes)
    assert len(graph2.edges) == len(graph.edges)
    np.testing.assert_allclose(net2.v, net.v)
    np.testing.assert_allclose(net2.g, net.g)
    np.testing.assert_allclose(net2.fire_time, net.fire_time)
    np.testing.assert_allclose(net2.W_learned, net.W_learned)
    np.testing.assert_array_equal(net2.total_spikes, net.total_spikes)
    assert net2.sim_time == pytest.approx(net.sim_time)


def test_runtime_rejects_wrong_version():
    bad = {"version": "99.0", "topology": {"nodes": [], "edges": []}, "state": {}}
    with pytest.raises(ValueError):
        runtime_from_neuronshard(bad)


def test_weight_matrix_matches_edges():
    g = ShardBrainGraph()
    a = g.add_node("A", NeuronType.IDENTITY_ANCHOR)
    b = g.add_node("B", NeuronType.EMOTION)
    g.add_edge(a, b, 0.7)
    g.add_edge(b, a, -0.3)
    W = g.build_weight_matrix()
    assert W[a, b] == pytest.approx(0.7)
    assert W[b, a] == pytest.approx(-0.3)
    assert W[a, a] == 0.0
    assert W[b, b] == 0.0
