class_name Shardcore
extends RefCounted
## SHARDCORE v1.x bundle I/O for Godot: the GDScript port of shardcore/core.py.
##
## The canonical copy lives at shardcore/vendor/shardcore.gd. It is vendored (copied
## verbatim) into every Godot app that reads or writes .shard bundles, so they emit the
## same manifest shape and make the same trust decisions as the Python apps. Edit only
## the canonical copy, then run
##
##     uv run python tools/ecosystem/ecosystem.py sync     (from shardcore)
##
## tests/test_vendor_gdscript.py holds this file to the library: same version, schema
## ids and identity derivation, bundles it writes diagnose current, and its strict
## reader agrees with shardcore.read_bundle_document on the conformance cases.
##
## Writer contract (spec 2, 5, 9, 11.4, 11.5), as in the Python helper: spec_version and
## the bundle_version alias stamped "1.12", no memory_format, every files entry carries
## {schema, sha256, size} from the exact bytes written, timestamps are UTC with a Z,
## shard_id survives every save (one is minted when missing), a branch gets a new id and
## a lineage block, manifest.revision is the prior state's n plus 1 and pins it (a new
## identity starts at n 1), and a bundle stamped with a newer spec is never rewritten.
## Not ported: the list-to-map anatomy fold and the three-way merge (core.py
## anatomy_parts_map, merge_bundles); no Godot writer stores list-shape anatomy, and a
## game that needs a merge runs shardcore's. Reader
## contract: shardcore/document.py read_bundle_document, strict, in memory, nothing
## extracted to disk.
##
## GDScript has no exceptions, so calls that can fail return a result dictionary:
## {"ok": true, ...} or {"ok": false, "code": <reason>, "error": <message>}.
##
## Godot's JSON parser reads every number as a float, so this file writes JSON itself
## (json_text, canonical_json): a float with no fractional part is written as an integer,
## which is what the Python writers emitted for it.
## shortcut: a manifest that held a genuine float like 1.0 digests differently here than
## in Python (1 against 1.0), so a derived shard_id for it would differ. No manifest field
## the spec defines is a float; keep JSON floats out of manifests.

const SPEC_VERSION := "1.12"
## What a new shard is stamped with: the lowest version that covers what writers put in
## one (compatibility RFC section 4). A save keeps the version a shard declares.
const NEW_SHARD_SPEC := "1.12"
## The oldest form this helper writes. A save of an older shard upgrades it.
const OLDEST_KEPT_SPEC := "1.9"
## The highest spec major this reader understands (spec section 1).
const SUPPORTED_MAJOR := 1
const MIND_FORMAT_VERSION := "2.1"

## The closed ten stats of soul.stat_block (spec 5.1).
const CANONICAL_STATS: Array[String] = ["STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS"]
## Average default when a soul has no stat_block at all (spec 5.1).
const DEFAULT_STAT := 5
const STAT_LONG_FORMS := {
	"STRENGTH": "STR", "ENDURANCE": "END", "VIGOR": "VIG", "DEXTERITY": "DEX",
	"TEMPERAMENT": "TMP", "ACUMEN": "ACU", "INSIGHT": "INS", "ATTUNEMENT": "ATT",
	"CONVICTION": "CNV", "PRESENCE": "PRS",
}

## Recognized runtime fields shared across the Nexus runtimes; they nest under soul.x_nexus
## (spec 5.5). App-private state belongs under the app's own x_<vendor> namespace.
const X_NEXUS_KEYS: Array[String] = [
	"asset_profile", "dormancy_behavior", "dynamic_data", "eidolon_signature",
	"haunting_tier", "integration_data", "loop_behavior_data", "loop_state",
	"loyalty_kernel_v1_0", "reicodex_commands", "reicodex_rituals_data",
]

const ASSETS_SCHEMA := "shardcore/assets@1.0"
## The neuron pillar's schema id follows its content: the document's own
## "version" picks the id. PILLAR_SCHEMAS holds the id used without the bytes.
const NEURON_SCHEMAS := {
	"1.0": "shardcore/neuron@1.0",
	"1.1": "shardcore/neuron@1.1",
}
const PILLAR_SCHEMAS := {
	"soulshard.json": "shardcore/soul@1.9",
	"shellshard.json": "shardcore/shell@1.12",
	"mindshard.json": "shardcore/mind@2.1",
	"memoryshard.json": "shardcore/mind@2.1",
	"neuronshard.json": "shardcore/neuron@1.1",
	"canonshard.json": "shardcore/canon@1.0",
	"statshard.json": "shardcore/stat@1.0",
	"driveshard.json": "shardcore/drive@0.1",
	"worldshard.json": "shardcore/world@1.0",
}
## The ids a pillar has carried, newest first with the version each came in.
const _SCHEMAS_SINCE := {
	"shellshard.json": [[[1, 12], "shardcore/shell@1.12"], [[1, 11], "shardcore/shell@1.10"], [[1, 9], "shardcore/shell@1.9"]],
	"neuronshard.json": [[[1, 12], "shardcore/neuron@1.1"], [[1, 9], "shardcore/neuron@1.0"]],
}
## Folder prefixes, legacy top-level asset folders included (still mapped pre-consolidation).
const PREFIX_SCHEMAS := [
	["body/", "shardcore/body@1.0"],
	["assets/", ASSETS_SCHEMA],
	["images/", ASSETS_SCHEMA],
	["attestations/", ASSETS_SCHEMA],
	["skills/", ASSETS_SCHEMA],
	["references/", ASSETS_SCHEMA],
]
const ASSET_EXTENSIONS: Array[String] = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ots"]

## Spec section 12: migration 0015 derives ids under this namespace.
const IDENTITY_NAMESPACE := "7e027d65-5d78-55a0-b193-cd8e1ecdccc3"
const BRANCH_RELATIONSHIPS: Array[String] = ["alternate-universe", "derivative", "interpretation"]
const MAX_SHARD_ID_LENGTH := 128

## Strict reader caps, matching shardcore/document.py and bundle.py.
const MAX_BUNDLE_BYTES := 64 * 1024 * 1024
const MAX_MEMBER_BYTES := 16 * 1024 * 1024
const MAX_TOTAL_UNCOMPRESSED_BYTES := 64 * 1024 * 1024

const _MIND_TIERS: Array[String] = ["short_term", "long_term", "core", "archive"]
const _FLAT_ENTRY_KEYS: Array[String] = ["memories", "entries", "slots", "log"]

static var _sha256_hex := RegEx.create_from_string("^[a-f0-9]{64}$")
static var _spec_version := RegEx.create_from_string("^[0-9]+\\.[0-9]+$")
static var _version_text := RegEx.create_from_string("^[0-9]+(\\.[0-9]+)*$")
static var _iso_local := RegEx.create_from_string("^(\\d{4}-\\d{2}-\\d{2})(?:[T ](\\d{2}:\\d{2}(?::\\d{2})?)(?:\\.\\d+)?)?([+-]\\d{2}:?\\d{2})?$")


# --------------------------------------------------------------------------- #
# Schema ids
# --------------------------------------------------------------------------- #

