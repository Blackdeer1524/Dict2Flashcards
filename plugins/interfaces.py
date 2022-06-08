from typing import Callable, Protocol
from parsers.return_types import SentenceGenerator, ImageGenerator
from dataclasses import dataclass, field


class WebWordParserInterface(Protocol):
    @staticmethod
    def define(word: str) -> dict:
        ...

    @staticmethod
    def translate(word: str, word_dict: dict) -> dict:
        ...


@dataclass(slots=True, repr=False, frozen=True, eq=False, order=False)
class WebWordParserContainer:
    source_module: WebWordParserInterface
    define: Callable[[str], dict] = field(init=False)
    translate: Callable[[str, dict], dict] = field(init=False)

    def __post_init__(self):
        super().__setattr__("define", self.source_module.define)
        super().__setattr__("translate", self.source_module.translate)


class LocalWordParserInterface(Protocol):
    DICTIONARY_PATH: str

    @staticmethod
    def translate(word: str, word_dict: dict) -> dict:
        ...


@dataclass(slots=True, repr=False, frozen=True, eq=False, order=False)
class LocalWordParserContainer:
    source_module: LocalWordParserInterface
    local_dict_name: str = field(init=False)
    translate: Callable[[str], dict] = field(init=False)

    def __post_init__(self):
        super().__setattr__("local_dict_name", self.source_module.DICTIONARY_PATH)
        super().__setattr__("translate", self.source_module.translate)


class WebSentenceParserInterface(Protocol):
    @staticmethod
    def get_sentence_batch(word: str, size: int) -> SentenceGenerator:
        ...


@dataclass(slots=True, repr=False, frozen=True, eq=False, order=False)
class WebSentenceParserContainer:
    source_module: WebSentenceParserInterface
    get_sentence_batch: Callable[[str, int], SentenceGenerator] = field(init=False)

    def __post_init__(self):
        super().__setattr__("get_sentence_batch", self.source_module.get_sentence_batch)


class ImageParserInterface(Protocol):
    @staticmethod
    def get_image_links(word: str) -> ImageGenerator:
        ...


class ImageParserContainer:
    source_module: ImageParserInterface
    get_image_links: Callable[[str], ImageGenerator] = field(init=False)

    def __post_init__(self):
        super().__setattr__("get_sentence_batch", self.source_module.get_image_links)

