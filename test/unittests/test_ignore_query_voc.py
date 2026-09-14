"""Regression coverage for ovos_skill_wolfie/locale/<lang>/ignore_query.voc.

Runs the shipped matcher verbatim: remove_accents_and_punct on both sides,
then the word-boundary regex `voc_match` applies at
ovos_workshop/skills/ovos.py:2620. Each shipped locale gets ordinary factual
questions that must NOT match (a Wolfram-worthy query) and the assistant
collocations that MUST match (the class the file exists to catch).

The file holds collocations, not single words. A single common word such as
"install", "skills" or "can you" refuses ordinary questions that contain it,
so every line names the assistant explicitly.
"""
import os
import re

import pytest
from ovos_utils.text_utils import remove_accents_and_punct

LOCALE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "ovos_skill_wolfie", "locale"
)

CASES = {
    "en-US": {
        "ordinary": [
            "can you tell me how tall the eiffel tower is",
            "how do i install an air conditioner",
            "what skills does a cat have",
            "is it going to rain in lisbon",
        ],
        "fillers": [
            "can you install this skill",
            "how do i install skills",
            "what are your skills",
        ],
    },
    "ca-ES": {
        "ordinary": [
            "pots dir-me la capital de franca",
            "com instal·lar un aire condicionat",
            "quines habilitats te un gat",
            "es aixo cert",
        ],
        "fillers": [
            "pots instal·lar aquesta skill",
            "com instal·lar skills",
            "quines son les teves habilitats",
        ],
    },
    "da-DK": {
        "ordinary": [
            "kan du fortælle mig hovedstaden i frankrig",
            "hvordan installerer man et klimaanlæg",
            "hvilke færdigheder har en kat",
            "er det rigtigt",
        ],
        "fillers": [
            "kan du installere denne skill",
            "hvordan installere skills",
            "hvad er dine færdigheder",
        ],
    },
    "de-DE": {
        "ordinary": [
            "kannst du mir die hauptstadt von frankreich sagen",
            "wie installiere ich eine klimaanlage",
            "welche fahigkeiten hat eine katze",
            "ist es morgen kalt",
        ],
        "fillers": [
            "kannst du diese skill installieren",
            "wie kann ich skills installieren",
            "was sind deine fahigkeiten",
        ],
    },
    "es-ES": {
        "ordinary": [
            "puedes decirme la capital de francia",
            "como instalar un aire acondicionado",
            "que habilidades tiene un gato",
            "que es eso",
        ],
        "fillers": [
            "puedes instalar esta skill",
            "como instalar skills",
            "cuales son tus habilidades",
        ],
    },
    "eu-ES": {
        "ordinary": [
            "esan ahal duzu frantziako hiriburua",
            "nola instalatu aire girogailu bat",
            "zer trebetasun ditu katu batek",
            "hori al da erantzuna",
        ],
        "fillers": [
            "skill hau instalatu ahal duzu",
            "nola instalatu dezakezu skill bat",
            "zein dira zure trebetasunak",
        ],
    },
    "fr-FR": {
        "ordinary": [
            "peux-tu me dire la capitale de la france",
            "comment installer une climatisation",
            "quelles competences a un chat",
            "c'est ca la reponse",
        ],
        "fillers": [
            "peux-tu installer cette skill",
            "comment installer des skills",
            "quelles sont tes competences",
        ],
    },
    "gl-ES": {
        "ordinary": [
            "podes dicirme a capital de franza",
            "como instalar un aire acondicionado",
            "cales son as habilidades dun gato",
            "isto e grande",
        ],
        "fillers": [
            "podes instalar esta skill",
            "como instalar skills",
            "cales son as tuas habilidades",
        ],
    },
    "it-IT": {
        "ordinary": [
            "puoi dirmi quanto e alta la torre eiffel",
            "come installare un condizionatore",
            "quali competenze ha un gatto",
            "lo sai che ore sono a tokyo",
        ],
        "fillers": [
            "puoi installare questa skill",
            "come installare skill nuove",
            "quali sono le tue competenze",
        ],
    },
    "nl-NL": {
        "ordinary": [
            "kun je me vertellen hoe hoog de eiffeltoren is",
            "hoe installeer je een airco",
            "welke vaardigheden heeft een kat",
            "is dat het antwoord",
        ],
        "fillers": [
            "kun je deze skill installeren",
            "hoe kan ik skills installeren",
            "wat zijn jouw vaardigheden",
        ],
    },
    "pt-BR": {
        "ordinary": [
            "voce pode me dizer a capital da franca",
            "como instalar um ar condicionado",
            "quais habilidades tem um gato",
            "isso e verdade",
        ],
        "fillers": [
            "voce pode instalar essa skill",
            "como instalar skills",
            "quais sao suas habilidades",
        ],
    },
    "pt-PT": {
        "ordinary": [
            "podes dizer-me a capital de franca",
            "como instalar um ar condicionado",
            "quais as habilidades de um gato",
            "isso e verdade",
        ],
        "fillers": [
            "podes instalar esta skill",
            "consegues instalar skills",
            "quais sao as tuas habilidades",
        ],
    },
    "sv-SE": {
        "ordinary": [
            "kan du beratta huvudstaden i frankrike",
            "hur installerar man en luftkonditionering",
            "vilka fardigheter har en katt",
            "ar det sant",
        ],
        "fillers": [
            "kan du installera denna skill",
            "hur installera skills",
            "vilka ar dina fardigheter",
        ],
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


def test_every_shipped_locale_is_covered():
    """A new locale file must come with its own cases."""
    shipped = {
        name
        for name in os.listdir(LOCALE_DIR)
        if os.path.isfile(os.path.join(LOCALE_DIR, name, "ignore_query.voc"))
    }
    assert shipped == set(CASES), (
        f"locales without cases: {sorted(shipped - set(CASES))}; "
        f"cases without a locale file: {sorted(set(CASES) - shipped)}"
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
def test_assistant_collocations_still_refused(locale):
    vocs = _load_voc(locale)
    for filler in CASES[locale]["fillers"]:
        assert _voc_match(filler, vocs), (
            f"{locale}: assistant-facing collocation no longer matched "
            f"ignore_query.voc: {filler!r}"
        )


@pytest.mark.parametrize("locale", sorted(CASES))
def test_no_single_word_lines(locale):
    """A one-word line is the defect class this file exists to keep out."""
    for line in _load_voc(locale):
        assert len(line.split()) > 1, (
            f"{locale}: single-word ignore_query.voc line refuses ordinary "
            f"questions: {line!r}"
        )
