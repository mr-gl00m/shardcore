"""The bridge between a conversation and a brain: what was said goes in, how the character is comes out."""

from __future__ import annotations

import json
import re

import pytest

from shardcore.brain import Brain, chat

SOUL = {
    "name": "Jarvis",
    "stat_block": {
        "STR": 3,
        "END": 7,
        "VIG": 5,
        "DEX": 6,
        "TMP": 3,
        "ACU": 9,
        "INS": 7,
        "ATT": 8,
        "CNV": 7,
        "PRS": 6,
    },
}
MIND = {
    "core": [
        {
            "entry_title": "The night the workshop flooded",
            "the_moment": "Cid stayed up until dawn with me saving the workshop drives. He trusted me.",
            "the_truth": "We are loyal to each other.",
        }
    ]
}
LINE = "Can you help me plan tomorrow in the workshop?"


def model_says(
    speaker: str = "Cid", frame: str = "Unstated", acted: bool = False, topics=(), **senses: float
) -> dict:
    """What read_perception makes of a well-formed model answer."""
    raw = {"senses": {name: senses.get(name, 0.0) for name in chat.EVENT_SENSES}, "frame": frame,
           "topics": list(topics), "acted": acted}  # fmt: skip
    return chat.read_perception(json.dumps(raw), speaker)


KIND = model_says(Kindness=0.9, Pleasure=0.4, topics=["thanks"])
CRUEL = model_says(Challenge=0.9, Pain=0.7, frame="Hostile", topics=["insult"])
SORRY = model_says(Kindness=0.8, topics=["apology"])
ASK = model_says(topics=["schedule"])


def after(*steps: tuple[dict, int]) -> Brain:
    brain = Brain.build(SOUL, MIND, 1)
    for perception, times in steps:
        for _ in range(times):
            chat.hear(brain, "", "Cid", perception)
            brain.rest(12)
    return brain


def asked(brain: Brain) -> str:
    return chat.stance(chat.hear(brain, LINE, "Cid", ASK, learn=False), "Jarvis", "Cid")


def test_the_request_asks_a_model_what_happened_and_not_how_it_feels() -> None:
    system, user, schema = chat.perception_request("You're useless.", "Dex", "Jarvis")
    assert user == "Dex says to Jarvis: You're useless."
    assert (
        "Do not guess how Jarvis will feel" in system
        and "Challenge" in system
        and "acted" in system
    )
    assert set(schema["properties"]["senses"]["required"]) == set(chat.EVENT_SENSES)
    assert schema["properties"]["frame"]["enum"] == ["Unstated", "Contest", "Wanted", "Hostile"]
    json.dumps(schema)


def test_a_models_answer_is_checked_clamped_and_weighed_as_words() -> None:
    raw = {"senses": {"Challenge": 3, "Pain": 0.8, "Threat": 0.6, "Kindness": 0.01, "Bogus": 1, "Foul": "yes"},
           "frame": "Hostile", "topics": ["Being Useless", "", 4, "being useless", "a", "b"], "acted": False}  # fmt: skip
    seen = chat.read_perception(raw, "Dex")
    assert seen["senses"] == {
        "Challenge": 1.0,
        "Pain": 0.4,
        "Threat": 0.3,
    }  # said, not done: half the hurt
    assert seen["frames"] == {"Hostile": 1.0}
    assert seen["cues"] == ("actor:dex", "topic:being_useless")  # three topics at most, no repeats
    assert chat.read_perception({**raw, "acted": True}, "Dex")["senses"]["Pain"] == 0.8
    assert chat.read_perception({**raw, "frame": "Sarcastic"}, "Dex")["frames"] == {}
    for bad in ("not json", "[]", '{"frame": "Hostile"}', {"senses": "lots"}):
        with pytest.raises(ValueError):
            chat.read_perception(bad, "Dex")


def test_without_a_model_the_words_are_read_and_read_as_said() -> None:
    seen = chat.perceive_words("He hits her and she cries for help", "Dex")
    assert seen["senses"] == {"Pain": 0.3, "Distress": 0.8} and seen["cues"] == ("actor:dex",)
    assert (
        chat.perceive_words("You're a useless pile of scrap.", "Dex")["senses"] == {}
    )  # what the table cannot see