static func _neuron_schema(data: PackedByteArray) -> String:
	if data.is_empty():
		return ""
	var json := JSON.new()
	if json.parse(data.get_string_from_utf8()) != OK or not json.data is Dictionary:
		return ""
	var version: Variant = (json.data as Dictionary).get("version")
	return NEURON_SCHEMAS[version] if version is String and NEURON_SCHEMAS.has(version) else ""


## The schema id for an archive member, or "" when unmappable. Pass the
## member's bytes when they are at hand: a neuronshard is stamped by the
## version its document declares (NEURON_SCHEMAS). Pass spec for the id a shard of that
## version carries; the default is the current one.
static func schema_for_member(name: String, data: PackedByteArray = PackedByteArray(), spec := "") -> String:
	if name == "neuronshard.json":
		var own := _neuron_schema(data)
		if own != "":
			return own
	var declared := version_tuple(spec)
	if not declared.is_empty():
		for since in _SCHEMAS_SINCE.get(name, []):
			if not _version_less(declared, since[0]):
				return since[1]
	if PILLAR_SCHEMAS.has(name):
		return PILLAR_SCHEMAS[name]
	for pair in PREFIX_SCHEMAS:
		if name.begins_with(pair[0]):
			return pair[1]
	var lower := name.to_lower()
	for ext in ASSET_EXTENSIONS:
		if lower.ends_with(ext):
			return ASSETS_SCHEMA
	return ""


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #

## Current time as ISO-8601 UTC with a trailing Z: 2026-07-08T12:34:56Z.
static func utc_now() -> String:
	return Time.get_datetime_string_from_system(true) + "Z"


## A timestamp string normalized to UTC with a Z, or "" when it can't be read. A string
## with no offset is assumed local, as the Python helper reads a naive stamp.
## shortcut: local time uses today's UTC offset, so a naive stamp from the other side of a
## DST change lands an hour off. Python reads the historical offset.
static func to_utc_z(value: Variant) -> String:
	if not (value is String or value is StringName):
		return ""
	var text := String(value).strip_edges()
	if text == "":
		return ""
	if text.ends_with("Z"):
		return text
	var m := _iso_local.search(text)
	if m == null:
		return ""
	var clock := m.get_string(2)
	if clock == "":
		clock = "00:00:00"
	elif clock.length() == 5:
		clock += ":00"
	var unix := Time.get_unix_time_from_datetime_string("%sT%s" % [m.get_string(1), clock])
	var offset := m.get_string(3)
	if offset == "":
		unix -= int(Time.get_time_zone_from_system().get("bias", 0)) * 60
	else:
		var digits := offset.substr(1).replace(":", "")
		var minutes := int(digits.substr(0, 2)) * 60 + int(digits.substr(2, 2))
		unix -= minutes * 60 * (1 if offset.begins_with("+") else -1)
	return Time.get_datetime_string_from_unix_time(unix, false) + "Z"


# --------------------------------------------------------------------------- #
# JSON (ints stay ints; canonical form per spec 11.1)
# --------------------------------------------------------------------------- #

## JSON text for value. indent "" writes compact JSON with Python's default separators
## (", " and ": "); pass "  " for the indented form the Python writers use.
static func json_text(value: Variant, indent := "") -> String:
	return _json(value, indent, false, "", ", ", ": ")


## Spec 11.1 canonical form: sorted keys, no insignificant whitespace, UTF-8.
static func canonical_json(value: Variant) -> PackedByteArray:
	return _json(value, "", true, "", ",", ":").to_utf8_buffer()


static func _json(v: Variant, indent: String, sort: bool, pad: String, item_sep: String, key_sep: String) -> String:
	match typeof(v):
		TYPE_NIL:
			return "null"
		TYPE_BOOL:
			return "true" if v else "false"
		TYPE_INT:
			return str(v)
		TYPE_FLOAT:
			return _json_number(v)
		TYPE_STRING, TYPE_STRING_NAME, TYPE_NODE_PATH:
			return _json_string(String(v))
		TYPE_DICTIONARY:
			var d: Dictionary = v
			if d.is_empty():
				return "{}"
			var by_key := {}
			for k in d:
				by_key[String(k) if (k is String or k is StringName) else str(k)] = d[k]
			var keys: Array = by_key.keys()
			if sort:
				keys.sort()
			var inner := pad + indent
			var parts := PackedStringArray()
			for k in keys:
				parts.append(_json_string(k) + key_sep + _json(by_key[k], indent, sort, inner, item_sep, key_sep))
			if indent == "":
				return "{" + item_sep.join(parts) + "}"
			return "{\n" + inner + (",\n" + inner).join(parts) + "\n" + pad + "}"
		_:
			if v is Array or (typeof(v) >= TYPE_PACKED_BYTE_ARRAY and typeof(v) <= TYPE_PACKED_VECTOR4_ARRAY):
				var arr: Array = Array(v)
				if arr.is_empty():
					return "[]"
				var inner := pad + indent
				var parts := PackedStringArray()
				for item in arr:
					parts.append(_json(item, indent, sort, inner, item_sep, key_sep))
				if indent == "":
					return "[" + item_sep.join(parts) + "]"
				return "[\n" + inner + (",\n" + inner).join(parts) + "\n" + pad + "]"
			return _json_string(str(v))


static func _json_number(f: float) -> String:
	if is_nan(f):
		return "NaN"
	if is_inf(f):
		return "Infinity" if f > 0.0 else "-Infinity"
	if f == floorf(f) and absf(f) < 9.0e18:
		return str(int(f))
	return str(f)


## Escapes as Python's json.dumps(ensure_ascii=False) does.
static func _json_string(s: String) -> String:
	var out := "\""
	for i in s.length():
		var c := s.unicode_at(i)
		match c:
			0x22:
				out += "\\\""
			0x5c:
				out += "\\\\"
			0x0a:
				out += "\\n"
			0x0d:
				out += "\\r"
			0x09:
				out += "\\t"
			0x08:
				out += "\\b"
			0x0c:
				out += "\\f"
			_:
				out += ("\\u%04x" % c) if c < 0x20 else char(c)
	return out + "\""


## Parses JSON bytes that must be strict UTF-8. Returns {"ok", "value"} or a failure.
static func parse_json(data: PackedByteArray, name := "") -> Dictionary:
	var text := data.get_string_from_utf8()
	if text.to_utf8_buffer() != data:
		return _fail("json_encoding", "JSON member is not strict UTF-8: %s" % name)
	var json := JSON.new()
	if json.parse(text) != OK:
		return _fail("json_syntax", "JSON member is invalid: %s: %s" % [name, json.get_error_message()])
	return {"ok": true, "value": json.data}


# --------------------------------------------------------------------------- #
# Hashes and identity (spec 11.1, 11.4, migration 0015)
# --------------------------------------------------------------------------- #

static func sha256_hex(data: PackedByteArray) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	if not data.is_empty():
		ctx.update(data)
	return ctx.finish().hex_encode()


## The spec 11.1 manifest_sha256 of a parsed manifest (what lineage pins).
static func manifest_digest(manifest: Dictionary) -> String:
	return sha256_hex(canonical_json(manifest))


## A fresh identity: random UUIDv4, lowercase hyphenated (spec 11.4.1).
static func new_shard_id() -> String:
	var b := Crypto.new().generate_random_bytes(16)
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return _uuid_text(b)


