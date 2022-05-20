import requests
import bs4
import re
from typing import Iterator


def get_sentence_batch(word: str, step: int = 5) -> Iterator[tuple[list, bool]]:
    re_pattern = re.compile("^(.?\d+.? )")
    try:
        page = requests.get(f"https://sentencedict.com/{word}.html")
        st_code = page.status_code
        if st_code == 200:
            soup = bs4.BeautifulSoup(page.content, "html.parser")
        else:
            return [], True
        sentences_block = soup.find("div", {"id": "all"})
        if sentences_block is not None:
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
        else:
            yield [], False
    except Exception:
        yield [], True
