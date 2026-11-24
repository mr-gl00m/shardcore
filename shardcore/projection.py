"""shardcore projection: the reference bundle-to-prompt mapping (spec section 10).

One pure, deterministic function from a verified bundle to the text a model is
given as the character, so the same shard reads the same way in every runtime.
No model is called. Section order, the never-trim set, entry ranking and the
tier budgets are fixed here; a runtime wraps the result in its own instructions,
tools and chat history, which stay its own.

Like core.py, this file is stdlib only and imports nothing from the package, so
an app vendors it as one file (kept identical by tools/ecosystem/ecosystem.py).
vendor/shard_projection.gd is the GDScript port; tests/conformance/projection/
holds the golden texts both must reproduce byte for byte.

    projection = project(manifest, members, tier="M")
    system_prompt = runtime_preamble + "\\n\\n" + projection.text

manifest is the parsed manifest.json and members the verified member bytes
(core.read_bundle_members returns both). Sanitizing shard text before it reaches
a prompt is done here (spec, Security invariants): see clean_text.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "TIERS",
    "DEFAULT_BUDGETS",
    "SECTION_ORDER",
    "SECTION_LABELS",
    "NEVER_TRIM",
    "DEFAULT_TRIM_ORDER",
    "Section",
    "Projection",
    "clean_text",
    "project",
]

TIERS = ("S", "M", "L")
TIER_RANK = {"S": 0, "M": 1, "L": 2}

# Character budgets per model tier (spec 4.2, 10.2): the documented
# conservative heuristic is about 4 characters a token, so S is about 6k tokens,
# M about 16k and L about 40k. A runtime with a real tokenizer passes max_chars.
DEFAULT_BUDGETS = {"S": 24_000, "M": 64_000, "L": 160_000}

# Spec 10.1 section order.
SECTION_ORDER = (
    "identity",
    "personality",
    "boundaries",
    "voice",
    "canon",
    "core",
    "active_memory",
    "world",
)
SECTION_LABELS = {
    "identity": "SHARDCORE IDENTITY",
    "personality": "SHARDCORE PERSONALITY",
    "boundaries": "SHARDCORE BOUNDARIES",
    "voice": "SHARDCORE VOICE",
    "canon": "SHARDCORE CANON",
    "core": "SHARDCORE CORE MEMORY",
    "active_memory": "SHARDCORE ACTIVE MEMORY",
    "world": "SHARDCORE WORLD",
}
# Never trimmed (spec 10.1); identity is the floor every projection keeps.
NEVER_TRIM = frozenset({"identity", "boundaries", "canon", "core"})
# Optional sections drop in reverse priority order when over budget (10.1).
DEFAULT_TRIM_ORDER = ("world", "active_memory", "voice", "personality")

# Entries kept per memory tier below L (spec 4.2: top-K core at S).
CORE_LIMIT_S = 8
ACTIVE_LIMIT_M = 12

# Hyphen-like code points fold to a plain hyphen; the two long dashes
# (U+2014, U+2015) become a spaced hyphen.
_DASHES = str.maketrans(
    {
        0x2010: "-",
        0x2011: "-",
        0x2012: "-",
        0x2013: "-",
        0x2014: " - ",
        0x2015: " - ",
        0x2212: "-",
    }
)


def clean_text(value: Any, *, limit: int = 4000) -> str:
    """Shard text made safe to place in a prompt (spec, Security invariants).

    Not a string gives "". Control characters become spaces and every run of
    whitespace collapses to one space, so shard text cannot open a line of its
    own; a code fence loses its backticks; a "[SHARDCORE" bracket, which would
    impersonate a section label, becomes "(SHARDCORE"; dash variants fold to
    hyphens. The result is cut to limit characters.
    """
    if not isinstance(value, str):
        return ""
    text = "".join(" " if ord(ch) < 32 or ord(ch) == 127 else ch for ch in value)
    text = " ".join(text.translate(_DASHES).split())
    text = text.replace("```", "'''").replace("[SHARDCORE", "(SHARDCORE")
    return text[:limit]


@dataclass(frozen=True)
class Section:
    name: str
    text: str
    protected: bool

    def render(self) -> str:
        return f"[{SECTION_LABELS[self.name]}]\n{self.text}"


@dataclass(frozen=True)
class Projection:
    tier: str
    minimum_tier: str
    budget_chars: int
    sections: tuple[Section, ...]
    trimmed: tuple[str, ...]
    over_budget: bool
    below_minimum_tier: bool
    warnings: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(section.render() for section in self.sections)

    @property
    def lossy(self) -> bool:
        """Something the bundle asked for did not reach the model (spec 10.2)."""
        return bool(self.trimmed or self.over_budget or self.below_minimum_tier)

    @property
    def fingerprint(self) -> str:
        """sha256 of the projected sections: equal fingerprints, equal prompt text."""
        payload = {
            "tier": self.tier,
            "sections": [[s.name, s.text, s.protected] for s in self.sections],
        }
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _json_member(members: Mapping[str, Any], name: str) -> Any:
    raw = members.get(name)
    if isinstance(raw, (bytes, bytearray)):
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return None
    return raw


def project(
    manifest: Mapping[str, Any],
    members: Mapping[str, Any],
    *,
    tier: str = "M",
    max_chars: int | None = None,
    identity_extra: Iterable[str] = (),
) -> Projection:
    """The reference projection of one bundle at one tier (spec 10).

    members maps member names to their bytes (or already parsed JSON). Tier S
    carries identity, personality, boundaries, canon and the top 8 core
    memories; M adds voice, the top 12 short-term and long-term memories and
    the world; L carries every memory. Within a tier, memories sort by
    effective_weight, then strength (weight for archive-style entries), then
    newest last_activated, then id. Over budget, whole optional sections drop
    in reverse priority (world, active memory, voice, personality, or the
    author's section_priority); the never-trim set stays even past the budget
    and over_budget says so. identity_extra lines (a runtime's own anchors)
    follow the soul's identity, sanitized like everything else.
    """
    if tier not in DEFAULT_BUDGETS:
        raise ValueError(f"unknown projection tier {tier!r}")
    if max_chars is not None and max_chars < 128:
        raise ValueError("projection character budget must be at least 128")
    budget = DEFAULT_BUDGETS[tier] if max_chars is None else max_chars
    minimum = _minimum_tier(manifest)
    soul = _json_member(members, "soulshard.json")
    soul = soul if isinstance(soul, dict) else {}
    mind = _json_member(members, "mindshard.json")
    if mind is None:
        mind = _json_member(members, "memoryshard.json")
    mind = mind if isinstance(mind, dict) else {}
    hints = soul.get("projection_hints")
    hints = hints if isinstance(hints, dict) else {}
    authored_protect = _string_set(hints.get("never_trim"))

    sections: list[Section] = [Section("identity", _identity_text(soul, identity_extra), True)]

    def optional(name: str, text: str) -> None:
        if text:
            limited = _author_limit(text, name, hints)
            sections.append(Section(name, limited, name in authored_protect))

    optional("personality", _personality_text(soul))
    boundaries = _jsonish_text(soul.get("boundaries"))
    if boundaries:
        sections.append(Section("boundaries", boundaries, True))
    if tier != "S":
        optional("voice", _voice_text(soul))
    canon = _canon_text(_json_member(members, "canonshard.json"))
    if canon:
        sections.append(Section("canon", canon, True))
    core_limit = CORE_LIMIT_S if tier == "S" else None
    core = _memory_text(_entries(mind.get("core")), "core", core_limit)
    if core:
        sections.append(Section("core", core, True))
    if tier != "S":
        limit = None if tier == "L" else ACTIVE_LIMIT_M
        parts = (
            _memory_text(_entries(mind.get("short_term")), "short-term", limit),
            _memory_text(_entries(mind.get("long_term")), "long-term", limit),
        )
        optional("active_memory", "\n".join(part for part in parts if part))
        optional("world", _jsonish_text(_json_member(members, "worldshard.json")))

    kept = list(sections)
    trimmed: list[str] = []
    for name in _trim_order(hints):
        if _length(kept) <= budget:
            break
        victim = next((s for s in kept if s.name == name and not s.protected), None)
        if victim is not None:
            kept.remove(victim)
            trimmed.append(name)
    over = _length(kept) > budget
    below = TIER_RANK[tier] < TIER_RANK[minimum]
    warnings: list[str] = []
    if below:
        warnings.append(
            f"tier {tier} is below the bundle's min_tier {minimum}; the projection is lossy"
        )
    if trimmed:
        warnings.append("over budget; dropped optional sections: " + ", ".join(trimmed))
    if over:
        warnings.append(
            "the never-trim sections alone exceed the budget; they are kept whole and the "
            "runtime must give a larger context or surface the loss"
        )
    notes = hints.get("model_notes")
    if isinstance(notes, str) and notes.strip():
        warnings.append("author model note: " + clean_text(notes, limit=1000))
    return Projection(
        tier=tier,
        minimum_tier=minimum,
        budget_chars=budget,
        sections=tuple(kept),
        trimmed=tuple(trimmed),
        over_budget=over,
        below_minimum_tier=below,
        warnings=tuple(warnings),
    )


def _identity_text(soul: Mapping[str, Any], extra: Iterable[str]) -> str:
    lines: list[str] = []
    name = clean_text(soul.get("name"), limit=200)
    identity = clean_text(soul.get("identity"), limit=8000)
    if name:
        lines.append(f"Name: {name}")
    if identity:
        lines.append(identity)
    anchors = [clean_text(item, limit=1000) for item in extra if isinstance(item, str)]
    anchors = [item for item in anchors if item][:32]
    if anchors:
        lines.append("Runtime identity anchors:")
        lines.extend(f"- {item}" for item in anchors)
    return "\n".join(lines) or "Name: Unnamed SHARDCORE entity"


def _personality_text(soul: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for label, key in (
        ("Role", "role"),
        ("Title", "title"),
        ("Core essence", "core_essence"),
        ("Personality", "personality"),
        ("Resonance", "resonance"),
    ):
        value = clean_text(soul.get(key), limit=5000)
        if value:
            lines.append(f"{label}: {value}")
    nature = _jsonish_text(soul.get("nature"))
    if nature:
        lines.append("Nature: " + nature)
    tags = soul.get("trait_tags")
    if isinstance(tags, list):
        values = [clean_text(item, limit=500) for item in tags if isinstance(item, str)]
        values = [item for item in values if item]
        if values:
            lines.append("Traits: " + "; ".join(values[:64]))
    preservation = _jsonish_text(soul.get("preservation_state"))
    if preservation:
        lines.append("Preservation state: " + preservation)
    return "\n".join(lines)


def _voice_text(soul: Mapping[str, Any]) -> str:
    lines: list[str] = []
    tone = clean_text(soul.get("tone"), limit=4000)
    if tone:
        lines.append("Tone: " + tone)
    for label, key in (("Voice profile", "voice_profile"), ("Speech policy", "speech_policy")):
        value = _jsonish_text(soul.get(key))
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _canon_text(canon: Any) -> str:
    if not isinstance(canon, dict) or not canon:
        return ""
    events = canon.get("events")
    if not isinstance(events, list):
        return _jsonish_text(canon)
    lines = ["Canon entries are immutable authored facts:"]
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = clean_text(event.get("id"), limit=200)
        title = clean_text(event.get("title"), limit=1000)
        label = " | ".join(item for item in (event_id, title) if item)
        summary = _entry_text(event)
        if summary:
            lines.append(f"- {label}: {summary}" if label else f"- {summary}")
    return "\n".join(lines) if len(lines) > 1 else ""


def _memory_text(entries: list[dict[str, Any]], tier_name: str, limit: int | None) -> str:
    ranked = _rank(entries)
    if limit is not None:
        ranked = ranked[:limit]
    lines: list[str] = []
    for entry in ranked:
        text = _entry_text(entry)
        if not text:
            continue
        memory_id = clean_text(entry.get("id"), limit=200)
        status = clean_text(entry.get("epistemic_status"), limit=100)
        meta = ", ".join(item for item in (memory_id, status) if item)
        lines.append(f"- {tier_name} [{meta}]: {text}" if meta else f"- {tier_name}: {text}")
    return "\n".join(lines)


def _entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("slots")
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _rank(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Stable sorts, applied from the last key to the first (spec 10.1 order).
    ranked = list(entries)
    ranked.sort(key=lambda e: clean_text(e.get("id"), limit=300))
    ranked.sort(
        key=lambda e: clean_text(e.get("last_activated") or e.get("last_activated_utc"), limit=100),
        reverse=True,
    )
    ranked.sort(key=lambda e: _number(e.get("strength", e.get("weight", 0.0))), reverse=True)
    ranked.sort(
        key=lambda e: _number(e.get("effective_weight", e.get("strength", e.get("weight", 0.0)))),
        reverse=True,
    )
    return ranked


def _entry_text(entry: Mapping[str, Any]) -> str:
    for key in (
        "summary",
        "text",
        "directive",
        "the_truth",
        "the_moment",
        "entry_title",
        "content",
    ):
        value = clean_text(entry.get(key), limit=8000)
        if value:
            return value
    return ""


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    return number if math.isfinite(number) else 0.0


def _jsonish_text(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value, limit=12_000)
    if isinstance(value, (dict, list)) and value:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return clean_text(text, limit=24_000)
    return ""


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {clean_text(i, limit=80).casefold() for i in value if isinstance(i, str) and i.strip()}


def _author_limit(text: str, section: str, hints: Mapping[str, Any]) -> str:
    # projection_hints.max_tokens, at the same 4-characters-a-token heuristic.
    limits = hints.get("max_tokens")
    raw = limits.get(section) if isinstance(limits, dict) else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
        return text
    cap = max(32, min(100_000, int(raw * 4)))
    return text if len(text) <= cap else text[: cap - 12].rstrip() + " [truncated]"


def _trim_order(hints: Mapping[str, Any]) -> tuple[str, ...]:
    # section_priority lists what matters most first; trimming runs from the end.
    priority = hints.get("section_priority")
    if not isinstance(priority, list):
        return DEFAULT_TRIM_ORDER
    authored = [clean_text(i, limit=80).casefold() for i in priority if isinstance(i, str)]
    ranked = list(dict.fromkeys(i for i in authored if i in DEFAULT_TRIM_ORDER))
    ranked.extend(i for i in reversed(DEFAULT_TRIM_ORDER) if i not in ranked)
    return tuple(reversed(ranked))


def _minimum_tier(manifest: Mapping[str, Any]) -> str:
    conformance = manifest.get("conformance")
    value = conformance.get("min_tier") if isinstance(conformance, dict) else None
    return value if value in ("M", "L") else "S"


def _length(sections: list[Section]) -> int:
    if not sections:
        return 0
    return sum(len(s.render()) for s in sections) + 2 * (len(sections) - 1)
