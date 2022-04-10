import requests
import bs4
import re


def get_sentence_batch(word, step=5):
    re_pattern = re.compile("^(.?\d+.? )")
    page = requests.get(f"https://sentencedict.com/{word}.html")
    st_code = page.status_code
    if st_code == 200:
        soup = bs4.BeautifulSoup(page.content, "html.parser")
    else:
        raise AttributeError
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
            yield sentences[i:i + step]
    else:
        yield []
