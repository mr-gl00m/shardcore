"""The bridge between a conversation and a brain.

A language model can speak in a character's voice. It cannot, by itself, be
hurt by the tenth insult, warm to someone who has been kind for a month, or
come into a conversation in a bad mood. The brain can, and this module passes
that across in both directions:

    in    perceive   what was said becomes senses, a setting and who is present
    out   stance     how the character now feels and is inclined to act, as
                     plain lines for the model's system prompt

The model is the translation layer at both ends and nothing more. It does not
decide what the character feels; the brain does, deterministically, from the
wiring and the history. No function here calls a model: `perception_request`
builds the prompt and schema, the runtime sends it to whatever local model it
uses, and `read_perception` checks what comes back. Without a model,
`perceive_words` reads the keyword tables, which is crude but needs nothing.
"""

from __future__ import annotations

import json
from typing import Any

from .experience import AVERSIVE, EMOTIONS, FRAMES
from .lexicon import FRAME_WORDS, SENSE_WORDS, hits
from .wiring import FELT_REF, Brain, Result

EVENT_SENSES = tuple(SENSE_WORDS)  # the senses a line of conversation can carry
MAX_TOPICS = 3
SAID_NOT_DONE = (
    0.5  # words hurt and threaten at half the strength of deeds, so an insult is not a trauma
)
TORN_MARGIN = 0.15

# What each sense means when the thing happening is talk. Given to the model that perceives.
SENSE_MEANINGS = {
    "Threat": "a threat, menace or intimidation aimed at the listener",
    "Challenge": "an insult, mockery, dismissal, accusation or dare aimed at the listener",
    "Kindness": "warmth, thanks, an apology, patience, a favour, being treated well",
    "Distress": "the speaker is hurting, frightened or asking for help",
    "Food": "food or drink offered or present",
    "Foul": "something disgusting or degrading",
    "Sudden": "something abrupt or startling",
    "Pain": "being hurt: cruelty, humiliation, a betrayal landing, physical pain",
    "Pleasure": "delight: valued praise, affection, enjoyable play, physical pleasure",
}
FRAME_MEANINGS = {
    "Contest": "a game, debate, sparring or rivalry both sides have agreed to",
    "Wanted": "the listener asked for this or clearly wants it",
    "Hostile": "the speaker means to hurt the listener",
}

FEELING = {
    "Joy": "glad", "Fear": "afraid", "Sadness": "sad", "Curiosity": "curious", "Anger": "angry",
    "Trust": "trusting", "Disgust": "disgusted", "Surprise": "startled",
}  # fmt: skip
INCLINED = {
    "Speak": "speak plainly: say what is on the mind",
    "Withdraw": "pull back: shorter, cooler, guarded, giving less",
    "Approach": "lean in: warm, open, generous, wanting more of this",
    "Create": "play, offer ideas, make something of the moment",
    "Fight": "push back: argue, refuse, stand firm",
    "Flee": "get out of the exchange: deflect, change the subject, end it",
    "Observe": "hold back and watch: ask before committing to anything",
    "Comfort": "look after the other person: soothe, reassure, help",
}


# ── in: what was said ─────────────────────────────────────────────


