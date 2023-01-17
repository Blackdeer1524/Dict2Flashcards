import importlib
import os.path
import pkgutil
from abc import ABC
from collections import Counter
from dataclasses import dataclass
from types import ModuleType
from typing import (Callable, ClassVar, Generator, Generic, Iterable, Optional,
                    Type, TypedDict, TypeVar, Union)

from .. import plugins
from ..consts import CardFormat
from ..consts.parser_types import ParserType, TypedParserName
from ..consts.paths import *
from ..plugins_management.config_management import LoadableConfig, LoadableConfigProtocol
from .exceptions import LoaderError, UnknownPluginName
from ..app_utils.parser_interfaces import CardGeneratorProtocol, GeneratorReturn, SentenceGeneratorProtocol
from ..app_utils.cards import Card
from ..app_utils.plugin_wrappers import BatchGeneratorWrapper, WRAPPED_EXTERNAL_DATA_GENERATOR_T
from ..app_utils.parser_interfaces import Named, Configurable


class ChainConfig(LoadableConfig):
    def __init__(self,
                 config_dir: str,
                 config_name: str,
                 name_config_pairs: list[tuple[TypedParserName, LoadableConfig]],
                 ):
        validation_scheme = {}
        docs_list = []

        validation_scheme["query_type"] = ("all", [str], ["first_found", "all"])
        validation_scheme["error_verbosity"] = ("silent", [str], ["silent", "if_found", "all"])
        docs_list.append("""
query_type:
    How to get data from sources
    first_found: get only first available
    all: get data from all sources

error_verbosity:
    silent: doesn't save any errors
    if_found: saves errors ONLY IF found something
    all: saves all errors
""")

        validation_scheme["parsers"] = {}
        seen_config_ids = set()
        self.enum_name2config = {}
        for enum_name, (name, config) in zip(get_enumerated_names((item[0] for item in name_config_pairs)),
                                             name_config_pairs):
            self.enum_name2config[enum_name] = config
            validation_scheme["parsers"][enum_name] = config.validation_scheme
            if id(config) not in seen_config_ids:
                docs_list.append("{}:\n{}".format(name, config.docs.replace("\n", "\n" + " " * 4)))
                seen_config_ids.add(id(config))
            config.save()

        docs = "\n\n".join(docs_list)
        super(ChainConfig, self).__init__(validation_scheme=validation_scheme,
                                          docs=docs,
                                          config_location=config_dir,
                                          _config_file_name=config_name)
        self.load()

    def update_children_configs(self):
        for enum_name, config in self.enum_name2config.items():
            config.data = self["parsers"][enum_name]

    def update_config(self, enum_name: str):
        self.enum_name2config[enum_name].data = self["parsers"][enum_name]

    def load(self) -> Optional[LoadableConfig.SchemeCheckResults]:
        errors = super(ChainConfig, self).load()
        self.update_children_configs()
        return errors

    def save(self):
        self.update_children_configs()
        super(ChainConfig, self).save()


def get_enumerated_names(names: list[TypedParserName]) -> list[str]:
    seen_names_count = Counter((name.full_name for name in names))
    seen_so_far = {key: value for key, value in seen_names_count.items()}
    enum_names = []
    for parser_data in names:
        name = parser_data.full_name
        if seen_names_count[name] == 1:
            enum_names.append(name)
        else:
            seen_so_far[name] -= 1
            enum_names.append(f"{name} [{seen_names_count[name] - seen_so_far[name]}]")
    return enum_names


class ChainConfigurations(TypedDict):
    chain:       list[TypedParserName]
    config_name: str


CHAIN_NAME_T  = str
PARSER_NAME_T = str
CHAIN_INFO_T  = dict[CHAIN_NAME_T, ChainConfigurations] 


