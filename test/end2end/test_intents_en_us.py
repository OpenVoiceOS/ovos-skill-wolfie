"""End-to-end coverage for the en-US Wolfram Alpha intent definitions.

A MiniCroft loads the real skill plugin, so the assertions exercise the same
resource loading and intent registration path used at runtime. Utterance
matching is checked against the trained Padacioso container the skill registers
its ``search_wolfie.intent`` samples into, which yields the intent name and the
extracted ``{query}`` slot deterministically.

The whole scenario lives in a single test so exactly one MiniCroft is booted:
concurrent MiniCroft instances share the on-disk GUI resource cache and would
race while syncing it.
"""
from unittest import TestCase

from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-wolfie.openvoiceos"
INTENT = f"{SKILL_ID}:search_wolfie"
LANG = "en-US"


class TestWolfieIntents(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])
        loader = cls.minicroft.plugin_skills[SKILL_ID]
        cls.skill = loader.instance
        cls.container = cls.minicroft.intents.pipeline_plugins[
            "ovos-padacioso-pipeline-plugin"
        ].containers[LANG]

    @classmethod
    def tearDownClass(cls):
        if cls.minicroft:
            cls.minicroft.stop()

    def test_en_us_wolfram_intents(self):
        self.assertIn(SKILL_ID, self.minicroft.plugin_skills)
        self.assertIn(INTENT, self.container.intent_samples)

        speed = self.container.calc_intent(
            "ask wolfram what is the speed of light"
        )
        self.assertEqual(speed["name"], INTENT)
        self.assertEqual(speed["entities"]["query"], "what is the speed of light")

        everest = self.container.calc_intent(
            "according to wolfram how tall is everest"
        )
        self.assertEqual(everest["name"], INTENT)
        self.assertEqual(everest["entities"]["query"], "how tall is everest")

        # handle_search is registered with voc_blacklist=["MiscBlacklist"]; a
        # MiscBlacklist utterance is flagged so the query is never forwarded to
        # Wolfram Alpha. The blacklist words ("install", "skills", "can you",
        # "is it") are themselves stripped as noise by the padacioso container,
        # so an utterance built from them does not padacioso-match the intent
        # in the first place; only the voc_match gate is exercised here.
        blacklisted = "ask wolfram can you install skills"
        self.assertTrue(
            self.skill.voc_match(blacklisted, "MiscBlacklist", lang=LANG)
        )
        self.assertFalse(
            self.skill.voc_match(
                "what is the speed of light", "MiscBlacklist", lang=LANG
            )
        )