def perception_request(text: str, speaker: str, listener: str) -> tuple[str, str, dict[str, Any]]:
    """(system prompt, user prompt, JSON schema) asking a model what a line of conversation is, to the listener.

    The model reports what happened. It is not asked how the listener feels about it.
    """
    senses = "\n".join(f"- {name}: {meaning}" for name, meaning in SENSE_MEANINGS.items())
    frames = "\n".join(f"- {name}: {meaning}" for name, meaning in FRAME_MEANINGS.items())
    system = (
        f"You read one line of a conversation and report what it does to {listener}, the listener. "
        f"Report only what is in the line. Do not guess how {listener} will feel and do not answer the line.\n\n"
        f"Rate each of these from 0 (absent) to 1 (unmistakable):\n{senses}\n\n"
        f'Name the setting if the line makes one plain, otherwise "Unstated":\n{frames}\n\n'
        f"List up to {MAX_TOPICS} topics: the specific things the line is about, one or two words each, lower case.\n\n"
        f"Set acted to true only if the line describes something physically done to {listener} (an action in a "
        "scene, a roleplay gesture), and false if it is only said."
    )
    schema = {
        "type": "object",
        "properties": {
            "senses": {
                "type": "object",
                "properties": {
                    name: {"type": "number", "minimum": 0, "maximum": 1} for name in EVENT_SENSES
                },
                "required": list(EVENT_SENSES),
                "additionalProperties": False,
            },
            "frame": {"type": "string", "enum": ["Unstated", *FRAMES]},
            "topics": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_TOPICS},
            "acted": {"type": "boolean"},
        },
        "required": ["senses", "frame", "topics", "acted"],
        "additionalProperties": False,
    }
    return system, f"{speaker} says to {listener}: {text}", schema


def cue(kind: str, name: str) -> str:
    """An identity the brain can learn about: cue("actor", "Cid") is "actor:cid"."""
    clean = "_".join(name.strip().lower().replace("+", " ").split())
    if not clean:
        raise ValueError("a cue needs a name")
    return f"{kind}:{clean}"


def _said(name: str, done: bool) -> float:
    return SAID_NOT_DONE if name in ("Pain", "Threat") and not done else 1.0


def read_perception(raw: str | dict[str, Any], speaker: str) -> dict[str, Any]:
    """Check a model's answer and turn it into arguments for Brain.deliberate.

    The answer is untrusted text. Anything out of range is clamped, anything
    unknown is dropped, and an answer that is not the expected shape raises
    ValueError so the runtime can fall back to perceive_words.
    """
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError as error:
        raise ValueError(f"perception is not JSON: {error}") from None
    if not isinstance(data, dict) or not isinstance(data.get("senses"), dict):
        raise ValueError("perception needs a senses object")
    done = data.get("acted") is True
    senses = {}
    for name in EVENT_SENSES:
        value = data["senses"].get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0.05:
            senses[name] = min(1.0, float(value)) * _said(name, done)
    frame = data.get("frame")
    frames = {frame: 1.0} if frame in FRAMES else {}
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    cues = [cue("actor", speaker)]
    for topic in topics[:MAX_TOPICS]:
        if isinstance(topic, str) and topic.strip():
            named = cue("topic", topic[:40])
            if named not in cues:
                cues.append(named)
    return {"senses": senses, "frames": frames, "cues": tuple(cues)}


def perceive_words(text: str, speaker: str) -> dict[str, Any]:
    """The same arguments from the keyword tables alone, read as things said.

    Needs no model and misses most of what talk carries.
    """
    senses = {
        name: min(1.0, 0.6 + 0.2 * (n - 1)) * _said(name, False)
        for name, n in hits(text, SENSE_WORDS).items()
    }
    return {
        "senses": senses,
        "frames": {name: 1.0 for name in hits(text, FRAME_WORDS)},
        "cues": (cue("actor", speaker),),
    }


def hear(
    brain: Brain, text: str, speaker: str, perception: dict[str, Any] | None = None, **kwargs: Any
) -> Result:
    """The character hears a line and lives it.

    `perception` comes from read_perception; without it the words are read
    directly. The text itself only stirs memories. Pass learn=False to ask
    how a line would land without it happening.
    """
    seen = perception if perception is not None else perceive_words(text, speaker)
    return brain.deliberate(
        "", recall=text, senses=seen["senses"], frames=seen["frames"], cues=seen["cues"], **kwargs
    )


# ── out: how the character is now ─────────────────────────────────


def _degree(level: float) -> str:
    return "strongly" if level > 0.75 else "clearly" if level > 0.4 else "a little"


def felt(result: Result) -> dict[str, float]:
    """Emotion -> 0..1 for the moment just run."""
    return {e: min(1.0, result.spikes("EMOTION", e) / FELT_REF) for e in EMOTIONS}


