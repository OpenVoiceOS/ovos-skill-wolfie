"""Every locale that ships the search intent anchors it with a `.required` file.

OVOS-INTENT-2 4.5: an intent is rejected when none of its required keywords
occurs in the utterance. The keywords here name the Wolfram Alpha service, so a
general question never reaches the search intent.
"""
import json
from pathlib import Path

import pytest
from ovos_spec_tools.resources import LocaleResources, required_keywords_reject

ROOT = Path(__file__).parents[2]
LOCALE_DIR = ROOT / "ovos_skill_wolfie" / "locale"
GOLDEN_DIR = ROOT / "test" / "end2end"
INTENT = "search_wolfie"
LANGS = sorted(p.parent.name for p in LOCALE_DIR.glob(f"*/{INTENT}.intent"))
RESOURCES = LocaleResources(str(LOCALE_DIR))


def _keywords(lang):
    return RESOURCES.load_required_keywords(INTENT, lang)


def test_the_intent_ships_in_locales():
    assert LANGS


@pytest.mark.parametrize("lang", LANGS)
def test_locale_has_a_required_file(lang):
    path = LOCALE_DIR / lang / f"{INTENT}.required"
    assert path.is_file(), f"{path} is missing"
    assert _keywords(lang)


@pytest.mark.parametrize("lang", LANGS)
def test_every_intent_sample_contains_a_keyword(lang):
    keywords = _keywords(lang)
    dead = [s for s in RESOURCES.load_intent(INTENT, lang)
            if required_keywords_reject(s, keywords)]
    assert not dead, f"samples the requirement rejects: {dead[:5]}"


@pytest.mark.parametrize("lang", LANGS)
def test_golden_positives_contain_a_keyword(lang):
    keywords = _keywords(lang)
    path = GOLDEN_DIR / f"golden_utterances_{lang}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    rejected = [r["utterance"] for r in rows
                if r["intent_label"] == INTENT
                and required_keywords_reject(r["utterance"], keywords)]
    assert not rejected, f"golden rows with no required keyword: {rejected}"


@pytest.mark.parametrize("lang", ["en-US"])
def test_general_question_is_rejected(lang):
    assert required_keywords_reject("how far away is the moon", _keywords(lang))
