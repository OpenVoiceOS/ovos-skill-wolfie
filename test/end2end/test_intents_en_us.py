"""End-to-end coverage for the en-US Wolfram Alpha intent definitions.

A MiniCroft loads the real skill plugin, so the assertions exercise the same
resource loading and intent registration path used at runtime. Utterance
matching is checked against the trained Padacioso container the skill registers
its ``search_wolfie.intent`` samples into, which yields the intent name and the
extracted ``{query}`` slot deterministically.
"""
from unittest import TestCase

from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-wolfie.openvoiceos"
INTENT = f"{SKILL_ID}:search_wolfie.intent"
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

    def test_skill_loaded(self):
        self.assertIn(SKILL_ID, self.minicroft.plugin_skills)

    def test_intent_registered(self):
        self.assertIn(INTENT, self.container.intent_samples)

    def test_ask_wolfram_routes_to_search(self):
        match = self.container.calc_intent(
            "ask wolfram what is the speed of light"
        )
        self.assertEqual(match["name"], INTENT)
        self.assertEqual(match["entities"]["query"], "what is the speed of light")

    def test_according_to_wolfram_routes_to_search(self):
        match = self.container.calc_intent(
            "according to wolfram how tall is everest"
        )
        self.assertEqual(match["name"], INTENT)
        self.assertEqual(match["entities"]["query"], "how tall is everest")

    def test_blacklisted_utterance_is_gated(self):
        # ``handle_search`` is registered with voc_blacklist=["MiscBlacklist"];
        # a MiscBlacklist utterance is flagged so the query is never forwarded to
        # Wolfram Alpha, even though the intent samples would otherwise match it.
        blacklisted = "ask wolfram can you install skills"
        self.assertEqual(
            self.container.calc_intent(blacklisted)["name"], INTENT
        )
        self.assertTrue(
            self.skill.voc_match(blacklisted, "MiscBlacklist", lang=LANG)
        )
        self.assertFalse(
            self.skill.voc_match(
                "what is the speed of light", "MiscBlacklist", lang=LANG
            )
        )
