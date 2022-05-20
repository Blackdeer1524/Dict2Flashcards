from tkinter import Toplevel
from typing import Callable
from concurrent.futures import ThreadPoolExecutor


class ImageSearch:
    def __init__(self, url_scrapper: Callable[[str], list[str]] = lambda x: [], start_urls: list[str] = []):
        self.__url_scrapper = url_scrapper
        self.__url_list = start_urls

    def search(self, query: str):
        self.__url_list = self.__url_scrapper(query)
        



