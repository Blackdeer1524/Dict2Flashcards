import json
import os
import re

import bs4
import requests

from .. import config_management, parsers_return_types

PLUGIN_NAME = os.path.split(os.path.dirname(__file__))[-1]

_CONF_VALIDATION_SCHEME = {"timeout": (1, [int, float], [])}

_CONF_DOCS = """
timeout:
    Request timeout in seconds
    type: integer
    default value: 1
"""

config = config_management.LoadableConfig(
    config_location=os.path.dirname(__file__),
    validation_scheme=_CONF_VALIDATION_SCHEME,
    docs=_CONF_DOCS,
)


def get(word: str):  # -> parsers_return_types.IMAGE_SCRAPPER_RETURN_T:
    link = f"https://www.google.com/search?tbm=isch&q={word}"
    user_agent = (
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/114.0"
    )
    headers = {"User-Agent": user_agent}
    try:
        r = requests.get(link, headers=headers, timeout=config["timeout"])
        r.raise_for_status()
    except requests.RequestException:
        return [], f"[{PLUGIN_NAME}]: Couldn't get a web page!"

    html = r.text
    soup = bs4.BeautifulSoup(r.text, "html.parser")
    rg_meta = soup.find_all("div", {"class": "rg_meta"})
    metadata = [json.loads(e.text) for e in rg_meta]
    results = [d["ou"] for d in metadata]

    batch_size = yield
    if not results:
        regex = re.escape("AF_initDataCallback({")
        regex += r"[^<]*?data:[^<]*?" + r"(\[[^<]+\])"

        re.compile(r"[^<]*?data:[^<]*?")

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
                try:
                    for d in data[56][1][0][0][1][0]:
                        try:
                            results.append(d[0][0]["444383007"][1][3][0])
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

    image_url_gen = get("test")
    try:
        next(image_url_gen)
        while True:
            urls, error_message = image_url_gen.send(3)
            pprint(urls)
    except StopIteration as exception:
        pprint(exception.value)
