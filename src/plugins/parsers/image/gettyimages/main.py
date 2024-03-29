import os
import re

import bs4
import requests

from .. import config_management, parsers_return_types

PLUGIN_NAME = os.path.split(os.path.dirname(__file__))[-1]

_CONF_VALIDATION_SCHEME = {
    "timeout": (1, [int, float], [])
}

_CONF_DOCS = """
timeout:
    Request timeout in seconds
    type: integer
    default value: 1
"""

config = config_management.LoadableConfig(config_location=os.path.dirname(__file__),
                                          validation_scheme=_CONF_VALIDATION_SCHEME,
                                          docs=_CONF_DOCS)


def get(word: str) -> parsers_return_types.IMAGE_SCRAPPER_RETURN_T:
    user_agent = "Mozilla/5.0 (Windows NT 6.1; Win64; x64) ApplewebKit/537.36 (KHTML, like Gecko) " \
                 "Chrome/70.0.3538.67 Safari/537.36"
    headers = {'User-Agent': user_agent}
    link = "https://www.gettyimages.com/photos/{}".format(word)
    try:
        r = requests.get(link, headers=headers, timeout=config["timeout"])
        r.raise_for_status()
    except Exception:
        return [], f"[{PLUGIN_NAME}]: Couldn't get a web page!"

    soup = bs4.BeautifulSoup(r.content, "html.parser")
    gallery = soup.find("div", {"class": re.compile("GalleryItems-module__searchContent")})
    if gallery is None:
        return [], f"[{PLUGIN_NAME}] Couldn't parse a web page!"

    images = [] if gallery is None else gallery.find_all("div",
                                                         {"class": re.compile("MosaicAsset-module__galleryMosaicAsset")})
    batch_size = yield
    results = []
    for ind, image_block in enumerate(images):
        found = image_block.find("a", {"class": re.compile("MosaicAsset-module__link")})
        if found is not None:
            preview_image_link = found.get("href")
            if preview_image_link is not None:
                split_preview_image_link = preview_image_link.split("/")
                image_name, image_id = split_preview_image_link[-2], split_preview_image_link[-1]
                image_link = f"https://media.gettyimages.com/photos/{image_name}-id{image_id}"
                results.append(image_link)
        if not ind % batch_size:
            batch_size = yield results, ""
            results = []
    return results, ""


if __name__ == "__main__":
    from pprint import pprint

    image_url_gen = get("do")
    try:
        next(image_url_gen)
        while True:
            urls, error_message = image_url_gen.send(1)
            pprint(urls)
    except StopIteration as exception:
        pprint(exception.value)