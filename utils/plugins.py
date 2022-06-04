import importlib
import pkgutil
from dataclasses import dataclass

from utils.storages import FrozenDict
import parsers.image_parsers
import parsers.word_parsers.local
import parsers.word_parsers.web
import parsers.sentence_parsers


@dataclass(init=False, frozen=True, repr=False)
class PluginLoader:
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

        super().__setattr__("web_word_parsers", FrozenDict({name: (module.translate, module.define)
                                                            for name, module in
                                                            parse_namespace(parsers.word_parsers.web).items()}))
        super().__setattr__("local_word_parsers", FrozenDict({name: (module.translate, module.DICTIONARY_PATH)
                                                              for name, module in
                                                              parse_namespace(parsers.word_parsers.local).items()}))
        super().__setattr__("web_sent_parsers", FrozenDict({name: (module.get_sentence_batch)
                                                            for name, module in
                                                            parse_namespace(parsers.sentence_parsers).items()}))
        super().__setattr__("image_parsers", FrozenDict({name: (module.get_image_links)
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


plugins = PluginLoader()