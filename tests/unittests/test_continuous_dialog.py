import json
import unittest
from unittest.mock import Mock

from ovos_utils.messagebus import FakeBus, Message
from skill_ovos_wolfie import WolframAlphaSkill
from time import sleep

class TestDialog(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.bus.emitted_msgs = []

        def get_msg(msg):
            self.bus.emitted_msgs.append(json.loads(msg))

        self.bus.on("message", get_msg)

        self.skill = WolframAlphaSkill()
        self.skill._startup(self.bus, "wolfie.test")
        self.skill.wolfie.long_answer = Mock()
        self.skill.wolfie.long_answer.return_value = [
            {"title": f"title 1", "summary": f"this is the answer number 1"},
            {"title": f"title 2", "summary": f"this is the answer number 2"}
        ]
        self.skill.has_context = False

        def set_context(message):
            self.skill.has_context = True

        def unset_context(message):
            self.skill.has_context = False

        self.bus.on('add_context', set_context)
        self.bus.on('remove_context', unset_context)

    def test_continuous_dialog(self):
        self.bus.emitted_msgs = []

        # "ask the wolf X"
        self.assertFalse(self.skill.has_context)
        self.skill.handle_search(Message("search_wolfie.intent",
                                         {"query": "what is the speed of light"}))
        sleep(0.5)
        self.assertEqual(self.bus.emitted_msgs[0],
                         {'context': {'skill_id': 'wolfie.test'},
                          'data': {'context': 'wolfie_testWolfieKnows',
                                   'origin': '',
                                   'word': 'what is the speed of light'},
                          'type': 'add_context'})
        self.assertEqual(self.bus.emitted_msgs[-1],
                         {'context': {'skill_id': 'wolfie.test'},
                          'data': {'expect_response': False,
                                   'lang': 'en-us',
                                   'meta': {'skill': 'wolfie.test'},
                                   'utterance': 'this is the answer number 1'},
                          'type': 'speak'})

        # "tell me more"
        self.assertTrue(self.skill.has_context)
        self.skill.handle_tell_more(Message("WolfieMore"))
        sleep(0.5)
        self.assertEqual(self.bus.emitted_msgs[-1],
                         {'context': {'skill_id': 'wolfie.test'},
                          'data': {'expect_response': False,
                                   'lang': 'en-us',
                                   'meta': {'skill': 'wolfie.test'},
                                   'utterance': 'this is the answer number 2'},
                          'type': 'speak'})
        self.assertTrue(self.skill.has_context)

        # "tell me more" - no more data dialog
        self.skill.handle_tell_more(Message("WolfieMore"))
        sleep(0.5)
        self.assertEqual(self.bus.emitted_msgs[-2]["type"], "speak")
        self.assertEqual(self.bus.emitted_msgs[-2]["data"]["meta"],
                         {'data': {}, 'dialog': 'thats all', 'skill': 'wolfie.test'})

        # removal of context to disable "tell me more"
        self.assertEqual(self.bus.emitted_msgs[-1],
                         {'context': {'skill_id': 'wolfie.test'},
                          'data': {'context': 'wolfie_testWolfieKnows'},
                          'type': 'remove_context'})
        self.assertFalse(self.skill.has_context)
