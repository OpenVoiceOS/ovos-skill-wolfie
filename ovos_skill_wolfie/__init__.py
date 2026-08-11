# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import time
from collections import OrderedDict
from typing import Optional, Tuple

from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_wolfram_alpha_plugin import WolframAlphaRetrievalEngine
from ovos_workshop.decorators import intent_handler, common_query, fallback_handler
from ovos_workshop.skills.fallback import FallbackSkill

# how many recent questions keep their answer
CACHE_SIZE = 64


class WolframAlphaSkill(FallbackSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_results = {}
        self._cache = OrderedDict()
        self.wolfie = WolframAlphaRetrievalEngine(
            config={"appid": self.settings.get("appid")}
        )

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(
            internet_before_load=True,
            network_before_load=True,
            gui_before_load=False,
            requires_internet=True,
            requires_network=True,
            requires_gui=False,
            no_internet_fallback=False,
            no_network_fallback=False,
            no_gui_fallback=True,
        )

    # explicit wolfram intent
    @intent_handler("search_wolfie.intent", voc_blacklist=["MiscBlacklist"])
    def handle_search(self, message: Message):
        query = message.data["query"]
        sess = SessionManager.get(message)
        if sess.session_id == "default":
            self.gui.show_animated_image("wolfie.gif")
        lang = (message.data.get("lang") or sess.lang).split("-")[0]
        answer = self._get_answer(query, lang)
        if answer:
            self.speak(answer)
        else:
            self.speak_dialog("no_answer")

    def _get_answer(self, utterance: str, lang: str) -> Optional[str]:
        """Ask Wolfram Alpha, reusing a recent answer for the same question.

        One question reaches this skill up to three times: the fallback ping,
        the fallback handler that follows it, and common query. Without a cache
        that is three identical requests for one thing the user asked once.

        A failed request is not cached, so a transient outage does not pin a
        negative answer for the whole TTL.
        """
        key = (utterance.strip().lower(), lang)
        cached = self._cache.get(key)
        if cached is not None:
            answer, stamp = cached
            if time.monotonic() - stamp < self.settings.get("cache_ttl", 300):
                self._cache.move_to_end(key)
                return answer
            del self._cache[key]

        try:
            answer = self.wolfie.get_spoken_answer(utterance, lang=lang)
        except Exception as e:
            self.log.error(f"Wolfram Alpha query failed: {e}")
            return None

        self._cache[key] = (answer, time.monotonic())
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return answer

    def can_answer(self, message: Message) -> bool:
        utterance = message.data["utterances"][0]
        if self.voc_match(utterance, "Help"):
            return False
        lang = SessionManager.get(message).lang.split("-")[0]
        # Answering this honestly means asking Wolfram Alpha. The request is
        # fast enough for the ping, and the answer is cached, so the fallback
        # handler that follows serves it without a second round trip.
        return bool(self._get_answer(utterance, lang))

    # fallback — last resort before "I don't understand"
    @fallback_handler(priority=91)
    def handle_wolfram_fallback(self, message: Message) -> bool:
        utterance = message.data["utterance"]
        if self.voc_match(utterance, "Help"):
            return False
        sess = SessionManager.get(message)
        lang = (message.data.get("lang") or sess.lang).split("-")[0]
        answer = self._get_answer(utterance, lang)
        if answer:
            self.speak(answer)
            # Do not emit question:action here. That is the common query
            # pipeline telling a skill its answer was spoken, and workshop's
            # handler for it speaks the answer, so a fallback answer would be
            # spoken twice. Run the same GUI callback directly instead.
            self.cq_callback(utterance, answer, sess.lang)
            return True
        return False

    # common query
    def cq_callback(self, utterance: str, answer: str, lang: str):
        sess = SessionManager.get()
        if sess.session_id == "default":
            image = self.wolfie.get_image(utterance, lang=lang.split("-")[0])
            self.gui["wolfram_image"] = image or "logo.png"
            self.gui.show_page("wolf", override_idle=45)

    @common_query(callback=cq_callback)
    def match_common_query(self, phrase: str, lang: str) -> Optional[Tuple[str, float]]:
        if self.voc_match(phrase, "MiscBlacklist"):
            return None

        sess = SessionManager.get()
        answer = self._get_answer(phrase, sess.lang.split("-")[0])
        if answer:
            self.session_results[sess.session_id] = {"phrase": phrase, "answer": answer}
            return answer, 0.8