## The deterministic id migration 0015 mints for an existing bundle (spec 12), or "" when
## manifest_sha256 isn't 64 lowercase hex characters.
static func derived_shard_id(manifest_sha256: String) -> String:
	if _sha256_hex.search(manifest_sha256) == null:
		return ""
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA1)
	ctx.update(IDENTITY_NAMESPACE.replace("-", "").hex_decode())
	ctx.update(manifest_sha256.to_utf8_buffer())
	var b := ctx.finish().slice(0, 16)
	b[6] = (b[6] & 0x0f) | 0x50
	b[8] = (b[8] & 0x3f) | 0x80
	return _uuid_text(b)


static func _uuid_text(b: PackedByteArray) -> String:
	var hex := b.hex_encode()
	return "%s-%s-%s-%s-%s" % [hex.substr(0, 8), hex.substr(8, 4), hex.substr(12, 4), hex.substr(16, 4), hex.substr(20, 12)]


## Why value is not a valid shard_id, or "" when it is (spec 11.4.1).
static func shard_id_error(value: Variant) -> String:
	if not (value is String or value is StringName) or String(value).strip_edges() == "":
		return "shard_id must be a non-empty string"
	var s := String(value)
	if s.length() > MAX_SHARD_ID_LENGTH:
		return "shard_id exceeds %d characters" % MAX_SHARD_ID_LENGTH
	for i in s.length():
		var c := s.unicode_at(i)
		if c < 0x20 or c == 0x7f:
			return "shard_id contains control characters"
	return ""


## The shard_id for a write whose manifest has none yet. A prior bundle manifest (one with
## a files map) gets the id migration 0015 derives from it; anything else is new.
static func mint_shard_id(prior_manifest: Variant = null) -> String:
	if prior_manifest is Dictionary and prior_manifest.has("files"):
		return derived_shard_id(manifest_digest(prior_manifest))
	return new_shard_id()


## The prior manifest for a branch of parent, ready for build_manifest (spec 11.2, 11.4):
## no immutable flag, a new shard_id, and a branch block pinning the exact parent state.
## The files map and revision go too, so the branch's revision chain starts at n 1.
## Returns {} for a relationship that isn't a branch.
static func branch_manifest(parent: Dictionary, relationship := "derivative") -> Dictionary:
	if not BRANCH_RELATIONSHIPS.has(relationship):
		push_error("branch relationship must be one of: %s" % ", ".join(BRANCH_RELATIONSHIPS))
		return {}
	var pin := {"manifest_sha256": manifest_digest(parent)}
	var parent_id: Variant = parent.get("shard_id")
	if shard_id_error(parent_id) == "":
		pin["shard_id"] = parent_id
	var card: Variant = parent.get("card")
	var label: Variant = card.get("name") if card is Dictionary else null
	if not (label is String and label.strip_edges() != ""):
		label = parent.get("shard_name")
	if label is String and label.strip_edges() != "":
		pin["label"] = label
	var child := parent.duplicate(true)
	for key in ["immutable", "files", "revision"]:
		child.erase(key)
	child["shard_id"] = new_shard_id()
	child["lineage"] = {"relationship": relationship, "parent": pin}
	return child


# --------------------------------------------------------------------------- #
# Revision chain (spec 11.5), port of core.py next_revision and compare_revisions
# --------------------------------------------------------------------------- #

## Prior states a manifest remembers, newest first.
const REVISION_HISTORY_MAX := 16


static func _is_digest(value: Variant) -> bool:
	return value is String and value.length() == 64 and value == value.to_lower() and value.is_valid_hex_number()


## A JSON count: an int, or a float with no fraction (Godot reads every number as a float).
static func _count(value: Variant) -> int:
	if value is int:
		return value
	if value is float and value == floorf(value) and value > 0.0:
		return int(value)
	return 0


## The prior-state digests a manifest records, newest first. Never fails.
static func revision_history(manifest: Dictionary) -> Array:
	var revision: Variant = manifest.get("revision")
	if not revision is Dictionary:
		return []
	var out := []
	var history: Variant = revision.get("history")
	if history is Array:
		for d in history:
			if _is_digest(d) and out.size() < REVISION_HISTORY_MAX:
				out.append(d)
	if out.is_empty() and _is_digest(revision.get("prior")):
		out.append(revision["prior"])
	return out


## The revision block for a write that replaces prior_manifest's state: {"n": 1} with no
## prior bundle state (new, branch, offspring), else n plus 1 with prior pinned and the
## prior's history behind it. merged_with is the other side of a merge.
static func next_revision(prior_manifest: Variant, merged_with: Variant = null) -> Dictionary:
	if not (prior_manifest is Dictionary and prior_manifest.has("files")):
		return {"n": 1}
	var prior := manifest_digest(prior_manifest)
	var chains := [[prior] + revision_history(prior_manifest)]
	var revision_value: Variant = prior_manifest.get("revision")
	var n := (_count(revision_value.get("n")) if revision_value is Dictionary else 0) + 1
	var merged := ""
	if merged_with is Dictionary and merged_with.has("files"):
		merged = manifest_digest(merged_with)
		chains.append([merged] + revision_history(merged_with))
		var other: Variant = merged_with.get("revision")
		n = maxi(n, (_count(other.get("n")) if other is Dictionary else 0) + 1)
	var history := []
	var depth := 0
	var longest := 0
	for chain in chains:
		longest = maxi(longest, chain.size())
	while depth < longest:
		for chain in chains:
			if depth < chain.size() and not history.has(chain[depth]):
				history.append(chain[depth])
		depth += 1
	var out := {"n": n, "prior": prior, "history": history.slice(0, REVISION_HISTORY_MAX)}
	if merged != "":
		out["merged"] = merged
	return out


## same, a_newer, b_newer, diverged or unknown (core.py compare_revisions); "" when the
## two carry different shard_ids, which have no order.
static func compare_revisions(a: Dictionary, b: Dictionary) -> String:
	if a.get("shard_id") != b.get("shard_id"):
		return ""
	var digest_a := manifest_digest(a)
	var digest_b := manifest_digest(b)
	if digest_a == digest_b:
		return "same"
	var history_a := revision_history(a)
	var history_b := revision_history(b)
	if history_a.has(digest_b):
		return "a_newer"
	if history_b.has(digest_a):
		return "b_newer"
	for d in history_a:
		if history_b.has(d):
			return "diverged"
	return "unknown"


## The newest state both manifests descend from, in a's order, or "".
static func common_ancestor(a: Dictionary, b: Dictionary) -> String:
	var history_b := revision_history(b)
	for d in revision_history(a):
		if history_b.has(d):
			return d
	return ""


# --------------------------------------------------------------------------- #
# Soul normalization (migrations 0013 and 0010)
# --------------------------------------------------------------------------- #

