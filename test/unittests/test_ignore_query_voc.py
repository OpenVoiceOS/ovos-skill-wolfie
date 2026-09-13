"""Regression coverage for ovos_skill_wolfie/locale/<lang>/ignore_query.voc.

Runs the shipped matcher verbatim: remove_accents_and_punct on both sides,
then the word-boundary regex `voc_match` applies at
ovos_workshop/skills/ovos.py:2620. Each locale gets three ordinary factual
questions that must NOT match (a Wolfram-worthy query) and one assistant
filler utterance that MUST match (the class the file exists to catch).
"""
import os
import re

import pytest
from ovos_utils.text_utils import remove_accents_and_punct

LOCALE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "ovos_skill_wolfie", "locale"
)

CASES = {
    "it-IT": {
        "ordinary": [
            "lo sai quanto e alta la torre eiffel",
            "che ore sono a tokyo",
            "quanti abitanti ha roma",
        ],
        "filler": "puoi installare questa skill",
    },
    "gl-ES": {
        "ordinary": [
            "isto e grande",
            "que hora e en toquio",
            "canto pesa a terra",
        ],
        "filler": "podes instalar esta skill",
    },
    "pt-PT": {
        "ordinary": [
            "isso e verdade",
            "quantos habitantes tem lisboa",
            "que horas sao em toquio",
        ],
        "filler": "você pode instalar esta skill",
    },
    "pt-BR": {
        "ordinary": [
            "isso e verdade",
            "quantos habitantes tem sao paulo",
            "que horas sao em toquio",
        ],
        "filler": "você pode instalar essa skill",
    },
    "es-ES": {
        "ordinary": [
            "que es eso",
            "cuantos habitantes tiene madrid",
            "que hora es en tokio",
        ],
        "filler": "puedes instalar esta skill",
    },
    "eu-ES": {
        "ordinary": [
            "hori al da erantzuna",
            "zenbat biztanle ditu madrilek",
            "zer ordu da tokion",
        ],
        "filler": "instalatu ahal duzu skill hau",
    },
    "fr-FR": {
        "ordinary": [
            "c'est ca la reponse",
            "combien d'habitants a paris",
            "quelle heure est-il a tokyo",
        ],
        "filler": "peux-tu installer cette skill",
    },
    "nl-NL": {
        "ordinary": [
            "is dat het antwoord",
            "hoeveel inwoners heeft amsterdam",
            "hoe laat is het in tokio",
        ],
        "filler": "kun je installeren deze skill",
    },
}


def _load_voc(locale):
    path = os.path.join(LOCALE_DIR, locale, "ignore_query.voc")
    with open(path, encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip()]


def _voc_match(utt, vocs):
    """Mirrors ovos_workshop.skills.ovos.OVOSSkill.voc_match at ovos.py:2620."""
    utt = remove_accents_and_punct(utt)
    vocs = [remove_accents_and_punct(v) for v in vocs]
    return any(
        re.match(r".*\b" + re.escape(v) + r"\b.*", utt, re.IGNORECASE)
        for v in vocs
    )


@pytest.mark.parametrize("locale", sorted(CASES))
def test_ordinary_questions_not_refused(locale):
    vocs = _load_voc(locale)
    for question in CASES[locale]["ordinary"]:
        assert not _voc_match(question, vocs), (
            f"{locale}: ordinary question wrongly matched ignore_query.voc: "
            f"{question!r}"
        )


@pytest.mark.parametrize("locale", sorted(CASES))
def test_assistant_filler_still_refused(locale):
    vocs = _load_voc(locale)
    filler = CASES[locale]["filler"]
    assert _voc_match(filler, vocs), (
        f"{locale}: assistant-facing filler no longer matched "
        f"ignore_query.voc: {filler!r}"
    )
