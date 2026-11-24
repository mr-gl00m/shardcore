extends RefCounted

## The SHARDCORE reference projection (spec 10) for Godot: the GDScript port of
## shardcore/projection.py. One deterministic function from a verified bundle to the
## text a model is given as the character. No model is called.
##
## The canonical copy lives at shardcore/vendor/shard_projection.gd and is vendored
## verbatim next to shardcore.gd, which it preloads for canonical JSON. Edit only the
## canonical copy, then run tools/ecosystem/ecosystem.py sync (from shardcore).
## tests/test_vendor_projection_gdscript.py holds it to the golden texts under
## tests/conformance/projection/, byte for byte.
##
##     var r := SC.read_bundle(path)
##     var p := ShardProjection.project(r["manifest"], r["members"], "M")
##     var prompt: String = preamble + "\n\n" + p["text"]
##
## project() returns {"text", "sections" (name, text, protected), "tier",
## "minimum_tier", "budget_chars", "trimmed", "over_budget", "below_minimum_tier",
## "warnings"}, the fields of projection.py's Projection.
## shortcut: a float with no fraction inside a JSON-rendered field (nature, boundaries,
## voice_profile, world) prints as an integer here and with ".0" in Python, as in
## shardcore.gd; keep such values integers in shard JSON.

const SC = preload("shardcore.gd")

const DEFAULT_BUDGETS := {"S": 24000, "M": 64000, "L": 160000}
const TIER_RANK := {"S": 0, "M": 1, "L": 2}
const SECTION_LABELS := {
	"identity": "SHARDCORE IDENTITY",
	"personality": "SHARDCORE PERSONALITY",
	"boundaries": "SHARDCORE BOUNDARIES",
	"voice": "SHARDCORE VOICE",
	"canon": "SHARDCORE CANON",
	"core": "SHARDCORE CORE MEMORY",
	"active_memory": "SHARDCORE ACTIVE MEMORY",
	"world": "SHARDCORE WORLD",
}
const DEFAULT_TRIM_ORDER: Array[String] = ["world", "active_memory", "voice", "personality"]
const CORE_LIMIT_S := 8
const ACTIVE_LIMIT_M := 12

## Python's str.isspace() set, which str.split() breaks on.
const _SPACE_CODES := [0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0,
	0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009,
	0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000]


## Shard text made safe for a prompt: control characters and whitespace runs become one
## space, a code fence loses its backticks, "[SHARDCORE" becomes "(SHARDCORE", dash
## variants fold to hyphens, cut to limit characters. Not a string gives "".
static func clean_text(value: Variant, limit := 4000) -> String:
	if not value is String:
		return ""
	var words: PackedStringArray = []
	var word := ""
	for i in value.length():
		var c: int = value.unicode_at(i)
		var piece := ""
		if c < 32 or c == 127 or _SPACE_CODES.has(c):
			piece = " "
		elif c == 0x2014 or c == 0x2015:
			piece = " - "
		elif c == 0x2010 or c == 0x2011 or c == 0x2012 or c == 0x2013 or c == 0x2212:
			piece = "-"
		else:
			word += char(c)
			continue
		for p in piece:
			if p == " ":
				if word != "":
					words.append(word)
					word = ""
			else:
				word += p
	if word != "":
		words.append(word)
	var text := " ".join(words).replace("```", "'''").replace("[SHARDCORE", "(SHARDCORE")
	return text.left(limit)


static func _json_member(members: Dictionary, name: String) -> Variant:
	var raw: Variant = members.get(name)
	if raw is PackedByteArray:
		var parsed: Dictionary = SC.parse_json(raw, name)
		return parsed["value"] if parsed["ok"] else null
	return raw