## Folds soul.stat_block to the canonical ten, in place. Returns notes. Long-form and
## case-variant keys fold onto the abbreviations, a Resonance key moves to soul.resonance,
## other keys keep under soul.x_nexus.legacy_stats, missing stats get the default.
static func normalize_stat_block(soul: Dictionary) -> PackedStringArray:
	var notes := PackedStringArray()
	var block: Variant = soul.get("stat_block")
	if not block is Dictionary or block.is_empty():
		var fresh := {}
		for stat in _sorted(CANONICAL_STATS):
			fresh[stat] = DEFAULT_STAT
		soul["stat_block"] = fresh
		notes.append("no stat_block; stamped average default (all %d)" % DEFAULT_STAT)
		return notes
	var normalized := {}
	var legacy := {}
	for key in block:
		var upper := String(key).to_upper()
		var canonical: String = upper if CANONICAL_STATS.has(upper) else STAT_LONG_FORMS.get(upper, "")
		var value: Variant = block[key]
		if canonical != "":
			normalized[canonical] = _coerce_stat(canonical, value, notes)
		elif upper == "RESONANCE":
			if soul.has("resonance") and soul["resonance"] != value:
				legacy[key] = value
				notes.append("stat_block.%s kept as legacy (soul.resonance already set)" % key)
			else:
				soul["resonance"] = value
				notes.append("relocated %s to soul.resonance" % key)
		else:
			legacy[key] = value
			notes.append("unrecognized stat %s preserved under x_nexus.legacy_stats" % key)
	for stat in _sorted(CANONICAL_STATS):
		if not normalized.has(stat):
			normalized[stat] = DEFAULT_STAT
			notes.append("missing stat %s stamped %d" % [stat, DEFAULT_STAT])
	var out := {}
	for stat in _sorted(normalized.keys()):
		out[stat] = normalized[stat]
	soul["stat_block"] = out
	if not legacy.is_empty():
		var nested: Dictionary = soul.get("x_nexus") if soul.get("x_nexus") is Dictionary else {}
		var legacy_stats: Dictionary = nested.get("legacy_stats") if nested.get("legacy_stats") is Dictionary else {}
		legacy_stats.merge(legacy, true)
		nested["legacy_stats"] = legacy_stats
		soul["x_nexus"] = nested
	return notes


static func _coerce_stat(stat: String, value: Variant, notes: PackedStringArray) -> int:
	if not (value is int or value is float):
		notes.append("%s non-numeric %s, stamped default %d" % [stat, str(value), DEFAULT_STAT])
		return DEFAULT_STAT
	var coerced := _round_half_even(float(value))
	var clamped := clampi(coerced, 1, 10)
	if float(clamped) != float(value):
		notes.append("%s %s -> %d" % [stat, str(value), clamped])
	return clamped


## Python's round(): halves go to the even neighbor.
static func _round_half_even(f: float) -> int:
	var low := floorf(f)
	var frac := f - low
	if frac > 0.5:
		return int(low) + 1
	if frac < 0.5:
		return int(low)
	return int(low) if int(low) % 2 == 0 else int(low) + 1


## Moves recognized runtime fields to soul.x_nexus, in place. Returns the moved keys.
## Top-level wins on collision (it is what the runtime was reading).
static func renest_x_nexus(soul: Dictionary) -> PackedStringArray:
	var nested: Dictionary = soul.get("x_nexus") if soul.get("x_nexus") is Dictionary else {}
	var moved := PackedStringArray()
	for key in X_NEXUS_KEYS:
		if soul.has(key):
			nested[key] = soul[key]
			soul.erase(key)
			moved.append(key)
	if not moved.is_empty():
		soul["x_nexus"] = nested
	return moved


## Normalizes a soul for a write, in place: stat block plus x_nexus re-nest. Shell fields
## are app-specific and not split here.
static func prepare_soul_for_write(soul: Dictionary) -> Dictionary:
	normalize_stat_block(soul)
	renest_x_nexus(soul)
	return soul


# --------------------------------------------------------------------------- #
# Mind pillar (migration 0003): never write a bare array
# --------------------------------------------------------------------------- #

## A tiered mind@2.1 dictionary. A flat list becomes long_term slots, a tiered dict passes
## through with format_version stamped, a flat dict with an entry list under a known key is
## folded with its other keys riding along, and anything else becomes empty tiers.
static func ensure_tiered_mind(mind: Variant) -> Dictionary:
	if mind is Array:
		return _empty_tiers(mind)
	if not mind is Dictionary:
		return _empty_tiers([])
	var d: Dictionary = mind
	for tier in _MIND_TIERS:
		if d.has(tier):
			var out := d.duplicate(true)
			out["format_version"] = MIND_FORMAT_VERSION
			return out
	for key in _FLAT_ENTRY_KEYS:
		if d.get(key) is Array:
			var tiered := _empty_tiers(d[key])
			for k in d:
				if k != key and k != "format_version":
					tiered[k] = d[k]
			tiered["format_version"] = MIND_FORMAT_VERSION
			return tiered
	var bare := _empty_tiers([])
	for k in d:
		if k != "format_version":
			bare[k] = d[k]
	bare["format_version"] = MIND_FORMAT_VERSION
	return bare


static func _empty_tiers(long_term: Array) -> Dictionary:
	return {
		"format_version": MIND_FORMAT_VERSION,
		"short_term": {"slots": []},
		"long_term": {"slots": long_term.duplicate(true)},
		"core": [],
		"archive": [],
	}


# --------------------------------------------------------------------------- #
# Manifest construction (migrations 0005/0007/0008/0009/0011/0015)
# --------------------------------------------------------------------------- #

## Regenerates manifest.card from the soul (migration 0008), over any prior card.
static func build_card(soul: Variant, prior_card: Variant = null) -> Dictionary:
	var card: Dictionary = prior_card.duplicate(true) if prior_card is Dictionary else {}
	if not soul is Dictionary:
		return card
	for key in ["name", "title", "role", "core_essence"]:
		var value: Variant = soul.get(key)
		if value is String and value.strip_edges() != "":
			card[key] = value
	var tags: Variant = soul.get("trait_tags")
	if not (tags is Array and not tags.is_empty()):
		tags = soul.get("traits")
	if tags is Array:
		var clean := []
		for t in tags:
			if t is String and clean.size() < 12:
				clean.append(t)
		if not clean.is_empty():
			card["tags"] = clean
	return card


## The manifest.files map: {sha256, size, schema} per member. manifest.json and folder
## entries are skipped. A member keeps the schema id it declares in keep_from (the
## manifests this write replaces; the higher of a merge's two), except a neuronshard,
## whose id follows its document. Any other member gets the id a shard of version spec
## carries; one with no known schema still gets sha256 and size.
static func build_files_info(members: Dictionary, keep_from := [], spec := "") -> Dictionary:
	var files := {}
	for name in _sorted(members.keys()):
		if name == "manifest.json" or name.ends_with("/"):
			continue
		var data: PackedByteArray = members[name]
		var entry := {"sha256": sha256_hex(data), "size": data.size()}
		var schema := _neuron_schema(data) if name == "neuronshard.json" else ""
		if schema == "":
			schema = _declared_schema(name, keep_from)
		if schema == "":
			schema = schema_for_member(name, data, spec)
		if schema != "":
			entry["schema"] = schema
		files[name] = entry
	return files


