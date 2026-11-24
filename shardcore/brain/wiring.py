"""Topology: a shard's soul and mind turned into a wired brain, and the pillar it is stored as.

Layout, loosely the fly's sensory to motor path with pooled inhibition:

    ANCHOR (ten stats, tonic)  -> EMOTION     personality as a standing bias
    SENSE  (innate detectors)  -> EMOTION     instinct: fixed wiring, no memory needed
    SENSE                      -> IMPULSE     reflexes (food when hungry, rest when spent)
    COND   (one per emotion)   -> EMOTION     what she has learned, and her mood
    MEMORY (real mind entries) -> EMOTION     what a memory makes her feel
    EMOTION                    -> IMPULSE     what a feeling makes her do
    EMOTION                    -> MEMORY      mood pulls matching memories back up
    pool members <-> INTERNEURON              one inhibitory cell per pool

The clash lives in the two pools (emotions, impulses). Every member excites
the pool's interneuron and the interneuron inhibits every member, the same
global-feedback motif as APL over the Kenyon cells.

Instinct and memory are two parallel routes into the same emotions, as the
fly's lateral horn (hardwired valence) and mushroom body (learned valence)
both read the same odour. Instinct edges are not plastic: experience wins by
outvoting an instinct, never by erasing it. Needs act as gain on the senses
(hunger sharpens the food detector), which is where the fly paper puts
hunger too: at the sugar-sensing neurons, not downstream.

This module wires the network, runs a moment and reads and writes the pillar
(neuronshard.json, version 1.1). What she has learned lives in experience.py;
reading text lives in lexicon.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .engine import DT, POISSON_KICK, V_REST, V_TH, Engine
from .experience import EMOTIONS, FRAMES, Experience
from .lexicon import FRAME_WORDS, SENSE_WORDS, affinities, hits, tokens

VERSION = "1.1"
KINDS = ("ANCHOR", "SENSE", "COND", "MEMORY", "EMOTION", "IMPULSE", "INTERNEURON")

STATS = ("STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS")
IMPULSES = ("Speak", "Withdraw", "Approach", "Create", "Fight", "Flee", "Observe", "Comfort")

# Senses that are computed or felt from inside, beside the ones read from the moment.
#   Novelty, Familiar   expectation: nothing answers the stimulus, or it has been met before
#   Fatigue, Unease, Lonely, Craving   inner state
#   Relief              what sought-out pain turns into
SENSES = (*SENSE_WORDS, "Novelty", "Familiar", "Fatigue", "Unease", "Lonely", "Relief", "Craving")
NOT_EVENTS = (
    "Novelty",
    "Familiar",
    "Fatigue",
    "Unease",
    "Lonely",
    "Craving",
)  # these teach nothing

# (stat, emotion, strength). Strengths are the neuron@1.0 table, kept as the
# authored personality map; only the unit changed (see the *_SYN scales).
ANCHOR_EMOTION = (
    ("ATT", "Trust", 0.60), ("ATT", "Sadness", 0.35), ("INS", "Fear", 0.50), ("INS", "Sadness", 0.40),
    ("INS", "Curiosity", 0.35), ("TMP", "Anger", 0.55), ("TMP", "Surprise", 0.30), ("TMP", "Fear", 0.25),
    ("ACU", "Curiosity", 0.60), ("ACU", "Surprise", 0.30), ("PRS", "Trust", 0.45), ("PRS", "Joy", 0.35),
    ("CNV", "Anger", 0.30), ("CNV", "Trust", 0.30), ("END", "Trust", 0.40), ("END", "Joy", 0.25),
    ("VIG", "Joy", 0.50), ("VIG", "Surprise", 0.30), ("STR", "Anger", 0.40), ("DEX", "Surprise", 0.35),
)  # fmt: skip

# (emotion, impulse, strength, stat that scales it)
EMOTION_IMPULSE = (
    ("Joy", "Approach", 0.55, "PRS"), ("Joy", "Speak", 0.35, "PRS"), ("Fear", "Flee", 0.60, "INS"),
    ("Fear", "Withdraw", 0.45, "INS"), ("Sadness", "Withdraw", 0.55, "INS"), ("Sadness", "Comfort", 0.30, "ATT"),
    ("Curiosity", "Observe", 0.55, "ACU"), ("Curiosity", "Approach", 0.35, "ACU"), ("Anger", "Fight", 0.60, "TMP"),
    ("Anger", "Speak", 0.35, "TMP"), ("Trust", "Approach", 0.50, "ATT"), ("Trust", "Comfort", 0.45, "ATT"),
    ("Disgust", "Withdraw", 0.45, "CNV"), ("Surprise", "Observe", 0.40, "ACU"), ("Joy", "Create", 0.30, "PRS"),
)  # fmt: skip

# (sense, emotion, strength, stat that scales it). Starting dispositions; what
# things come to mean is learned on top. Novelty is the judgement call against
# the unknown: curiosity and caution both fire, temperament decides which is louder.
INNATE = (
    ("Threat", "Fear", 1.0, "INS"), ("Threat", "Anger", 0.7, "TMP"),
    ("Challenge", "Anger", 1.0, "TMP"), ("Challenge", "Fear", 0.4, "INS"),
    ("Kindness", "Trust", 0.9, "ATT"), ("Kindness", "Joy", 0.6, "PRS"),
    ("Distress", "Trust", 0.7, "ATT"), ("Distress", "Sadness", 0.6, "ATT"),
    ("Novelty", "Curiosity", 0.9, "ACU"), ("Novelty", "Fear", 0.6, "INS"),
    ("Familiar", "Trust", 0.6, "ATT"),
    ("Foul", "Disgust", 1.0, "CNV"),
    ("Sudden", "Surprise", 1.0, "DEX"), ("Sudden", "Fear", 0.4, "INS"),
    ("Food", "Joy", 0.3, "VIG"),
    ("Pain", "Fear", 0.8, "INS"), ("Pain", "Anger", 0.7, "TMP"), ("Pain", "Sadness", 0.4, "ATT"),
    ("Pleasure", "Joy", 1.0, "VIG"), ("Pleasure", "Trust", 0.5, "ATT"),
    ("Fatigue", "Anger", 0.3, "TMP"), ("Fatigue", "Sadness", 0.3, "ATT"),
    ("Unease", "Fear", 0.6, "INS"), ("Lonely", "Sadness", 0.4, "ATT"),
    ("Relief", "Joy", 0.6, "VIG"), ("Relief", "Trust", 0.6, "ATT"),
    ("Craving", "Sadness", 0.4, "ATT"), ("Craving", "Anger", 0.4, "TMP"),
)  # fmt: skip
# sense -> impulse, skipping emotion. Loneliness is a hunger for company, so it pulls toward whoever is there.
REFLEX = (("Food", "Approach", 1.0), ("Fatigue", "Withdraw", 0.8), ("Lonely", "Approach", 0.5))

# Needs are inputs owned by the runtime (the driveshard, when coupled): hunger,
# loneliness, fatigue, unsafe, each 0..1. A need acts two ways.
# sense -> (need, gain with the need at zero). Gain rises to 1 as the need fills.
# Feeling unsafe is not a gain: a knife is a knife however safe she felt. It is felt directly (Unease).
NEED_GAIN = {"Food": ("hunger", 0.15), "Kindness": ("loneliness", 0.6)}
INTERNAL = {
    "fatigue": "Fatigue",
    "unsafe": "Unease",
    "loneliness": "Lonely",
}  # need -> the sense that feels it
NEEDS = ("hunger", "loneliness", "fatigue", "unsafe")

# Synapse-count scales, hand-tuned by sweep. One synapse is 0.275 mV, and the
# fly model zeroes g on every spike, so a relay edge needs about 110 synapses
# to pass one spike per input spike. Strong edges sit near that; stat biases
# sit well under it and never fire a target alone.
ANCHOR_HZ_PER_POINT = 6.0  # a stat of 5 is a 30 Hz tonic input
ANCHOR_SYN = 40.0
INSTINCT_SYN = (
    110.0  # times strength times (0.5 + stat / 10): a middling stat relays, a low one does not
)
COND_SYN = 130.0  # a fully learned response is a little louder than a full instinct
MEMORY_SYN = 120.0
EMOTION_IMPULSE_SYN = 300.0
MOOD_RECALL_SYN = 12.0
POOL_IN_SYN = 50.0  # member -> interneuron
POOL_OUT_SYN = 40.0  # interneuron -> member
SENSE_HZ = 150.0  # drive on a sense, or a learned response, at full strength
MEMORY_HZ = 150.0  # drive on a fully relevant, full-weight memory
MOOD_HZ = 45.0  # mood is a bias: it tips contests and does not fire an emotion alone
FELT_REF = 40.0  # spikes in a moment that count as feeling an emotion fully
REMINDED = 0.5  # a thing brought to mind recalls memories at this share of a thing actually present
FULL_DRIVE_MV = 2.0 * (
    V_TH - V_REST
)  # sustained drive on a sense that counts as that sense at full strength

RING = {"INTERNEURON": 40.0, "EMOTION": 150.0, "COND": 235.0, "ANCHOR": 315.0, "SENSE": 400.0, "MEMORY": 485.0,
        "IMPULSE": 570.0}  # fmt: skip


@dataclass
class Node:
    label: str
    kind: str  # one of KINDS
    tonic_hz: float = 0.0
    ref: str = ""  # MEMORY: "<tier>:<index>" into the mind; otherwise empty
    text: str = ""  # MEMORY: searchable text, not serialized (re-read from the mind)
    weight: float = 1.0  # MEMORY: the entry's weight
    x: float = 0.0  # where a tool draws it; no effect on dynamics
    y: float = 0.0


def mind_entries(mind: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(mind, dict):
        return []
    out: list[tuple[str, Any]] = []
    core = mind.get("core")
    out += [(f"core:{i}", e) for i, e in enumerate(core if isinstance(core, list) else [])]
    for tier in ("long_term", "short_term"):
        slots = mind[tier].get("slots") if isinstance(mind.get(tier), dict) else None
        out += [(f"{tier}:{i}", e) for i, e in enumerate(slots if isinstance(slots, list) else [])]
    archive = mind.get("archive")
    out += [(f"archive:{i}", e) for i, e in enumerate(archive if isinstance(archive, list) else [])]
    return [(ref, e) for ref, e in out if isinstance(e, dict)]


def entry_text(entry: dict[str, Any]) -> str:
    parts = [
        entry.get(k)
        for k in ("entry_title", "the_moment", "the_shift", "the_truth", "summary", "content")
    ]
    tags = entry.get("tags")
    tags = tags if isinstance(tags, list) else []
    return " ".join(
        [p for p in parts if isinstance(p, str)] + [t for t in tags if isinstance(t, str)]
    )


def lay_out(nodes: list[Node]) -> None:
    """Concentric rings by kind, evenly spaced. Deterministic."""
    by_kind: dict[str, list[Node]] = {}
    for node in nodes:
        by_kind.setdefault(node.kind, []).append(node)
    for ring, (kind, members) in enumerate(
        sorted(by_kind.items(), key=lambda kv: RING.get(kv[0], 650.0))
    ):
        radius = RING.get(kind, 650.0)
        for i, node in enumerate(members):
            angle = 2 * math.pi * i / len(members) + 0.35 * ring
            node.x, node.y = round(radius * math.cos(angle), 2), round(radius * math.sin(angle), 2)


def _check(given: dict[str, float], allowed: tuple[str, ...] | set[str], what: str) -> None:
    unknown = sorted(set(given) - set(allowed))
    if unknown:
        raise ValueError(
            f"unknown {what}: {', '.join(unknown)}; one of {', '.join(sorted(allowed))}"
        )


def _clamp(x: float) -> float:
    return max(0.0, min(float(x), 1.0))


def _stat(raw: Any) -> float:
    return float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else 5.0


@dataclass
class Moment:
    """One moment, worked out and ready to run: what drives the network and why."""

    stimulus: str
    present: set[str]
    recruited: dict[int, float]
    reminded: dict[str, float]
    learned: dict[str, float]
    sensed: dict[str, float]
    reading: dict[str, float]
    mood: dict[str, float]
    rate: np.ndarray  # Poisson Hz per node
    inject: np.ndarray  # sustained mV per node (body parts, spec 8.9)
    unknown_drive: list[str]  # drive labels no node carries


class Brain:
    def __init__(self, nodes: list[Node], engine: Engine, xp: Experience | None = None) -> None:
        self.nodes = nodes
        self.engine = engine
        self.xp = xp or Experience()
        self.index = {(n.kind, n.label): i for i, n in enumerate(nodes)}
        self.by_label: dict[str, int] = {}
        for i, n in enumerate(nodes):
            self.by_label.setdefault(
                n.label, i
            )  # the first node carrying a label answers to it (spec 8.9)
        self.senses = {n.label for n in nodes if n.kind == "SENSE"}
        self._tonic = np.array([nd.tonic_hz for nd in nodes])
        self._memory_tokens = {
            i: tokens(nd.text) for i, nd in enumerate(nodes) if nd.kind == "MEMORY"
        }
        self._remembered: set[str] = set().union(*self._memory_tokens.values())
        self._emotion_ix = [self.index["EMOTION", e] for e in EMOTIONS]
        self._cond_ix = [self.index["COND", e] for e in EMOTIONS]

    # ── construction ──────────────────────────────────────────────
    @classmethod
    def build(cls, soul: dict[str, Any], mind: dict[str, Any] | None, seed: int) -> Brain:
        raw_stats = soul.get("stat_block") if isinstance(soul, dict) else None
        raw_stats = raw_stats if isinstance(raw_stats, dict) else {}
        stats = {k: _stat(raw_stats.get(k)) for k in STATS}

        nodes: list[Node] = [
            Node(k, "ANCHOR", tonic_hz=stats[k] * ANCHOR_HZ_PER_POINT) for k in STATS
        ]
        nodes += [Node(e, "EMOTION") for e in EMOTIONS]
        nodes += [Node(i, "IMPULSE") for i in IMPULSES]
        nodes += [Node("emotion_pool", "INTERNEURON"), Node("impulse_pool", "INTERNEURON")]
        nodes += [Node(s, "SENSE") for s in SENSES]
        nodes += [Node(e, "COND") for e in EMOTIONS]
        memories: list[tuple[int, dict[str, float]]] = []
        for ref, entry in mind_entries(mind):
            text = entry_text(entry)
            aff = affinities(text)
            if not aff:
                continue  # a memory with no feeling attached has nothing to say in a clash
            title = str(entry.get("entry_title") or ref)
            weight = max(0.1, min(_stat(entry.get("weight")) if "weight" in entry else 1.0, 2.0))
            memories.append((len(nodes), aff))
            nodes.append(Node(title, "MEMORY", ref=ref, text=text, weight=weight))
        lay_out(nodes)

        n = len(nodes)
        idx = {(nd.kind, nd.label): i for i, nd in enumerate(nodes)}
        sign = np.array([-1.0 if nd.kind == "INTERNEURON" else 1.0 for nd in nodes])
        syn = np.zeros((n, n))
        plastic = np.zeros((n, n), dtype=bool)

        for stat, emo, strength in ANCHOR_EMOTION:
            syn[idx["ANCHOR", stat], idx["EMOTION", emo]] = strength * ANCHOR_SYN
        for emo, imp, strength, stat in EMOTION_IMPULSE:
            a, b = idx["EMOTION", emo], idx["IMPULSE", imp]
            syn[a, b] = strength * (stats[stat] / 10.0) * EMOTION_IMPULSE_SYN
            plastic[a, b] = True
        for sense, emo, strength, stat in INNATE:
            syn[idx["SENSE", sense], idx["EMOTION", emo]] = (
                strength * (0.5 + stats[stat] / 10.0) * INSTINCT_SYN
            )
        for emo in EMOTIONS:
            syn[idx["COND", emo], idx["EMOTION", emo]] = COND_SYN
        for sense, imp, strength in REFLEX:
            syn[idx["SENSE", sense], idx["IMPULSE", imp]] = strength * INSTINCT_SYN
        for m, aff in memories:
            for emo, a in aff.items():
                e = idx["EMOTION", emo]
                syn[m, e] = a * nodes[m].weight * MEMORY_SYN
                plastic[m, e] = True
                syn[e, m] = a * MOOD_RECALL_SYN
        for pool, kind, names in (
            ("emotion_pool", "EMOTION", EMOTIONS),
            ("impulse_pool", "IMPULSE", IMPULSES),
        ):
            p = idx["INTERNEURON", pool]
            for name in names:
                syn[idx[kind, name], p] = POOL_IN_SYN
                syn[p, idx[kind, name]] = POOL_OUT_SYN

        return cls(nodes, Engine(sign, syn, plastic, seed))

    # ── perception ────────────────────────────────────────────────
    @staticmethod
    def present(stimulus: str, cues: tuple[str, ...] = ()) -> set[str]:
        """The things in a moment: the words of the stimulus plus any identities the runtime names."""
        for c in cues:
            if "+" in c or not c.strip():
                raise ValueError(f"cue {c!r} is empty or contains '+', which is reserved for pairs")
        return tokens(stimulus) | {c.lower() for c in cues}

    def relevance(
        self, stimulus: str, reminded: dict[str, float] | None = None
    ) -> dict[int, float]:
        """Memory node -> 0..1 by overlap with the stimulus and with what it brings to mind."""
        # shortcut: token overlap. Swap for the mind's own retrieval score
        # (QUICKENING already computes Recall.score) when this moves into a runtime.
        stim = tokens(stimulus)
        out: dict[int, float] = {}
        for i, toks in self._memory_tokens.items():
            hit = len(stim & toks) + REMINDED * sum(
                s for t, s in (reminded or {}).items() if t in toks
            )
            if hit > 0.05:
                out[i] = min(1.0, hit / 2)
        return out

    def sense(self, stimulus: str) -> dict[str, float]:
        """Sense -> 0..1 from the keyword tables. One mention is 0.6, each further one adds 0.2."""
        return {
            name: min(1.0, 0.6 + 0.2 * (n - 1)) for name, n in hits(stimulus, SENSE_WORDS).items()
        }

    # ── running ───────────────────────────────────────────────────
    def prepare(
        self,
        stimulus: str = "",
        needs: dict[str, float] | None = None,
        senses: dict[str, float] | None = None,
        cues: tuple[str, ...] = (),
        frames: dict[str, float] | None = None,
        drive: dict[str, float] | None = None,
        recall: str | None = None,
    ) -> Moment:
        """Work a moment out without running it: what she recalls, senses, reads into it, and the drive that makes.

        `senses` replaces the keyword perception, `cues` adds identities (who
        and what is present) and `frames` states the setting, when a runtime
        knows them. `drive` is sustained input in mV by node label, the form a
        body part's `neural` weights take (spec 6.3 and 8.9). `recall` is text
        that only stirs memories: a line of conversation whose words should
        bring things back without each word becoming a thing she learns about.
        """
        needs = needs or {}
        drive = drive or {}
        _check(needs, NEEDS, "need")
        if senses is not None:
            _check(senses, self.senses, "sense")
        if frames is not None:
            _check(frames, FRAMES, "frame")

        xp = self.xp
        present = self.present(stimulus, cues)
        reminded = xp.reminded(present)
        recruited = self.relevance(f"{stimulus} {recall}" if recall else stimulus, reminded)
        learned = xp.conditioned(present)

        raw = dict(senses) if senses is not None else self.sense(stimulus)
        for name, (need, floor) in NEED_GAIN.items():
            if name in raw:
                raw[name] *= floor + (1.0 - floor) * _clamp(needs.get(need, 0.0))
        for need, name in INTERNAL.items():
            if _clamp(needs.get(need, 0.0)) > 0.05:
                raw[name] = _clamp(needs[need])
        if present:
            # Whether this is new to her is hers to know; a runtime may still state it outright.
            # Someone her memories already speak of is no stranger, whatever name the runtime uses.
            remembered = sum(1 for c in present if c.rsplit(":", 1)[-1] in self._remembered)
            # That makes them less new, not more comforting: the memories speak for themselves.
            fresh = xp.novelty(present)
            unremembered = 1.0 - remembered / len(present)
            novelty = (1.0 - max(recruited.values(), default=0.0)) * fresh * unremembered
            if novelty > 0.05 and "Novelty" not in raw:
                raw["Novelty"] = novelty
            if 1.0 - fresh > 0.05 and "Familiar" not in raw:
                raw["Familiar"] = 1.0 - fresh
        # A body part driving a sense is that sense happening, so she appraises it and learns from it.
        inject = np.zeros(len(self.nodes))
        unknown: list[str] = []
        for label, mv in drive.items():
            i = self.by_label.get(label)
            if i is None:
                unknown.append(label)
            elif self.nodes[i].kind == "SENSE" and mv > 0:
                raw[label] = _clamp(raw.get(label, 0.0) + mv / FULL_DRIVE_MV)
            else:
                inject[i] += mv
        if frames is None:
            frames = {name: 1.0 for name in hits(stimulus, FRAME_WORDS)}
        sensed, reading = xp.appraise(raw, frames, learned, present)
        sensed = {name: _clamp(v) for name, v in sensed.items() if v > 0.01}

        pull = xp.pull(present)
        if pull > 0.05 and "Joy" in learned:
            learned = {**learned, "Joy": min(1.0, learned["Joy"] * (1.0 + pull))}

        rate = self._tonic.copy()
        for i, rel in recruited.items():
            rate[i] += rel * self.nodes[i].weight * MEMORY_HZ
        for name, strength in sensed.items():
            rate[self.index["SENSE", name]] += strength * SENSE_HZ
        mood = dict(xp.mood)
        for emo, i in zip(EMOTIONS, self._cond_ix, strict=True):
            rate[i] += learned.get(emo, 0.0) * SENSE_HZ + mood.get(emo, 0.0) * MOOD_HZ
        return Moment(
            stimulus,
            present,
            recruited,
            reminded,
            learned,
            sensed,
            reading,
            mood,
            rate,
            inject,
            unknown,
        )

    def deliberate(
        self,
        stimulus: str = "",
        ms: float = 600.0,
        learn: bool = True,
        bins: int = 6,
        needs: dict[str, float] | None = None,
        senses: dict[str, float] | None = None,
        cues: tuple[str, ...] = (),
        frames: dict[str, float] | None = None,
        drive: dict[str, float] | None = None,
        recall: str | None = None,
        seed: int | None = None,
    ) -> Result:
        """Run one moment.

        `learn=False` is a probe: the moment is run and taken back, leaving
        her exactly as she was, so the same probe gives the same answer every
        time. Pass `seed` to a probe to see one of the other ways the moment
        could have gone. The other arguments are prepare()'s.
        """
        if seed is not None and learn:
            raise ValueError("seed is for probes; a lived moment draws from her own RNG")
        m = self.prepare(stimulus, needs, senses, cues, frames, drive, recall)
        eng = self.engine
        steps = int(round(ms / DT))
        memory = None
        if learn:
            trace = eng.run(m.rate, steps, True, bins, m.inject)
            total = trace.sum(axis=0)
            felt = {
                e: min(1.0, float(total[i]) / FELT_REF)
                for e, i in zip(EMOTIONS, self._emotion_ix, strict=True)
            }
            harm = max(m.sensed.get("Pain", 0.0), m.sensed.get("Threat", 0.0))
            outcome = self.xp.live(m.present, self._happened(m.sensed), harm, felt)
            memory = self._memory(m, outcome, felt)
        else:
            snap = eng.snapshot()
            if seed is not None:
                eng.rng = np.random.Generator(np.random.PCG64(seed))
            trace = eng.run(m.rate, steps, False, bins, m.inject)
            if seed is not None:
                eng.rng = np.random.Generator(np.random.PCG64(0))  # restore() sets its state next
            eng.restore(snap)
        return Result(self, m, trace, ms, memory)

    def _happened(self, sensed: dict[str, float]) -> dict[str, float]:
        """Emotion -> 0..1: her innate reaction to the events of the moment, read off her own wiring.

        Harm, in the caller, is being hurt or threatened as she read it. A
        rival's blow in a match makes her angry and is not harm.
        """
        syn = self.engine.syn
        out = dict.fromkeys(EMOTIONS, 0.0)
        for name, strength in sensed.items():
            if name not in NOT_EVENTS:
                row = syn[self.index["SENSE", name]]
                for emo, i in zip(EMOTIONS, self._emotion_ix, strict=True):
                    out[emo] += strength * float(row[i])
        return {emo: min(1.0, total / INSTINCT_SYN) for emo, total in out.items()}

    def _memory(
        self, m: Moment, outcome: dict[str, Any], felt: dict[str, float]
    ) -> dict[str, Any] | None:
        """A mind entry for a moment strong enough to keep, or None.

        Written the 1st, 3rd, 10th, 30th and 100th time the same things come
        together this strongly, so a pattern is remembered as a pattern and
        not as a hundred entries. The runtime stamps the time and files it;
        this function neither reads a clock nor touches the mind.
        """
        # shortcut: template prose. An LLM, as the escalation step, can rewrite
        # the three sentences in her voice; the facts in them come from here.
        times = outcome["times"]
        if times not in (1, 3, 10, 30, 100):
            return None
        things = sorted(m.present)
        feeling = max(felt, key=lambda e: (felt[e], e))
        about = m.stimulus.strip() or "A moment with " + ", ".join(things)
        if outcome["trauma"] >= 0.5:
            kind, truth = "trauma", "This does not leave me."
        elif outcome["betrayed"]:
            kind, truth = "betrayal", "It was made right, and then it happened again."
        elif outcome["harm"] > outcome["good"]:
            kind, truth = "harm", "It hurt, and I will be ready for it."
        else:
            kind, truth = "good", "It was good, and I want it again."
        if times > 1:
            truth += f" It has happened {times} times now."
        learned = self.xp.conditioned(m.present)
        strongest = max(learned, key=lambda e: (learned[e], e)) if learned else feeling
        return {
            "entry_title": about[:80],
            "the_moment": about,
            "the_shift": f"I felt {feeling.lower()}. These things now mean {strongest.lower()} to me: {', '.join(things[:6])}.",
            "the_truth": truth,
            "tags": [kind, *things[:6]],
            "weight": round(
                0.5 + 0.5 * max(outcome["harm"], outcome["good"], float(outcome["betrayed"])), 2
            ),
            "suggested_tier": "core" if kind in ("trauma", "betrayal") else "short_term",
        }

    def rest(self, hours: float) -> None:
        """Time passes with nothing happening."""
        if hours < 0:
            raise ValueError("hours must be 0 or more")
        self.xp.rest(hours)

    def imprint(self, phrase: str, feelings: dict[str, float], cues: tuple[str, ...] = ()) -> None:
        """Author a learned response for a phrase (see Experience.imprint)."""
        self.xp.imprint(self.present(phrase, cues), feelings)

    def poke(self, index: int) -> None:
        """Fire one neuron by hand (a tool's double-click)."""
        self.engine.v[index] += POISSON_KICK

    def activation(self) -> np.ndarray:
        """0..1 per node: how close each membrane is to threshold."""
        return np.clip((self.engine.v - V_REST) / (V_TH - V_REST), 0.0, 1.0)

    # ── the pillar ────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        """The neuronshard.json document, version 1.1."""
        eng = self.engine
        src, dst = np.nonzero(eng.syn)
        return {
            "version": VERSION,
            "nodes": [
                {
                    "id": i,
                    "label": nd.label,
                    "kind": nd.kind,
                    "tonic_hz": nd.tonic_hz,
                    "ref": nd.ref,
                    "weight": nd.weight,
                    "x": nd.x,
                    "y": nd.y,
                }
                for i, nd in enumerate(self.nodes)
            ],  # fmt: skip
            "edges": [
                {
                    "src": int(a),
                    "dst": int(b),
                    "syn": float(eng.syn[a, b]),
                    "plastic": bool(eng.plastic[a, b]),
                }
                for a, b in zip(src, dst, strict=True)
            ],
            "experience": self.xp.to_dict(),
            "state": eng.state(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], mind: dict[str, Any] | None = None) -> Brain:
        """Rebuild from a pillar. `mind` supplies the text of the memories the nodes point at."""
        problems = errors(data)
        if problems:
            raise ValueError("not a usable neuronshard 1.1: " + "; ".join(problems))
        texts = {ref: entry_text(entry) for ref, entry in mind_entries(mind)}
        nodes = [
            Node(r["label"], r["kind"], float(r.get("tonic_hz", 0.0)), r.get("ref", ""), texts.get(r.get("ref", ""), ""),
                 float(r.get("weight", 1.0)), float(r.get("x", 0.0)), float(r.get("y", 0.0)))
            for r in data["nodes"]
        ]  # fmt: skip
        n = len(nodes)
        sign = np.array([-1.0 if nd.kind == "INTERNEURON" else 1.0 for nd in nodes])
        syn = np.zeros((n, n))
        plastic = np.zeros((n, n), dtype=bool)
        for e in data["edges"]:
            syn[e["src"], e["dst"]] = e["syn"]
            plastic[e["src"], e["dst"]] = bool(e.get("plastic", False))
        engine = Engine(sign, syn, plastic, seed=int(data.get("seed", 0)))
        if isinstance(data.get("state"), dict):
            engine.load_state(data["state"])
        xp = Experience.from_dict(data["experience"]) if data.get("experience") else Experience()
        return cls(nodes, engine, xp)


REQUIRED_NODES = (
    [("EMOTION", e) for e in EMOTIONS] + [("COND", e) for e in EMOTIONS] + [("IMPULSE", i) for i in IMPULSES]
    + [("SENSE", s) for s in SENSES]
)  # fmt: skip


def errors(doc: Any) -> list[str]:
    """Why a document is not a usable neuronshard 1.1, or [] when it is."""
    if not isinstance(doc, dict):
        return ["neuronshard.json is not an object"]
    if doc.get("version") != VERSION:
        return [f"unsupported neuronshard version: {doc.get('version')!r}"]
    nodes, edges = doc.get("nodes"), doc.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["needs a nodes list and an edges list"]
    found: list[str] = []
    seen: set[tuple[str, str]] = set()
    for position, node in enumerate(nodes):
        if not isinstance(node, dict) or node.get("id") != position:
            found.append(f"node {position}: id does not match its position")
        elif (
            not isinstance(node.get("label"), str)
            or not node["label"].strip()
            or node.get("kind") not in KINDS
        ):
            found.append(f"node {position}: needs a label and a known kind")
        elif (node["kind"], node["label"]) in seen:
            found.append(f"node {position}: a second {node['kind']} labelled {node['label']!r}")
        else:
            seen.add((node["kind"], node["label"]))
    for kind, label in REQUIRED_NODES:
        if (kind, label) not in seen and len(found) < 8:
            found.append(f"missing the {kind} node {label!r}")
    count = len(nodes)
    for position, edge in enumerate(edges):
        ok = (
            isinstance(edge, dict)
            and all(isinstance(edge.get(k), int) and not isinstance(edge.get(k), bool) and 0 <= edge[k] < count
                    for k in ("src", "dst"))
            and edge["src"] != edge["dst"]
            and isinstance(edge.get("syn"), (int, float)) and not isinstance(edge.get("syn"), bool)
            and math.isfinite(edge["syn"]) and edge["syn"] >= 0
        )  # fmt: skip
        if not ok:
            found.append(f"edge {position}: bad endpoints or synapse count")
    if "experience" in doc and not isinstance(doc["experience"], dict):
        found.append("experience is not an object")
    if "state" in doc and not isinstance(doc["state"], dict):
        found.append("state is not an object")
    return found[:8]


@dataclass
class Result:
    brain: Brain
    moment: Moment
    trace: np.ndarray  # (bins, nodes) spike counts
    ms: float
    memory: dict[str, Any] | None = (
        None  # a mind entry for a moment worth keeping (lived moments only)
    )

    @property
    def stimulus(self) -> str:
        return self.moment.stimulus

    @property
    def recruited(self) -> dict[int, float]:
        return self.moment.recruited

    @property
    def sensed(self) -> dict[str, float]:
        """What she took the moment to be, after appraisal."""
        return self.moment.sensed

    @property
    def learned(self) -> dict[str, float]:
        """What the things present have come to mean."""
        return self.moment.learned

    @property
    def mood(self) -> dict[str, float]:
        """As she walked into the moment."""
        return self.moment.mood

    @property
    def reading(self) -> dict[str, float]:
        """How she took it: hostile, benign, contest, wanted, craving."""
        return self.moment.reading

    @property
    def reminded(self) -> dict[str, float]:
        """Things not present that the moment brought to mind."""
        return self.moment.reminded

    def counts(self, kind: str) -> list[tuple[str, int]]:
        total = self.trace.sum(axis=0)
        rows = [
            (nd.label, int(total[i])) for i, nd in enumerate(self.brain.nodes) if nd.kind == kind
        ]
        return sorted(rows, key=lambda r: (-r[1], r[0]))

    def spikes(self, kind: str, label: str) -> int:
        return int(self.trace[:, self.brain.index[kind, label]].sum())

    @property
    def winner(self) -> str | None:
        top = self.counts("IMPULSE")
        return top[0][0] if top and top[0][1] > 0 else None

    @property
    def margin(self) -> float:
        """0 is a dead heat, 1 is uncontested."""
        (_, a), (_, b) = self.counts("IMPULSE")[:2]
        return (a - b) / (a + b) if a + b else 0.0

    def leaders(self) -> list[str]:
        """Leading impulse per time bin, '-' where nothing fired."""
        ids = [i for i, nd in enumerate(self.brain.nodes) if nd.kind == "IMPULSE"]
        out = []
        for row in self.trace:
            best = max(ids, key=lambda i: (row[i], -i))
            out.append(self.brain.nodes[best].label if row[best] else "-")
        return out
