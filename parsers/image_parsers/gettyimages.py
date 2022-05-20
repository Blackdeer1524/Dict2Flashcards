import requests
import bs4
from typing import Iterator
import os


FILE_PATH = os.path.dirname(__file__)


def get_image_links(word, batch_size=5) -> Iterator[tuple[list[str], str]]:
    user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
    headers = {'User-Agent': user_agent}
    link = "https://www.gettyimages.com/photos/{}".format(word)
    try:
        r = requests.get(link, headers=headers, timeout=5)
        r.raise_for_status()
    except Exception:
        return [], f"{FILE_PATH} couldn't get web page!"

    soup = bs4.BeautifulSoup(r.content, "html.parser")
    gallery = soup.find("div", {"class": "GalleryItems-module__searchContent___3eEaB"})
    if gallery is None:
        return [], f"{FILE_PATH} couldn't parse web page!"

    images = [] if gallery is None else gallery.find_all("div",
                                                         {"class": "MosaicAsset-module__galleryMosaicAsset___3lcaf"})
    results = []
    for ind, image_block in enumerate(images):
        found = image_block.find("a", {"class": "MosaicAsset-module__link___15w9c"})
        if found is not None:
            preview_image_link = found.get("href")
            if preview_image_link is not None:
                split_preview_image_link = preview_image_link.split("/")
                image_name, image_id = split_preview_image_link[-2], split_preview_image_link[-1]
                image_link = f"https://media.gettyimages.com/photos/{image_name}-id{image_id}"
                results.append(image_link)
        if not ind % batch_size:
            yield results, ""
            results.clear()
    if results:
        yield results, ""