static func _declared_schema(name: String, manifests: Array) -> String:
	var found := ""
	for manifest in manifests:
		var files: Variant = manifest.get("files") if manifest is Dictionary else null
		var entry: Variant = files.get(name) if files is Dictionary else null
		var schema: Variant = entry.get("schema") if entry is Dictionary else null
		if schema is String and schema.strip_edges() != "":
			if found == "" or _version_less(version_tuple(found.get_slice("@", 1)), version_tuple(schema.get_slice("@", 1))):
				found = schema
	return found


# --------------------------------------------------------------------------- #
# The version a write stamps (compatibility RFC sections 3 and 4)
# --------------------------------------------------------------------------- #

static func _declared_spec(manifest: Variant) -> String:
	if manifest is Dictionary:
		for key in ["spec_version", "bundle_version"]:
			var text: Variant = manifest.get(key)
			if text is String and not version_tuple(text).is_empty():
				return text.strip_edges()
	return ""


## manifest.min_writer when it is a version, else "".
static func min_writer(manifest: Variant) -> String:
	var text: Variant = manifest.get("min_writer") if manifest is Dictionary else null
	return text.strip_edges() if text is String and not version_tuple(text).is_empty() else ""


static func _later(a: String, b: String) -> String:
	if a == "" or b == "":
		return a if b == "" else b
	return b if _version_less(version_tuple(a), version_tuple(b)) else a


## The spec_version a write stamps: the one the shard already declares, the higher of a
## merge's sides, or NEW_SHARD_SPEC for a new shard and one older than OLDEST_KEPT_SPEC.
static func kept_spec(prior_manifest: Variant, merged_with: Variant = null) -> String:
	var held := _later(_declared_spec(prior_manifest), _declared_spec(merged_with))
	if held == "" or _version_less(version_tuple(held), version_tuple(OLDEST_KEPT_SPEC)):
		return NEW_SHARD_SPEC
	return held


## The lowest version that covers these members: a neuron@1.1 document and
## parts[id].neural came in 1.12; anything else a 1.9 shard can hold.
static func content_spec(members: Dictionary) -> String:
	if _neuron_schema(members.get("neuronshard.json", PackedByteArray())) == NEURON_SCHEMAS["1.1"]:
		return "1.12"
	var json := JSON.new()
	var raw: PackedByteArray = members.get("shellshard.json", PackedByteArray())
	if raw.is_empty() or json.parse(raw.get_string_from_utf8()) != OK or not json.data is Dictionary:
		return OLDEST_KEPT_SPEC
	var anatomy: Variant = json.data.get("anatomy_profile")
	var parts: Variant = anatomy.get("parts") if anatomy is Dictionary else null
	if parts is Dictionary:
		for part in parts.values():
			if part is Dictionary and part.has("neural"):
				return "1.12"
	return OLDEST_KEPT_SPEC


## {"spec": the version this write stamps, "problem": why it can't, or ""}. A changed
## member that needs more than the shard declares is a problem until opts.upgrade_to says
## otherwise; a new identity takes the version it needs.
static func _write_spec(members: Dictionary, prior_manifest: Variant, opts: Dictionary) -> Dictionary:
	var merged_with: Variant = opts.get("merged_with")
	var spec := kept_spec(prior_manifest, merged_with)
	var upgrade: String = str(opts.get("upgrade_to", ""))
	if upgrade != "":
		var wanted := version_tuple(upgrade)
		if wanted.is_empty() or _version_less(wanted, version_tuple(spec)) or _version_less(version_tuple(SPEC_VERSION), wanted):
			return {"spec": spec, "problem": "upgrade_to %s must be from %s to %s" % [upgrade, spec, SPEC_VERSION]}
		spec = upgrade
	var fresh := {}
	for name in ["neuronshard.json", "shellshard.json"]:
		if not members.has(name):
			continue
		var held := false
		for manifest in [prior_manifest, merged_with]:
			var files: Variant = manifest.get("files") if manifest is Dictionary else null
			var entry: Variant = files.get(name) if files is Dictionary else null
			if entry is Dictionary and entry.get("sha256") == sha256_hex(members[name]):
				held = true
		if not held:
			fresh[name] = members[name]
	var needed := content_spec(fresh)
	if _version_less(version_tuple(spec), version_tuple(needed)):
		if prior_manifest is Dictionary and prior_manifest.has("files"):
			return {"spec": spec, "problem": "the shard declares spec %s and these members need %s; write without them, or upgrade it (upgrade_to)" % [spec, needed]}
		spec = needed
	return {"spec": spec, "problem": ""}


## A complete manifest for the given member bytes (payload only, no manifest.json). Keeps
## the version and schema ids the shard declares and unknown keys from prior_manifest
## (shard_id, lineage, conformance, min_writer, vendor fields). Returns {} when
## check_spec_writable refuses the prior manifest or a changed member needs a newer
## version; pack_bundle reports that as a failure. prior_manifest is the state this write
## replaces: the file as loaded, or what the last save returned.
## opts: shard_name, immutable, extra (merged last), now (the timestamp to stamp),
## merged_with (the other side's manifest, for a merge), upgrade_to (raise the version).
static func build_manifest(members: Dictionary, soul: Variant = null, prior_manifest: Variant = null, opts := {}) -> Dictionary:
	if check_spec_writable(prior_manifest) != "" or check_spec_writable(opts.get("merged_with")) != "":
		return {}
	var decided := _write_spec(members, prior_manifest, opts)
	if decided["problem"] != "":
		return {}
	var spec: String = decided["spec"]
	var level := version_tuple(spec)
	var stamp: String = opts.get("now", utc_now())
	var manifest: Dictionary = prior_manifest.duplicate(true) if prior_manifest is Dictionary else {}
	manifest.erase("memory_format")
	manifest.erase("last_modified")
	manifest["spec_version"] = spec
	manifest["bundle_version"] = spec
	if opts.get("merged_with") is Dictionary:
		var floor_spec := _later(min_writer(prior_manifest), min_writer(opts["merged_with"]))
		manifest.erase("min_writer")
		if floor_spec != "":
			manifest["min_writer"] = floor_spec
	var created := to_utc_z(manifest.get("created"))
	manifest["created"] = created if created != "" else stamp
	manifest["last_modified_utc"] = stamp
	if opts.has("shard_name"):
		manifest["shard_name"] = opts["shard_name"]
	elif not manifest.has("shard_name") and soul is Dictionary:
		var name: Variant = soul.get("name")
		if name is String and name.strip_edges() != "":
			manifest["shard_name"] = name
	if soul != null:
		manifest["card"] = build_card(soul, manifest.get("card"))
	if opts.has("immutable"):
		manifest["immutable"] = bool(opts["immutable"])
	if opts.get("extra") is Dictionary:
		manifest.merge(opts["extra"], true)
	if not manifest.has("shard_id"):
		manifest["shard_id"] = mint_shard_id(prior_manifest)
	if manifest.has("revision") or not _version_less(level, [1, 11]):
		manifest["revision"] = next_revision(prior_manifest, opts.get("merged_with"))
	var replaced := [] if str(opts.get("upgrade_to", "")) != "" else [prior_manifest, opts.get("merged_with")]
	manifest["files"] = build_files_info(members, replaced, spec)
	return manifest


# --------------------------------------------------------------------------- #
# Backup vault (port of shardcore/backup_vault.py record_bundle)
# --------------------------------------------------------------------------- #

