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

import requests
from ovos_backend_client.api import WolframAlphaApi as _WA
from ovos_bus_client import Message
from ovos_config import Configuration
from ovos_plugin_manager.templates.solvers import QuestionSolver
from ovos_utils import classproperty
from ovos_utils.gui import can_use_gui
from ovos_utils.intents import IntentBuilder
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel


class WolframAlphaApi(_WA):
    def get_image(self, query):
        """
        query assured to be in self.default_lang
        return path/url to a single image to acompany spoken_answer
        """
        # TODO - extend backend-client method for picture
        units = Configuration().get("system_unit", "metric")
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
    enable_cache = True
    enable_tx = True

    def __init__(self, config=None):
        config = config or {}
        config["lang"] = "en"  # only supports english
        super().__init__(config=config)
        self.api = WolframAlphaApi(key=self.config.get("appid") or "Y7R353-9HQAAL8KKA")
        # TODO - debug, key doesnt seem to be passed along to base class ???
        self.api.backend.credentials = self.api.credentials

    @staticmethod
    def make_speakable(summary):
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
    def get_data(self, query, context=None):
        """
       query assured to be in self.default_lang
       return a dict response
       """
        units = Configuration().get("system_unit", "metric")
        return self.api.full_results(query, units=units)

    # image api (simple)
    def get_image(self, query, context=None):
        """
        query assured to be in self.default_lang
        return path/url to a single image to acompany spoken_answer
        """
        return self.api.get_image(query)

    # spoken answers api (spoken)
    def get_spoken_answer(self, query, context):
        """
        query assured to be in self.default_lang
        return a single sentence text response
        """
        units = Configuration().get("system_unit", "metric")
        answer = self.api.spoken(query, units=units)
        bad_answers = ["no spoken result available",
                       "wolfram alpha did not understand your input"]
        if answer.lower().strip() in bad_answers:
            return None
        return answer

    def get_expanded_answer(self, query, context=None):
        """
        query assured to be in self.default_lang
        return a list of ordered steps to expand the answer, eg, "tell me more"

        {
            "title": "optional",
            "summary": "speak this",
            "img": "optional/path/or/url
        }

        """
        data = self.get_data(query, context)
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
        # continuous dialog, "tell me more"
        self.idx = 0
        self.last_query = None
        self.results = []

        # answer processing options
        self.skip_images = True  # some wolfram results are pictures with no speech
        # if a gui is available the title is read and image displayed

        # These results are usually unwanted as spoken responses
        # they are either spammy or cant be handled by TTS properly
        self.skips = [
            # quantities, eg speed of light
            'Comparison',  # spammy
            'Corresponding quantities',  # spammy
            'Basic unit dimensions',  # TTS will fail hard 99% of time
            # when asking about word definitions
            'American pronunciation',  # can not pronounce IPA phonemes
            'Translations',  # TTS wont handle other langs or charsets
            'Hyphenation',  # spammy
            'Anagrams',  # spammy
            'Lexically close words',  # spammy
            'Overall typical frequency',  # spammy
            'Crossword puzzle clues',  # spammy
            'Scrabble score',  # spammy
            'Other notable uses'  # spammy
        ]

    @property
    def wolfie(self):
        # property to allow api key changes in config
        try:
            return WolframAlphaSolver({
                "units": self.config_core['system_unit'],
                "appid": self.settings.get("api_key")
            })
        except Exception as err:
            self.log.error("WolframAlphaSkill failed to initialize: %s", err)
        return None

    @classproperty
    def runtime_requirements(self):
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
        response = self.ask_the_wolf(query)
        if response:
            self.speak_result()
        else:
            self.speak_dialog("no_answer")

    @intent_handler(IntentBuilder("WolfieMore").require("More").
                    require("WolfieKnows"))
    def handle_tell_more(self, message: Message):
        """ Follow up query handler, "tell me more"."""
        self.speak_result()

    # common query integration
    def CQS_match_query_phrase(self, phrase: str):
        self.log.debug("WolframAlpha query: " + phrase)
        if self.wolfie is None:
            self.log.error("WolframAlphaSkill not initialized, no response")
            return
        response = self.ask_the_wolf(phrase)
        if response:
            self.idx += 1  # spoken by common query framework
            self.log.debug("WolframAlpha response: %s", response)
            return (phrase, CQSMatchLevel.GENERAL, response,
                    {'query': phrase, 'answer': response})

    def CQS_action(self, phrase: str, data: dict):
        """ If selected show gui """
        self.display_wolfie()

    # wolfram integration
    def ask_the_wolf(self, query: str):
        # context for follow up questions
        self.set_context("WolfieKnows", query)
        results = self.wolfie.long_answer(query,
                                          context={"lang": self.lang})
        self.idx = 0
        self.last_query = query
        self.results = [s for s in results if s.get("title") not in self.skips]
        if len(self.results):
            return self.results[0]["summary"]
        self.log.debug("WolframAlpha had no answers for %s", query)

    def display_wolfie(self):
        if not can_use_gui(self.bus):
            return
        image = None
        # issues can happen if skill reloads
        # eg. "tell me more" -> invalid self.idx
        if self.idx < len(self.results):
            image = self.results[self.idx].get("img")
        if self.last_query:
            image = image or self.wolfie.visual_answer(self.last_query,
                                                       context={"lang": self.lang})
        if image:
            self.gui["wolfram_image"] = image
            # scrollable full result page
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
                ans = ans.replace(" | ", "; ")
                self.speak(ans)
            self.idx += 1


if __name__ == "__main__":
    d = WolframAlphaSolver()

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
