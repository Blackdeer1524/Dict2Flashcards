from typing import Protocol
from parsers.return_types import SentenceGenerator, ImageGenerator


class WebWordParserInterface(Protocol):
    @staticmethod
    def define(word: str) -> dict:
        ...

    @staticmethod
    def translate(word: str, word_dict: dict) -> dict:
        ...


class LocalWordParserInterface(Protocol):
    DICTIONARY_PATH: str

    @staticmethod
    def translate(word: str, word_dict: dict) -> dict:
        ...


class WebSentenceParserInterface(Protocol):
    @staticmethod
    def get_sentence_batch(word: str, size: int) -> SentenceGenerator:
        ...


class ImageParserInterface(Protocol):
    @staticmethod
    def get_image_links(word: str) -> ImageGenerator:
        ...


