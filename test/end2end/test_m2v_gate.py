"""The search_wolfie handler speaks the answer on the m2v pipeline (en-US).

Boots the skill on the published m2v model with ovoscope's
``get_m2v_minicroft``, sends each utterance over the bus, and asserts both
routing (``ovos.intent.matched`` names this skill's ``search_wolfie``
intent) and effect (the spoken text carries the retrieval answer, not the
bare dialog name). ``test_golden_utterances.py`` gates how many golden rows
route; this test checks what the handler does once a row routes.

``WolframAlphaSkill._get_answer`` is stubbed to a fixed answer, so the
effect assertion does not depend on live Wolfram Alpha access. The fallback
and common query paths run outside the intent pipeline and are out of scope.
"""
from unittest.mock import patch

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import M2V_PUBLISHED_MODEL, CaptureSession, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-wolfie.openvoiceos"
LANG = "en-US"
STUBBED_ANSWER = "the speed of light is 299792458 meters per second"


def _fake_get_answer(self, utterance, lang):
    return STUBBED_ANSWER


# Phrasings that route to search_wolfie; the effect check needs a routed row.
ROWS = [
    {"utterance": "ask the wolf something", "intent_label": "search_wolfie"},
    {"utterance": "ask the wolfram about something", "intent_label": "search_wolfie"},
    {"utterance": "ask the wolfram alpha about something", "intent_label": "search_wolfie"},
    {"utterance": "search the wolf for something", "intent_label": "search_wolfie"},
    {"utterance": "search wolfram alpha for something", "intent_label": "search_wolfie"},
]


@pytest.fixture(scope="module")
def minicroft():
    p = patch.object(
        __import__("ovos_skill_wolfie").WolframAlphaSkill,
        "_get_answer",
        _fake_get_answer,
    )
    p.start()
    mc = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL, lang=LANG, classifier=False)
    warm_m2v_models(mc)
    yield mc
    mc.stop()
    p.stop()


def _capture(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc)
    capture.capture(utterance, timeout=30)
    return capture.finish()


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["utterance"])
def test_m2v_gate(minicroft, row):
    expected_intent = f"{SKILL_ID}:{row['intent_label']}"
    messages = _capture(minicroft, row["utterance"], f"m2v-{row['utterance']}")

    matched = [m for m in messages if m.msg_type == "ovos.intent.matched"]
    assert matched, (
        f"{row['utterance']!r}: expected ovos.intent.matched, got "
        f"{[m.msg_type for m in messages]!r}"
    )
    names = [m.data.get("intent_name") for m in matched]
    assert expected_intent in names, (
        f"{row['utterance']!r}: expected intent_name {expected_intent!r}, got {names!r}"
    )

    speaks = [m for m in messages if m.msg_type in ("speak", "ovos.utterance.speak")]
    assert speaks, f"{row['utterance']!r}: no speak message captured"
    spoken = speaks[0].data.get("utterance", "")
    assert STUBBED_ANSWER in spoken, (
        f"{row['utterance']!r}: stubbed Wolfram Alpha answer did not reach "
        f"speech: {spoken!r}"
    )
