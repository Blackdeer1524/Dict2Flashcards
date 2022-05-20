from tkinter import Toplevel
from typing import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from PIL import Image


class ImageSearch:
    def __init__(self, url_scrapper: Callable[[str], Iterator[tuple[list[str], str]]] = lambda x: [],
                 n_display_rows=1, n_display_cols=1):
        self.__n_display_rows = n_display_rows
        self.__n_display_cols = n_display_cols
        self.__batch_size = n_display_rows * n_display_cols

        self.__url_scrapper = url_scrapper
        self.__url_generator: Callable[[str], Iterator[tuple[list[str], str]]] = url_scrapper
        self.__start_urls = []
        self.__start_images: list[Image] = []

    def start(self, start_urls: list[str] = None, start_images=None):
        self.__start_urls = start_urls if start_urls is not None else []
        self.__start_images = start_images if start_urls is not None else []

    def display(self):
        for i in range(0, len(self.__start_images), self.__batch_size):
            pass


