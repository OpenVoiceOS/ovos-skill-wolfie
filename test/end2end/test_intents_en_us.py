"""End-to-end coverage for the en-US Wolfram Alpha intent definitions.

A MiniCroft loads the real skill plugin, so the assertions exercise the same
resource loading and intent registration path used at runtime. A routed
request must carry the extracted ``{query}`` slot.

``WolframAlphaSkill._get_answer`` is stubbed, so the handler never calls the
Wolfram Alpha service.

One MiniCroft serves the whole class: concurrent MiniCroft instances share
the on-disk GUI resource cache and would race while syncing it.
"""
from unittest import TestCase
from unittest.mock import patch

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

from ovos_skill_wolfie import WolframAlphaSkill

SKILL_ID = "ovos-skill-wolfie.openvoiceos"
INTENT = f"{SKILL_ID}:search_wolfie"
LANG = "en-US"


class TestWolfieIntents(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.answer_patch = patch.object(WolframAlphaSkill, "_get_answer",
                                        lambda self, utterance, lang: "42")
        cls.answer_patch.start()
        cls.minicroft = get_prototype_minicroft([SKILL_ID], lang=LANG)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()
        cls.answer_patch.stop()

    def _messages(self, utterance):
        session = Session(f"e2e-wolfie-{abs(hash(utterance))}")
        session.lang = LANG
        session.pipeline = PIPELINE
        capture = CaptureSession(self.minicroft)
        capture.capture(Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG},
            {"session": session.serialize()},
        ), timeout=30)
        return capture.finish()

    def _assert_query(self, utterance, query):
        messages = self._messages(utterance)
        TALLY.assert_routed(utterance, INTENT, [m.msg_type for m in messages])
        data = next(m.data for m in messages if m.msg_type == INTENT)
        self.assertEqual(data.get("query"), query)

    def test_skill_loads(self):
        self.assertIn(SKILL_ID, self.minicroft.plugin_skills)

    def test_speed_of_light(self):
        self._assert_query("ask wolfram what is the speed of light",
                           "what is the speed of light")

    def test_height_of_everest(self):
        self._assert_query("according to wolfram how tall is everest",
                           "how tall is everest")

    def test_blacklisted_phrase_does_not_match(self):
        # search_wolfie.intent ships a sibling locale/en-US/search_wolfie.blacklist
        # (loaded natively by ovos-workshop's register_intent_file). A
        # blacklisted phrase excludes the intent from matching.
        utterance = "ask wolfram can you install skills"
        TALLY.assert_not_routed(utterance, INTENT,
                                [m.msg_type for m in self._messages(utterance)])

    def test_installment_is_not_blacklisted(self):
        # "installment" must not collide with the "install" blacklist entry:
        # a single blacklisted word only excludes on a whole-word hit.
        self._assert_query("ask wolfram what is an installment loan",
                           "what is an installment loan")