const BACKUP_VAULT_ENV := "SHARD_BACKUP_VAULT"
const BACKUP_APP_ENV := "SHARD_APP"
const BACKUP_VAULT_DEFAULT := ".vault/backup_vault"
## A workspace kept in this folder at the root of a drive is found by programs that live
## elsewhere on that drive.
const BACKUP_DRIVE_FOLDER := ".shards"
const _BACKUP_MAX_BUNDLE_BYTES := 256 * 1024 * 1024


## The first WORKSPACE.toml at or above start (a file or a folder), or "".
static func _bv_workspace_toml(start: String) -> String:
	var dir := start.replace("\\", "/").simplify_path()
	if FileAccess.file_exists(dir):
		dir = dir.get_base_dir()
	while dir != "":
		if FileAccess.file_exists(dir.path_join("WORKSPACE.toml")):
			return dir.path_join("WORKSPACE.toml")
		var parent := dir.get_base_dir()
		if parent == dir:
			break
		dir = parent
	return ""


## [artifacts] and the [[consumers]] name/path pairs, read line by line.
static func _bv_read_workspace(toml: String) -> Dictionary:
	var artifacts := {}
	var consumers: Array = []
	var section := ""
	var line_re := RegEx.create_from_string("^\\s*([A-Za-z0-9_]+)\\s*=\\s*\"([^\"]*)\"")
	for raw in FileAccess.get_file_as_string(toml).split("\n"):
		var line := raw.strip_edges()
		if line.begins_with("["):
			section = line
			if line == "[[consumers]]":
				consumers.append({})
			continue
		var m := line_re.search(line)
		if m == null:
			continue
		if section == "[artifacts]":
			artifacts[m.get_string(1)] = m.get_string(2)
		elif section == "[[consumers]]" and m.get_string(1) in ["name", "path"]:
			consumers[-1][m.get_string(1)] = m.get_string(2)
	return {"artifacts": artifacts, "consumers": consumers}


static func _bv_origins() -> Array:
	return [ProjectSettings.globalize_path("res://"), OS.get_executable_path()]


## "D:/" for "D:/games/x", "/" for a POSIX path, "" for a relative one.
static func _bv_drive_root(start: String) -> String:
	var path := start.replace("\\", "/")
	if path.begins_with("/"):
		return "/"
	return path.substr(0, 3) if path.length() > 2 and path.substr(1, 2) == ":/" else ""


static func _bv_workspace(near: String) -> String:
	var starts: Array = [near] if near != "" else []
	starts.append_array(_bv_origins())
	for start in starts:
		var found := _bv_workspace_toml(start)
		if found != "":
			return found
	for start in starts:
		var root := _bv_drive_root(start)
		var candidate := root.path_join(BACKUP_DRIVE_FOLDER).path_join("WORKSPACE.toml")
		if root != "" and FileAccess.file_exists(candidate):
			return candidate
	return ""


## Where states are recorded, or "" when recording is off (see the Python module).
static func backup_vault_dir(near := "") -> String:
	var setting := OS.get_environment(BACKUP_VAULT_ENV).strip_edges()
	if setting.to_lower() == "off":
		return ""
	if setting != "":
		return setting.replace("\\", "/")
	var toml := _bv_workspace(near)
	if toml == "":
		return ""
	var artifacts: Dictionary = _bv_read_workspace(toml)["artifacts"]
	return toml.get_base_dir().path_join(artifacts.get("backup_vault", BACKUP_VAULT_DEFAULT)).simplify_path()


static func _bv_app(app: String) -> String:
	var name := app if app != "" else OS.get_environment(BACKUP_APP_ENV)
	if name == "":
		var toml := _bv_workspace("")
		if toml != "":
			for origin in _bv_origins():
				var where: String = origin.replace("\\", "/").simplify_path().to_lower().trim_suffix("/")
				for consumer in _bv_read_workspace(toml)["consumers"]:
					var root: String = toml.get_base_dir().path_join(consumer.get("path", "")).simplify_path().to_lower().trim_suffix("/")
					if consumer.get("name", "") != "" and (where == root or where.begins_with(root + "/")):
						name = consumer["name"]
						break
				if name != "":
					break
	if name == "":
		name = str(ProjectSettings.get_setting("application/config/name", "unknown"))
	var slug := RegEx.create_from_string("[^a-z0-9_-]+").sub(name.to_lower(), "_", true)
	slug = slug.strip_edges().trim_prefix("_").trim_suffix("_")
	return slug if slug != "" else "unknown"


static func _bv_in_temp(path: String) -> bool:
	for key in ["TEMP", "TMP", "TMPDIR"]:
		var temp := OS.get_environment(key).replace("\\", "/").simplify_path().to_lower().trim_suffix("/")
		if temp != "" and path.to_lower().begins_with(temp + "/"):
			return true
	return false


static func _bv_put(objects: String, data: PackedByteArray) -> String:
	var sha := sha256_hex(data)
	var target := objects.path_join(sha.substr(0, 2)).path_join(sha)
	if not FileAccess.file_exists(target):
		DirAccess.make_dir_recursive_absolute(target.get_base_dir())
		var tmp := "%s.%s.tmp" % [target, Crypto.new().generate_random_bytes(4).hex_encode()]
		var f := FileAccess.open(tmp, FileAccess.WRITE)
		if f == null:
			return ""
		f.store_buffer(data)
		f.close()
		if DirAccess.rename_absolute(tmp, target) != OK:
			DirAccess.remove_absolute(tmp)
			if not FileAccess.file_exists(target):
				return ""
	return sha


static func _bv_last_entry(journal: String) -> Dictionary:
	if not FileAccess.file_exists(journal):
		return {}
	var f := FileAccess.open(journal, FileAccess.READ)
	if f == null:
		return {}
	var size := f.get_length()
	f.seek(maxi(0, size - 65536))
	var lines := f.get_buffer(size - f.get_position()).get_string_from_utf8().split("\n", false)
	f.close()
	for i in range(lines.size() - 1, -1, -1):
		var entry: Variant = JSON.parse_string(lines[i])
		if entry is Dictionary:
			return entry
	return {}