def test_hearing_a_line_teaches_about_who_said_it_and_not_about_every_word() -> None:
    brain = after()
    before = json.dumps(brain.to_dict(), sort_keys=True)
    probe = chat.hear(
        brain,
        "You are a useless pile of scrap",
        "Dex",
        CRUEL | {"cues": ("actor:dex",)},
        learn=False,
    )
    assert json.dumps(brain.to_dict(), sort_keys=True) == before and probe.memory is None
    for _ in range(5):
        chat.hear(
            brain,
            "You are a useless pile of scrap",
            "Dex",
            CRUEL | {"cues": ("actor:dex", "topic:insult")},
        )
    assert set(brain.xp.assoc) == {"actor:dex", "topic:insult", "actor:dex+topic:insult"}
    assert brain.xp.assoc["actor:dex"]["Anger"][0] > 0.4
    assert not brain.xp.scar.get("actor:dex", 0.0) > 0.5  # five insults are not a trauma


def test_the_words_of_a_line_stir_memories() -> None:
    brain = after()
    stirred = chat.hear(brain, "Remember when the workshop flooded?", "Cid", ASK, learn=False)
    silent = chat.hear(brain, "What time is it?", "Cid", ASK, learn=False)
    assert [brain.nodes[i].label for i in stirred.recruited] == ["The night the workshop flooded"]
    assert not silent.recruited
    assert '"The night the workshop flooded"' in chat.stance(stirred, "Jarvis", "Cid")


def test_the_same_request_lands_differently_after_different_histories() -> None:
    fresh, warm, cold = asked(after()), asked(after((KIND, 30))), asked(after((CRUEL, 10)))
    assert len({fresh, warm, cold}) == 3
    assert "Inclined to lean in" in warm and "glad and trusting" in warm
    assert "Inclined to pull back" in cold or "Inclined to get out of the exchange" in cold
    assert "have come to make Jarvis" in cold and "afraid" in cold
    assert "does not owe politeness" not in warm
    assert asked(after((CRUEL, 10))) == cold  # the same history gives the same words


def test_a_repeat_offender_is_named_as_one() -> None:
    text = asked(after((CRUEL, 5), (SORRY, 6), (CRUEL, 5), (SORRY, 2)))
    assert "Cid has hurt Jarvis again after making up, 1 time." in text
    assert "An apology from Cid counts for less each time." in text


def test_the_state_text_assumes_no_pronouns_and_ends_with_the_instruction() -> None:
    for brain in (
        after(),
        after((KIND, 30)),
        after((CRUEL, 10)),
        after((CRUEL, 5), (SORRY, 6), (CRUEL, 5)),
    ):
        text = asked(brain)
        assert not re.search(r"\b(she|her|hers|he|him|his)\b", text, re.IGNORECASE), text
        assert (
            text.startswith("[Jarvis's state right now.")
            and "Write Jarvis's reply from inside this state." in text
        )
    stranger = chat.stance(
        chat.hear(after(), "hello", "Dex", model_says("Dex"), learn=False), "Jarvis", "Dex"
    )
    assert "Jarvis has never met Dex before." in stranger


def test_a_blow_in_a_scene_counts_in_full_and_a_sparring_match_is_not_an_attack() -> None:
    brain = after()
    said = chat.hear(brain, "", "Dex", model_says("Dex", Pain=0.9), learn=False)
    done = chat.hear(brain, "", "Dex", model_says("Dex", Pain=0.9, acted=True), learn=False)
    spar = chat.hear(
        brain, "", "Dex", model_says("Dex", Pain=0.9, acted=True, frame="Contest"), learn=False
    )
    assert said.sensed["Pain"] < done.sensed["Pain"]
    assert spar.sensed["Pain"] < 0.2 and "contest between rivals" in chat.stance(
        spar, "Jarvis", "Dex"
    )


def test_someone_her_memories_speak_of_is_not_a_stranger() -> None:
    brain = after()
    known = chat.hear(brain, "Good morning.", "Cid", model_says("Cid"), learn=False)
    unknown = chat.hear(brain, "Good morning.", "Dex", model_says("Dex"), learn=False)
    assert (
        "Novelty" not in known.sensed and "Familiar" not in known.sensed
    )  # not new, and not yet a habit
    assert unknown.sensed["Novelty"] > 0.9
    assert known.spikes("EMOTION", "Fear") < unknown.spikes("EMOTION", "Fear")
    assert "never met" not in chat.stance(known, "Jarvis", "Cid")
