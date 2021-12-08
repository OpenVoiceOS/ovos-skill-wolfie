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
from mycroft.api import Api
from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel
from mycroft.skills.core import intent_handler
from neon_solver_wolfram_alpha_plugin import WolframAlphaSolver


class WAApi(Api):
    """ Wrapper for wolfram alpha calls through Mycroft Home API. """

    def __init__(self):
        super(WAApi, self).__init__("wolframAlphaSpoken")

    def spoken(self, query, lat_lon, units='metric'):
        try:
            return self.request(
                {'query': {'i': query,
                           'geolocation': '{},{}'.format(*lat_lon),
                           'units': units}})
        except Exception as e:
            # don't care what the cause was
            return None


class WolframAlphaSkill(CommonQuerySkill):

    @intent_handler("search_wolfie.intent")
    def handle_search(self, message):
        query = message.data["query"]
        response = self.ask_the_wolf(query)
        if response:
            self.speak(response)
        else:
            self.speak_dialog("no_answer")

    def CQS_match_query_phrase(self, utt):
        self.log.debug("WolframAlpha query: " + utt)
        response = self.ask_the_wolf(utt)
        if response:
            return (utt, CQSMatchLevel.GENERAL, response,
                    {'query': utt, 'answer': response})

    def ask_the_wolf(self, query):
        wolfie = WolframAlphaSolver({
            "units": self.config_core['system_unit'],
            "appid": self.settings["api_key"]
        })
        for sentence in wolfie.spoken_answers(query):
            return sentence


def create_skill():
    return WolframAlphaSkill()
