"""Seeded LIF engine: the dynamics of shardcore/neuron@1.1 (draft, spec 1.12 section 8).

Follows the Shiu et al. 2024 whole-brain fly model (model.py in the archived
fly_brain experiment): same membrane equations and constants, and the same
weight rule, where an edge is a synapse count and one synapse moves the
target by W_SYN mV. neuron@1.0 kept the constants but used weights near
0.3 mV, about one synapse, so nothing downstream of a noise node could fire.

Differences from the fly model, all deliberate:
  * A neuron is excitatory or inhibitory at the source (Dale's law), as in
    the connectome's per-neuron transmitter prediction.
  * Plasticity. The fly model is static. Here a post spike grows the inputs
    that fired inside the window and shrinks the ones that stayed silent,
    so the losing side of a clash fades instead of only the winner growing.
  * The RNG is owned by the engine and its state is serialized, so
    (state, input, steps) gives exactly one next state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

V_REST = -52.0  # mV
V_TH = -45.0  # mV
V_RESET = -52.0  # mV
TAU_M = 20.0  # ms
TAU_S = 5.0  # ms
W_SYN = 0.275  # mV per synapse
POISSON_KICK = W_SYN * 250  # mV, "sufficient to cause spiking" in the fly model
DT = 0.1  # ms, the fly model's clock
REFR_STEPS = round(2.2 / DT)
DELAY_STEPS = round(1.8 / DT)

WINDOW_STEPS = round(20.0 / DT)  # co-firing window
ETA_PLUS = 0.02  # synapses gained per post spike by an input that fired in the window
ETA_MINUS = 0.01  # synapses lost per post spike by an input that did not
SYN_MIN = 1.0
SYN_MAX = 200.0


def rng_to_json(state: Mapping[str, Any]) -> dict[str, Any]:
    """PCG64 state with its two 128-bit integers as decimal strings (spec 8.10.4).

    Many JSON readers (GDScript, JavaScript) hold numbers as 64-bit floats and
    would corrupt a 128-bit value; strings survive every reader.
    """
    if state.get("bit_generator") != "PCG64":
        raise ValueError(f"state.rng must be PCG64, got {state.get('bit_generator')!r}")
    inner = state["state"]
    return {
        "bit_generator": "PCG64",
        "state": {"state": str(int(inner["state"])), "inc": str(int(inner["inc"]))},
        "has_uint32": int(state["has_uint32"]),
        "uinteger": int(state["uinteger"]),
    }


def rng_from_json(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Inverse of rng_to_json. int() also takes the JSON integers pre-1.12 drafts wrote."""
    if raw.get("bit_generator") != "PCG64":
        raise ValueError(f"state.rng must be PCG64, got {raw.get('bit_generator')!r}")
    inner = raw["state"]
    return {
        "bit_generator": "PCG64",
        "state": {"state": int(inner["state"]), "inc": int(inner["inc"])},
        "has_uint32": int(raw["has_uint32"]),
        "uinteger": int(raw["uinteger"]),
    }


NEVER = -(10**9)

Snapshot = tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, dict[str, Any]
]


