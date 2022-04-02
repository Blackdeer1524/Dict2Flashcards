import requests
import bs4


def get_image_links(word):
    user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
    headers = {'User-Agent': user_agent}
    link = "https://www.gettyimages.com/photos/{}".format(word)
    page = requests.get(link, headers=headers, timeout=5)
    soup = bs4.BeautifulSoup(page.content, "html.parser")
    
    gallery = soup.find("div", {"class": "GalleryItems-module__searchContent___3eEaB"})
    
    images = [] if gallery is None else gallery.find_all("div",
                                                         {"class": "MosaicAsset-module__galleryMosaicAsset___3lcaf"})
    results = []
    for image_block in images:
        found = image_block.find("a", {"class": "MosaicAsset-module__link___15w9c"})
        if found is not None:
            preview_image_link = found.get("href")
            if preview_image_link is not None:
                split_preview_image_link = preview_image_link.split("/")
                image_name, image_id = split_preview_image_link[-2], split_preview_image_link[-1]
                image_link = f"https://media.gettyimages.com/photos/{image_name}-id{image_id}"
                results.append(image_link)
    return results