## Records the bundle state at path in the backup vault: members are the exact
## archive members just written (with manifest.json), or empty to read the file.
## Returns the manifest digest recorded, or "" when off, scratch, or failed.
## Never fails the caller: a backup must not block the save it guards.
static func record_bundle(path: String, event: String, app := "", members := {}) -> String:
	var setting := OS.get_environment(BACKUP_VAULT_ENV).strip_edges().to_lower()
	var explicit := setting != "" and setting != "off"
	var where := path.replace("\\", "/").simplify_path()
	var store := backup_vault_dir(where)
	if store == "" or (not explicit and _bv_in_temp(where)):
		return ""
	var parts: Dictionary = members.duplicate()
	if parts.is_empty():
		if not FileAccess.file_exists(where):
			return ""
		var zip := ZIPReader.new()
		if zip.open(where) != OK:
			return ""
		for name in zip.get_files():
			if not name.ends_with("/"):
				parts[name] = zip.read_file(name)
		zip.close()
	if not parts.has("manifest.json"):
		return ""
	var manifest: Variant = JSON.parse_string((parts["manifest.json"] as PackedByteArray).get_string_from_utf8())
	if not manifest is Dictionary:
		return ""
	var digest := manifest_digest(manifest)
	var journal := store.path_join("journal").path_join(_bv_app(app) + ".jsonl")
	var last := _bv_last_entry(journal)
	if last.get("path", "") == where and last.get("manifest_sha256", "") == digest:
		return digest
	var shas := {}
	for name in _sorted(parts.keys()):
		var sha := _bv_put(store.path_join("objects"), parts[name])
		if sha == "":
			push_warning("backup vault: could not store %s from %s" % [name, where])
			return ""
		shas[name] = sha
	var card: Variant = manifest.get("card")
	var shard_name: Variant = manifest.get("shard_name")
	if not shard_name is String and card is Dictionary:
		shard_name = card.get("name")
	var entry := {
		"utc": Time.get_datetime_string_from_system(true) + "Z",
		"app": journal.get_file().get_basename(),
		"event": event,
		"path": where,
		"shard_id": manifest.get("shard_id"),
		"name": shard_name,
		"manifest_sha256": digest,
		"members": shas,
	}
	DirAccess.make_dir_recursive_absolute(journal.get_base_dir())
	var f := FileAccess.open(journal, FileAccess.READ_WRITE if FileAccess.file_exists(journal) else FileAccess.WRITE)
	if f == null:
		push_warning("backup vault: could not open %s" % journal)
		return ""
	f.seek_end()
	f.store_string(JSON.stringify(entry, "", true) + "\n")
	f.close()
	return digest


# --------------------------------------------------------------------------- #
# Packing (atomic write, forward-slash names, DEFLATED)
# --------------------------------------------------------------------------- #

## Copies the file an upgrade replaces beside itself, as <name>.v<version>.bak: an upgrade
## can be undone. The backup vault does this where there is one. False stops the upgrade.
static func _keep_before_upgrade(path: String, upgrade_to: String) -> bool:
	var zip := ZIPReader.new()
	if zip.open(path) != OK:
		return false
	var parsed := parse_json(zip.read_file("manifest.json"))
	zip.close()
	var declared := _declared_spec(parsed["value"]) if parsed["ok"] else ""
	if declared == "":
		declared = "unknown"
	if version_tuple(declared) == version_tuple(upgrade_to):
		return true
	var number := 1
	var kept := "%s.v%s.bak" % [path, declared]
	while FileAccess.file_exists(kept):
		number += 1
		kept = "%s.v%s.%d.bak" % [path, declared, number]
	return DirAccess.copy_absolute(path, kept) == OK


## Writes a .shard atomically: a temp file beside the target, renamed over it. The
## manifest hashes the exact member bytes written. Pass opts.manifest to write a prebuilt
## one; otherwise it is built from members, soul, prior_manifest and opts.
## Returns {"ok": true, "manifest": ...} or a failure (newer_spec, upgrade_needed,
## cannot_write).
## Records both the replaced and the written state in the backup vault (record_bundle).
static func pack_bundle(path: String, members: Dictionary, soul: Variant = null, prior_manifest: Variant = null, opts := {}) -> Dictionary:
	var refusal := check_spec_writable(prior_manifest)
	if refusal == "":
		refusal = check_spec_writable(opts.get("merged_with"))
	if refusal != "":
		return _fail("newer_spec", refusal)
	if not opts.get("manifest") is Dictionary:
		var decided := _write_spec(members, prior_manifest, opts)
		if decided["problem"] != "":
			return _fail("upgrade_needed", decided["problem"])
	var manifest: Dictionary = opts["manifest"] if opts.get("manifest") is Dictionary else build_manifest(members, soul, prior_manifest, opts)
	var manifest_bytes := json_text(manifest, "  ").to_utf8_buffer()
	var dir := path.get_base_dir()
	if dir != "" and not DirAccess.dir_exists_absolute(dir):
		DirAccess.make_dir_recursive_absolute(dir)
	var tmp := "%s.%s.tmp" % [path, Crypto.new().generate_random_bytes(4).hex_encode()]
	var zip := ZIPPacker.new()
	if zip.open(tmp) != OK:
		return _fail("cannot_write", "cannot open %s for writing" % tmp)
	var names: Array = ["manifest.json"]
	for name in _sorted(members.keys()):
		if name != "manifest.json" and not name.ends_with("/"):
			names.append(name)
	var failed := ""
	var written := {}
	for name in names:
		var data: PackedByteArray = manifest_bytes if name == "manifest.json" else members[name]
		if zip.start_file(name.replace("\\", "/")) != OK or zip.write_file(data) != OK or zip.close_file() != OK:
			failed = name
			break
		written[name.replace("\\", "/")] = data
	zip.close()
	# Both states land in the backup vault: the file being replaced, whoever
	# wrote it, and the one written (opts.backup_event, default "write").
	if failed == "" and FileAccess.file_exists(path):
		var recorded := record_bundle(path, "replaced", str(opts.get("app", "")))
		if recorded == "" and str(opts.get("upgrade_to", "")) != "" and not _keep_before_upgrade(path, str(opts["upgrade_to"])):
			failed = "a copy of the file from before the upgrade"
	if failed != "" or DirAccess.rename_absolute(tmp, path) != OK:
		DirAccess.remove_absolute(tmp)
		return _fail("cannot_write", "could not write %s" % (failed if failed != "" else path))
	record_bundle(path, str(opts.get("backup_event", "write")), str(opts.get("app", "")), written)
	return {"ok": true, "manifest": manifest}


# --------------------------------------------------------------------------- #
# Strict reader (shardcore/document.py read_bundle_document)
# --------------------------------------------------------------------------- #

