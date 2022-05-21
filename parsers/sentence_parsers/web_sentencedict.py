import requests
import bs4
import re
from typing import Iterator
import os
from utils.error_handling import create_exception_message


FILE_PATH = os.path.dirname(__file__)


def get_sentence_batch(word: str, step: int = 5) -> Iterator[tuple[list, str]]:
    re_pattern = re.compile("^(.?\d+.? )")
    try:
        page = requests.get(f"https://sentencedict.com/{word}.html")
        page.raise_for_status()
        soup = bs4.BeautifulSoup(page.content, "html.parser")
        sentences_block = soup.find("div", {"id": "all"})
        if sentences_block is None:
            yield [], f"{FILE_PATH} couldn't parse a web page!"
            return

        sentences_block = sentences_block.find_all("div")
        sentences = []
        for sentence in sentences_block:
            if sentence is not None:
                text = sentence.get_text().strip()
                if text:
                    text = re.sub(re_pattern, "", text)
                    sentences.append(text)

        sentences.sort(key=len)
        for i in range(0, len(sentences), step):
            yield sentences[i:i + step], False
    except Exception as e:
        yield [], create_exception_message()
        return