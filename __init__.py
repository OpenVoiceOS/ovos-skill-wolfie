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
import re
from os.path import join
from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel
from mycroft.skills.core import intent_handler
from neon_solver_wolfram_alpha_plugin import WolframAlphaSolver
from adapt.intent import IntentBuilder
from ovos_utils.gui import can_use_gui


# TODO move into ovos_utils for reusability
def remove_parentheses(answer):
    # remove [xx] (xx) {xx}
    answer = re.sub(r'\[[^)]*\]', '', answer)
    answer = re.sub(r'\([^)]*\)', '', answer)
    answer = re.sub(r'\{[^)]*\}', '', answer)
    answer = answer.replace("(", "").replace(")", "") \
        .replace("[", "").replace("]", "").replace("{", "") \
        .replace("}", "").strip()
    # remove extra spaces
    words = [w for w in answer.split(" ") if w.strip()]
    answer = " ".join(words)
    if not answer:
        return None
    return answer


class WolframAlphaSkill(CommonQuerySkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.idx = 0
        self.last_query = None
        self.results = []
        self.wolfie = WolframAlphaSolver({
            "units": self.config_core['system_unit'],
            "appid": self.settings.get("api_key")
        })
        self.image = None
        self.skip_images = True  # some wolfram results are pictures with no speech
                                 # if a gui is available the title is read and image displayed

    # explicit intents
    @intent_handler("search_wolfie.intent")
    def handle_search(self, message):
        query = message.data["query"]
        response = self.ask_the_wolf(query)
        if response:
            self.speak_result()
        else:
            self.speak_dialog("no_answer")

    @intent_handler(IntentBuilder("WolfieMore").require("More").
                    require("WolfieKnows"))
    def handle_tell_more(self, message):
        """ Follow up query handler, "tell me more"."""
        self.speak_result()

    # common query integration
    def CQS_match_query_phrase(self, utt):
        self.log.debug("WolframAlpha query: " + utt)
        response = self.ask_the_wolf(utt)
        if response:
            self.idx += 1  # spoken by common query framework
            return (utt, CQSMatchLevel.GENERAL, response,
                    {'query': utt, 'answer': response})

    def CQS_action(self, phrase, data):
        """ If selected show gui """
        self.display_wolfie()

    # wolfram integration
    def ask_the_wolf(self, query):
        # context for follow up questions
        self.set_context("WolfieKnows", query)
        self.results = self.wolfie.long_answer(query)
        self.idx = 0
        self.image = None
        if len(self.results):
            self.image = self.wolfie.visual_answer(query)
            return self.results[0]["summary"]

    def display_wolfie(self):
        image = self.results[self.idx].get("img") or\
                self.wolfie.visual_answer(self.last_query)
        # scrollable full result page
        self.gui["wolfram_image"] = image
        self.gui.show_page(join(self.root_dir, "ui", "wolf.qml"), override_idle=45)

    def speak_result(self):
        if self.idx + 1 > len(self.results):
            self.speak_dialog("thats all")
            self.remove_context("WolfieKnows")
            self.idx = 0
        else:
            if not self.results[self.idx].get("summary"):
                if not self.skip_images and can_use_gui(self.bus):
                    self.speak(self.results[self.idx]["title"])
                    self.display_wolfie()
                else:
                    # skip image only result
                    self.idx += 1
                    self.speak_result()
                    return
            else:
                self.display_wolfie()
                # make it more speech friendly
                ans = self.results[self.idx]["summary"]
                ans = ans.replace(" | ", "; ").replace("\n", ".\n")
                ans = remove_parentheses(ans)
                self.speak(ans)
            self.idx += 1


def create_skill():
    return WolframAlphaSkill()
