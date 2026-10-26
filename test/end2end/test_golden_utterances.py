"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row's utterance goes through that pipeline's high, medium and low tiers in
order, and the row passes when the first tier to match names its
``intent_label``. The engine embeds the utterance, so a row that no template
spells out word for word still matches when it means the same thing.

Each ``negative_utterances_<lang>.jsonl`` holds requests that belong to other
skills. On the same MiniCroft, none of them may match an intent of this skill,
except a claim listed in ``NEGATIVE_KNOWN_CLAIMS``.

Each locale must pass at least ``MIN_MATCH_RATE`` of its golden rows, and
every intent with rows in a locale must match at least
``MIN_MATCHED_ROWS_PER_INTENT`` of them. All rows run, including rows marked
``needs_manual`` or ``machine_generated``, and the test prints every row that
misses. A locale named in ``GOLDEN_LOCALE_GAPS`` may stay below the rate as an
xfail, down to a margin under its measured rate, but never below the
per-intent floor and never with an unlisted negative claim.

The fallback and common query handlers of this skill do not run here: the
test calls the m2v engine directly, so no Wolfram Alpha request is made.
"""
import json
from collections import Counter
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-wolfie.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
TIERS = ("high", "medium", "low")
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row.
MIN_MATCH_RATE = 0.8
# a high locale rate must not hide an intent that matches none of its rows
MIN_MATCHED_ROWS_PER_INTENT = 1
# Locales whose golden rows match below MIN_MATCH_RATE on the published m2v
# model with the intent lines the locale ships. Each entry is
# {lang: (lowest measured rate, reason)}. Such a locale still fails when an
# intent has no matched row, and when its rate falls more than GAP_MARGIN below
# the measured rate. Between those bounds the rate check is an xfail.
GOLDEN_LOCALE_GAPS = {
    "ca-ES": (0.75, "9 of 12 rows match in each of three runs with the shipped lines only"),
    "da-DK": (0.75, "9 of 12 rows match in each of three runs with the shipped lines only"),
    "es-CO": (0.75, "9 of 12 rows match in each of three runs with the shipped lines only"),
    "es-ES": (0.583, "7 of 12 rows match in each of three runs with the shipped lines only"),
    "eu-ES": (0.667, "8 of 12 rows match in each of three runs with the shipped lines only"),
    "fa-IR": (0.333, "4 of 12 rows match in each of three runs with the shipped lines only"),
    "fr-FR": (0.75, "9 of 12 rows match in each of three runs with the shipped lines only"),
    "gl-ES": (0.75, "9 of 12 rows match in each of three runs with the shipped lines only"),
    "it-IT": (0.75, "9 of 12 rows match in each of three runs with the shipped lines only"),
    "nl-NL": (0.75, "9 of 12 rows match in each of three runs with the shipped lines only"),
    "pl-PL": (0.667, "8 of 12 rows match in each of three runs with the shipped lines only"),
    "ru-RU": (0.583, "7 of 12 rows match in each of three runs with the shipped lines only"),
}
GAP_MARGIN = 0.10
# negative rows that m2v claims in repeated runs: {lang: {utterance: intent}}
NEGATIVE_KNOWN_CLAIMS = {}
END2END_DIR = Path(__file__).parent
LOCALE_ROOT = END2END_DIR.parents[1] / "ovos_skill_wolfie" / "locale"


def _rows_by_lang(prefix):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}_*.jsonl")):
        lang = path.stem.removeprefix(f"{prefix}_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang("golden_utterances")
NEGATIVES = _rows_by_lang("negative_utterances")


def _matched_intent(engine, utterance, lang):
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    match = next(filter(None, (getattr(engine, f"match_{tier}")([utterance], lang, message)
                               for tier in TIERS)), None)
    return match.match_type if match else None


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    try:
        warm_m2v_models(minicroft)
        engine = minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]
        misses = []
        matched = Counter()
        for row in ROWS[lang]:
            expected = f"{SKILL_ID}:{row['intent_label']}"
            got = _matched_intent(engine, row["utterance"], lang)
            if got == expected:
                matched[row["intent_label"]] += 1
            else:
                misses.append(f"{row['utterance']!r}: expected {row['intent_label']}, got {got}")
        known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
        claimed = []
        for row in NEGATIVES.get(lang, []):
            got = _matched_intent(engine, row["utterance"], lang)
            if (got and got.startswith(f"{SKILL_ID}:")
                    and got != f"{SKILL_ID}:{known.get(row['utterance'])}"):
                claimed.append(f"{row['utterance']!r}: claimed by {got}")
    finally:
        minicroft.stop()
    rate = 1 - len(misses) / len(ROWS[lang])
    print(f"[{lang}] {rate:.1%} of {len(ROWS[lang])} rows match", *misses, sep="\n  ")
    starved = sorted(label for label in {row["intent_label"] for row in ROWS[lang]}
                     if matched[label] < MIN_MATCHED_ROWS_PER_INTENT)
    assert not starved, (
        f"[{lang}] intents with fewer than {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    )
    if NEGATIVES.get(lang):
        print(f"[{lang}] {len(claimed)} of {len(NEGATIVES[lang])} negatives claimed",
              *claimed, sep="\n  ")
        assert not claimed, f"[{lang}] negatives claimed by this skill:\n  " + "\n  ".join(claimed)
    if lang in GOLDEN_LOCALE_GAPS:
        measured, reason = GOLDEN_LOCALE_GAPS[lang]
        assert rate >= measured - GAP_MARGIN, (
            f"[{lang}] {rate:.1%} of rows match, more than {GAP_MARGIN:.0%} below the "
            f"measured {measured:.1%}:\n  " + "\n  ".join(misses)
        )
        if rate < MIN_MATCH_RATE:
            pytest.xfail(f"[{lang}] {reason}")
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of rows match, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    shipping = {d.name for d in LOCALE_ROOT.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"
