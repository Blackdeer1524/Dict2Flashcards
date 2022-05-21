import requests
import bs4
import re
import json
from typing import Generator, Any
import os


FILE_PATH = os.path.dirname(__file__)


def get_image_links(word: Any) -> Generator[tuple[list[str], str], int, tuple[list[str], str]]:
    link = f"https://www.google.com/search?tbm=isch&q={word}&safe=active"
    user_agent = "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                 "Chrome/70.0.3538.67 Safari/537.36"
    headers = {'User-Agent': user_agent}
    try:
        r = requests.get(link, headers=headers, timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        return [], f"{FILE_PATH} couldn't get a web page!"

    html = r.text
    soup = bs4.BeautifulSoup(r.text, "html.parser")
    rg_meta = soup.find_all("div", {"class": "rg_meta"})
    metadata = [json.loads(e.text) for e in rg_meta]
    results = [d["ou"] for d in metadata]

    batch_size = yield
    if not results:
        regex = re.escape("AF_initDataCallback({")
        regex += r'[^<]*?data:[^<]*?' + r'(\[[^<]+\])'

        for txt in re.findall(regex, html):
            data = json.loads(txt)

            try:
                for d in data[31][0][12][2]:
                    try:
                        results.append(d[1][3][0])
                        if not len(results) % batch_size:
                            batch_size = yield results, ""
                            results = []
                    except Exception as exception:
                        pass
            except Exception as exception:
                pass
    return results, ""


if __name__ == "__main__":
    from pprint import pprint

    image_url_gen = get_image_links("test")
    try:
        next(image_url_gen)
        while True:
            urls, error_message = image_url_gen.send(1000)
            pprint(urls)
    except StopIteration as exception:
        pprint(exception.value)
