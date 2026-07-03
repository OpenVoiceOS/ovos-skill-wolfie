"""
Unit tests for WolframAlphaSkill.

Uses FakeBus and mocked WolframAlphaRetrievalEngine — no network, no API key, no daemon.
"""
import unittest
from unittest.mock import MagicMock, patch

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus


def _make_skill():
    with patch("ovos_skill_wolfie.WolframAlphaRetrievalEngine") as mock_cls:
        mock_cls.return_value = MagicMock()
        from ovos_skill_wolfie import WolframAlphaSkill
        skill = WolframAlphaSkill(bus=FakeBus(), skill_id="test.wolfie")
        skill.wolfie = mock_cls.return_value
        return skill


# ---------------------------------------------------------------------------
# Skill instantiation
# ---------------------------------------------------------------------------

class TestSkillInit(unittest.TestCase):

    def test_skill_creates_engine(self):
        with patch("ovos_skill_wolfie.WolframAlphaRetrievalEngine") as mock_cls, \
             patch("ovos_wolfram_alpha_plugin.load_tx_plugin", return_value=None):
            from ovos_skill_wolfie import WolframAlphaSkill
            WolframAlphaSkill(bus=FakeBus(), skill_id="test.wolfie")
        mock_cls.assert_called_once()

    def test_session_results_starts_empty(self):
        skill = _make_skill()
        self.assertEqual(skill.session_results, {})

    def test_runtime_requires_internet(self):
        skill = _make_skill()
        req = skill.runtime_requirements
        self.assertTrue(req.requires_internet)
        self.assertTrue(req.internet_before_load)
        self.assertFalse(req.no_internet_fallback)


# ---------------------------------------------------------------------------
# handle_search — explicit intent
# ---------------------------------------------------------------------------

class TestHandleSearch(unittest.TestCase):

    def setUp(self):
        self.skill = _make_skill()
        self.skill.speak = MagicMock()
        self.skill.speak_dialog = MagicMock()
        self.skill.gui = MagicMock()

    def _msg(self, query="speed of light"):
        return Message("ovos.skills.test", data={"query": query})

    def test_speaks_answer(self):
        self.skill.wolfie.get_spoken_answer.return_value = "About 3×10^8 m/s."
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "default"
            sm.get.return_value.lang = "en-US"
            self.skill.handle_search(self._msg())
        self.skill.speak.assert_called_once_with("About 3×10^8 m/s.")

    def test_speaks_no_answer_when_none(self):
        self.skill.wolfie.get_spoken_answer.return_value = None
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "default"
            sm.get.return_value.lang = "en-US"
            self.skill.handle_search(self._msg("xyzzy"))
        self.skill.speak_dialog.assert_any_call("no_answer")

    def test_gui_shown_for_default_session(self):
        self.skill.wolfie.get_spoken_answer.return_value = "42"
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "default"
            sm.get.return_value.lang = "en-US"
            self.skill.handle_search(self._msg())
        self.skill.gui.show_animated_image.assert_called_once_with("wolfie.gif")

    def test_gui_not_shown_for_remote_session(self):
        self.skill.wolfie.get_spoken_answer.return_value = "42"
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "remote-xyz"
            sm.get.return_value.lang = "en-US"
            self.skill.handle_search(self._msg())
        self.skill.gui.show_animated_image.assert_not_called()

    def test_lang_stripped_to_base(self):
        self.skill.wolfie.get_spoken_answer.return_value = "42"
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "default"
            sm.get.return_value.lang = "pt-PT"
            self.skill.handle_search(self._msg("velocidade da luz"))
        self.skill.wolfie.get_spoken_answer.assert_called_once_with("velocidade da luz", lang="pt")

    def test_blacklisted_utterance_suppresses_lookup(self):
        self.skill._intent_blacklist = MagicMock(return_value={"install"})
        msg = Message("ovos.skills.test",
                      data={"query": "skills", "utterance": "ask wolfram can you install skills"})
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "default"
            sm.get.return_value.lang = "en-US"
            self.skill.handle_search(msg)
        self.skill.wolfie.get_spoken_answer.assert_not_called()
        self.skill.speak.assert_not_called()

    def test_intent_blacklist_reads_resource(self):
        self.skill.find_resource = MagicMock(return_value="search_wolfie.blacklist")
        with patch("builtins.open",
                   unittest.mock.mock_open(read_data="# comment\ncan you\ninstall\n")):
            terms = self.skill._intent_blacklist("en-US")
        self.assertEqual(terms, {"can you", "install"})


# ---------------------------------------------------------------------------
# handle_wolfram_fallback
# ---------------------------------------------------------------------------

