"""m2v-multilingual candidate-default gate for ovos-skill-wolfie (en-US).

Boots the skill under the candidate default engine -- the m2v multilingual
classifier (``OpenVoiceOS/ovos-m2v-intents-multi-128M-v5``) via ovoscope's
``get_m2v_minicroft`` -- and replays the skill's own golden utterances for
its one explicit, classifier-routable intent, ``search_wolfie.intent``
(``golden_utterances.jsonl``). Padatious/padacioso stay the skill's
deterministic floor (see ``test_golden_utterances.py``); this gate
validates the candidate model that may replace them as the shipping
default. The fallback and common-query paths are not classifier-routed
(they run outside the intent pipeline) and are out of scope here.

``WolframAlphaSkill._get_answer`` -- the seam the existing golden suite
also patches -- is stubbed to a fixed answer instead of ``None``, so the
effect assertion checks that ``handle_search`` actually speaks the
retrieval result, not just that the intent routes.

Run:
    uv run pytest test/end2end/test_m2v_gate.py -v
"""
from unittest.mock import patch

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_m2v_minicroft

SKILL_ID = "ovos-skill-wolfie.openvoiceos"
LANG = "en-US"
STUBBED_ANSWER = "the speed of light is 299792458 meters per second"


def _fake_get_answer(self, utterance, lang):
    return STUBBED_ANSWER


# The skill's own golden utterances for its one classifier-routable intent.
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
    mc = get_m2v_minicroft(skill_ids=[SKILL_ID], lang=LANG)
    pipe = mc.intents.pipeline_plugins["ovos-m2v-pipeline"]
    pipe._ensure_model(background_ok=False)
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
