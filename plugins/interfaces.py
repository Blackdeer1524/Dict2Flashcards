from typing import Protocol
from parsers.return_types import SentenceGenerator, ImageGenerator
from utils.storages import FrozenDict


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


class CardProcessingInterface(Protocol):
    @staticmethod
    def get_saving_image_name(word: str, image_source: str, dict_tags: dict) -> str:
        ...

    @staticmethod
    def get_card_image_name(saved_image_path: str) -> str:
        ...

    @staticmethod
    def get_save_audio_name(word: str, dict_tags: dict, word_parser_name: str) -> str:
        ...

    @staticmethod
    def get_card_audio_name(saved_audio_path: str) -> str:
        ...

    @staticmethod
    def process_dict_tags(tags: dict) -> dict:
        ...

