import importlib
import pkgutil
from dataclasses import dataclass, field

import parsers.image_parsers
import parsers.word_parsers.local
import parsers.word_parsers.web
import parsers.sentence_parsers


@dataclass(init=False, frozen=True, repr=False)
class PluginLoader:
    web_word_parsers:   dict
    local_word_parsers: dict
    web_sent_parsers:   dict
    image_parsers:      dict
    
    def __init__(self):
        def parse_namespace(namespace, name_prefix: str) -> dict:
            def iter_namespace(ns_pkg):
                # Specifying the second argument (prefix) to iter_modules makes the
                # returned name an absolute name instead of a relative one. This allows
                # import_module to work without having to do additional modification to
                # the name.
                return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

            res = {}
            for finder, name, ispkg in iter_namespace(namespace):
                parser_trunc_name = name.split(sep=".")[-1]
                if parser_trunc_name.startswith(name_prefix):
                    res[parser_trunc_name] = importlib.import_module(name)
            return res

        super().__setattr__("web_word_parsers", parse_namespace(parsers.word_parsers.web, ""))
        super().__setattr__("local_word_parsers", parse_namespace(parsers.word_parsers.local, ""))
        super().__setattr__("web_sent_parsers", parse_namespace(parsers.sentence_parsers, "web"))
        super().__setattr__("image_parsers", parse_namespace(parsers.image_parsers, ""))

    def __repr__(self):
        indent = "\n\t"

        res = self.__class__.__name__
        for name, keys in zip(("Web word parsers", "Local word parsers", "Web sentence parsers", "Image Parsers"),
                              (self.web_word_parsers.keys(), self.local_word_parsers.keys(),
                               self.web_sent_parsers.keys(), self.image_parsers.keys())):
            res += f"\n{name}{indent}{indent.join(keys)}"
        return res


print(PluginLoader())