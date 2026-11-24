"""Experience: everything about her that changes because of what she has lived.

No spiking here. The brain asks this object three questions each moment (what
do the things present mean to her, how does she take what her senses report,
and what does this moment teach) and reads the answers into the network as
drive on its neurons. This is the state that belongs in the neuron pillar.

    assoc     what each thing, and each pair of things, has come to mean
    met       how many eventful moments each of those has been part of
    grudge    betrayals per thing, and whether a making-up is under way
    exposure  how often each thing has simply been around (habituation)
    distrust  one number: how she expects people to treat her
    habit     liked things she has come to depend on
    mood      a slow trace of what she has been feeling
    scar      how traumatic the worst moment with each thing was
    told      how many times each kind of strong moment has happened (for memories)
"""

from __future__ import annotations

from typing import Any

EMOTIONS = ("Joy", "Fear", "Sadness", "Curiosity", "Anger", "Trust", "Disgust", "Surprise")
AVERSIVE = ("Fear", "Anger", "Sadness", "Disgust")
APPETITIVE = ("Joy", "Trust")
FRAMES = ("Contest", "Wanted", "Hostile")

HABITUATION = 0.75  # each meeting leaves this much of a thing's novelty

BIND = 0.25  # share of the gap to what happened that one moment closes
BIND_HARM = 0.5  # harm is learned twice as fast as anything else
EXTINCTION = 0.1  # unlearning runs at a tenth of learning
CONSOLIDATE = 0.5  # and stops at half the peak
EVENT = 0.2  # how much harm or good has to happen for a moment to count as either
LAYER = 0.25  # each further thing a cue has been paired with in the same feeling adds this much
SECOND_CUE = 0.3  # the strongest cue leads; the next one adds this share of itself
AUTHORED_MET = 8  # an imprinted response counts as this well known
TRAUMA_FROM = 0.7  # harm past this is trauma: learned in one moment and kept
MEMORABLE = 0.6  # harm or good past this makes a moment worth a memory of its own
REMIND_FROM = 2  # eventful moments two things must share before one brings the other to mind

DISTRUST_PER_HARM = 0.03  # each harmful moment, times how bad it was
DISTRUST_PER_BETRAYAL = 0.1
DISTRUST_PER_KINDNESS = 0.01  # and what a good moment gives back
DISTRUST_HALF_LIFE_H = 24.0 * 90  # quiet time alone barely heals it

HABIT_FROM = 0.5  # how well liked a thing must be before it can become a habit
HABIT_STEP = 0.03  # dependence gained each time it pays off
CRAVING_HOURS = 12.0  # time without it for the craving to reach half strength
CRAVING_DULLS = 0.4  # how much a full craving takes off every other pleasure

MOOD_GAIN = 0.3
MOOD_KEEP = 0.85  # carried from one moment to the next
MOOD_HALF_LIFE_H = 3.0  # and halved by this many hours of rest


def pair(a: str, b: str) -> str:
    return f"{a}+{b}" if a < b else f"{b}+{a}"


