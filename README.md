# ovos-skill-wolfie

[![PyPI](https://img.shields.io/pypi/v/ovos-skill-wolfie)](https://pypi.org/project/ovos-skill-wolfie/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)

This is a Wolfram Alpha skill for [OpenVoiceOS](https://openvoiceos.org). It adds a voice interface on top of [OpenVoiceOS/ovos-wolfram-alpha-plugin](https://github.com/OpenVoiceOS/ovos-wolfram-alpha-plugin), which sends the queries to Wolfram Alpha and returns the answers.

The skill answers in three ways:

- **Explicit intent**: this skill handles utterances that name Wolfram Alpha directly, for example "ask the wolf what is the speed of light".
- **Common Query**: the [OVOS Common Query pipeline](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin) handles general knowledge questions, for example "how tall is Mount Everest?". The pipeline asks all registered knowledge skills and picks the highest-confidence answer.
- **Fallback**: if no intent or pipeline handler answers, Wolfram Alpha gets a last chance to respond before OVOS says "I don't understand".

---

## Installation

```bash
pip install ovos-skill-wolfie
```

An [API key](https://products.wolframalpha.com/api/) is required. Configure it in the skill settings:

```json
{
  "appid": "YOUR-WOLFRAM-API-KEY"
}
```

---

## Explicit intent utterances

These always route to this skill because they name Wolfram or "the wolf" explicitly:

- "Ask the wolf what is the speed of light"
- "Ask Wolfram Alpha about the population of Japan"
- "Search Wolfram for the boiling point of ethanol"
- "What does Wolfram say about the Eiffel Tower?"

## Common Query utterances

These go through the pipeline. Wolfram answers if it wins:

- "How tall is Mount Everest?"
- "What's 18 times 4?"
- "How many inches in a meter?"
- "When was The Rocky Horror Picture Show released?"
- "What is Madonna's real name?"

---

## Common Query pipeline

When the [Common Query pipeline plugin](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin) is active, this skill competes against other knowledge skills, for example Wikipedia and WordNet, to answer general questions. The pipeline picks the response with the highest confidence score.

---

## Fallback

This skill also registers as a fallback handler at priority 91. If no intent or pipeline handler answers an utterance, Wolfram Alpha gets a last chance to respond before OVOS says "I don't know".

---

## Related projects

- [OpenVoiceOS/ovos-wolfram-alpha-plugin](https://github.com/OpenVoiceOS/ovos-wolfram-alpha-plugin): sends the queries to Wolfram Alpha and parses the answers. This skill depends on it.
- [OpenVoiceOS/ovos-common-query-pipeline-plugin](https://github.com/OpenVoiceOS/ovos-common-query-pipeline-plugin): the Common Query pipeline that ranks answers from this skill against other knowledge skills.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
