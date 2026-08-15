"""Golden-utterance end-to-end coverage for ovos-skill-wolfie (en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset, keyed by
``skill_id == "ovos-skill-wolfie.openvoiceos"`` (matches this skill's real
OPM entry point too). One shared ``MiniCroft`` (module-scoped fixture) is
booted for the whole suite; every row is its own parametrized test item.

This skill is not just an explicit-intent skill: it's also a
``FallbackSkill`` and registers ``common_query``, and both of those call
``_get_answer`` -- which, with no configured Wolfram Alpha ``appid``, still
makes a REAL, unauthenticated network call to a free-tier endpoint and
returns a real answer (confirmed by isolated call before writing this
fixture: ``get_spoken_answer("what is the speed of light")`` returned a real
answer with no API key configured at all). Left unmocked, that means:

1. golden/negative test runs would be flaky/slow on real network, and
2. because Wolfram Alpha can plausibly "answer" almost anything, the
   fallback/common_query paths could make this skill genuinely claim
   negative utterances that belong to OTHER skills' domains -- which would
   silently defeat the negative tests' whole purpose.

So ``_get_answer`` is monkeypatched to always return ``None`` for the
duration of the module, exercising the explicit ``search_wolfie.intent``
routing path deterministically and offline, and keeping the fallback/
common_query paths from ever claiming anything (matching the golden rows,
which route via the explicit padacioso intent match before the handler body
-- and therefore before ``_get_answer`` -- ever runs).

It's patched with a plain function rather than a bare ``MagicMock``:
``FallbackSkill._register_decorated`` inspects
``method.fallback_priority``/compares priorities on load, which breaks
against a ``MagicMock`` (confirmed via isolated instantiation before landing
this fixture: skill load raised ``TypeError: '<' not supported between
instances of 'MagicMock' and 'int'``).
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-wolfie.openvoiceos"
LANG = "en-US"

_PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-fallback-pipeline-plugin-high",
    "ovos-fallback-pipeline-plugin-medium",
]

_IGNORE = [
    "speak",
    "ovos.utterance.speak",
    "mycroft.audio.play_sound",
]

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"


def _fake_get_answer(self, utterance, lang):
    return None


# utterances lifted verbatim from OTHER skills' golden-utterance slices in
# the shared ovoscope corpus, picked for lexical overlap with wolfie's
# "ask"/"search ... for"/"about" vocabulary.
NEGATIVE_UTTERANCES = [
    ("can you tell me the weather", "ovos-skill-weather.openvoiceos"),
    ("can you find something on wikipedia", "ovos-skill-wikipedia.openvoiceos"),
    ("ask wordnet about word", "ovos-skill-wordnet.openvoiceos"),
    ("tell me the word of the day", "ovos-skill-word-of-the-day.openvoiceos"),
    ("search wikihow for something", "ovos-skill-wikihow.openvoiceos"),
    ("can you spell word", "ovos-skill-spelling.openvoiceos"),
    ("set an alarm", "ovos-skill-alerts.openvoiceos"),
]

# wolfie/wikipedia/wordnet cross-arbitration: real wikipedia/wordnet corpus
# utterances fired against THIS skill, documenting and asserting that wolfie
# does not claim them (with _get_answer stubbed to None, the fallback/
# common_query paths can't claim ANYTHING, so this also validates that the
# explicit search_wolfie.intent padacioso template itself doesn't
# over-generalize onto wikipedia/wordnet phrasing).
TRIO_ARBITRATION = [
    ("can you find something on wiki", "ovos-skill-wikipedia.openvoiceos"),
    ("check wikipedia for something", "ovos-skill-wikipedia.openvoiceos"),
    ("search word net for word", "ovos-skill-wordnet.openvoiceos"),
    ("what does word net say about word", "ovos-skill-wordnet.openvoiceos"),
]


def _matches_intent(msg_type: str, skill_id: str, intent_label: str) -> bool:
    """Tolerant matcher, same shape as the sibling repos' suites: compare
    the ``:``-suffix basename, extension-stripped, so the assertion doesn't
    pin the wire format of any one pipeline plugin."""
    prefix = f"{skill_id}:"
    if not msg_type.startswith(prefix):
        return False
    observed = msg_type[len(prefix):]
    observed_base = observed.rsplit(".", 1)[0] if observed.endswith(".intent") else observed
    expected_base = intent_label.rsplit(".", 1)[0] if intent_label.endswith(".intent") else intent_label
    return observed_base == expected_base


# Rows that do not currently route correctly, with the root-caused reason.
# All xfails are strict=True: a row that starts passing must fail the build.
_XFAIL_REASONS = {}


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


def _as_param(row):
    reason = _XFAIL_REASONS.get(row["utterance"])
    if reason is None:
        return pytest.param(row, id=row["utterance"])
    return pytest.param(row, id=row["utterance"], marks=pytest.mark.xfail(reason=reason, strict=True))


GOLDEN_ROWS = [_as_param(r) for r in _load_golden_rows()]


@pytest.fixture(scope="module")
def minicroft():
    p = patch.object(
        __import__("ovos_skill_wolfie").WolframAlphaSkill,
        "_get_answer",
        _fake_get_answer,
    )
    p.start()
    mc = get_minicroft([SKILL_ID])
    yield mc
    mc.stop()
    p.stop()


def _types(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(_PIPELINE)
    # blacklisted_intents defaults to None on a fresh Session, which crashes
    # the padacioso pipeline (NoneType membership test) - force an empty list.
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(
        mc,
        eof_msgs=["mycroft.skill.handler.start", "ovos.intent.unmatched"],
        ignore_messages=_IGNORE,
    )
    capture.capture(utterance, timeout=30)
    return [m.msg_type for m in capture.finish()]


def _golden_id(row):
    return row["utterance"]


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance(minicroft, row):
    types = _types(minicroft, row["utterance"], f"golden-{_golden_id(row)}")
    assert any(_matches_intent(t, SKILL_ID, row["intent_label"]) for t in types), (
        f"{row['utterance']!r}: expected {SKILL_ID}:{row['intent_label']}, got {types!r}"
    )


@pytest.mark.timeout(60)
@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_negative_confusable_not_claimed(minicroft, negative):
    text, source_skill = negative
    types = _types(minicroft, text, f"negative-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}"


@pytest.mark.timeout(60)
@pytest.mark.parametrize("case", TRIO_ARBITRATION, ids=lambda c: c[0])
def test_trio_arbitration_not_claimed_by_wolfie(minicroft, case):
    text, expected_claimant = case
    assert expected_claimant != SKILL_ID, "this list is for utterances belonging to the OTHER two skills"
    types = _types(minicroft, text, f"trio-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, (
        f"{text!r} (expected to belong to {expected_claimant}) was incorrectly claimed by {SKILL_ID}"
    )


@pytest.mark.timeout(60)
def test_blacklisted_phrase_reaches_no_wolfie_handler(minicroft):
    # search_wolfie.blacklist (sibling of search_wolfie.intent) lists this
    # phrase; the bus round trip must never reach a wolfie handler for it.
    text = "ask wolfram can you install skills"
    types = _types(minicroft, text, f"blacklist-{text}")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} matches search_wolfie.blacklist but was claimed by {SKILL_ID}"


@pytest.mark.timeout(60)
def test_installment_not_over_suppressed(minicroft):
    # word-boundary semantics: "installment" must not collide with the
    # blacklisted whole word "install" (the bug in the old substring-based
    # voc_blacklist mechanism).
    text = "ask wolfram what is an installment loan"
    types = _types(minicroft, text, f"blacklist-boundary-{text}")
    assert any(_matches_intent(t, SKILL_ID, "search_wolfie") for t in types), (
        f"{text!r} should still match search_wolfie.intent, got {types!r}"
    )