class Experience:
    def __init__(self) -> None:
        self.assoc: dict[
            str, dict[str, tuple[float, float]]
        ] = {}  # cue -> emotion -> (strength, peak)
        self.met: dict[str, int] = {}
        self.grudge: dict[str, list[int | bool]] = {}  # cue -> [betrayals, making up]
        self.exposure: dict[str, int] = {}
        self.distrust = 0.0
        self.habit: dict[
            str, list[float]
        ] = {}  # cue -> [dependence 0..1, hours since she last had it]
        self.mood: dict[str, float] = {}
        self.scar: dict[str, float] = {}  # cue -> 0..1
        self.told: dict[str, int] = {}  # the things in a strong moment -> times it has happened

    # ── what things mean ──────────────────────────────────────────
    @staticmethod
    def cues(present: set[str]) -> list[str]:
        """Every thing present, plus every pair of them.

        The pairs make "Dax + hit" a thing of its own beside "Dax" and "hit".
        A blow from Dax can come to mean something a blow from anyone else
        does not, while "hit" alone keeps collecting from everyone who did it.
        """
        # shortcut: all pairs, so a long sentence makes many. A scene-driven
        # runtime should pair actors with acts instead of every word with every word.
        single = sorted(present)
        return single + [f"{a}+{b}" for i, a in enumerate(single) for b in single[i + 1 :]]

    def novelty(self, present: set[str]) -> float:
        """1 for things never met, falling toward 0 as they become familiar."""
        if not present:
            return 0.0
        return sum(HABITUATION ** self.exposure.get(t, 0) for t in present) / len(present)

    def conditioned(self, present: set[str]) -> dict[str, float]:
        """Emotion -> 0..1: what the things present have come to mean to her.

        Specific beats general, in proportion to how well she knows the
        specific. A pair she has lived a dozen times ("rolf+slap") speaks for
        both of its halves, so a slap from Rolf is not softened by what a slap
        from Dax means. A pair met once only half silences them. With no pair
        to go on (a newcomer), the lone things answer, and they layer: "hit"
        learned from four people is louder than "hit" learned from one.
        """
        single = sorted(present)
        pairs = [
            k
            for i, a in enumerate(single)
            for b in single[i + 1 :]
            if (k := f"{a}+{b}") in self.assoc
        ]
        spoken_for: dict[str, float] = {}
        for key in pairs:
            known = 1.0 - 0.5 ** self.met.get(key, 1)
            for half in key.split("+"):
                spoken_for[half] = max(spoken_for.get(half, 0.0), known)
        alone = [c for c in single if c in self.assoc]
        breadth = self._breadth(set(alone))
        out: dict[str, float] = {}
        for emo in EMOTIONS:
            vals = [self.assoc[k][emo][0] for k in pairs if emo in self.assoc[k]]
            for c in alone:
                if emo in self.assoc[c]:
                    layered = min(
                        1.0, self.assoc[c][emo][0] * (1.0 + LAYER * (breadth.get((c, emo), 1) - 1))
                    )
                    vals.append(layered * (1.0 - spoken_for.get(c, 0.0)))
            if vals:
                vals.sort(reverse=True)
                strength = min(1.0, vals[0] + (SECOND_CUE * vals[1] if len(vals) > 1 else 0.0))
                if strength > 0.05:
                    out[emo] = strength
        return out

    def reminded(self, present: set[str], top: int = 5) -> dict[str, float]:
        """Thing not here -> 0..1: what the things here bring to mind.

        Two things that have shared eventful moments recall each other, more
        strongly the more moments they shared. A cigar brings back the
        grandfather who smoked them, and with him the rest of the scene.
        """
        # shortcut: scans every learned pair, like _breadth. Same index fixes both.
        out: dict[str, float] = {}
        for key, n in self.met.items():
            if n >= REMIND_FROM and "+" in key:
                a, b = key.split("+")
                other = b if a in present else a if b in present else None
                if other is not None and other not in present:
                    out[other] = max(out.get(other, 0.0), 1.0 - 0.5 ** (n - REMIND_FROM + 1))
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))[:top])

    def _breadth(self, wanted: set[str]) -> dict[tuple[str, str], int]:
        """(cue, emotion) -> how many different things the cue has been paired with in that feeling."""
        # shortcut: one pass over every learned pair per moment. Index pairs by half if the table gets large.
        out: dict[tuple[str, str], int] = {}
        if not wanted:
            return out
        for key, slot in self.assoc.items():
            if "+" not in key:
                continue
            for half in key.split("+"):
                if half in wanted:
                    for emo, (value, _) in slot.items():
                        if value > EVENT:
                            out[half, emo] = out.get((half, emo), 0) + 1
        return out

    # ── how she takes a moment ────────────────────────────────────
    def appraise(
        self,
        raw: dict[str, float],
        frames: dict[str, float],
        learned: dict[str, float],
        present: set[str],
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Turn what her senses report into what she takes it to be.

        The same blow is a rival's point in a match, a relief she asked for,
        or an attack, and only the last is harm. Where the setting does not
        say, she fills it in from what she already believes: dread of who is
        present and distrust of people in general push toward "meant to hurt
        me", trust pushes toward "did not mean it", and affection in the same
        moment argues against malice.

        Distrust also discounts kindness and keeps her on edge with everyone.
        An unfed habit nags at her and dulls every other pleasure.
        """
        s = dict(raw)
        contest, wanted, stated = (
            frames.get("Contest", 0.0),
            frames.get("Wanted", 0.0),
            frames.get("Hostile", 0.0),
        )
        pain = s.get("Pain", 0.0)
        reading: dict[str, float] = {}
        if pain:
            hostile, benign = stated, 0.0
            if not (contest or wanted):
                dread = max(learned.get("Fear", 0.0), learned.get("Anger", 0.0))
                warmth = max(s.get("Pleasure", 0.0), s.get("Kindness", 0.0))
                hostile = min(1.0, max(stated, (0.6 * dread + self.distrust) * (1.0 - warmth)))
                if not stated:
                    benign = 0.5 * learned.get("Trust", 0.0)
            s["Pain"] = min(
                1.0,
                pain
                * (1 + 0.3 * hostile)
                * (1 - 0.4 * benign)
                * (1 - 0.85 * contest)
                * (1 - 0.85 * wanted),
            )
            for sense, amount in (
                ("Threat", 0.5 * hostile),
                ("Challenge", 0.6 * contest),
                ("Relief", 0.7 * wanted),
            ):
                if amount * pain > 0.01:
                    s[sense] = min(1.0, s.get(sense, 0.0) + amount * pain)
            named = (
                ("hostile", hostile),
                ("benign", benign),
                ("contest", contest),
                ("wanted", wanted),
            )
            reading = {k: v for k, v in named if v > 0.05}
        elif stated:
            s["Threat"] = min(
                1.0, s.get("Threat", 0.0) + 0.4 * stated
            )  # someone's rage is a threat before a blow lands
            reading["hostile"] = stated
        if self.distrust > 0.05:
            if "Kindness" in s:
                s["Kindness"] *= 1.0 - 0.6 * self.distrust
            if "Familiar" in s:
                s["Familiar"] *= 1.0 - self.distrust
            s["Unease"] = max(s.get("Unease", 0.0), self.distrust)
        if "Familiar" in s:
            # Familiar comfort only where nothing bad has been learned about what is here.
            s["Familiar"] *= 1.0 - max((learned.get(e, 0.0) for e in AVERSIVE), default=0.0)
        craving = max(
            (self.want(c) for c in self.habit if not self._at_hand(c, present)), default=0.0
        )
        if craving > 0.05:
            s["Craving"] = craving
            for pleasure in ("Pleasure", "Kindness", "Food"):
                if pleasure in s:
                    s[pleasure] *= 1.0 - CRAVING_DULLS * craving
            reading["craving"] = craving
        return s, reading

    def want(self, cue: str) -> float:
        dependence, hours = self.habit[cue]
        return dependence * (1.0 - 0.5 ** (hours / CRAVING_HOURS))

    def _at_hand(self, cue: str, present: set[str]) -> bool:
        """The habit is here, or something she has enjoyed it together with is."""
        if cue in present:
            return True
        return any(
            self.assoc.get(pair(cue, p), {}).get("Joy", (0.0, 0.0))[0] > HABIT_FROM for p in present
        )

    def pull(self, present: set[str]) -> float:
        """How hard a habit in front of her tugs: stronger the longer she has gone without."""
        return max((self.want(c) for c in self.habit if c in present), default=0.0)

    # ── what a moment teaches ─────────────────────────────────────
    def live(
        self, present: set[str], happened: dict[str, float], harm: float, felt: dict[str, float]
    ) -> dict[str, Any]:
        """Take a lived moment in. Returns what kind of moment it was (see the last lines).

        `happened` is emotion -> 0..1, the innate reaction to what her senses
        reported after she appraised it. `harm` is how hurt or threatened she
        was by her own reading. `felt` is emotion -> 0..1, what actually fired.
        """
        for t in sorted(present):
            self.exposure[t] = self.exposure.get(t, 0) + 1
        good = max(happened.get(e, 0.0) for e in APPETITIVE)
        betrayed = self._bind(present, happened, harm, good)
        if harm > EVENT and good <= EVENT:  # harm with nothing good in it
            self.distrust = min(
                1.0, self.distrust + DISTRUST_PER_HARM * harm + DISTRUST_PER_BETRAYAL * betrayed
            )
        elif good > EVENT and harm <= EVENT:
            self.distrust = max(0.0, self.distrust - DISTRUST_PER_KINDNESS * good)
        if good > EVENT:
            for cue in sorted(present):
                if cue in self.habit:
                    self.habit[cue][1] = 0.0  # she got it
                if good > 0.5 and self.assoc.get(cue, {}).get("Joy", (0.0, 0.0))[0] > HABIT_FROM:
                    entry = self.habit.setdefault(cue, [0.0, 0.0])
                    entry[0] = min(1.0, entry[0] + HABIT_STEP * good)
        for emo in EMOTIONS:
            level = min(1.0, self.mood.get(emo, 0.0) * MOOD_KEEP + MOOD_GAIN * felt.get(emo, 0.0))
            if level > 0.01:
                self.mood[emo] = level
            else:
                self.mood.pop(emo, None)
        trauma = max(0.0, (harm - TRAUMA_FROM) / (1.0 - TRAUMA_FROM))
        outcome: dict[str, Any] = {
            "harm": harm,
            "good": good,
            "betrayed": betrayed,
            "trauma": trauma,
            "times": 0,
        }
        if betrayed or max(harm, good) >= MEMORABLE:
            key = " ".join(sorted(present))
            self.told[key] = outcome["times"] = self.told.get(key, 0) + 1
        return outcome

    def _bind(
        self, present: set[str], happened: dict[str, float], harm: float, good: float
    ) -> bool:
        """Bind everything present to what happened. Returns whether this moment was a betrayal.

        Only events teach. Her anticipation, her needs and her mood are kept
        out of `happened` by the caller, which is what lets a fear fade when
        the feared thing stops happening and stops it re-teaching itself.

        Harm binds at BIND_HARM, everything else at BIND. Unbinding runs at
        EXTINCTION times BIND and stops at CONSOLIDATE times the peak: a
        learned response fades toward half, never to nothing.

        Trust is slower and more fragile than fear. Kindness binds more slowly
        to something she dreads, and harm with nothing good in it cuts what
        she liked about everything present at the harm rate.

        Forgiveness wears out. Harm arriving after a making-up had begun is a
        betrayal, and each one halves, for that cue: how fast its fear fades,
        how far it can fade, and how much trust kindness can rebuild.

        Trauma is different in kind. Harm past TRAUMA_FROM binds in a single
        moment and leaves a scar on everything present; a full scar means the
        fear it taught does not fade at all.
        """
        trauma = max(0.0, (harm - TRAUMA_FROM) / (1.0 - TRAUMA_FROM))
        eventful = harm > EVENT or max(happened.values(), default=0.0) > EVENT
        betrayed = False
        for cue in self.cues(present):
            if cue not in self.assoc:
                if not eventful:
                    continue  # nothing happened, so nothing new is worth remembering
                self.assoc[cue] = self._inherit(cue)
            slot = self.assoc[cue]
            count, making_up = self.grudge.get(cue, [0, False])
            if harm > EVENT:
                if making_up:
                    count += 1
                    betrayed = True
                making_up = False
            elif good > EVENT and any(slot.get(e, (0.0, 0.0))[0] > 0.05 for e in AVERSIVE):
                making_up = True
            if count or making_up:
                self.grudge[cue] = [count, making_up]
            if trauma > self.scar.get(cue, 0.0):
                self.scar[cue] = trauma
            healable = 1.0 - self.scar.get(cue, 0.0)
            trust_left = 0.5**count
            dread = max((slot.get(e, (0.0, 0.0))[0] for e in AVERSIVE), default=0.0)
            for e in EMOTIONS:
                target = happened.get(e, 0.0)
                value, peak = slot.get(e, (0.0, 0.0))
                if e in AVERSIVE:
                    if target > value:
                        value += (BIND_HARM + (1.0 - BIND_HARM) * trauma) * (target - value)
                        peak = max(peak, value)
                    else:
                        floor = (1.0 - (1.0 - CONSOLIDATE) * trust_left * healable) * peak
                        value = max(
                            value - BIND * EXTINCTION * trust_left * (value - target), floor
                        )
                elif e in APPETITIVE:
                    target *= trust_left
                    if target > value:
                        value += BIND * (1.0 - dread) * (target - value)
                        peak = max(peak, value)
                    else:
                        rate = BIND_HARM if harm > EVENT else BIND * EXTINCTION
                        value = max(
                            value - rate * (value - target), CONSOLIDATE * trust_left * peak
                        )
                elif target > value:
                    value += BIND * (target - value)
                    peak = max(peak, value)
                else:
                    value = max(value - BIND * EXTINCTION * (value - target), CONSOLIDATE * peak)
                if value > 0.01:
                    slot[e] = (value, peak)
                elif e in slot:
                    del slot[e]
            if not slot:
                del self.assoc[cue]
            elif eventful:
                self.met[cue] = self.met.get(cue, 0) + 1
        return betrayed

    def _inherit(self, cue: str) -> dict[str, tuple[float, float]]:
        """A new combination starts out meaning what its parts mean.

        The first time Dax does something at the well, "dax+well" begins from
        what she already feels about Dax, then goes its own way. The inherited
        strength carries no peak: only what the pair itself teaches is kept
        against fading, so a pair can fully unlearn what it merely assumed.
        """
        if "+" not in cue:
            return {}
        out: dict[str, tuple[float, float]] = {}
        for half in cue.split("+"):
            for emo, (value, _) in self.assoc.get(half, {}).items():
                if value > out.get(emo, (0.0, 0.0))[0]:
                    out[emo] = (value, 0.0)
        return out

    def rest(self, hours: float) -> None:
        """Time passes with nothing happening. Mood drains, habits go unfed, and what she has learned stays."""
        keep = 0.5 ** (hours / MOOD_HALF_LIFE_H)
        self.mood = {e: v * keep for e, v in self.mood.items() if v * keep > 0.01}
        self.distrust *= 0.5 ** (hours / DISTRUST_HALF_LIFE_H)
        for entry in self.habit.values():
            entry[1] += hours

    # ── authoring and inspection (what an editor calls) ───────────
    def imprint(self, things: set[str], feelings: dict[str, float]) -> None:
        """Author a learned response: give her a history she did not live.

        Writes the same table experience writes (the thing itself when there
        is one, the pairs when there are several, since a phrase is about the
        combination), so an authored taste behaves like an earned one: it can
        be outvoted and it fades no further than half.
        """
        for emo, strength in feelings.items():
            if emo not in EMOTIONS:
                raise ValueError(f"unknown emotion {emo!r}; one of {', '.join(EMOTIONS)}")
            if not 0.0 <= strength <= 1.0:
                raise ValueError(f"{emo} strength must be 0..1, got {strength}")
        if not things:
            raise ValueError("nothing to imprint: the phrase has no usable words")
        targets = self.cues(things)
        if len(things) > 1:
            targets = [c for c in targets if "+" in c]
        for cue in targets:
            slot = self.assoc.setdefault(cue, {})
            for emo, strength in feelings.items():
                if strength > 0.01:
                    slot[emo] = (
                        float(strength),
                        max(slot.get(emo, (0.0, 0.0))[1], float(strength)),
                    )
                else:
                    slot.pop(emo, None)
            if slot:
                self.met[cue] = max(self.met.get(cue, 0), AUTHORED_MET)
            else:
                del self.assoc[cue]

    def describe(self, top: int = 12) -> list[str]:
        """Who she has become, in lines a person can read."""
        lines = []
        ranked = sorted(
            self.assoc.items(), key=lambda kv: (-max(v for v, _ in kv[1].values()), kv[0])
        )
        for cue, slot in ranked[:top]:
            feelings = "  ".join(
                f"{e} {v:.2f}" for e, (v, _) in sorted(slot.items(), key=lambda kv: -kv[1][0])
            )
            count = self.grudge.get(cue, [0, False])[0]
            notes = [f"betrayed {count}x"] if count else []
            if self.scar.get(cue, 0.0) > 0.3:
                notes.append(f"scar {self.scar[cue]:.2f}")
            lines.append(f"{cue:<22} {feelings}" + (f"  ({', '.join(notes)})" if notes else ""))
        if len(ranked) > top:
            lines.append(f"... and {len(ranked) - top} more learned cues")
        if self.distrust > 0.01:
            lines.append(f"distrust of people in general: {self.distrust:.2f}")
        for cue, (dependence, hours) in sorted(self.habit.items(), key=lambda kv: -kv[1][0]):
            if dependence > 0.05:
                lines.append(
                    f"habit: {cue}, dependence {dependence:.2f}, {hours:.0f} h since, craving {self.want(cue):.2f}"
                )
        if self.mood:
            lines.append(
                "mood: "
                + "  ".join(
                    f"{e} {v:.2f}" for e, v in sorted(self.mood.items(), key=lambda kv: -kv[1])
                )
            )
        return lines or ["nothing learned yet"]

    # ── persistence ───────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return {
            "assoc": {
                c: {e: list(vp) for e, vp in slot.items()} for c, slot in sorted(self.assoc.items())
            },
            "met": dict(sorted(self.met.items())),
            "grudge": {c: list(g) for c, g in sorted(self.grudge.items())},
            "exposure": dict(sorted(self.exposure.items())),
            "distrust": self.distrust,
            "habit": {c: list(h) for c, h in sorted(self.habit.items())},
            "mood": dict(sorted(self.mood.items())),
            "scar": dict(sorted(self.scar.items())),
            "told": dict(sorted(self.told.items())),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Experience:
        """Read the experience block of a pillar. A missing table is an empty one."""
        xp = cls()

        def table(key: str) -> dict[str, Any]:
            value = data.get(key)
            return value if isinstance(value, dict) else {}

        xp.assoc = {
            c: {e: (float(v), float(p)) for e, (v, p) in slot.items()}
            for c, slot in table("assoc").items()
        }
        xp.met = {c: int(n) for c, n in table("met").items()}
        xp.grudge = {c: [int(g[0]), bool(g[1])] for c, g in table("grudge").items()}
        xp.exposure = {c: int(n) for c, n in table("exposure").items()}
        xp.distrust = float(data.get("distrust", 0.0))
        xp.habit = {c: [float(h[0]), float(h[1])] for c, h in table("habit").items()}
        xp.mood = {e: float(v) for e, v in table("mood").items()}
        xp.scar = {c: float(v) for c, v in table("scar").items()}
        xp.told = {c: int(n) for c, n in table("told").items()}
        return xp