class Engine:
    """Dense LIF network. `syn[src, dst]` is a synapse count, 0 for no edge."""

    # shortcut: dense n x n arrays and a Python loop per 0.1 ms step. Fine to a
    # few hundred nodes at about 50k steps a second; past that, CSR edge arrays
    # (the serialized form is already an edge list) and a compiled step.

    def __init__(self, sign: np.ndarray, syn: np.ndarray, plastic: np.ndarray, seed: int) -> None:
        n = sign.shape[0]
        if syn.shape != (n, n) or plastic.shape != (n, n):
            raise ValueError(f"syn/plastic must be ({n}, {n})")
        self.n = n
        self.syn = syn.astype(np.float64)
        self.plastic = plastic.astype(bool)
        self._mv = sign.astype(np.float64) * W_SYN  # mV per synapse, signed by source
        self._w = self.syn * self._mv[:, None]  # kept in step with syn by _learn
        self.v = np.full(n, V_REST)
        self.g = np.zeros(n)
        self.ready = np.zeros(n, dtype=np.int64)  # step from which each neuron integrates again
        self.last_fire = np.full(n, NEVER, dtype=np.int64)
        self.spikes = np.zeros(n, dtype=np.int64)
        self.delay = np.zeros((DELAY_STEPS, n))
        self.slot = 0
        self.step_n = 0
        self.rng = np.random.Generator(np.random.PCG64(seed))

    def run(
        self,
        rate_hz: np.ndarray,
        steps: int,
        learn: bool,
        bins: int = 1,
        inject_mv: np.ndarray | None = None,
    ) -> np.ndarray:
        """Advance `steps` of DT under a fixed drive. Returns spike counts, shape (bins, n).

        `rate_hz` is Poisson input per node. `inject_mv` is sustained synaptic
        drive per node (spec 8.9): each step adds drive * DT / TAU_S to g, which
        settles g at the drive; a negative value holds a node down.
        """
        lam = rate_hz * (DT / 1000.0)
        driven = np.flatnonzero(lam > 0)
        rests = lam <= 0  # driven nodes have no refractory period, as in the fly model
        # Every Poisson kick of the run in one draw: a per-step draw costs more than the rest of the step.
        kicks = self.rng.poisson(lam[driven], size=(steps, driven.size)) * POISSON_KICK
        kicked = kicks.any(axis=1)
        trace = np.zeros((bins, self.n), dtype=np.int64)
        per_bin = max(1, steps // bins)
        leak_v, keep_g = DT / TAU_M, 1.0 - DT / TAU_S
        inject = None if inject_mv is None or not inject_mv.any() else inject_mv * (DT / TAU_S)
        v, g, ready, delay, w = self.v, self.g, self.ready, self.delay, self._w
        busy_until = int(ready.max())
        for s in range(steps):
            now = self.step_n
            if now >= busy_until:  # nobody refractory, the common case
                v += (V_REST - v + g) * leak_v
                g *= keep_g
            else:
                active = ready <= now
                v += (V_REST - v + g) * leak_v * active
                g *= np.where(active, keep_g, 1.0)

            slot = self.slot
            g += delay[slot]
            delay[slot] = 0.0
            if inject is not None:
                g += inject
            if kicked[s]:
                v[driven] += kicks[s]

            if v.max() > V_TH:
                fired = v > V_TH
                if learn:
                    self._learn(fired)
                v[fired] = V_RESET
                g[fired] = 0.0
                ready[fired & rests] = now + REFR_STEPS + 1
                busy_until = int(ready.max())
                self.last_fire[fired] = now
                self.spikes[fired] += 1
                delay[slot] += w[fired].sum(axis=0)  # read again DELAY_STEPS steps from now
                trace[min(s // per_bin, bins - 1)] += fired

            self.slot = (slot + 1) % DELAY_STEPS
            self.step_n = now + 1
        return trace

    def _learn(self, fired: np.ndarray) -> None:
        recent = (self.step_n - self.last_fire) <= WINDOW_STEPS
        cols = np.flatnonzero(fired)
        block = self.syn[:, cols]
        grown = np.clip(block + np.where(recent[:, None], ETA_PLUS, -ETA_MINUS), SYN_MIN, SYN_MAX)
        block = np.where(self.plastic[:, cols], grown, block)
        self.syn[:, cols] = block
        self._w[:, cols] = block * self._mv[:, None]

    # ── state ─────────────────────────────────────────────────────
    def snapshot(self) -> Snapshot:
        """Dynamic state as copies, for running a moment and taking it back."""
        return (self.v.copy(), self.g.copy(), self.ready.copy(), self.last_fire.copy(), self.spikes.copy(),
                self.delay.copy(), self.slot, self.step_n, self.rng.bit_generator.state)  # fmt: skip

    def restore(self, snap: Snapshot) -> None:
        v, g, ready, last_fire, spikes, delay, self.slot, self.step_n, rng_state = snap
        self.v[:], self.g[:], self.ready[:], self.last_fire[:], self.spikes[:], self.delay[:] = (
            v,
            g,
            ready,
            last_fire,
            spikes,
            delay,
        )
        self.rng.bit_generator.state = rng_state

    def state(self) -> dict[str, Any]:
        """Dynamic state only, as JSON. Topology (sign, syn, plastic) is serialized by Brain."""
        return {
            "step": self.step_n,
            "slot": self.slot,
            "v": self.v.tolist(),
            "g": self.g.tolist(),
            "ready_step": self.ready.tolist(),
            "last_fire_step": self.last_fire.tolist(),
            "total_spikes": self.spikes.tolist(),
            "delay": self.delay.tolist(),
            "rng": rng_to_json(self.rng.bit_generator.state),
        }

    def load_state(self, state: dict[str, Any]) -> None:
        arrays = {
            "v": (np.float64, (self.n,)), "g": (np.float64, (self.n,)),
            "ready_step": (np.int64, (self.n,)), "last_fire_step": (np.int64, (self.n,)),
            "total_spikes": (np.int64, (self.n,)), "delay": (np.float64, (DELAY_STEPS, self.n)),
        }  # fmt: skip
        loaded = {}
        for key, (dtype, shape) in arrays.items():
            arr = np.asarray(state[key], dtype=dtype)
            if arr.shape != shape:
                raise ValueError(f"state[{key!r}] has shape {arr.shape}, expected {shape}")
            loaded[key] = arr
        slot = int(state["slot"])
        if not 0 <= slot < DELAY_STEPS:
            raise ValueError(f"state['slot'] {slot} is outside 0..{DELAY_STEPS - 1}")
        self.v, self.g, self.ready = loaded["v"], loaded["g"], loaded["ready_step"]
        self.last_fire, self.spikes, self.delay = (
            loaded["last_fire_step"],
            loaded["total_spikes"],
            loaded["delay"],
        )
        self.slot = slot
        self.step_n = int(state["step"])
        self.rng.bit_generator.state = rng_from_json(state["rng"])