static func project(manifest: Dictionary, members: Dictionary, tier := "M", max_chars := 0, identity_extra: Array = []) -> Dictionary:
	if not DEFAULT_BUDGETS.has(tier):
		push_error("unknown projection tier %s" % tier)
		return {}
	var budget: int = DEFAULT_BUDGETS[tier] if max_chars <= 0 else max_chars
	var minimum := _minimum_tier(manifest)
	var soul: Variant = _json_member(members, "soulshard.json")
	soul = soul if soul is Dictionary else {}
	var mind: Variant = _json_member(members, "mindshard.json")
	if mind == null:
		mind = _json_member(members, "memoryshard.json")
	mind = mind if mind is Dictionary else {}
	var hints: Variant = soul.get("projection_hints")
	hints = hints if hints is Dictionary else {}
	var protect := _string_set(hints.get("never_trim"))

	var sections: Array = [{"name": "identity", "text": _identity_text(soul, identity_extra), "protected": true}]
	_optional(sections, "personality", _personality_text(soul), hints, protect)
	var boundaries := _jsonish_text(soul.get("boundaries"))
	if boundaries != "":
		sections.append({"name": "boundaries", "text": boundaries, "protected": true})
	if tier != "S":
		_optional(sections, "voice", _voice_text(soul), hints, protect)
	var canon := _canon_text(_json_member(members, "canonshard.json"))
	if canon != "":
		sections.append({"name": "canon", "text": canon, "protected": true})
	var core := _memory_text(_entries(mind.get("core")), "core", CORE_LIMIT_S if tier == "S" else -1)
	if core != "":
		sections.append({"name": "core", "text": core, "protected": true})
	if tier != "S":
		var limit := -1 if tier == "L" else ACTIVE_LIMIT_M
		var parts: PackedStringArray = []
		for part in [_memory_text(_entries(mind.get("short_term")), "short-term", limit),
				_memory_text(_entries(mind.get("long_term")), "long-term", limit)]:
			if part != "":
				parts.append(part)
		_optional(sections, "active_memory", "\n".join(parts), hints, protect)
		_optional(sections, "world", _jsonish_text(_json_member(members, "worldshard.json")), hints, protect)

	var kept := sections.duplicate()
	var trimmed: Array = []
	for name in _trim_order(hints):
		if _length(kept) <= budget:
			break
		for s in kept:
			if s["name"] == name and not s["protected"]:
				kept.erase(s)
				trimmed.append(name)
				break
	var over := _length(kept) > budget
	var below: bool = TIER_RANK[tier] < TIER_RANK[minimum]
	var warnings: Array = []
	if below:
		warnings.append("tier %s is below the bundle's min_tier %s; the projection is lossy" % [tier, minimum])
	if not trimmed.is_empty():
		warnings.append("over budget; dropped optional sections: " + ", ".join(PackedStringArray(trimmed)))
	if over:
		warnings.append("the never-trim sections alone exceed the budget; they are kept whole and the runtime must give a larger context or surface the loss")
	var notes: Variant = hints.get("model_notes")
	if notes is String and notes.strip_edges() != "":
		warnings.append("author model note: " + clean_text(notes, 1000))
	var rendered: PackedStringArray = []
	for s in kept:
		rendered.append(_render(s))
	return {
		"text": "\n\n".join(rendered),
		"sections": kept,
		"tier": tier,
		"minimum_tier": minimum,
		"budget_chars": budget,
		"trimmed": trimmed,
		"over_budget": over,
		"below_minimum_tier": below,
		"warnings": warnings,
	}


static func _optional(sections: Array, name: String, text: String, hints: Dictionary, protect: Dictionary) -> void:
	if text != "":
		sections.append({"name": name, "text": _author_limit(text, name, hints), "protected": protect.has(name)})


static func _render(section: Dictionary) -> String:
	return "[%s]\n%s" % [SECTION_LABELS[section["name"]], section["text"]]


static func _length(sections: Array) -> int:
	if sections.is_empty():
		return 0
	var total := 2 * (sections.size() - 1)
	for s in sections:
		total += _render(s).length()
	return total


static func _identity_text(soul: Dictionary, extra: Array) -> String:
	var lines: PackedStringArray = []
	var name := clean_text(soul.get("name"), 200)
	var identity := clean_text(soul.get("identity"), 8000)
	if name != "":
		lines.append("Name: " + name)
	if identity != "":
		lines.append(identity)
	var anchors: PackedStringArray = []
	for item in extra:
		var a := clean_text(item, 1000)
		if a != "" and anchors.size() < 32:
			anchors.append(a)
	if not anchors.is_empty():
		lines.append("Runtime identity anchors:")
		for a in anchors:
			lines.append("- " + a)
	return "\n".join(lines) if not lines.is_empty() else "Name: Unnamed SHARDCORE entity"


static func _personality_text(soul: Dictionary) -> String:
	var lines: PackedStringArray = []
	for pair in [["Role", "role"], ["Title", "title"], ["Core essence", "core_essence"],
			["Personality", "personality"], ["Resonance", "resonance"]]:
		var value := clean_text(soul.get(pair[1]), 5000)
		if value != "":
			lines.append("%s: %s" % [pair[0], value])
	var nature := _jsonish_text(soul.get("nature"))
	if nature != "":
		lines.append("Nature: " + nature)
	var tags: Variant = soul.get("trait_tags")
	if tags is Array:
		var values: PackedStringArray = []
		for item in tags:
			var v := clean_text(item, 500)
			if v != "" and values.size() < 64:
				values.append(v)
		if not values.is_empty():
			lines.append("Traits: " + "; ".join(values))
	var preservation := _jsonish_text(soul.get("preservation_state"))
	if preservation != "":
		lines.append("Preservation state: " + preservation)
	return "\n".join(lines)


static func _voice_text(soul: Dictionary) -> String:
	var lines: PackedStringArray = []
	var tone := clean_text(soul.get("tone"), 4000)
	if tone != "":
		lines.append("Tone: " + tone)
	for pair in [["Voice profile", "voice_profile"], ["Speech policy", "speech_policy"]]:
		var value := _jsonish_text(soul.get(pair[1]))
		if value != "":
			lines.append("%s: %s" % [pair[0], value])
	return "\n".join(lines)


