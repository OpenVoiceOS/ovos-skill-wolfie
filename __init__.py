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

import tempfile
from os.path import join, isfile
from typing import Optional

import requests
from ovos_backend_client.api import WolframAlphaApi as _WA
from ovos_bus_client import Message
from ovos_bus_client.session import SessionManager
from ovos_config import Configuration
from ovos_plugin_manager.templates.solvers import QuestionSolver
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel


class WolframAlphaApi(_WA):
    def get_image(self, query: str, units: Optional[str] = None):
        """
        query assured to be in self.default_lang
        return path/url to a single image to acompany spoken_answer
        """
        # TODO - extend backend-client method for picture
        units = units or Configuration().get("system_unit", "metric")
        url = 'http://api.wolframalpha.com/v1/simple'
        params = {"appid": self.credentials["wolfram"],
                  "i": query,
                  # "background": "F5F5F5",
                  "layout": "labelbar",
                  "units": units}
        path = join(tempfile.gettempdir(), query.replace(" ", "_") + ".gif")
        if not isfile(path):
            image = requests.get(url, params=params).content
            with open(path, "wb") as f:
                f.write(image)
        return path


class WolframAlphaSolver(QuestionSolver):
    priority = 25
    enable_cache = False
    enable_tx = True

    def __init__(self, config=None):
        config = config or {}
        config["lang"] = "en"  # only supports english
        super().__init__(config=config)
        self.api = WolframAlphaApi(key=self.config.get("appid") or "Y7R353-9HQAAL8KKA")
        # TODO - debug, key doesnt seem to be passed along to base class ???
        self.api.backend.credentials = self.api.credentials

    @staticmethod
    def make_speakable(summary: str):
        # let's remove unwanted data from parantheses
        #  - many results have (human: XX unit) ref values, remove them
        if "(human: " in summary:
            splits = summary.split("(human: ")
            for idx, s in enumerate(splits):
                splits[idx] = ")".join(s.split(")")[1:])
            summary = " ".join(splits)

        # remove duplicated units in text
        # TODO probably there's a lot more to add here....
        replaces = {
            "cm (centimeters)": "centimeters",
            "cm³ (cubic centimeters)": "cubic centimeters",
            "cm² (square centimeters)": "square centimeters",
            "mm (millimeters)": "millimeters",
            "mm² (square millimeters)": "square millimeters",
            "mm³ (cubic millimeters)": "cubic millimeters",
            "kg (kilograms)": "kilograms",
            "kHz (kilohertz)": "kilohertz",
            "ns (nanoseconds)": "nanoseconds",
            "µs (microseconds)": "microseconds",
            "m/s (meters per second)": "meters per second",
            "km/s (kilometers per second)": "kilometers per second",
            "mi/s (miles per second)": "miles per second",
            "mph (miles per hour)": "miles per hour",
            "ª (degrees)": " degrees"
        }
        for k, v in replaces.items():
            summary = summary.replace(k, v)

        # replace units, only if they are individual words
        units = {
            "cm": "centimeters",
            "cm³": "cubic centimeters",
            "cm²": "square centimeters",
            "mm": "millimeters",
            "mm²": "square millimeters",
            "mm³": "cubic millimeters",
            "kg": "kilograms",
            "kHz": "kilohertz",
            "ns": "nanoseconds",
            "µs": "microseconds",
            "m/s": "meters per second",
            "km/s": "kilometers per second",
            "mi/s": "miles per second",
            "mph": "miles per hour"
        }
        words = [w if w not in units else units[w]
                 for w in summary.split(" ")]
        summary = " ".join(words)

        return summary

    # data api
    def get_data(self, query: str,
                 lang: Optional[str] = None,
                 units: Optional[str] = None):
        """
       query assured to be in self.default_lang
       return a dict response
       """
        units = units or Configuration().get("system_unit", "metric")
        return self.api.full_results(query, units=units)

    # image api (simple)
    def get_image(self, query: str,
                  lang: Optional[str] = None,
                  units: Optional[str] = None):
        """
        query assured to be in self.default_lang
        return path/url to a single image to acompany spoken_answer
        """
        units = units or Configuration().get("system_unit", "metric")
        return self.api.get_image(query, units=units)

    # spoken answers api (spoken)
    def get_spoken_answer(self, query: str,
                          lang: Optional[str] = None,
                          units: Optional[str] = None):
        """
        query assured to be in self.default_lang
        return a single sentence text response
        """
        units = units or Configuration().get("system_unit", "metric")
        answer = self.api.spoken(query, units=units)
        bad_answers = ["no spoken result available",
                       "wolfram alpha did not understand your input"]
        if answer.lower().strip() in bad_answers:
            return None
        return answer

    def get_expanded_answer(self, query,
                            lang: Optional[str] = None,
                            units: Optional[str] = None):
        """
        query assured to be in self.default_lang
        return a list of ordered steps to expand the answer, eg, "tell me more"

        {
            "title": "optional",
            "summary": "speak this",
            "img": "optional/path/or/url
        }
        """
        data = self.get_data(query, lang, units)
        # these are returned in spoken answer or otherwise unwanted
        skip = ['Input interpretation', 'Interpretation',
                'Result', 'Value', 'Image']
        steps = []

        for pod in data['queryresult'].get('pods', []):
            title = pod["title"]
            if title in skip:
                continue

            for sub in pod["subpods"]:
                subpod = {"title": title}
                summary = sub["img"]["alt"]
                subtitle = sub.get("title") or sub["img"]["title"]
                if subtitle and subtitle != summary:
                    subpod["title"] = subtitle

                if summary == title:
                    # it's an image result
                    subpod["img"] = sub["img"]["src"]
                elif summary.startswith("(") and summary.endswith(")"):
                    continue
                else:
                    subpod["summary"] = summary
                steps.append(subpod)

        # do any extra processing here
        prev = ""
        for idx, step in enumerate(steps):
            # merge steps
            if step["title"] == prev:
                summary = steps[idx - 1]["summary"] + "\n" + step["summary"]
                steps[idx]["summary"] = summary
                steps[idx]["img"] = step.get("img") or steps[idx - 1].get("img")
                steps[idx - 1] = None
            elif step.get("summary") and step["title"]:
                # inject title in speech, eg we do not want wolfram to just read family names without context
                steps[idx]["summary"] = step["title"] + ".\n" + step["summary"]

            # normalize summary
            if step.get("summary"):
                steps[idx]["summary"] = self.make_speakable(steps[idx]["summary"])

            prev = step["title"]
        return [s for s in steps if s]


