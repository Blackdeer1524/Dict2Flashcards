from collections import Counter
from typing import Callable, Generator, Optional, TypedDict, TypeVar, Sized

from ..app_utils.cards import Card
from ..consts import CardFormat
from ..consts.parser_types import TypedParserName
from ..consts.paths import *
from ..plugins_management.config_management import (LoadableConfig,
                                                    LoadableConfigProtocol)
from .wrappers import WrappedBatchGeneratorProtocol, CardGeneratorProtocol, GeneratorReturn


class ChainConfig(LoadableConfig):
    def __init__(self,
                 config_dir: str,
                 config_name: str,
                 name_config_pairs: list[tuple[TypedParserName, LoadableConfigProtocol]],
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
        for enum_name, (name, config) in zip(get_enumerated_names([item[0] for item in name_config_pairs]),
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


BATCH_T = TypeVar("BATCH_T", bound=Sized)
class ChainOfGenerators(WrappedBatchGeneratorProtocol[BATCH_T]):
    name: str
    config: ChainConfig

    def __init__(self,
                chain_name: str,
                chain_data: CHAIN_INFO_T,
                generator_getter: Callable[[TypedParserName, CHAIN_INFO_T], WrappedBatchGeneratorProtocol]):
        object.__setattr__(self, "name", chain_name)

        if (requested_chain_info := chain_data.get(chain_name)) is None:
            raise ValueError(f"{self.__class__.__name__}: {chain_name} not found")

        self.enum_name2get_sentences_functions: dict[str, 
                                                     Callable[[str, CardFormat], 
                                                              Generator[list[GeneratorReturn[BATCH_T]], 
                                                                        int, 
                                                                        list[GeneratorReturn[BATCH_T]]]]] = {}
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

    def get(self, word: str, card_data: CardFormat) -> Generator[list[GeneratorReturn[BATCH_T]], int, list[GeneratorReturn[BATCH_T]]]:
        batch_size = yield  # type: ignore
        
        res: list[GeneratorReturn[BATCH_T]] = []
        res_total_length = 0

        for i, (enum_name, get_sentences_generator) in enumerate(self.enum_name2get_sentences_functions.items()):
            self.config.update_config(enum_name)
            sent_generator = get_sentences_generator(word, card_data)
            next(sent_generator)  # it is guaranteed that it will start without errors

            while True: 
                try:
                    res.extend(sent_generator.send(batch_size))
                except StopIteration as e:
                    res.extend(e.value)
                    break
                finally:
                    res_total_length += len(res[-1].result)
                    object.__setattr__(res, "name", f"{self.name}::{enum_name}")
                    if i == len(self.enum_name2get_sentences_functions) - 1:
                        return res
                    batch_size = yield res
        return res

SentenceParsersChain = ChainOfGenerators[list[str]]
ImageParsersChain    = ChainOfGenerators[list[str]]
AudioGettersChain    = ChainOfGenerators[tuple[list[str], list[str]]]