static func _canon_text(canon: Variant) -> String:
	if not canon is Dictionary or canon.is_empty():
		return ""
	var events: Variant = canon.get("events")
	if not events is Array:
		return _jsonish_text(canon)
	var lines: PackedStringArray = ["Canon entries are immutable authored facts:"]
	for event in events:
		if not event is Dictionary:
			continue
		var bits: PackedStringArray = []
		for v in [clean_text(event.get("id"), 200), clean_text(event.get("title"), 1000)]:
			if v != "":
				bits.append(v)
		var label := " | ".join(bits)
		var summary := _entry_text(event)
		if summary != "":
			lines.append(("- %s: %s" % [label, summary]) if label != "" else ("- " + summary))
	return "\n".join(lines) if lines.size() > 1 else ""


static func _memory_text(entries: Array, tier_name: String, limit: int) -> String:
	var ranked := _rank(entries)
	if limit >= 0 and ranked.size() > limit:
		ranked = ranked.slice(0, limit)
	var lines: PackedStringArray = []
	for entry in ranked:
		var text := _entry_text(entry)
		if text == "":
			continue
		var bits: PackedStringArray = []
		for v in [clean_text(entry.get("id"), 200), clean_text(entry.get("epistemic_status"), 100)]:
			if v != "":
				bits.append(v)
		var meta := ", ".join(bits)
		lines.append(("- %s [%s]: %s" % [tier_name, meta, text]) if meta != "" else ("- %s: %s" % [tier_name, text]))
	return "\n".join(lines)


static func _entries(value: Variant) -> Array:
	if value is Dictionary:
		value = value.get("slots")
	var out: Array = []
	if value is Array:
		for item in value:
			if item is Dictionary:
				out.append(item)
	return out


## One comparator equal to projection.py's four stable sorts: effective_weight desc,
## strength (or weight) desc, newest last_activated, id asc, then input order.
static func _rank(entries: Array) -> Array:
	var keyed: Array = []
	for i in entries.size():
		var e: Dictionary = entries[i]
		var strength := _number(e.get("strength", e.get("weight", 0.0)))
		var effective := _number(e.get("effective_weight", e.get("strength", e.get("weight", 0.0))))
		var activated: Variant = e.get("last_activated")
		if not (activated is String and activated != ""):
			activated = e.get("last_activated_utc")
		keyed.append([effective, strength, clean_text(activated, 100), clean_text(e.get("id"), 300), i, e])
	keyed.sort_custom(func(a, b):
		if a[0] != b[0]:
			return a[0] > b[0]
		if a[1] != b[1]:
			return a[1] > b[1]
		if a[2] != b[2]:
			return a[2] > b[2]
		if a[3] != b[3]:
			return a[3] < b[3]
		return a[4] < b[4])
	var out: Array = []
	for k in keyed:
		out.append(k[5])
	return out


static func _entry_text(entry: Dictionary) -> String:
	for key in ["summary", "text", "directive", "the_truth", "the_moment", "entry_title", "content"]:
		var value := clean_text(entry.get(key), 8000)
		if value != "":
			return value
	return ""


static func _number(value: Variant) -> float:
	if value is bool or not (value is int or value is float):
		return 0.0
	var f := float(value)
	return f if is_finite(f) else 0.0


static func _jsonish_text(value: Variant) -> String:
	if value is String:
		return clean_text(value, 12000)
	if (value is Dictionary or value is Array) and not value.is_empty():
		return clean_text(SC.canonical_json(value).get_string_from_utf8(), 24000)
	return ""


static func _string_set(value: Variant) -> Dictionary:
	var out := {}
	if value is Array:
		for item in value:
			if item is String and item.strip_edges() != "":
				out[clean_text(item, 80).to_lower()] = true
	return out


static func _author_limit(text: String, section: String, hints: Dictionary) -> String:
	var limits: Variant = hints.get("max_tokens")
	var raw: Variant = limits.get(section) if limits is Dictionary else null
	if raw is bool or not (raw is int or raw is float) or raw <= 0:
		return text
	var cap := clampi(int(raw * 4), 32, 100000)
	if text.length() <= cap:
		return text
	return text.left(cap - 12).strip_edges(false, true) + " [truncated]"


static func _trim_order(hints: Dictionary) -> Array:
	var priority: Variant = hints.get("section_priority")
	if not priority is Array:
		return DEFAULT_TRIM_ORDER.duplicate()
	var ranked: Array = []
	for item in priority:
		if item is String:
			var name := clean_text(item, 80).to_lower()
			if DEFAULT_TRIM_ORDER.has(name) and not ranked.has(name):
				ranked.append(name)
	var defaults := DEFAULT_TRIM_ORDER.duplicate()
	defaults.reverse()
	for name in defaults:
		if not ranked.has(name):
			ranked.append(name)
	ranked.reverse()
	return ranked


static func _minimum_tier(manifest: Dictionary) -> String:
	var conformance: Variant = manifest.get("conformance")
	var value: Variant = conformance.get("min_tier") if conformance is Dictionary else null
	return value if value == "M" or value == "L" else "S"