class CardGeneratorsChain(CardGeneratorProtocol):
    name: str
    config: ChainConfig
    scheme_docs: str

    def __init__(self,
                 chain_name: str,
                 chain_data: CHAIN_INFO_T,
                 card_generator_getter: Callable[[TypedParserName, CHAIN_INFO_T], CardGeneratorProtocol]):
        object.__setattr__(self, "name", chain_name)
        self.enum_name2generator: dict[str, CardGeneratorProtocol] = {}

        parser_configs = []

        if (requested_chain_info := chain_data.get(chain_name)) is None:
            raise ValueError(f"{self.__class__.__name__}: {chain_name} not found")

        scheme_docs_list = []

        parser_data: TypedParserName
        enum_parser_name: str
        for parser_data, enum_parser_name in zip(requested_chain_info["chain"], get_enumerated_names(requested_chain_info["chain"])):
            generator = card_generator_getter(parser_data, chain_data)
            self.enum_name2generator[enum_parser_name] = generator
            parser_configs.append(generator.config)
            scheme_docs_list.append("{}\n{}".format(parser_data.full_name, generator.scheme_docs.replace("\n", "\n |\t")))

        config: ChainConfig = ChainConfig(config_dir=str(CHAIN_WORD_PARSERS_DATA_DIR),
                                          config_name=requested_chain_info["config_name"],
                                          name_config_pairs=[(parser_name, config) for parser_name, config in
                                                             zip(requested_chain_info["chain"], parser_configs)])
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "scheme_docs", "\n".join(scheme_docs_list))

    def get(self,
            query: str,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        res: list[GeneratorReturn[list[Card]]] = []
        for enum_name, generator in self.enum_name2generator.items():
            self.config.update_config(enum_name)
            current_generator_results = generator.get(query, additional_filter)
        
            for i, parser_result in enumerate(current_generator_results):
                if self.config["error_verbosity"] == "silent":
                    object.__setattr__(parser_result, "error_message", "")
                elif self.config["error_verbosity"] == "if_found" and not parser_result.result and parser_result.error_message:
                    current_generator_results.pop(i)
            
            res.extend(current_generator_results)
            if self.config["query_type"] == "first_found" and res:
                break
        return res


BATCH_T = TypeVar("BATCH_T")


from typing import Protocol

T = TypeVar("T")
WRAPPED_BATCH_T = Generator[GeneratorReturn[T], int, GeneratorReturn[T]]

class WrappedBatchGeneratorProtocol(Protocol):
    name: str
    config: LoadableConfigProtocol
     
    def get(self, word: str, card_data: CardFormat) -> WRAPPED_BATCH_T:
        ...


class ChainOfGenerators(Named, Configurable, Generic[BATCH_T]):
    name: str
    config: ChainConfig

    def __init__(self,
                chain_name: str,
                chain_data: CHAIN_INFO_T,
                generator_getter: Callable[[TypedParserName, CHAIN_INFO_T], WrappedBatchGeneratorProtocol]):
        object.__setattr__(self, "name", chain_name)

        if (requested_chain_info := chain_data.get(chain_name)) is None:
            raise ValueError(f"{self.__class__.__name__}: {chain_name} not found")

        self.enum_name2get_sentences_functions: dict[str, Callable[[str, CardFormat], WRAPPED_BATCH_T[BATCH_T]]] = {}
        parser_configs = []
        for parser_name, enum_name in zip(requested_chain_info["chain"], get_enumerated_names(requested_chain_info["chain"])):
            batch_generator = generator_getter(parser_name, chain_data)
            self.enum_name2get_sentences_functions[enum_name] = batch_generator.get
            parser_configs.append(batch_generator.config)
        config = ChainConfig(config_dir=str(CHAIN_SENTENCE_PARSERS_DATA_DIR),
                             config_name=requested_chain_info["config_name"],
                             name_config_pairs=[(parser_name, config) for parser_name, config in
                                                 zip(requested_chain_info["chain"], parser_configs)])
        object.__setattr__(self, "config", config)

    def get(self, word: str, card_data: CardFormat) -> WRAPPED_BATCH_T[BATCH_T]:  # type: ignore
        batch_size = yield  # type: ignore
        for i, (enum_name, get_sentences_generator) in enumerate(self.enum_name2get_sentences_functions.items()):
            self.config.update_config(enum_name)
            sent_generator = get_sentences_generator(word, card_data)
            next(sent_generator)  # it is guaranteed that it will start without errors

            while True: 
                try:
                    res = sent_generator.send(batch_size)
                except StopIteration as e:
                    res = e.value
                    break
                finally:
                    object.__setattr__(res, "name", f"{self.name}::{enum_name}")
                    if i == len(self.enum_name2get_sentences_functions) - 1:
                        return res
                    batch_size = yield res
        

SentenceParsersChain = ChainOfGenerators[list[str]]
ImageParsersChain    = ChainOfGenerators[list[str]]
AudioGettersChain    = ChainOfGenerators[tuple[list[str], list[str]]]

# class SentenceParsersChain(SentenceGeneratorProtocol):
#     def __init__(self,
#                  chain_name: str,
#                  chain_data: CHAIN_INFO_T,
#                  generator_getter: Callable[[TypedParserName, CHAIN_INFO_T], BatchGeneratorWrapper]):
#         object.__setattr__(self, "name", chain_name)

#         if (requested_chain_info := chain_data.get(chain_name)) is None:
#             raise ValueError(f"{self.__class__.__name__}: {chain_name} not found")

#         self.enum_name2get_sentences_functions: dict[str, Callable[[str, CardFormat], WRAPPED_EXTERNAL_DATA_GENERATOR_T]] = {}
#         parser_configs = []
#         for parser_name, enum_name in zip(requested_chain_info["chain"], get_enumerated_names(requested_chain_info["chain"])):
#             batch_generator = generator_getter(parser_name, chain_data)
#             self.enum_name2get_sentences_functions[enum_name] = batch_generator.get
#             parser_configs.append(batch_generator.config)
#         config = ChainConfig(config_dir=str(CHAIN_SENTENCE_PARSERS_DATA_DIR),
#                              config_name=requested_chain_info["config_name"],
#                              name_config_pairs=[(parser_name, config) for parser_name, config in
#                                                  zip(requested_chain_info["chain"], parser_configs)])
#         object.__setattr__(self, "config", config)

#     def get(self, word: str, card_data: CardFormat) -> WRAPPED_EXTERNAL_DATA_GENERATOR_T[list[str]]:
#         batch_size = yield  # type: ignore
#         for enum_name, get_sentences_generator in self.enum_name2get_sentences_functions.items():
#             sent_generator = get_sentences_generator(word, card_data)
#             next(sent_generator)  # it is guaranteed that it will start without errors

#             while True: 
#                 try:
#                     batch_size = yield sent_generator.send(batch_size)
#                 except StopIteration as e:
#                     break
#         return


# class ImageParsersChain:
#     def __init__(self,
#                     loaded_plugins: "PluginFactory",
#                     name: str,
#                     chain_data: dict[str, str | list[str]]):
#         self.loaded_plugins = loaded_plugins
#         self.name = name
#         self.enum_name2url_getting_functions: dict[str, Callable[[str], ImageGeneratorProtocol]] = {}
#         parser_configs = []
#         for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
#             parser = self.loaded_plugins.get_image_parser(
#                 name=parser_name[len(ParserType.web.prefix()) + 1:],
#                 parser_type=ParserType.web,
#                 chain_data=None)
#             self.enum_name2url_getting_functions[enum_name] = parser.get
#             parser_configs.append(parser.config)

#         self.config = ChainConfig(config_dir=CHAIN_IMAGE_PARSERS_DATA_DIR,
#                                         config_name=chain_data["config_name"],
#                                         name_config_pairs=[(parser_name, config) for parser_name, config in
#                                                             zip(chain_data["chain"], parser_configs)])

#     def get(self, word: str) -> ImageGeneratorProtocol:
#         batch_size = yield
#         for enum_name, url_getting_function in self.enum_name2url_getting_functions.items():
#             self.config.update_config(enum_name)
#             url_generator = url_getting_function(word)
#             try:
#                 next(url_generator)
#             except StopIteration as e:
#                 url_batch, error_message = e.value
#                 if url_batch or error_message:
#                     yield url_batch, error_message
#                 continue

#             while True:
#                 try:
#                     batch_size = yield url_generator.send(batch_size)
#                 except StopIteration:
#                     break
#         return [], ""

# class AudioGettersChain:
#     def __init__(self,
#                     loaded_plugins: "PluginFactory",
#                     name: str,
#                     chain_data: dict[str, str | list[str]]):
#         self.loaded_plugins = loaded_plugins
#         self.name = name
#         self.enum_name2parsers_data: dict[
#             str, tuple[ParserType, Callable[[str, dict], AudioGeneratorProtocol] | None]] = {}
#         parser_configs = []
#         for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):

#             if parser_name.startswith(ParserType.web.prefix()):
#                 parser_type = ParserType.web
#                 getter = self.loaded_plugins\
#                                     .get_audio_getter(parser_name[len(ParserType.web.prefix()) + 1:],
#                                                         ParserType.web)
#             elif parser_name.startswith(ParserType.local.prefix()):
#                 parser_type = ParserType.local
#                 getter = self.loaded_plugins\
#                                     .get_audio_getter(parser_name[len(ParserType.local.prefix()) + 1:],
#                                                         ParserType.local)
#             else:
#                 raise NotImplementedError(f"Audio getter of unknown type: {parser_name}")
#             self.enum_name2parsers_data[enum_name] = (parser_type, getter.get)
#             parser_configs.append(getter.config)

#         self.config = ChainConfig(config_dir=CHAIN_AUDIO_GETTERS_DATA_DIR,
#                                         config_name=chain_data["config_name"],  # type: ignore
#                                         name_config_pairs=[(parser_name, config) for parser_name, config
#                                                             in zip(chain_data["chain"], parser_configs)])

#     def get(self, word: str, card_data: dict) -> \
#             Generator[list[tuple[tuple[str, str], AudioData]], int, list[tuple[tuple[str, str], AudioData]]]:
#         batch_size = yield
#         results: list[tuple[tuple[str, ParserType], AudioData]] = []
#         yielded_once = False
#         for enum_name, (parser_type, get_audio_generator) in self.enum_name2parsers_data.items():
#             self.config.update_config(enum_name)

#             audio_data_generator = get_audio_generator(word, card_data)
#             try:
#                 next(audio_data_generator)
#             except StopIteration as e:
#                 _, error_message = e.value
#                 if self.config["error_verbosity"] == "silent":
#                     error_message = ""

#                 if error_message and self.config["error_verbosity"] == "all":
#                     results.append(((enum_name, parser_type), (([], []), error_message)))
#                 continue

#             while True:
#                 try:
#                     ((audios, additional_info), error_message) = audio_data_generator.send(batch_size)
#                     if self.config["error_verbosity"] == "silent":
#                         error_message = ""

#                     if audios or self.config["error_verbosity"] == "all" and error_message:
#                         results.append(((enum_name, parser_type),
#                                         ((audios, additional_info), error_message)))
#                         batch_size -= len(audios)
#                         if batch_size <= 0:
#                             batch_size = yield results
#                             yielded_once = True
#                             results = []

#                 except StopIteration as e:
#                     ((audios, additional_info), error_message) = e.value
#                     if self.config["error_verbosity"] == "silent":
#                         error_message = ""

#                     if audios or self.config["error_verbosity"] == "all" and error_message:
#                         results.append(((enum_name, parser_type),
#                                         ((audios, additional_info), error_message)))
#                         batch_size -= len(audios)
#                         if batch_size <= 0:
#                             batch_size = yield results
#                             yielded_once = True
#                             results = []
#                     break

#             if self.config["query_type"] == "first_found" and yielded_once:
#                 break
#         return results