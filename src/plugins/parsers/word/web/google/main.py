import os

import requests

from .. import config_management, consts

FILE_PATH = os.path.split(os.path.dirname(__file__))[-1]

SCHEME_DOCS = """
tags: {
        pos: part of speach (list[str])
    }
    """

_CONFIG_DOCS = """
timeout
    Request timeout in seconds
    type: integer | float
    default value: 1
"""

_CONF_VALIDATION_SCHEME = {"timeout": (1, [int, float], [])}

config = config_management.LoadableConfig(
    config_location=os.path.dirname(__file__),
    validation_scheme=_CONF_VALIDATION_SCHEME,
    docs=_CONFIG_DOCS,
)


API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) ApplewebKit/537.36 (KHTML, like Gecko) "
    "Chrome/70.0.3538.67 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}


def define(word: str) -> tuple[list[consts.CardFormat], str]:
    rsp = requests.get(f"{API_URL}/{word}", timeout=config["timeout"], headers=HEADERS)
    json_rsp = None
    try:
        rsp.raise_for_status()
        json_rsp = rsp.json()
    except requests.exceptions.JSONDecodeError as e:
        return [], f"{FILE_PATH} couldn't parse response: {e}"
    except requests.RequestException as e:
        return [], f"{FILE_PATH} couldn't make request: {e}"
    except Exception as e:
        return [], f"{FILE_PATH} fatal: {e}"

    res = []
    for b in json_rsp:
        word = b.get("word", "")
        audios = [i["audio"] for i in b.get("phonetics", [])]
        for m in b.get("meanings", []):
            pos = m["partOfSpeech"]
            for d in m.get("definitions", []):
                definition = d["definition"]
                card = {
                    "word": word,
                    "definition": definition,
                    "audio_links": audios,
                    "tags": {"pos": pos},
                }
                example = d.get("example", "")
                if example:
                    card["examples"] = [example]
                res.append(card)
    return res, ""
