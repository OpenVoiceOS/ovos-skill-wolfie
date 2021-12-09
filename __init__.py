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
from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel
from mycroft.skills.core import intent_handler
from neon_solver_wolfram_alpha_plugin import WolframAlphaSolver


class WolframAlphaSkill(CommonQuerySkill):

    @property
    def wolfie(self):
        return WolframAlphaSolver({
            "units": self.config_core['system_unit'],
            "appid": self.settings.get("api_key")
        })

    @intent_handler("search_wolfie.intent")
    def handle_search(self, message):
        query = message.data["query"]
        response = self.ask_the_wolf(query)
        if response:
            self.speak(response)
            image = self.wolfie.get_image(query, {"lang": self.lang})
            self.gui.show_image(image)
        else:
            self.speak_dialog("no_answer")

    def CQS_match_query_phrase(self, utt):
        self.log.debug("WolframAlpha query: " + utt)
        response = self.ask_the_wolf(utt)
        if response:
            return (utt, CQSMatchLevel.GENERAL, response,
                    {'query': utt, 'answer': response})

    def CQS_action(self, phrase, data):
        """ If selected show gui """
        image = self.wolfie.get_image(phrase, {'lang': self.lang})
        self.gui.show_image(image)

    def ask_the_wolf(self, query):
        for sentence in self.wolfie.spoken_answers(query):
            return sentence


def create_skill():
    return WolframAlphaSkill()
