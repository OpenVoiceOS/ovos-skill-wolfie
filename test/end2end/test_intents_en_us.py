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

        # search_wolfie.intent ships a sibling locale/en-US/search_wolfie.blacklist
        # (loaded natively by ovos-workshop's register_intent_file, no
        # voc_blacklist wiring needed). A blacklisted phrase excludes the
        # intent from padacioso matching entirely, so calc_intent returns no
        # match for it, while an unrelated query keeps matching.
        blacklisted = "ask wolfram can you install skills"
        self.assertIsNone(self.container.calc_intent(blacklisted)["name"])

        # "installment" must not collide with the "install" blacklist entry:
        # padacioso's exclude_keywords uses \b-bounded matching, so a single
        # blacklisted word only excludes on a whole-word hit.
        installment = self.container.calc_intent(
            "ask wolfram what is an installment loan"
        )
        self.assertEqual(installment["name"], INTENT)
        self.assertEqual(installment["entities"]["query"], "what is an installment loan")
