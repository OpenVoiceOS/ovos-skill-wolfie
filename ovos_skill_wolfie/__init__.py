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
from typing import Optional, Tuple

from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_wolfram_alpha_plugin import WolframAlphaRetrievalEngine
from ovos_workshop.decorators import intent_handler, common_query, fallback_handler
from ovos_workshop.skills.fallback import FallbackSkill


class WolframAlphaSkill(FallbackSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_results = {}
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
        lang = (message.data.get("lang") or sess.lang or self.lang).split("-")[0]
        try:
            answer = self.wolfie.get_spoken_answer(query, lang=lang)
        except Exception as e:
            self.log.error(f"Wolfram Alpha search failed: {e}")
            answer = None
        if answer:
            self.speak(answer)
        else:
            self.speak_dialog("no_answer")

    # fallback — last resort before "I don't understand"
    @fallback_handler(priority=91)
    def handle_wolfram_fallback(self, message: Message) -> bool:
        utterance = message.data["utterance"]
        if self.voc_match(utterance, "Help"):
            return False
        lang = (message.data.get("lang") or self.lang).split("-")[0]
        try:
            answer = self.wolfie.get_spoken_answer(utterance, lang=lang)
            if answer:
                self.speak(answer)
                self.bus.emit(message.forward(
                    f"question:action.{self.skill_id}",
                    {"phrase": utterance, "answer": answer}
                ))
                return True
        except Exception as e:
            self.log.error(f"Wolfram Alpha fallback failed: {e}")
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
        answer = self.wolfie.get_spoken_answer(phrase, lang=sess.lang.split("-")[0])
        if answer:
            self.session_results[sess.session_id] = {"phrase": phrase, "answer": answer}
            return answer, 0.8