class TestFallback(unittest.TestCase):

    def setUp(self):
        self.skill = _make_skill()
        self.skill.speak = MagicMock()
        self.skill.voc_match = MagicMock(return_value=False)
        self.skill.bus.emit = MagicMock()

    def _msg(self, utterance="how tall is Everest"):
        return Message("ovos.skills.test", data={"utterance": utterance})

    def test_returns_true_when_answer_found(self):
        self.skill.wolfie.get_spoken_answer.return_value = "8849 meters."
        result = self.skill.handle_wolfram_fallback(self._msg())
        self.assertTrue(result)
        self.skill.speak.assert_called_once_with("8849 meters.")

    def test_returns_false_when_no_answer(self):
        self.skill.wolfie.get_spoken_answer.return_value = None
        result = self.skill.handle_wolfram_fallback(self._msg("xyzzy"))
        self.assertFalse(result)

    def test_returns_false_for_help_utterance(self):
        self.skill.voc_match.return_value = True
        result = self.skill.handle_wolfram_fallback(self._msg("help me"))
        self.assertFalse(result)
        self.skill.wolfie.get_spoken_answer.assert_not_called()

    def test_returns_false_on_exception(self):
        self.skill.wolfie.get_spoken_answer.side_effect = Exception("network error")
        result = self.skill.handle_wolfram_fallback(self._msg())
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# match_common_query
# ---------------------------------------------------------------------------

class TestMatchCommonQuery(unittest.TestCase):

    def setUp(self):
        self.skill = _make_skill()
        self.skill.voc_match = MagicMock(return_value=False)

    def test_returns_answer_and_conf(self):
        self.skill.wolfie.get_spoken_answer.return_value = "8849 meters."
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "s1"
            sm.get.return_value.lang = "en-US"
            result = self.skill.match_common_query("how tall is Everest", "en-US")
        self.assertEqual(result, ("8849 meters.", 0.8))

    def test_returns_none_when_no_answer(self):
        self.skill.wolfie.get_spoken_answer.return_value = None
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "s1"
            sm.get.return_value.lang = "en-US"
            result = self.skill.match_common_query("xyzzy", "en-US")
        self.assertIsNone(result)

    def test_returns_none_for_blacklisted_phrase(self):
        self.skill._intent_blacklist = MagicMock(return_value={"install"})
        result = self.skill.match_common_query("how do I install this", "en-US")
        self.assertIsNone(result)
        self.skill.wolfie.get_spoken_answer.assert_not_called()

    def test_stores_result_in_session(self):
        self.skill.wolfie.get_spoken_answer.return_value = "8849 meters."
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "s2"
            sm.get.return_value.lang = "en-US"
            self.skill.match_common_query("how tall is Everest", "en-US")
        self.assertIn("s2", self.skill.session_results)
        self.assertEqual(self.skill.session_results["s2"]["answer"], "8849 meters.")


# ---------------------------------------------------------------------------
# cq_callback
# ---------------------------------------------------------------------------

class TestCqCallback(unittest.TestCase):

    def setUp(self):
        self.skill = _make_skill()
        self.skill.gui = MagicMock()

    def test_shows_image_for_default_session(self):
        self.skill.wolfie.get_image.return_value = "/tmp/everest.gif"
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "default"
            self.skill.cq_callback("how tall is Everest", "8849 meters.", "en-US")
        self.skill.gui.show_page.assert_called_once_with("wolf", override_idle=45)
        self.skill.gui.__setitem__.assert_called_with("wolfram_image", "/tmp/everest.gif")

    def test_fallback_logo_when_no_image(self):
        self.skill.wolfie.get_image.return_value = None
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "default"
            self.skill.cq_callback("xyzzy", "42", "en-US")
        self.skill.gui.__setitem__.assert_called_with("wolfram_image", "logo.png")

    def test_no_gui_for_remote_session(self):
        with patch("ovos_skill_wolfie.SessionManager") as sm:
            sm.get.return_value.session_id = "remote-xyz"
            self.skill.cq_callback("query", "answer", "en-US")
        self.skill.gui.show_page.assert_not_called()


# ---------------------------------------------------------------------------
# Locale resources — en-US intent definitions
# ---------------------------------------------------------------------------

class TestEnUsLocaleResources(unittest.TestCase):
    """Guard the shape of the packaged en-US resources the skill relies on."""

    def _locale(self, name):
        import os
        import ovos_skill_wolfie
        path = os.path.join(os.path.dirname(ovos_skill_wolfie.__file__),
                            "locale", "en-US", name)
        with open(path) as f:
            return [ln.strip() for ln in f
                    if ln.strip() and not ln.strip().startswith("#")]

    def test_help_voc_present(self):
        # handle_wolfram_fallback voc_matches "Help"; the file must ship so
        # meta requests are not forwarded to Wolfram Alpha
        self.assertIn("install", self._locale("Help.voc"))

    def test_intent_names_backend(self):
        # every explicit template names the backend in a (wolfram|...) group,
        # so none acts as a bare open-{query} catcher
        lines = self._locale("search_wolfie.intent")
        self.assertTrue(lines)
        for line in lines:
            self.assertIn("{query}", line)
            self.assertIn("wolfram", line)

    def test_wolfram_voc_names(self):
        names = self._locale("wolfram.voc")
        self.assertIn("wolfram", names)
        self.assertIn("the wolf", names)

    def test_query_blacklist_excludes_pronouns(self):
        # anaphoric pronouns must not fill {query} (INTENT-2 §4.3 slot-value
        # exclusion) so CONTEXT-1 §7 can resolve the referent
        excluded = self._locale("query.blacklist")
        for pronoun in ("it", "he", "she", "they", "this", "that"):
            self.assertIn(pronoun, excluded)


if __name__ == "__main__":
    unittest.main()