class WolframAlphaSkill(CommonQuerySkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_results = {}  # session_id: {}
        self.wolfie = WolframAlphaSolver({
            "appid": self.settings.get("api_key")
        })

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
    @intent_handler("search_wolfie.intent")
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

    # common query integration
    def CQS_match_query_phrase(self, phrase: str):
        self.log.debug("WolframAlpha query: " + phrase)
        if self.wolfie is None:
            self.log.error("WolframAlphaSkill not initialized, no response")
            return

        sess = SessionManager.get()
        self.session_results[sess.session_id] = {"phrase": phrase,
                                                 "image": None,
                                                 "lang": sess.lang,
                                                 "system_unit": sess.system_unit,
                                                 "spoken_answer": None}

        response = self.ask_the_wolf(phrase, sess.lang, sess.system_unit)
        if response:
            self.session_results[sess.session_id]["spoken_answer"] = response
            self.log.debug(f"WolframAlpha response: {response}")
            return (phrase, CQSMatchLevel.EXACT, response,
                    {'query': phrase, 'answer': response})

    def CQS_action(self, phrase: str, data: dict):
        """ If selected show gui """
        # generate image for the query after skill was selected for speed
        image = self.wolfie.visual_answer(phrase, lang=self.lang, units=self.system_unit)
        self.gui["wolfram_image"] = image or f"{self.root_dir}/res/logo.png"
        # scrollable full result page
        self.gui.show_page("wolf", override_idle=45)

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

    exit()

    query = "who is Isaac Newton"

    # full answer
    ans = d.spoken_answer(query)
    print(ans)
    # Sir Isaac Newton (25 December 1642 – 20 March 1726/27) was an English mathematician, physicist, astronomer, alchemist, theologian, and author (described in his time as a "natural philosopher") widely recognised as one of the greatest mathematicians and physicists of all time and among the most influential scientists.

    ans = d.visual_answer(query)
    print(ans)
    # /tmp/who_is_Isaac_Newton.gif

    # chunked answer, "tell me more"
    for sentence in d.long_answer(query):
        print("#", sentence["title"])
        print(sentence.get("summary"), sentence.get("img"))

        # who is Isaac Newton
        # Sir Isaac Newton was an English mathematician, physicist, astronomer, alchemist, theologian, and author widely recognised as one of the greatest mathematicians and physicists of all time and among the most influential scientists.
        # https://duckduckgo.com/i/ea7be744.jpg

        # who is Isaac Newton
        # He was a key figure in the philosophical revolution known as the Enlightenment.
        # https://duckduckgo.com/i/ea7be744.jpg

        # who is Isaac Newton
        # His book Philosophiæ Naturalis Principia Mathematica, first published in 1687, established classical mechanics.
        # https://duckduckgo.com/i/ea7be744.jpg

        # who is Isaac Newton
        # Newton also made seminal contributions to optics, and shares credit with German mathematician Gottfried Wilhelm Leibniz for developing infinitesimal calculus.
        # https://duckduckgo.com/i/ea7be744.jpg

        # who is Isaac Newton
        # In the Principia, Newton formulated the laws of motion and universal gravitation that formed the dominant scientific viewpoint until it was superseded by the theory of relativity.
        # https://duckduckgo.com/i/ea7be744.jpg

    # bidirectional auto translate by passing lang context
    sentence = d.spoken_answer("Quem é Isaac Newton",
                               context={"lang": "pt"})
    print(sentence)
