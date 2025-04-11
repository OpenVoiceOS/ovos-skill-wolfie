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
#

from typing import Optional, Tuple

from ovos_bus_client import Message
from ovos_bus_client.session import SessionManager
from ovos_utils.decorators import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_wolfram_alpha_solver import WolframAlphaSolver
from ovos_workshop.decorators import intent_handler, common_query, fallback_handler
from ovos_workshop.skills.fallback import FallbackSkill


class WolframAlphaSkill(FallbackSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_results = {}  # session_id: {}
        self.wolfie = WolframAlphaSolver({
            "appid": self.settings.get("api_key")
        }, translator=self.translator, detector=self.lang_detector)

    @classproperty
    def runtime_requirements(self):
        """this skill requires internet"""
        return RuntimeRequirements(internet_before_load=True,
                                   network_before_load=True,
                                   gui_before_load=False,
                                   requires_internet=True,
                                   requires_network=True,
                                   requires_gui=False,
                                   no_internet_fallback=False,
                                   no_network_fallback=False,
                                   no_gui_fallback=True)

    # explicit intents
    @intent_handler("search_wolfie.intent",
                    voc_blacklist=["Help"])
    def handle_search(self, message: Message):
        query = message.data["query"]
        sess = SessionManager.get(message)
        self.session_results[sess.session_id] = {"phrase": query,
                                                 "image": None,
                                                 "lang": sess.lang,
                                                 "system_unit": sess.system_unit,
                                                 "spoken_answer": ""}
        response = self.ask_the_wolf(query, sess.lang, sess.system_unit)
        if response:
            self.session_results[sess.session_id]["spoken_answer"] = response
            self.speak(response)
        else:
            self.speak_dialog("no_answer")


    @fallback_handler(priority=91)
    def handle_wolfram_fallback(self, message):
        """if this code is reached OVOS is about to give up and
        speak the "i don't understand" dialog, give wolfram alpha a shot at answering.
        This is what the original early days mycroft-core did before fallback skills were introduced"""
        utterance = message.data["utterance"]
        if self.voc_match(utterance, "Help"):
            return False
        try:
            answer = self.ask_the_wolf(utterance, self.lang, self.system_unit)
            if answer:
                self.speak(answer)
                # trigger the extra GUI info (re-use callback from common_query)
                self.bus.emit(message.forward(f"question:action.{self.skill_id}",
                                              {"phrase": utterance, "answer": answer}))
                return True
        except Exception as e:
            self.log.error(f"Failed to query wolfram alpha: ({e})")
        return False

    # common query integration
    def cq_callback(self, utterance: str, answer: str, lang: str):
        """ If selected show gui """
        # generate image for the query after skill was selected for speed
        image = self.wolfie.visual_answer(utterance, lang=lang, units=self.system_unit)
        self.gui["wolfram_image"] = image or "logo.png"
        # scrollable full result page
        self.gui.show_page("wolf", override_idle=45)

    @common_query(callback=cq_callback)
    def match_common_query(self, phrase: str, lang: str) -> Optional[Tuple[str, float]]:
        self.log.debug("WolframAlpha query: " + phrase)
        if self.wolfie is None:
            self.log.error("WolframAlphaSkill not initialized, no response")
            return

        if self.voc_match(phrase, "MiscBlacklist"):
            return

        sess = SessionManager.get()
        self.session_results[sess.session_id] = {"phrase": phrase,
                                                 "image": None,
                                                 "lang": lang,
                                                 "system_unit": sess.system_unit,
                                                 "spoken_answer": None}

        response = self.ask_the_wolf(phrase, lang, sess.system_unit)
        if response:
            self.session_results[sess.session_id]["spoken_answer"] = response
            self.log.debug(f"WolframAlpha response: {response}")
            return response, 0.7

    # wolfram integration
    def ask_the_wolf(self, query: str,
                     lang: Optional[str] = None,
                     units: Optional[str] = None):
        units = units or self.system_unit
        if units != "metric":
            units = "nonmetric"  # what wolfram api expects

        lang = lang or self.lang
        if lang.startswith("en"):
            self.log.debug(f"skipping auto translation for wolfram alpha, "
                           f"{lang} is supported")
            WolframAlphaSolver.enable_tx = False
        else:
            self.log.info(f"enabling auto translation for wolfram alpha, "
                          f"{lang} is not supported internally")
            WolframAlphaSolver.enable_tx = True
        return self.wolfie.spoken_answer(query, lang=lang, units=units)

    def stop_session(self, sess):
        if sess.session_id in self.session_results:
            self.session_results.pop(sess.session_id)


if __name__ == "__main__":
    from ovos_utils.fakebus import FakeBus

    d = WolframAlphaSkill(bus=FakeBus(), skill_id="fake.wolf")

    print(d.ask_the_wolf("what is the speed of light", units="nonmetric"))  # SI units regardless
    # The speed of light has a value of about 300 million meters per second
    print(d.ask_the_wolf("how tall is the eiffel tower", units="metric"))
    print(d.ask_the_wolf("how tall is the eiffel tower", units="nonmetric"))
    # The total height of the Eiffel Tower is 330 meters
    # The total height of the Eiffel Tower is about 1083 feet
