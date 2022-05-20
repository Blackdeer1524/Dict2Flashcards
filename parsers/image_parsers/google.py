import requests
import bs4
import re
import json
from typing import Iterator
import os


FILE_PATH = os.path.dirname(__file__)


def get_image_links(word, batch_size=5) -> Iterator[tuple[list[str], str]]:
    link = f"https://www.google.com/search?tbm=isch&q={word}&safe=active"
    user_agent = "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                 "Chrome/70.0.3538.67 Safari/537.36"
    headers = {'User-Agent': user_agent}
    try:
        r = requests.get(link, headers=headers, timeout=5)
        r.raise_for_status()
    except Exception:
        return [], f"{FILE_PATH} couldn't get web page!"

    html = r.text
    soup = bs4.BeautifulSoup(r.text, "html.parser")
    rg_meta = soup.find_all("div", {"class": "rg_meta"})
    metadata = [json.loads(e.text) for e in rg_meta]
    results = [d["ou"] for d in metadata]

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
                            yield results, ""
                    except Exception as e:
                        pass
            except Exception as e:
                pass
    # except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
    #     messagebox.showerror("Ошибка", "Ошибка получения web-страницы!\nПроверьте подключение к интернету.")
    if not len(results) % batch_size:
        yield results, ""
