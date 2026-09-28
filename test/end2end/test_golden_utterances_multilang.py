"""Multilingual golden-utterance end-to-end coverage for ovos-skill-wolfie.

The skill has exactly one explicit-intent file (search_wolfie.intent);
it is also a FallbackSkill and registers common_query, both calling
``_get_answer``, which is monkeypatched to always return ``None`` for the
duration of the module (same as the existing en-US suite) so the golden
rows exercise the explicit padacioso intent match, not the fallback/
common_query paths, and so a live network call is never made.

Every locale that ships a search_wolfie.intent gets its own
golden_utterances_<lang>.jsonl, rows expanded directly from that locale's
own template lines, {query} filled with an obvious loanword (pizza / yoga).
pt-PT ships only one template line, so it gets 2 rows instead of 3 -- a
real, unfixed locale-coverage gap, not a suite defect.

One MiniCroft is booted per locale in turn (lang=<locale>, no
secondary_langs -- see ovos-skill-date-time/test/end2end/test_intents_it_it.py
on dev).
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-wolfie.openvoiceos"

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

END2END_DIR = Path(__file__).parent

LANGS = [
    "ca-ES", "da-DK", "de-DE", "es-ES", "eu-ES", "fr-FR", "gl-ES",
    "it-IT", "kab", "nl-NL", "pt-BR", "pt-PT", "sv-SE",
]


def _fake_get_answer(self, *args, **kwargs):
    return None


def _matches_intent(msg_type: str, skill_id: str, intent_label: str) -> bool:
    prefix = f"{skill_id}:"
    if not msg_type.startswith(prefix):
        return False
    observed = msg_type[len(prefix):]
    observed_base = observed.rsplit(".", 1)[0] if observed.endswith(".intent") else observed
    expected_base = intent_label.rsplit(".", 1)[0] if intent_label.endswith(".intent") else intent_label
    return observed_base == expected_base


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


ALL_ROWS = []
for _lang in LANGS:
    for _row in _load_rows(_lang):
        ALL_ROWS.append(_row)


def _as_param(row):
    tag = "tier2" if row.get("machine_generated") else "tier1"
    return pytest.param(row, id=f"{row['lang']}-{tag}-{row['intent_label']}-{row['utterance']}")


GOLDEN_ROWS = [_as_param(r) for r in ALL_ROWS]

_BOOTED = {}
_PATCHER_STARTED = False


@pytest.fixture(scope="module")
def mc_factory(request):
    global _PATCHER_STARTED
    if not _PATCHER_STARTED:
        p = patch.object(
            __import__("ovos_skill_wolfie").WolframAlphaSkill,
            "_get_answer",
            _fake_get_answer,
        )
        p.start()
        _PATCHER_STARTED = True
        request.addfinalizer(p.stop)

    def _get(lang):
        if lang not in _BOOTED:
            mc = get_minicroft([SKILL_ID], max_wait=150, lang=lang)
            _BOOTED[lang] = mc
            request.addfinalizer(mc.stop)
        return _BOOTED[lang]
    return _get


def _types(mc, text, lang, session_id):
    session = Session(session_id)
    session.lang = lang
    session.pipeline = list(_PIPELINE)
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
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
    return f"{row['lang']}-{row['intent_label']}-{row['utterance']}"


KNOWN_BUGS = {}


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance_multilang(mc_factory, row):
    mc = mc_factory(row["lang"])
    types = _types(mc, row["utterance"], row["lang"], f"golden-{_golden_id(row)}")
    matched = any(_matches_intent(t, SKILL_ID, row["intent_label"]) for t in types)
    bug_key = (row["lang"], row["utterance"])
    if bug_key in KNOWN_BUGS and not matched:
        pytest.xfail(reason=f"known-bug: {KNOWN_BUGS[bug_key]}")
    assert matched, (
        f"[{row['lang']}] {row['utterance']!r}: expected {SKILL_ID}:{row['intent_label']}, got {types!r}"
    )
