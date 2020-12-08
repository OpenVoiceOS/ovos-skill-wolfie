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
import requests
from mycroft.api import Api
from mycroft.messagebus.message import Message
from mycroft.skills.core import intent_handler
from mycroft.configuration import LocalConf, USER_CONFIG
from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel
from google_trans_new import google_translator


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
    def __init__(self):
        super().__init__()
        if "use_selene" not in self.settings:
            self.settings["use_selene"] = True
        if "api_key" not in self.settings:
            self.settings["api_key"] = "Y7R353-9HQAAL8KKA"
        self.translator = google_translator()
        self.tx_cache = {}  # avoid translating twice
        self.answer_cache = {}  # avoid hitting wolfram twice for same question
        self.selene_api = WAApi()

    def initialize(self):
        self.blacklist_default_skill()

    def blacklist_default_skill(self):
        # load the current list of already blacklisted skills
        blacklist = self.config_core["skills"]["blacklisted_skills"]

        # check the folder name (skill_id) of the skill you want to replace
        skill_id = "fallback-wolfram-alpha.mycroftai"

        # add the skill to the blacklist
        if skill_id not in blacklist:
            self.log.debug("Blacklisting official mycroft skill")
            blacklist.append(skill_id)

            # load the user config file (~/.mycroft/mycroft.conf)
            conf = LocalConf(USER_CONFIG)
            if "skills" not in conf:
                conf["skills"] = {}

            # update the blacklist field
            conf["skills"]["blacklisted_skills"] = blacklist

            # save the user config file
            conf.store()

        # tell the intent service to unload the skill in case it was loaded already
        # this should avoid the need to restart
        self.bus.emit(Message("detach_skill", {"skill_id": skill_id}))

    def translate(self, utterance, lang_tgt=None, lang_src="en"):
        lang_tgt = lang_tgt or self.lang

        # if langs are the same do nothing
        if not lang_tgt.startswith(lang_src):
            if lang_tgt not in self.tx_cache:
                self.tx_cache[lang_tgt] = {}
            # if translated before, dont translate again
            if utterance in self.tx_cache[lang_tgt]:
                # get previous translated value
                translated_utt = self.tx_cache[lang_tgt][utterance]
            else:
                # translate this utterance
                translated_utt = self.translator.translate(utterance,
                                                           lang_tgt=lang_tgt,
                                                           lang_src=lang_src).strip()
                # save the translation if we need it again
                self.tx_cache[lang_tgt][utterance] = translated_utt
            self.log.debug("translated {src} -- {tgt}".format(src=utterance,
                                                              tgt=translated_utt))
        else:
            translated_utt = utterance.strip()
        return translated_utt

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
        return (utt, CQSMatchLevel.GENERAL, response,
                {'query': utt, 'answer': response})

    def ask_the_wolf(self, query):
        # Automatic translation to English
        utt = self.translate(query, "en", self.lang)

        if self.settings["use_selene"]:
            response = self.get_selene_response(utt)
        elif self.settings.get("api_key"):
            response = self.get_wolfram_response(utt)
        else:
            return None
        if response:
            return self.translate(response)

    def get_selene_response(self, query):
        response = self.selene_api.spoken(
            query=query,
            lat_lon=(self.location['coordinate']['latitude'],
                     self.location['coordinate']['longitude']),
            units=self.config_core['system_unit'])
        return response

    def get_wolfram_response(self, query):
        url = 'http://api.wolframalpha.com/v1/spoken'
        if query in self.answer_cache:
            answer = self.answer_cache[query]
        else:
            params = {"appid": self.settings["api_key"],
                      "i": query,
                      "units": self.config_core['system_unit']}
            answer = requests.get(url, params=params).text
            bad_answers = ["No spoken result available",
                           "Wolfram Alpha did not understand your input"]
            if answer in bad_answers:
                return None
        self.answer_cache[query] = answer
        return answer


def create_skill():
    return WolframAlphaSkill()
