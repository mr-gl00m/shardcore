"""Reading text: the keyword tables and the matching they share.

Everything in this file is the stand-in for perception. A runtime with a scene
model, or an LLM as the translation step, replaces it by handing senses, cues
and frames to Brain.deliberate() directly.
"""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "him",
        "his",
        "i",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "she",
        "so",
        "that",
        "the",
        "their",
        "them",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "who",
        "will",
        "with",
        "you",
        "your",
    ]
)

WORD = re.compile(r"[a-z']+")


def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def stem(word: str) -> str:
    """Crude suffix strip so "hits", "hitting" and "hit" are one cue."""
    for suffix in ("ing", "ed", "es"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)]
            if len(word) > 2 and word[-1] == word[-2] and word[-1] not in "ls":
                word = word[:-1]  # hitt -> hit, slapp -> slap
            return word
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokens(text: str) -> set[str]:
    return {stem(w) for w in words(text) if w not in STOPWORDS and len(w) > 2}


# What may follow a keyword stem for a word to count as that keyword. Plain
# prefix matching read "huge" as a hug, "begins" as begging, "painted" as pain
# and "Sparkles" as sparring.
_ENDINGS = frozenset(
    ["s", "es", "ed", "d", "ing", "ly", "y", "ness", "ful", "en", "th", "ty", "ment", "ous", "al"]
)
_LONG_STEM_ENDINGS = frozenset(
    ["e", "er", "ers", "ion", "ions", "ation", "ations", "ition", "itive", "ive"]
)  # stems of 4+ (er) or 5+ letters


def _ending_ok(rest: str, stem_len: int) -> bool:
    if rest in _ENDINGS:
        return True
    if rest in ("er", "ers"):
        return stem_len >= 4
    return rest in _LONG_STEM_ENDINGS and stem_len >= 5


def _rest_ok(rest: str, stem_len: int) -> bool:
    if not rest or _ending_ok(rest, stem_len):
        return True
    return any(_ending_ok(rest[:i], stem_len) and rest[i:] in _ENDINGS for i in range(1, len(rest)))


def matches(word: str, stems: tuple[str, ...]) -> bool:
    for s in stems:
        if word.startswith(s):
            rest = word[len(s) :]
            if _rest_ok(rest, len(s)) or (
                len(rest) > 1 and rest[0] == s[-1] and _rest_ok(rest[1:], len(s))
            ):
                return True
    return False


def hits(text: str, table: dict[str, tuple[str, ...]]) -> dict[str, int]:
    """Table key -> how many words of the text match it (keys with no match are left out)."""
    ws = words(text)
    out = {name: sum(1 for w in ws if matches(w, stems)) for name, stems in table.items()}
    return {name: n for name, n in out.items() if n}


# shortcut: keyword stems decide what a memory makes her feel. The upgrade is
# labelling at consolidation time (the dream pass, or an LLM as the escalation
# step) and storing the result on the mind entry, so this table goes away.
EMOTION_WORDS: dict[str, tuple[str, ...]] = {
    "Joy": (
        "joy",
        "happy",
        "laugh",
        "delight",
        "warm",
        "celebrat",
        "glad",
        "smile",
        "smiling",
        "love",
    ),
    "Trust": (
        "trust",
        "loyal",
        "saved",
        "rescu",
        "protect",
        "friend",
        "promis",
        "faith",
        "grateful",
        "owe",
        "debt",
    ),
    "Fear": (
        "fear",
        "afraid",
        "terror",
        "danger",
        "threat",
        "hunt",
        "trap",
        "panic",
        "dread",
        "hurt",
    ),
    "Anger": (
        "anger",
        "angry",
        "betray",
        "rage",
        "furious",
        "lied",
        "stole",
        "sold",
        "hate",
        "reveng",
        "cheat",
    ),
    "Sadness": (
        "sad",
        "grief",
        "loss",
        "lost",
        "mourn",
        "alone",
        "lonely",
        "cry",
        "cri",
        "died",
        "death",
        "regret",
    ),
    "Curiosity": (
        "curious",
        "wonder",
        "mystery",
        "secret",
        "discover",
        "learn",
        "question",
        "strange",
        "puzzl",
    ),
    "Disgust": ("disgust", "filth", "rot", "vile", "sick", "repuls", "contempt", "shame"),
    "Surprise": ("surpris", "sudden", "shock", "unexpected", "astonish"),
}

# What her senses pick out of a moment.
SENSE_WORDS: dict[str, tuple[str, ...]] = {
    "Threat": ("weapon", "knife", "blade", "gun", "attack", "threat", "snarl", "growl", "blood", "lunge", "scream",
               "hunt", "chase", "grab"),
    "Challenge": ("challeng", "rival", "insult", "mock", "dare", "taunt", "sneer", "shove", "accus"),
    "Kindness": ("smile", "smiling", "gift", "gentle", "gently", "kind", "offer", "warm", "thank", "hug", "welcom",
                 "share"),
    "Distress": ("cry", "cri", "wound", "hurt", "beg", "plead", "help", "sob", "bleed", "trembl", "whimper"),
    "Food": ("food", "bread", "eat", "stew", "milk", "fruit", "meat", "meal", "feast", "soup"),
    "Foul": ("rot", "stench", "filth", "vomit", "maggot", "sewage", "corpse"),
    "Sudden": ("sudden", "bang", "crash", "burst", "explod", "explos", "slam", "flash"),
    "Pain": ("hit", "slap", "strike", "struck", "punch", "kick", "beat", "whip", "burn", "bite", "pain"),
    "Pleasure": ("caress", "kiss", "stroke", "cuddle", "pleasure", "sweet", "candy", "cake", "sugar", "honey",
                 "prais", "embrac"),
}  # fmt: skip

# Frames are not things that happen; they are the setting she reads an act in.
# Intent is the hardest thing here to get from text, and the place an LLM
# earns its keep: it reads the scene once and hands over frames.
FRAME_WORDS: dict[str, tuple[str, ...]] = {
    "Contest": ("tournament", "match", "spar", "duel", "bout", "contest", "compet", "arena"),
    "Wanted": ("ask", "want", "consent", "invit", "willing"),
    "Hostile": ("angry", "anger", "rage", "furious", "cruel", "punish", "hate", "spite", "drunk"),
}


def affinities(text: str) -> dict[str, float]:
    """Emotion -> 0..1, the strongest emotion in the text at 1."""
    found = hits(text, EMOTION_WORDS)
    top = max(found.values(), default=0)
    return {emo: n / top for emo, n in found.items()}
