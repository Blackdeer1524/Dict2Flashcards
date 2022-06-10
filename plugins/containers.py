from dataclasses import dataclass, field
from typing import Callable

from parsers.return_types import SentenceGenerator, ImageGenerator
from plugins.interfaces import ImageParserInterface
from plugins.interfaces import LocalWordParserInterface
from plugins.interfaces import WebSentenceParserInterface
from plugins.interfaces import WebWordParserInterface


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False)
class WebWordParserContainer:
    define: Callable[[str], list[(str, dict)]] = field(init=False)
    translate: Callable[[str, dict], dict] = field(init=False)

    def __init__(self, source_module: WebWordParserInterface):
        super().__setattr__("define", source_module.define)
        super().__setattr__("translate", source_module.translate)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False)
class LocalWordParserContainer:
    local_dict_name: str = field(init=False)
    translate: Callable[[str], dict] = field(init=False)

    def __init__(self, source_module: LocalWordParserInterface):
        super().__setattr__("local_dict_name", source_module.DICTIONARY_PATH)
        super().__setattr__("translate", source_module.translate)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False)
class WebSentenceParserContainer:
    get_sentence_batch: Callable[[str, int], SentenceGenerator] = field(init=False)

    def __init__(self, source_module: WebSentenceParserInterface):
        super().__setattr__("get_sentence_batch", source_module.get_sentence_batch)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False)
class ImageParserContainer:
    get_image_links: Callable[[str], ImageGenerator] = field(init=False)

    def __init__(self, source_module: ImageParserInterface):
        super().__setattr__("get_image_links", source_module.get_image_links)
