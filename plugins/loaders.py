import importlib
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable
from typing import Protocol

import parsers.image_parsers
import parsers.sentence_parsers
import parsers.word_parsers.local
import parsers.word_parsers.web
from consts.paths import LOCAL_MEDIA_DIR
from parsers.return_types import ImageGenerator, SentenceGenerator
from plugins.containers import ImageParserContainer
from plugins.containers import LocalWordParserContainer
from plugins.containers import WebSentenceParserContainer
from plugins.containers import WebWordParserContainer
from utils.cards import WebCardGenerator, LocalCardGenerator
from utils.storages import FrozenDict


class PluginError(Exception):
    pass


class UnknownPluginName(PluginError):
    pass


def parse_namespace(namespace) -> dict:
    def iter_namespace(ns_pkg):
        # Specifying the second argument (prefix) to iter_modules makes the
        # returned name an absolute name instead of a relative one. This allows
        # import_module to work without having to do additional modification to
        # the name.
        return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

    res = {}
    for finder, name, ispkg in iter_namespace(namespace):
        parser_trunc_name = name.split(sep=".")[-1]
        res[parser_trunc_name] = importlib.import_module(name)
    return res


class ABCPluginLoader(ABC):
    @abstractmethod
    def load(self, callback: Callable[[Exception], None]) -> None:
        pass

    @abstractmethod
    def get(self, name: str) -> Protocol:
        pass


class WebWordParsersLoader(ABCPluginLoader):
    web_word_parsers: dict[str, WebWordParserContainer]

    def __init__(self):
        self.web_word_parsers = {}

    def load(self, callback: Callable[[Exception], None]) -> None:
        for name, module in parse_namespace(parsers.word_parsers.web).items():
            try:
                self.web_word_parsers[name] = \
                    WebWordParserContainer(module)
            except AttributeError as e:
                callback(e)

    def get(self, name: str) -> WebWordParserContainer:
        if value := self.web_word_parsers.get(name) is not None:
            return value
        raise UnknownPluginName(f"Unknown web word parser: {name}")


class LocalWordParsersLoader(ABCPluginLoader):
    local_word_parsers: dict[str, LocalWordParserContainer]

    def __init__(self):
        self.local_word_parsers = {}

    def load(self, callback: Callable[[Exception], None]) -> None:
        for name, module in parse_namespace(parsers.word_parsers.local).items():
            try:
                self.local_word_parsers[name] = LocalWordParserContainer(module)
            except AttributeError as e:
                callback(e)

    def get(self, name: str) -> LocalWordParserContainer:
        if value := self.local_word_parsers.get(name) is not None:
            return value
        raise UnknownPluginName(f"Unknown local word parser: {name}")


class WebSentenceParsersLoader(ABCPluginLoader):
    web_sentence_parsers: dict[str, WebSentenceParserContainer]

    def __init__(self):
        self.web_sentence_parsers = {}

    def load(self, callback: Callable[[Exception], None]) -> None:
        for name, module in parse_namespace(parsers.sentence_parsers).items():
            try:
                self.web_sentence_parsers[name] = \
                    WebSentenceParserContainer(module)
            except AttributeError as e:
                callback(e)

    def get(self, name: str) -> WebSentenceParserContainer:
        if value := self.web_sentence_parsers.get(name) is not None:
            return value
        raise UnknownPluginName(f"Unknown web sentence parser: {name}")


class ImageParsersLoader(ABCPluginLoader):
    image_parsers: dict[str, ImageParserContainer]

    def __init__(self):
        self.image_parsers = {}

    def load(self, callback: Callable[[Exception], None]) -> None:
        for name, module in parse_namespace(parsers.image_parsers).items():
            try:
                self.image_parsers[name] = \
                    ImageParserContainer(module)
            except AttributeError as e:
                callback(e)

    def get(self, name: str) -> ImageParserContainer:
        if value := self.image_parsers.get(name) is not None:
            return value
        raise UnknownPluginName(f"Unknown image parser: {name}")



@dataclass(init=False, frozen=True, repr=False)
class _PluginLoader:
    web_word_parsers:   FrozenDict
    local_word_parsers: FrozenDict
    web_sent_parsers:   FrozenDict
    image_parsers:      FrozenDict

    def __init__(self):


        super().__setattr__("web_word_parsers", FrozenDict({name: {"item_converter": module.translate,
                                                                   "parsing_function": module.define}
                                                            for name, module in
                                                            parse_namespace(parsers.word_parsers.web).items()}))
        super().__setattr__("local_word_parsers", FrozenDict({name: {"item_converter": module.translate,
                                                                     "local_dict_path": LOCAL_MEDIA_DIR / f"{module.DICTIONARY_PATH}.json"}
                                                              for name, module in
                                                              parse_namespace(parsers.word_parsers.local).items()}))
        super().__setattr__("web_sent_parsers", FrozenDict({name: module.get_sentence_batch
                                                            for name, module in
                                                            parse_namespace(parsers.sentence_parsers).items()}))
        super().__setattr__("image_parsers", FrozenDict({name: module.get_image_links
                                                         for name, module in
                                                         parse_namespace(parsers.image_parsers).items()}))

    def __repr__(self):
        indent = "\n\t"

        res = self.__class__.__name__
        for name, keys in zip(("Web word parsers", "Local word parsers", "Web sentence parsers", "Image Parsers"),
                              (self.web_word_parsers.keys(), self.local_word_parsers.keys(),
                               self.web_sent_parsers.keys(), self.image_parsers.keys())):
            res += f"\n{name}{indent}{indent.join(keys)}"
        return res

    def get_web_card_generator(self, name: str) -> WebCardGenerator:
        if (args := self.web_word_parsers.get(name)) is None:
            raise UnknownPluginName("Unknown WebCardGenerator!")
        return WebCardGenerator(**args)

    def get_local_card_generator(self, name: str) -> LocalCardGenerator:
        if (args := self.local_word_parsers.get(name)) is None:
            raise UnknownPluginName("Unknown LocalCardGenerator!")
        return LocalCardGenerator(**args)

    def get_sentence_parser(self, name: str) -> Callable[[str, int], SentenceGenerator]:
        if (gen := self.web_sent_parsers.get(name)) is None:
            raise UnknownPluginName("Unknown sentence parser!")
        return gen

    def get_image_parser(self, name: str) -> Callable[[str], ImageGenerator]:
        if (gen := self.image_parsers.get(name)) is None:
            raise UnknownPluginName("Unknown image parser!")
        return gen


plugins = _PluginLoader()