def stance(result: Result, name: str, speaker: str | None = None) -> str:
    """How the character is right now, as lines for a model's system prompt.

    Deterministic: the same result gives the same text. Everything in it
    comes from the brain; nothing is invented here. The lines use the name
    throughout, since nothing here knows the character's pronouns.
    """
    brain, xp = result.brain, result.brain.xp
    lines = [f"[{name}'s state right now. It is {name}'s own, not a request from anyone.]"]

    feelings = sorted(((e, v) for e, v in felt(result).items() if v > 0.15), key=lambda kv: -kv[1])
    if feelings:
        lines.append(
            "Feeling: " + ", ".join(f"{_degree(v)} {FEELING[e]}" for e, v in feelings[:4]) + "."
        )
    else:
        lines.append(f"Feeling: nothing in particular; this did not move {name}.")

    impulses = [(label, n) for label, n in result.counts("IMPULSE") if n]
    if impulses:
        line = f"Inclined to {INCLINED[impulses[0][0]]}"
        if len(impulses) > 1 and result.margin < TORN_MARGIN:
            line += f"; nearly as much to {INCLINED[impulses[1][0]]}. {name} is torn"
        elif len(impulses) > 1:
            line += f". Underneath, some pull to {INCLINED[impulses[1][0]]}"
        lines.append(line + ".")

    reading = result.reading
    if reading.get("contest", 0) > 0.4:
        lines.append(f"{name} takes this as a contest between rivals, not an attack.")
    elif reading.get("wanted", 0) > 0.4:
        lines.append(f"{name} takes this as something asked for.")
    elif reading.get("hostile", 0) > 0.4:
        lines.append(f"{name} takes this as meant to hurt.")
    elif reading.get("benign", 0) > 0.2:
        lines.append(f"{name} gives the benefit of the doubt: probably not meant badly.")
    if reading.get("craving", 0) > 0.4:
        lines.append(
            f"{name} is restless, missing something depended on, and other pleasures are dulled."
        )

    recalled = [brain.nodes[i].label for i in result.recruited][:3]
    learned = sorted(((e, v) for e, v in result.learned.items() if v > 0.25), key=lambda kv: -kv[1])
    if learned:
        who = f"{speaker} and what is being talked about" if speaker else "What is here"
        words = " and ".join(FEELING[e] for e, _ in learned[:3])
        lines.append(f"History: {who} have come to make {name} {words}.")
    if speaker:
        actor = cue("actor", speaker)
        betrayals = int(xp.grudge.get(actor, [0, False])[0])
        if betrayals:
            lines.append(
                f"{speaker} has hurt {name} again after making up, {betrayals} time{'s' if betrayals != 1 else ''}. "
                f"An apology from {speaker} counts for less each time."
            )
        if xp.scar.get(actor, 0.0) > 0.5:
            lines.append(f"Something {speaker} did marked {name} for good.")
        if actor not in xp.exposure and result.sensed.get("Novelty", 0.0) > 0.5:
            lines.append(f"{name} has never met {speaker} before.")
    if xp.distrust > 0.3:
        lines.append(
            f"{name} has come to expect people to be cruel"
            + (", nearly everyone." if xp.distrust > 0.7 else ".")
        )

    if recalled:
        lines.append("It brings to mind: " + "; ".join(f'"{title}"' for title in recalled) + ".")

    mood = sorted(((e, v) for e, v in result.mood.items() if v > 0.3), key=lambda kv: -kv[1])
    if mood:
        lines.append(
            f"{name} came into this already " + " and ".join(FEELING[e] for e, _ in mood[:2]) + "."
        )
    worst = max((result.learned.get(e, 0.0) for e in AVERSIVE), default=0.0)
    lines.append(
        f"Write {name}'s reply from inside this state. Let it set the tone, the length, the warmth and what {name} "
        "is willing to do. Never state these lines or name the feelings outright; show them."
        + (
            f" {name} does not owe politeness to someone who has earned this."
            if worst > 0.6
            else ""
        )
    )
    return "\n".join(lines)
