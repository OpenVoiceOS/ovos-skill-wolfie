"""A blacklist line must not suppress a request the intent is built for.

Engines compare a blacklist line with the utterance under their own
normalisation: padacioso folds accents on both sides, m2v compares exact word
sequences. A line passes only when neither engine suppresses these requests.
"""
from pathlib import Path

import pytest
from ovos_m2v_pipeline import _word_sequence
from ovos_spec_tools.resources import LocaleResources
from padacioso import IntentContainer

LOCALE_DIR = Path(__file__).parents[2] / "ovos_skill_wolfie" / "locale"
RESOURCES = LocaleResources(str(LOCALE_DIR))
INTENT = "search_wolfie"

ROWS = [
    ("ca-ES", "què diu es llop sobre la lluna"),
    ("ca-ES", "pregunta al llop com es diu la capital de frança"),
    ("ca-ES", "pregunta al llop quina és la capital de frança"),
    ("ca-ES", "pregunta al llop quants habitants té barcelona"),
    ("sv-SE", "fråga wolfram vilket år det var"),
    ("sv-SE", "fråga wolfram om månen"),
]


def _padacioso_label(lang, utterance):
    container = IntentContainer()
    container.add_intent(INTENT, RESOURCES.load_intent(INTENT, lang))
    container.exclude_keywords(INTENT, RESOURCES.load_blacklist(INTENT, lang))
    return container.calc_intent(utterance)["name"]


def _m2v_suppressed(lang, utterance):
    words = f" {_word_sequence(utterance)} "
    phrases = (_word_sequence(p) for p in RESOURCES.load_blacklist(INTENT, lang))
    return any(f" {p} " in words for p in phrases if p)


@pytest.mark.parametrize("lang,utterance", ROWS)
def test_padacioso_matches_the_request(lang, utterance):
    assert _padacioso_label(lang, utterance) == INTENT


@pytest.mark.parametrize("lang,utterance", ROWS)
def test_m2v_does_not_suppress_the_request(lang, utterance):
    assert not _m2v_suppressed(lang, utterance)


def test_sv_line_still_blocks_a_yes_no_question():
    assert _m2v_suppressed("sv-SE", "fråga wolfram är det farligt")