## Reads and verifies a bundle into memory. Every declared member is read and checked
## against its sha256 and size; JSON members must parse as strict UTF-8. Rejects duplicate,
## unsafe or undeclared member names, a missing soul, size caps, and a spec major above
## SUPPORTED_MAJOR (code future_spec). Returns {"ok": true, "manifest", "members" (name to
## bytes, manifest excluded), "manifest_sha256"} or a failure with document.py's code.
## opts, as read_bundle_document's keywords: require_schemas (default true) and
## reject_undeclared (default true). A writer about to resave a bundle passes
## require_schemas false: a missing schema id is drift its next save repairs, not tampering.
## shortcut: ZIPReader exposes no entry sizes before reading, so the member and total caps
## are checked as each member is read; the 64 MB compressed cap bounds a hostile archive.
static func read_bundle(path: String, opts := {}) -> Dictionary:
	if not FileAccess.file_exists(path):
		return _fail("cannot_stat", "no bundle at %s" % path)
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return _fail("cannot_read", "cannot open %s" % path)
	var length := f.get_length()
	f.close()
	if length > MAX_BUNDLE_BYTES:
		return _fail("bundle_size", "bundle exceeds compressed size cap")
	var zip := ZIPReader.new()
	if zip.open(path) != OK:
		return _fail("bad_zip", "bundle is not a valid ZIP archive")
	var names := []
	for name in zip.get_files():
		if not name.ends_with("/"):
			names.append(name)
	var seen := {}
	for name in names:
		if seen.has(name):
			zip.close()
			return _fail("duplicate_member", "duplicate archive member name: %s" % name, name)
		seen[name] = true
		var bad := member_name_error(name)
		if bad != "":
			zip.close()
			return _fail("invalid_member_name", bad, name)
	var raw := {}
	var total := 0
	for name in names:
		var data := zip.read_file(name)
		if data.size() > MAX_MEMBER_BYTES:
			zip.close()
			return _fail("member_size", "archive member exceeds size cap: %s" % name, name)
		total += data.size()
		if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
			zip.close()
			return _fail("total_size", "archive exceeds total uncompressed size cap")
		raw[name] = data
	zip.close()

	if not raw.has("manifest.json"):
		return _fail("missing_manifest", "bundle has no manifest.json")
	var parsed := parse_json(raw["manifest.json"], "manifest.json")
	if not parsed["ok"]:
		return parsed
	if not parsed["value"] is Dictionary:
		return _fail("manifest_type", "manifest.json is not a JSON object")
	var manifest: Dictionary = parsed["value"]
	var spec: Variant = manifest.get("spec_version")
	if not spec is String or _spec_version.search(spec) == null:
		return _fail("spec_version", "manifest.spec_version is missing or invalid")
	if spec_major(manifest) > SUPPORTED_MAJOR:
		return _fail("future_spec", "bundle spec_version %s exceeds supported major %d" % [spec, SUPPORTED_MAJOR])
	var shard_name: Variant = manifest.get("shard_name")
	if not shard_name is String or shard_name.strip_edges() == "":
		return _fail("shard_name", "manifest.shard_name is missing or empty")
	var files: Variant = manifest.get("files")
	if not files is Dictionary:
		return _fail("files_type", "manifest.files is not a JSON object")
	if files.has("manifest.json"):
		return _fail("manifest_self_listed", "manifest.json cannot list itself")
	for name in _sorted(files.keys()):
		if not raw.has(name):
			return _fail("missing_member", "manifest lists an absent member: %s" % name, name)
	for name in _sorted(raw.keys()):
		if bool(opts.get("reject_undeclared", true)) and name != "manifest.json" and not files.has(name):
			return _fail("undeclared_member", "archive contains an undeclared member: %s" % name, name)
	if not files.has("soulshard.json"):
		return _fail("missing_soul", "manifest does not list soulshard.json")
	for name in files:
		var bad := member_name_error(name)
		if bad != "":
			return _fail("invalid_member_name", bad, name)
		var entry: Variant = files[name]
		if not entry is Dictionary:
			return _fail("file_entry_type", "manifest file entry is not an object: %s" % name, name)
		var sha: Variant = entry.get("sha256")
		if not sha is String or _sha256_hex.search(sha) == null:
			return _fail("file_hash", "manifest file entry has an invalid SHA-256: %s" % name, name)
		var size: Variant = entry.get("size")
		if not (size is int or (size is float and size == floorf(size))) or size < 0:
			return _fail("file_size", "manifest file entry has an invalid size: %s" % name, name)
		var schema: Variant = entry.get("schema")
		if bool(opts.get("require_schemas", true)) and (not schema is String or schema.strip_edges() == ""):
			return _fail("file_schema", "manifest file entry has no schema: %s" % name, name)
		var data: PackedByteArray = raw[name]
		if data.size() != int(size):
			return _fail("size_mismatch", "member size does not match manifest: %s" % name, name)
		if sha256_hex(data) != sha:
			return _fail("hash_mismatch", "member SHA-256 does not match manifest: %s" % name, name)
		if name.ends_with(".json"):
			var member := parse_json(data, name)
			if not member["ok"]:
				member["member"] = name
				return member
	raw.erase("manifest.json")
	return {"ok": true, "manifest": manifest, "members": raw, "manifest_sha256": manifest_digest(manifest)}


## Why name is ambiguous, absolute or unsafe as an archive path, or "" when it is fine.
static func member_name_error(name: String) -> String:
	if name == "" or name.contains("\\"):
		return "invalid archive member name: %s" % name
	for i in name.length():
		if name.unicode_at(i) == 0:
			return "invalid archive member name: %s" % name
	if name.begins_with("/") or name.ends_with("/"):
		return "invalid archive member name: %s" % name
	for part in name.split("/"):
		if part == "" or part == "." or part == "..":
			return "invalid archive member name: %s" % name
	return ""


# --------------------------------------------------------------------------- #
# Version and write guards
# --------------------------------------------------------------------------- #

## The spec major of a manifest, reading spec_version then bundle_version; 1 when neither
## parses (a version-less legacy bundle predates any 2.x).
static func spec_major(manifest: Dictionary) -> int:
	for key in ["spec_version", "bundle_version"]:
		var value: Variant = manifest.get(key)
		if value is String and value.strip_edges() != "":
			var head: String = String(value).strip_edges().split(".")[0]
			if head.is_valid_int():
				return int(head)
	return 1


## A version string as integers, compared per component (spec section 3): "1.10" is
## [1, 10], after "1.9". [] for anything that is not dotted digits.
static func version_tuple(value: Variant) -> Array:
	if not (value is String or value is StringName) or _version_text.search(String(value).strip_edges()) == null:
		return []
	var out := []
	for part in String(value).strip_edges().split("."):
		out.append(int(part))
	return out


## Why this writer may not save the bundle, or "" when it may. Reading it is fine.
## manifest.min_writer names the oldest spec whose writers can save it without breaking
## it: below that this one refuses, whatever spec_version says. A bundle newer than
## SPEC_VERSION that names no floor is refused too.
static func check_spec_writable(manifest: Variant) -> String:
	if not manifest is Dictionary:
		return ""
	var declared_text := _declared_spec(manifest)
	var declared := version_tuple(declared_text)
	var floor_text := min_writer(manifest)
	var written := version_tuple(SPEC_VERSION)
	var why := ""
	if _version_less(written, version_tuple(floor_text)):
		why = "bundle needs a writer of spec %s or later" % floor_text
	elif _version_less(written, declared) and (floor_text == "" or declared[0] > SUPPORTED_MAJOR):
		why = "bundle spec_version %s is newer than this writer's" % declared_text
	if why == "":
		return ""
	return "%s; this one implements %s and will not rewrite it. Update the vendored shardcore.gd (shardcore: tools/ecosystem/ecosystem.py sync)." % [why, SPEC_VERSION]


static func is_immutable(manifest: Dictionary) -> bool:
	return bool(manifest.get("immutable", false))


## Why an in-place write of this manifest's bundle is refused (it is immutable), or "".
## An immutable shard is branched to a new file instead, with branch_manifest(parent).
static func writable_error(manifest: Variant) -> String:
	if manifest is Dictionary and is_immutable(manifest):
		return "bundle is marked immutable; refuse in-place write"
	return ""


static func _version_less(a: Array, b: Array) -> bool:
	for i in mini(a.size(), b.size()):
		if a[i] != b[i]:
			return a[i] < b[i]
	return a.size() < b.size()


static func _sorted(values: Array) -> Array:
	var out := []
	for v in values:
		out.append(String(v))
	out.sort()
	return out


static func _fail(code: String, message: String, member := "") -> Dictionary:
	var out := {"ok": false, "code": code, "error": message}
	if member != "":
		out["member"] = member
	return out
