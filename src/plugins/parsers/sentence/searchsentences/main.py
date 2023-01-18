import os

import bs4
import requests

from .. import config_management, parsers_return_types

FILE_PATH = os.path.split(os.path.dirname(__file__))[-1]

_CONF_VALIDATION_SCHEME = {
    "timeout": (1, [int, float], [])
}

_CONF_DOCS = """
timeout:
    Request timeout in seconds
    type: integer, float
    default value: 1
"""

config = config_management.LoadableConfig(config_location=os.path.dirname(__file__),
                                          validation_scheme=_CONF_VALIDATION_SCHEME,
                                          docs=_CONF_DOCS)


def get(word: str, card_data: dict) -> parsers_return_types.SENTENCE_SCRAPPER_RETURN_T:
    try:
        page = requests.get(f"https://searchsentences.com/words/{word}-in-a-sentence",
                            timeout=config["timeout"])
        page.raise_for_status()
    except requests.RequestException as e:
        return [], f"{FILE_PATH} couldn't get a web page: {e}"

    soup = bs4.BeautifulSoup(page.content, "html.parser")
    src = soup.find_all("li", {"class": "sentence-row"})
    sentences = []
    for sentence_block in src:
        if (sentence := sentence_block.find("span")) is None:
            continue
        text = sentence.get_text()
        if text:
            sentences.append(text)

    sentences.sort(key=len)
    i = 0
    size = yield
    while i < len(sentences):
        size = yield sentences[i:i + size], ""
        i += size

    return [], ""
