import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable

import parsers.image_parsers
import parsers.sentence_parsers
import parsers.word_parsers.local
import parsers.word_parsers.web
from parsers.return_types import ImageGenerator, SentenceGenerator
from utils.cards import WebCardGenerator, LocalCardGenerator
from utils.storages import FrozenDict
from consts.paths import LOCAL_MEDIA_DIR


class PluginError(Exception):
    pass


class UnknownPluginName(PluginError):
    pass


@dataclass(init=False, frozen=True, repr=False)
class _PluginLoader:
    web_word_parsers:   FrozenDict
    local_word_parsers: FrozenDict
    web_sent_parsers:   FrozenDict
    image_parsers:      FrozenDict

    def __init__(self):
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
