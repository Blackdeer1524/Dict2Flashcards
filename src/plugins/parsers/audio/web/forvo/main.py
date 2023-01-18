"""
Credits:
    https://github.com/Rascalov/Anki-Simple-Forvo-Audio
"""


import re

import requests.utils

from .. import config_management, parsers_return_types
from .consts import _PLUGIN_LOCATION, _PLUGIN_NAME
from .page_processing import get_audio_link, get_forvo_page

_CONFIG_DOCS = """
language_code
    audio language to fetch
    type: string

timeout
    request timeout in seconds.
    default value: 1
"""

_VALIDATION_SCHEME = {
    "language_code": ("en", [str], []),
    "timeout": (1, [int, float], [])
}

config = config_management.LoadableConfig(config_location=_PLUGIN_LOCATION,
                                          validation_scheme=_VALIDATION_SCHEME,
                                          docs=_CONFIG_DOCS)

CACHED_RESULT = {}

REMOVE_SPACES_PATTERN = re.compile(r"\s+", re.MULTILINE)


def remove_spaces(string: str) -> str:
    return re.sub(REMOVE_SPACES_PATTERN, " ", string.strip())

def get(word: str, card_data: dict) -> parsers_return_types.AUDIO_SCRAPPER_RETURN_T:
    global CACHED_RESULT

    word_with_lang_code = "{} {}".format(word, config["language_code"])

    if (audioListLis := CACHED_RESULT.get(word_with_lang_code)) is None:
        wordEncoded = requests.utils.requote_uri(word)
        forvoPage, error_message = get_forvo_page("https://forvo.com/word/" + wordEncoded, timeout=config["timeout"])
        if error_message:
            return ([], []), error_message
        speachSections = forvoPage.select("div#language-container-" + config["language_code"])
        if not len(speachSections):
            return ([], []), f"[{_PLUGIN_NAME}] Word not found (Language Container does not exist!)"
        speachSections = forvoPage.select_one("div#language-container-" + config["language_code"])
        audioListUl = speachSections.select_one("ul")
        if audioListUl is None or not len(audioListUl.findChildren(recursive=False)):
            return ([], []), f"[{_PLUGIN_NAME}] Word not found (Language Container exists, but audio not found)"
        if(config["language_code"] == "en"):
            audioListLis = forvoPage.select("li[class*=en_]")
        else:
            audioListLis = audioListUl.find_all("li")

        if audioListLis:
            CACHED_RESULT[word_with_lang_code] = audioListLis

    audio_links = []
    additional_info = []
    batch_size = yield
    for li in audioListLis:
        if (r := li.find("div")) is not None and (onclick := r.get("onclick")) is not None:
            audio_links.append(get_audio_link(onclick))
            by_whom_data = li.find("span", {"class": "info"})
            by_whom_data = remove_spaces(by_whom_data.text) if by_whom_data is not None else ""
            from_data = li.find("span", {"class": "from"})
            from_data = remove_spaces(from_data.text) if from_data is not None else ""
            additional_info.append(f"{by_whom_data}\n{from_data}") if from_data is not None else ""
            if len(audio_links) == batch_size:
                batch_size = yield ((audio_links, additional_info), "")
                audio_links = []
                additional_info = []
    return ((audio_links, additional_info), "")
