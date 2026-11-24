from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from shardcore.brain import Brain, errors
from shardcore.brain.engine import SYN_MAX, SYN_MIN

FIXTURE = Path(__file__).parent / "brain_mara.json"


def load_shard(path: Path) -> tuple[dict, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["soul"], data["mind"]


# No instinct keywords here on purpose: these tests isolate memory and temperament.
# Add "asking for help" and the Distress instinct pulls her toward Comfort.
DAX = "Dax is at the door"
BLANK = {
    "name": "Blank",
    "stat_block": dict.fromkeys(
        ("STR", "END", "VIG", "DEX", "TMP", "ACU", "INS", "ATT", "CNV", "PRS"), 5
    ),
}


def blank(**stats: int) -> dict:
    soul = copy.deepcopy(BLANK)
    soul["stat_block"].update(stats)
    return soul


def impulse(soul: dict, stimulus: str, name: str, **needs: float) -> int:
    result = Brain.build(soul, {}, 0).deliberate(stimulus, learn=False, needs=needs)
    return dict(result.counts("IMPULSE"))[name]


def winners(soul: dict, mind: dict, seeds: range = range(4)) -> set[str | None]:
    return {Brain.build(soul, mind, s).deliberate(DAX, learn=False).winner for s in seeds}


def test_same_seed_same_trajectory() -> None:
    soul, mind = load_shard(FIXTURE)
    a = Brain.build(soul, mind, 3).deliberate(DAX)
    b = Brain.build(soul, mind, 3).deliberate(DAX)
    assert np.array_equal(a.trace, b.trace)
    assert np.array_equal(a.brain.engine.syn, b.brain.engine.syn)


def test_save_and_resume_matches_an_unbroken_run() -> None:
    # Same two moments on both sides; only one is saved and reloaded between them.
    soul, mind = load_shard(FIXTURE)
    straight = Brain.build(soul, mind, 5)
    straight.deliberate(DAX, ms=300)
    straight.deliberate(DAX, ms=300)

    first = Brain.build(soul, mind, 5)
    first.deliberate(DAX, ms=300)
    resumed = Brain.from_dict(json.loads(json.dumps(first.to_dict())), mind)
    resumed.deliberate(DAX, ms=300)

    assert np.array_equal(resumed.engine.spikes, straight.engine.spikes)
    assert np.array_equal(resumed.engine.syn, straight.engine.syn)
    assert np.array_equal(resumed.engine.v, straight.engine.v)
    assert resumed.xp.to_dict() == straight.xp.to_dict()


def test_rng_state_is_decimal_strings_and_the_document_round_trips_byte_for_byte() -> None:
    # Spec 8.10.4 and 8.10.7.1: 128-bit PCG64 values survive float-only JSON readers,
    # and loading then saving without stepping gives the same canonical bytes.
    soul, mind = load_shard(FIXTURE)
    brain = Brain.build(soul, mind, 7)
    brain.deliberate(DAX, ms=200)
    doc = brain.to_dict()
    rng = doc["state"]["rng"]
    assert rng["bit_generator"] == "PCG64"
    assert all(isinstance(rng["state"][key], str) for key in ("state", "inc"))
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    again = Brain.from_dict(json.loads(canonical), mind).to_dict()
    assert json.dumps(again, sort_keys=True, separators=(",", ":")) == canonical


def test_rng_state_written_as_numbers_before_1_12_still_loads() -> None:
    soul, mind = load_shard(FIXTURE)
    doc = Brain.build(soul, mind, 7).to_dict()
    inner = doc["state"]["rng"]["state"]
    doc["state"]["rng"]["state"] = {key: int(value) for key, value in inner.items()}
    assert Brain.from_dict(doc, mind).to_dict()["state"]["rng"]["state"] == inner


def test_the_stronger_memory_wins_and_fading_it_flips_the_outcome() -> None:
    soul, mind = load_shard(FIXTURE)
    assert winners(soul, mind) == {"Fight"}
    faded = copy.deepcopy(mind)
    faded["core"][1]["weight"] = 0.5  # "Dax sold the route"
    assert winners(soul, faded) == {"Approach"}


def test_temperament_changes_the_outcome_with_the_same_memories() -> None:
    soul, mind = load_shard(FIXTURE)
    gentle = copy.deepcopy(soul)
    gentle["stat_block"].update(TMP=2, ATT=10)
    assert "Fight" not in winners(gentle, mind)


def test_instinct_judges_a_stranger_with_no_memories_and_temperament_picks_the_side() -> None:
    stranger = "a stranger stands at the gate"
    for seed in range(4):
        wary = Brain.build(blank(ACU=3, INS=9), {}, seed).deliberate(stranger, learn=False)
        bold = Brain.build(blank(ACU=9, INS=2), {}, seed).deliberate(stranger, learn=False)
        assert wary.winner == "Flee"
        assert bold.winner == "Observe"


def test_hunger_sharpens_the_food_reflex_and_overrides_caution() -> None:
    bread = "warm bread on the table"
    fed, peckish, starving = (impulse(BLANK, bread, "Approach", hunger=h) for h in (0.0, 0.5, 1.0))
    assert fed < peckish < starving

    offer = "a stranger smiles and offers bread"
    wary = blank(ACU=3, INS=9)
    assert (
        Brain.build(wary, {}, 0).deliberate(offer, learn=False, needs={"hunger": 0.0}).winner
        == "Flee"
    )
    assert (
        Brain.build(wary, {}, 0).deliberate(offer, learn=False, needs={"hunger": 1.0}).winner
        == "Approach"
    )


def test_a_plea_for_help_contests_a_grudge() -> None:
    soul, mind = load_shard(FIXTURE)
    plain = Brain.build(soul, mind, 0).deliberate(DAX, learn=False)
    plea = Brain.build(soul, mind, 0).deliberate(DAX + " asking for help", learn=False)
    comfort = lambda r: dict(r.counts("IMPULSE"))["Comfort"]  # noqa: E731
    assert comfort(plea) > comfort(plain)
    assert plea.margin < plain.margin


def test_a_repeated_stranger_stops_being_frightening() -> None:
    brain = Brain.build(blank(ACU=3, INS=9), {}, 0)
    results = [brain.deliberate("a stranger stands at the gate") for _ in range(10)]
    flee = [dict(r.counts("IMPULSE"))["Flee"] for r in results]
    assert results[0].winner == "Flee"
    assert results[-1].winner != "Flee"
    assert flee[-1] < flee[0] / 2
    assert results[-1].sensed["Familiar"] > 0.9


def lived(soul: dict, stimulus: str, times: int) -> Brain:
    brain = Brain.build(soul, {}, 1)
    live(brain, stimulus, times)
    return brain


def live(brain: Brain, stimulus: str, times: int) -> None:
    # A day between moments, so tests of what she learned are not also tests of her mood.
    for _ in range(times):
        brain.deliberate(stimulus)
        brain.rest(24)


def reaction(brain: Brain, stimulus: str) -> str | None:
    return brain.deliberate(stimulus, learn=False).winner


def test_abuse_teaches_distrust_of_that_person_only() -> None:
    gate = "Dax stands at the gate"
    # A few blows stay about him. Enough of them spread to everyone; see the souring test.
    abused = lived(BLANK, "Dax hits her", 3)
    at_dax = abused.deliberate(gate, learn=False)
    at_ilse = abused.deliberate("Ilse stands at the gate", learn=False)
    assert at_dax.winner in {"Flee", "Withdraw"}
    assert at_dax.learned["Fear"] > 0.3 and not at_ilse.learned
    # A stranger is a close call between watching and leaving, so compare the fear, not the winner.
    assert at_dax.spikes("EMOTION", "Fear") > at_ilse.spikes("EMOTION", "Fear")
    assert reaction(lived(BLANK, gate, 10), gate) == "Approach"
    assert "Trust" not in abused.xp.assoc["dax"]


def test_temperament_shapes_what_abuse_teaches() -> None:
    gate = "Dax stands at the gate"
    assert reaction(lived(blank(TMP=9, INS=3), "Dax hits her", 10), gate) == "Fight"
    assert reaction(lived(blank(TMP=2, INS=8), "Dax hits her", 10), gate) in {"Flee", "Withdraw"}


def test_the_same_blow_means_what_her_history_made_it_mean() -> None:
    harsh = lived(BLANK, "Dax slaps her", 12)
    mixed = lived(BLANK, "Dax slaps her then kisses and caresses her, praising her", 12)
    assert reaction(harsh, "a slap") in {"Flee", "Withdraw"}
    assert reaction(mixed, "a slap") == "Approach"
    assert (
        mixed.xp.assoc["slap"]["Fear"][0] > 0.3
    )  # the fear was learned too; it is outvoted, not absent


def test_a_learned_fear_fades_to_about_half_and_stops() -> None:
    brain = lived(BLANK, "Dax hits her", 10)
    peak = brain.xp.assoc["dax"]["Fear"][0]
    live(brain, "Dax smiles and offers a gift", 60)
    fear = brain.xp.assoc["dax"]["Fear"][0]
    live(brain, "Dax smiles and offers a gift", 60)
    assert brain.xp.assoc["dax"]["Fear"][0] == fear  # it has stopped
    assert (
        peak / 2 <= fear < 0.6 * peak
    )  # a little above half: he read as hostile by the end, which scars
    assert brain.deliberate("Dax stands at the gate", learn=False).spikes("EMOTION", "Fear") > 10


def test_one_terrible_night_is_learned_at_once_and_never_fades() -> None:
    smell = "the smell of a cigar"
    brain = Brain.build(BLANK, {}, 1)
    live(brain, "a man with a cigar lunges at her with a knife and attacks, blood everywhere", 1)
    assert brain.xp.assoc["cigar"]["Fear"][0] > 0.95 and brain.xp.scar["cigar"] == 1.0
    live(brain, smell, 60)
    assert brain.xp.assoc["cigar"]["Fear"][0] > 0.95
    assert reaction(Brain.from_dict(brain.to_dict(), {}), smell) in {"Flee", "Withdraw", "Fight"}


def test_one_smell_means_what_her_history_made_it_mean() -> None:
    smell = "the smell of a cigar"
    loved = lived(BLANK, "grandfather smokes his cigar and hugs her, smiling and gentle", 20)
    feared = lived(BLANK, "Dex smokes a cigar and beats her, furious and cruel", 20)
    assert reaction(Brain.build(BLANK, {}, 1), smell) == "Observe"
    assert reaction(loved, smell) == "Approach" and reaction(feared, smell) in {"Flee", "Withdraw"}
    assert loved.deliberate(smell, learn=False).reminded["grandfather"] > 0.9


def test_a_thing_brought_to_mind_recalls_memories_about_it() -> None:
    soul, mind = load_shard(FIXTURE)
    mind = copy.deepcopy(mind)
    mind["core"].append(
        {
            "entry_title": "Grandfather on the porch",
            "weight": 1.0,
            "the_moment": "Grandfather was the one person I trusted.",
        }
    )
    brain = Brain.build(soul, mind, 1)
    smell = "the smell of a cigar"
    assert not brain.deliberate(smell, learn=False).recruited
    live(brain, "grandfather smokes his cigar and hugs her", 5)
    recalled = [brain.nodes[i].label for i in brain.deliberate(smell, learn=False).recruited]
    assert recalled == ["Grandfather on the porch"]


def test_a_blow_means_something_different_from_each_person() -> None:
    brain = Brain.build(BLANK, {}, 1)
    for _ in range(12):
        live(brain, "Dax slaps her then kisses and caresses her, praising her", 1)
        live(brain, "Rolf slaps her", 1)
    assert reaction(brain, "Dax slaps her") == "Approach"
    assert reaction(brain, "Rolf slaps her") in {"Withdraw", "Flee", "Fight"}
    assert brain.xp.assoc["dax+slap"]["Joy"][0] > 0.7
    assert "Joy" not in brain.xp.assoc["rolf+slap"]


def test_harm_from_many_people_layers() -> None:
    def fear_of_a_newcomer(people: tuple[str, ...]) -> int:
        brain = Brain.build(BLANK, {}, 1)
        for _ in range(3):
            for who in people:
                live(brain, f"{who} hits her", 1)
        return dict(brain.deliberate("Tov hits her", learn=False).counts("EMOTION"))["Fear"]

    assert fear_of_a_newcomer(("Dax", "Rolf", "Ilse", "Marn")) > fear_of_a_newcomer(("Dax",))


def test_forgiveness_wears_out_with_each_betrayal() -> None:
    brain = Brain.build(BLANK, {}, 1)
    trust, faded = [], []
    for _ in range(4):
        live(brain, "Dax hits her", 3)
        before = brain.xp.assoc["dax"]["Fear"][0]
        live(brain, "Dax smiles and offers a gift", 15)
        faded.append(before - brain.xp.assoc["dax"]["Fear"][0])
        trust.append(brain.xp.assoc["dax"].get("Trust", (0.0, 0.0))[0])
    assert brain.xp.grudge["dax"][0] == 3
    assert trust == sorted(trust, reverse=True) and trust[-1] < trust[0] / 4
    assert faded == sorted(faded, reverse=True) and faded[-1] < faded[0] / 4
    assert reaction(Brain.from_dict(brain.to_dict(), {}), "Dax stands at the gate") != "Approach"


def test_mood_carries_over_and_drains_with_rest() -> None:
    brain = Brain.build(BLANK, {}, 1)
    for _ in range(3):
        brain.deliberate("a man lunges at her with a knife")
    offer = "Ilse smiles and offers bread"
    shaken = dict(brain.deliberate(offer, learn=False).counts("EMOTION"))["Fear"]
    assert brain.xp.mood["Fear"] > 0.5
    brain.rest(48)
    assert not brain.xp.mood
    assert dict(brain.deliberate(offer, learn=False).counts("EMOTION"))["Fear"] < shaken


def test_fatigue_and_feeling_unsafe_change_the_same_moment() -> None:
    stranger = "a stranger stands at the gate"
    brain = Brain.build(BLANK, {}, 0)
    assert brain.deliberate(stranger, learn=False).winner == "Observe"
    assert brain.deliberate(stranger, learn=False, needs={"fatigue": 1.0}).winner == "Withdraw"
    assert brain.deliberate(stranger, learn=False, needs={"unsafe": 1.0}).winner == "Flee"


def test_a_runtime_can_drive_it_with_identities_and_senses_and_no_words() -> None:
    brain = Brain.build(BLANK, {}, 1)
    for _ in range(6):
        brain.deliberate("", senses={"Pain": 1.0}, cues=("actor:dax",))
        brain.rest(24)
    assert brain.xp.conditioned({"actor:dax"})["Fear"] > 0.5
    assert not brain.xp.conditioned({"actor:ilse"})
    assert brain.deliberate("", cues=("actor:dax",), learn=False).winner in {
        "Flee",
        "Withdraw",
        "Fight",
    }


def test_the_same_beating_is_read_by_its_setting() -> None:
    def after_ten(stimulus: str, who: str) -> tuple[Brain, str | None]:
        brain = lived(BLANK, stimulus, 10)
        return brain, reaction(brain, f"{who} stands at the gate")

    rival, to_rival = after_ten("Akane beats her in the tournament match", "Akane")
    abuser, to_abuser = after_ten("Dex beats her, furious and cruel", "Dex")
    asked, to_asked = after_ten("she asks Dex to beat her", "Dex")

    assert to_rival == "Fight" and to_abuser in {"Flee", "Withdraw"} and to_asked == "Approach"
    assert rival.xp.distrust == 0.0 and asked.xp.distrust == 0.0 and abuser.xp.distrust > 0.15
    assert rival.xp.assoc["akane"]["Anger"][0] > rival.xp.assoc["akane"]["Fear"][0]
    assert abuser.xp.assoc["dex"]["Fear"][0] > 0.8
    assert asked.xp.assoc["dex"]["Trust"][0] > asked.xp.assoc["dex"].get("Fear", (0.0, 0.0))[0]


def test_an_unexplained_blow_is_read_through_what_she_believes_of_the_person() -> None:
    def pain_felt(history: str | None, times: int = 0) -> float:
        brain = lived(BLANK, history, times) if history else Brain.build(BLANK, {}, 1)
        return brain.deliberate("Ilse hits her", learn=False).sensed["Pain"]

    friend = pain_felt("Ilse smiles and offers a gift", 15)
    stranger = pain_felt(None)
    abuser = pain_felt("Ilse hits her, furious", 10)
    assert friend < stranger < abuser


def test_a_runtime_can_state_the_setting_outright() -> None:
    brain = Brain.build(BLANK, {}, 1)
    match = brain.deliberate(
        "", senses={"Pain": 1.0}, cues=("actor:akane",), frames={"Contest": 1.0}, learn=False
    )
    attack = brain.deliberate(
        "", senses={"Pain": 1.0}, cues=("actor:akane",), frames={"Hostile": 1.0}, learn=False
    )
    assert match.sensed["Pain"] < 0.2 < match.sensed["Challenge"]
    assert attack.sensed["Pain"] == 1.0 and attack.sensed["Threat"] > 0.4


def test_enough_abuse_from_one_person_sours_her_on_everyone() -> None:
    stranger, kindness = "a stranger stands at the gate", "Ilse smiles and offers a gift"
    brain = Brain.build(BLANK, {}, 1)
    assert reaction(brain, stranger) == "Observe" and reaction(brain, kindness) == "Approach"
    live(brain, "Dex beats her, furious and cruel", 50)
    assert brain.xp.distrust > 0.9
    assert reaction(brain, stranger) == "Flee" and reaction(brain, kindness) == "Flee"
    live(brain, kindness, 40)
    assert 0.4 < brain.xp.distrust < 0.9  # kindness gives some of it back, slowly
    assert reaction(Brain.from_dict(brain.to_dict(), {}), stranger) == "Flee"


def test_an_unfed_habit_nags_and_dulls_other_pleasures() -> None:
    def approach(brain: Brain, stimulus: str) -> int:
        return brain.deliberate(stimulus, learn=False).spikes("IMPULSE", "Approach")

    kindness, pudding = "Ilse smiles and offers a gift", "pudding on the table"
    likes = lived(BLANK, "she eats sweet pudding", 10)
    brain = Brain.build(BLANK, {}, 1)
    for _ in range(80):
        brain.deliberate("she eats sweet pudding")
        brain.rest(6)
    brain.deliberate("she eats sweet pudding")  # and one just now, so "fed" means fed
    (habit,) = brain.present("pudding")
    assert brain.xp.habit[habit][0] > 0.9
    fed = approach(brain, kindness)
    brain.rest(48)
    starved = brain.deliberate(kindness, learn=False)
    assert starved.reading["craving"] > 0.9
    assert starved.spikes("IMPULSE", "Approach") < fed
    assert starved.spikes("EMOTION", "Anger") > 5
    assert approach(brain, pudding) > approach(
        likes, pudding
    )  # dependence pulls harder than liking
    assert "craving" not in brain.deliberate(pudding, learn=False).reading  # it is in front of her


def test_an_authored_taste_can_be_previewed_and_behaves_like_an_earned_one() -> None:
    brain = Brain.build(BLANK, {}, 1)
    before = brain.deliberate("Ilse sucks her toes", learn=False)
    brain.imprint("sucks toes", {"Joy": 0.9, "Trust": 0.4})
    after = brain.deliberate("Ilse sucks her toes", learn=False)

    joy = lambda r: dict(r.counts("EMOTION"))["Joy"]  # noqa: E731
    assert joy(before) == 0 and joy(after) > 20 and after.winner == "Approach"
    assert any(line.startswith("suck+toe") for line in brain.xp.describe())
    assert Brain.from_dict(brain.to_dict(), {}).xp.assoc == brain.xp.assoc

    for _ in range(80):  # met again and again with nothing in it for her
        brain.deliberate("Ilse sucks her toes")
        brain.rest(24)
    assert (
        abs(brain.xp.assoc["suck+toe"]["Joy"][0] - 0.45) < 0.01
    )  # fades to half what was authored, no further


def test_learning_strengthens_the_recruited_path_and_stays_in_bounds() -> None:
    soul, mind = load_shard(FIXTURE)
    brain = Brain.build(soul, mind, 1)
    eng = brain.engine
    before = eng.syn.copy()
    for _ in range(3):
        brain.deliberate(DAX)
    betrayal = next(i for i, n in enumerate(brain.nodes) if n.label == "Dax sold the route")
    anger = brain.index["EMOTION", "Anger"]
    assert eng.syn[betrayal, anger] > before[betrayal, anger]
    assert np.array_equal(eng.syn[~eng.plastic], before[~eng.plastic])
    plastic = eng.syn[eng.plastic]
    assert plastic.min() >= SYN_MIN and plastic.max() <= SYN_MAX


def test_a_probe_changes_nothing_and_repeats_exactly() -> None:
    brain = lived(BLANK, "Dax hits her", 3)
    before = json.dumps(brain.to_dict(), sort_keys=True)
    first = brain.deliberate("Dax stands at the gate", learn=False)
    second = brain.deliberate("Dax stands at the gate", learn=False)
    assert np.array_equal(first.trace, second.trace)
    assert json.dumps(brain.to_dict(), sort_keys=True) == before


def test_a_seeded_probe_shows_other_ways_the_moment_could_go() -> None:
    soul, mind = load_shard(FIXTURE)
    brain = Brain.build(soul, mind, 1)
    before = json.dumps(brain.to_dict(), sort_keys=True)
    torn = {
        brain.deliberate("Dax is at the door asking for help", learn=False, seed=s).winner
        for s in range(12)
    }
    sure = {brain.deliberate("Dax is at the door", learn=False, seed=s).winner for s in range(12)}
    assert len(torn) > 1 and sure == {"Fight"}
    assert json.dumps(brain.to_dict(), sort_keys=True) == before


def test_keywords_do_not_fire_on_lookalike_words() -> None:
    brain = Brain.build(BLANK, {}, 1)
    for stimulus in (
        "a huge crate begins to tip",
        "she painted the hull",
        "Sparkles rotates the sober sickle",
    ):
        assert brain.sense(stimulus) == {}, stimulus
    assert not brain.deliberate("Sparkles hits her", learn=False).reading  # not a sparring match
    assert set(brain.sense("he hugged her, begging, and she was hitting and slapped")) == {
        "Kindness",
        "Distress",
        "Pain",
    }
    assert (
        brain.present("Dax hits her")
        == brain.present("Dax hit her")
        == brain.present("Dax is hitting her")
    )


def test_one_shared_moment_does_not_silence_long_experience() -> None:
    brain = lived(BLANK, "Dax hits her", 10)
    alone = brain.deliberate("Dax", learn=False).learned["Fear"]
    live(brain, "Dax laughs by the well", 1)  # nothing happens; no pair is learned
    assert "dax+well" not in brain.xp.assoc
    live(brain, "Dax hits her by the well", 1)  # one eventful moment at the well
    at_well = brain.deliberate("Dax by the well", learn=False).learned["Fear"]
    assert at_well > 0.8 * alone  # a pair met once only half speaks for him


def test_bad_input_is_refused_with_a_reason() -> None:
    brain = Brain.build(BLANK, {}, 1)
    for kwargs in (
        {"senses": {"Hunger": 1.0}},
        {"frames": {"Play": 1.0}},
        {"needs": {"thirst": 1.0}},
        {"cues": ("a+b",)},
        {"seed": 3},
    ):
        with pytest.raises(ValueError):
            brain.deliberate("x", **kwargs)
    with pytest.raises(ValueError):
        brain.imprint("the", {"Joy": 0.5})  # nothing but a stopword
    with pytest.raises(ValueError):
        brain.imprint("cake", {"Glee": 0.5})
    data = brain.to_dict()
    data["state"]["v"] = data["state"]["v"][:-1]
    with pytest.raises(ValueError):
        Brain.from_dict(data, {})


# --- the pillar, body parts and memories -------------------------------------


def test_the_pillar_is_version_1_1_and_round_trips_exactly() -> None:
    brain = lived(BLANK, "Dax hits her", 3)
    doc = json.loads(json.dumps(brain.to_dict()))
    assert doc["version"] == "1.1" and errors(doc) == []
    again = Brain.from_dict(doc, {})
    assert json.dumps(again.to_dict(), sort_keys=True) == json.dumps(doc, sort_keys=True)
    assert np.array_equal(
        again.deliberate("Dax", learn=False).trace, brain.deliberate("Dax", learn=False).trace
    )


def test_a_pillar_without_state_or_experience_loads_at_rest() -> None:
    doc = Brain.build(BLANK, {}, 1).to_dict()
    del doc["state"], doc["experience"]
    assert errors(doc) == []
    assert (
        Brain.from_dict(doc).deliberate("a stranger stands at the gate", learn=False).winner
        == "Observe"
    )


def test_errors_names_what_is_wrong_with_a_pillar() -> None:
    doc = Brain.build(BLANK, {}, 1).to_dict()
    assert errors({"version": "1.0", "topology": {}}) == ["unsupported neuronshard version: '1.0'"]
    assert errors([1, 2]) == ["neuronshard.json is not an object"]
    bad = copy.deepcopy(doc)
    bad["nodes"][3]["kind"] = "SENSORY"
    bad["edges"][0]["syn"] = -4
    bad["edges"][1]["dst"] = 9999
    found = errors(bad)
    assert (
        any("node 3" in e for e in found)
        and any("edge 0" in e for e in found)
        and any("edge 1" in e for e in found)
    )
    gone = copy.deepcopy(doc)
    gone["nodes"] = [n for n in gone["nodes"] if n["label"] != "Fear"]
    assert any("Fear" in e or "id does not match" in e for e in errors(gone))


def test_a_soul_or_mind_in_odd_shapes_still_builds() -> None:
    soul = {"name": "Odd", "nature": "gentle", "stat_block": "n/a"}
    mind = {
        "core": "nope",
        "long_term": [],
        "short_term": {"slots": [None, 4, {"entry_title": "She betrayed me"}]},
        "archive": [{"weight": "heavy", "tags": [3, "fear"], "the_truth": "I was afraid"}],
    }
    brain = Brain.build(soul, mind, 1)
    assert errors(brain.to_dict()) == []
    assert sum(1 for n in brain.nodes if n.kind == "MEMORY") == 2
    assert errors(Brain.build({}, None, 1).to_dict()) == []


def test_a_body_part_drives_the_brain_in_millivolts_and_teaches_her() -> None:
    brain = Brain.build(BLANK, {}, 1)
    quiet = brain.deliberate("", learn=False)
    below = brain.deliberate(
        "", drive={"Joy": 2.0}, learn=False
    )  # well under the 7 mV a resting node needs
    above = brain.deliberate("", drive={"Joy": 12.0}, learn=False)
    held = brain.deliberate("Dax hits her", drive={"Fear": -30.0}, learn=False)
    free = brain.deliberate("Dax hits her", learn=False)
    assert quiet.spikes("EMOTION", "Joy") == below.spikes("EMOTION", "Joy") == 0
    assert above.spikes("EMOTION", "Joy") > 10 and above.winner == "Approach"
    assert (
        held.spikes("EMOTION", "Fear") < free.spikes("EMOTION", "Fear") / 2
    )  # a negative weight holds a node down
    assert brain.prepare(drive={"Ghost": 9.0}).unknown_drive == ["Ghost"]

    # Drive on a sense is that sense happening: she appraises it and learns the part.
    for _ in range(6):
        brain.deliberate("", drive={"Pleasure": 14.0}, cues=("part:toes_l", "actor:ilse"))
        brain.rest(24)
    assert brain.xp.assoc["part:toes_l"]["Joy"][0] > 0.5
    assert brain.deliberate("", cues=("part:toes_l",), learn=False).winner == "Approach"


def test_a_tool_can_add_a_sense_of_its_own() -> None:
    doc = Brain.build(BLANK, {}, 1).to_dict()
    arousal = len(doc["nodes"])
    doc["nodes"].append({"id": arousal, "label": "Arousal", "kind": "SENSE"})
    by = {(n["kind"], n["label"]): n["id"] for n in doc["nodes"]}
    doc["edges"] += [
        {"src": arousal, "dst": by["EMOTION", "Joy"], "syn": 110.0},
        {"src": arousal, "dst": by["IMPULSE", "Approach"], "syn": 60.0},
    ]
    doc.pop("state")  # one more node than the saved state covers
    assert errors(doc) == []
    brain = Brain.from_dict(doc)
    assert brain.deliberate("", senses={"Arousal": 1.0}, learn=False).winner == "Approach"
    assert brain.deliberate("", drive={"Arousal": 14.0}, learn=False).spikes("EMOTION", "Joy") > 10
    for _ in range(5):
        brain.deliberate("", senses={"Arousal": 1.0}, cues=("part:toes_l",))
    assert brain.xp.assoc["part:toes_l"]["Joy"][0] > 0.4  # her own wiring decides what it teaches


def test_strong_moments_come_back_as_memories_and_weak_ones_do_not() -> None:
    brain = Brain.build(BLANK, {}, 1)
    assert brain.deliberate("a stranger stands at the gate").memory is None
    assert brain.deliberate("Dax hits her", learn=False).memory is None  # a probe is not lived

    first = brain.deliberate(
        "a man with a cigar lunges at her with a knife and attacks, blood everywhere"
    ).memory
    assert (
        first["tags"][0] == "trauma"
        and first["suggested_tier"] == "core"
        and first["weight"] == 1.0
    )
    assert "cigar" in first["tags"] and first["the_moment"].startswith("a man with a cigar")
    assert set(first) == {
        "entry_title",
        "the_moment",
        "the_shift",
        "the_truth",
        "tags",
        "weight",
        "suggested_tier",
    }

    told = [brain.deliberate("Dex beats her, furious and cruel").memory for _ in range(12)]
    kept = [i + 1 for i, m in enumerate(told) if m]
    assert kept == [1, 3, 10]  # a pattern is remembered as a pattern
    assert "3 times" in told[2]["the_truth"] and told[0]["tags"][0] == "harm"

    good = (
        Brain.build(BLANK, {}, 1)
        .deliberate("grandfather hugs her, smiling and gentle, and kisses her brow")
        .memory
    )
    assert good["tags"][0] == "good" and good["suggested_tier"] == "short_term"


def test_a_memory_she_formed_is_recalled_once_it_is_in_her_mind() -> None:
    brain = Brain.build(BLANK, {}, 1)
    memory = brain.deliberate("Dex beats her, furious and cruel").memory
    mind = {"archive": [memory]}
    rebuilt = Brain.build(BLANK, mind, 1)
    assert [n.label for n in rebuilt.nodes if n.kind == "MEMORY"] == [memory["entry_title"]]
    assert rebuilt.deliberate("Dex is at the door", learn=False).recruited
