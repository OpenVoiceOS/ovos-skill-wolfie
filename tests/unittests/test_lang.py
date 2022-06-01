import json
import unittest
from time import sleep
from unittest.mock import Mock

from ovos_utils.messagebus import FakeBus, Message
from skill_wolfie import WolframAlphaSkill


class TestTranslation(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.bus.emitted_msgs = []

        def get_msg(msg):
            self.bus.emitted_msgs.append(json.loads(msg))

        self.bus.on("message", get_msg)

        self.skill = WolframAlphaSkill()
        self.skill._startup(self.bus, "wolfie.test")

        self.skill.wolfie.translator.translate = Mock()
        self.skill.wolfie.translator.translate.return_value = "this text is in portuguese, trust me!"
        self.skill.wolfie.get_expanded_answer = Mock()
        self.skill.wolfie.get_expanded_answer.return_value = [
            {"title": "wolfie skill", "summary": "the answer is always 42"}
        ]

    def test_native_lang(self):
        # no translation
        self.skill.handle_search(Message("search_wolfie.intent",
                                         {"query": "english question here"}))
        sleep(0.5)
        self.assertEqual(self.bus.emitted_msgs[-1],
                         {'context': {'skill_id': 'wolfie.test'},
                          'data': {'expect_response': False,
                                   'lang': 'en-us',
                                   'meta': {'skill': 'wolfie.test'},
                                   'utterance': 'the answer is always 42'},
                          'type': 'speak'})

    def test_unk_lang(self):
        # translation
        self.skill.handle_search(Message("search_wolfie.intent",
                                         {"query": "not english!",
                                          "lang": "pt-pt"}))
        sleep(0.5)
        self.assertEqual(self.bus.emitted_msgs[-1],
                         {'context': {'skill_id': 'wolfie.test'},
                          'data': {'expect_response': False,
                                   'lang': 'pt-pt',
                                   'meta': {'skill': 'wolfie.test'},
                                   'utterance': "this text is in portuguese, trust me!"},
                          'type': 'speak'})
