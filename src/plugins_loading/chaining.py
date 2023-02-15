from collections import Counter
from typing import Callable, Literal, Generator, Optional, TypedDict, TypeVar, Sized, Iterator
import json

from ..app_utils.cards import Card
from ..consts import CardFormat, ParserType
from ..consts.parser_types import TypedParserName
from ..consts.paths import *
from ..plugins_management.config_management import (LoadableConfig,
                                                    LoadableConfigProtocol)
from .wrappers import WrappedBatchGeneratorProtocol, CardGeneratorProtocol, GeneratorReturn
from ..consts.paths import CHAIN_DATA_FILE_PATH
import itertools
from dataclasses import dataclass


class ChainConfig(LoadableConfig):
    def __init__(self,
                 config_dir: str,
                 config_name: str,
                 name_config_pairs: list[tuple[TypedParserName, LoadableConfigProtocol]],
                 ):
        validation_scheme = {}
        docs_list = []

        validation_scheme["query type"]      = ("all", [str], ["first found", "all"])
        validation_scheme["error verbosity"] = ("silent", [str], ["silent", "if found", "all"])
        docs_list.append("""
query type:
    How to get data from sources
    first found: get only first available
    all: get data from all sources

error verbosity:
    silent: doesn't save any errors
    if found: saves errors ONLY IF found something
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
                docs_list.append("{}:\n{}".format(name.full_name, config.docs.replace("\n", "\n" + " " * 4)))
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


class ChainInfoJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, dct: dict) -> dict:
        if dct.get("chain") is not None:
            dct["chain"] = [TypedParserName(parser_t=ParserType(parser_type), name=parser_name)
                            for parser_type, parser_name in dct["chain"]]
        return dct


class ChainInfoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, TypedParserName):
            return [obj.parser_t, obj.name]
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class ChainConfigurations(TypedDict):
    chain:       list[TypedParserName]
    config_name: str


CHAIN_NAME_T  = str
PARSER_NAME_T = str
CHAIN_INFO_T  = dict[CHAIN_NAME_T, ChainConfigurations] 

PossibleChainTypes = Literal[
    "word_parsers",
    "sentence_parsers",
    "image_parsers",
    "audio_getters"
]

ChainDataScheme = dict[PossibleChainTypes, CHAIN_INFO_T]
VERTEX_T = str
GRAPH_T = dict[VERTEX_T, list[VERTEX_T]]
ChainsDependencies = dict[PossibleChainTypes, list[list[VERTEX_T]]]


@dataclass(slots=True, frozen=True)
class SingleChainDependeciesInfo:
    graphs:   list[list[VERTEX_T]]
    forward:  GRAPH_T  # depending  -> list[dependencies] 
    backward: GRAPH_T  # dependency -> list[depending] 


ChainDependenciesData = dict[PossibleChainTypes, SingleChainDependeciesInfo]


class ChainDataStorage(LoadableConfig):
    data: ChainDataScheme
    _chains_dependencies: ChainDependenciesData

    def __init__(self) -> None:
        validation_scheme = {
            "word_parsers":     ({}, [dict], []),
            "sentence_parsers": ({}, [dict], []),
            "image_parsers":    ({}, [dict], []),
            "audio_getters":    ({}, [dict], []),
        }
        chaining_data_file_dir = os.path.dirname(CHAIN_DATA_FILE_PATH)
        chaining_data_file_name = os.path.basename(CHAIN_DATA_FILE_PATH)
        super().__init__(validation_scheme=validation_scheme,
                         docs="",
                         config_location=chaining_data_file_dir,
                         _config_file_name=chaining_data_file_name,
                         custom_json_decoder=ChainInfoJSONDecoder,
                         custom_json_encoder=ChainInfoJSONEncoder,
                         )

        self._chains_dependencies = {}
        self.compute_chains_dependencies()

    def compute_chains_dependencies(self) -> None:
        def compute_for_single_type(chain_type: PossibleChainTypes) -> None:
            forward = self._build_forward_graph(self[chain_type])
            backward = self._build_backward_graph(forward)
            graphs = self._split_on_non_intersecting_graphs(
                sorted_vertecies=self._toposort(backward),
                backward=backward
            )
            self._chains_dependencies[chain_type] = SingleChainDependeciesInfo(
                graphs=graphs,
                backward=backward,
                forward=forward
            )
        compute_for_single_type(chain_type="word_parsers")
        compute_for_single_type(chain_type="sentence_parsers")
        compute_for_single_type(chain_type="image_parsers")
        compute_for_single_type(chain_type="audio_getters")

    def _build_forward_graph(self, chains_of_particular_type: CHAIN_INFO_T) -> GRAPH_T:
        forward: GRAPH_T = {}
        for current_chain_name in chains_of_particular_type.keys():
            forward[current_chain_name] = []
            for dependent_chain_name in chains_of_particular_type[current_chain_name]["chain"]:
                if dependent_chain_name.parser_t == ParserType.chain:
                    if forward.get(dependent_chain_name.name) is None:
                        forward[dependent_chain_name.name] = []
                    forward[current_chain_name].append(dependent_chain_name.name)
        return forward

    def _build_backward_graph(self, forward: GRAPH_T) -> GRAPH_T:
        backward: GRAPH_T = {vertex: [] for vertex in forward.keys()}
        for vertex in forward:
            for next_vertex in forward[vertex]:
                backward[next_vertex].append(vertex)
        return backward
    
    def _toposort(self, backward: GRAPH_T) -> list[VERTEX_T]:    
        def traverse(current_vertex: VERTEX_T, 
                     seen_vertecies: set[VERTEX_T], 
                     sorted_vertecies: list[VERTEX_T]) -> None:
            if current_vertex in seen_vertecies:
                return

            for previous_vertex in backward[current_vertex]:
                traverse(previous_vertex, seen_vertecies, sorted_vertecies)
            
            seen_vertecies.add(current_vertex)
            sorted_vertecies.append(current_vertex)

        seen_vertecies: set[VERTEX_T] = set()
        sorted_vertecies: list[VERTEX_T] = []
        for vertex in backward:
            traverse(vertex, seen_vertecies, sorted_vertecies)
        return sorted_vertecies

    def _split_on_non_intersecting_graphs(self, 
                                          sorted_vertecies: list[VERTEX_T], 
                                          backward: GRAPH_T) -> list[list[VERTEX_T]]:
        res: list[list[VERTEX_T]] = []
        start = 0
        for i in range(1, len(sorted_vertecies)):
            current_vertex = sorted_vertecies[i]
            if all(sorted_vertecies[j] not in backward[current_vertex] for j in range(i - 1, start - 1, -1)):
                res.append(sorted_vertecies[start:i])
                start = i
        
        res.append(sorted_vertecies[start:])
        return res

    def get_non_dependent_chains(self, chain_type: PossibleChainTypes, chain_name: str) -> Iterator[str]:
        for i, chain_dependency_relations in enumerate(self._chains_dependencies[chain_type].graphs):
            for j, chain in enumerate(chain_dependency_relations):
                if chain == chain_name:
                    return itertools.chain(*self._chains_dependencies[chain_type].graphs[:i],
                                           chain_dependency_relations[j + 1:],
                                           *self._chains_dependencies[chain_type].graphs[i + 1:])
        return (_ for _ in range(0))

    def get_dependent_chains(self, chain_type: PossibleChainTypes, chain_name: str) -> list[str]:
        chains_of_requested_type = self._chains_dependencies[chain_type].backward
        res: set[VERTEX_T] = set()

        def traverse(start: VERTEX_T, seen_vertecies: set[VERTEX_T]) -> None:
            if start in seen_vertecies:
                return
            seen_vertecies.add(start)
            for next_chain in chains_of_requested_type[start]:
                traverse(next_chain, seen_vertecies)
        
        for next_chain in chains_of_requested_type[chain_name]:
            traverse(next_chain, res)
        return list(res)

    def rename_chain(self, chain_type: PossibleChainTypes, old_name: str, new_name: str):
        chain_type_configurations = self[chain_type]
        chain_type_data = self._chains_dependencies[chain_type]
        for vertex in chain_type_data.backward[old_name]:
            for i in range(len(chain_type_configurations[vertex]["chain"])):
                if chain_type_configurations[vertex]["chain"][i].name == old_name:
                    object.__setattr__(chain_type_configurations[vertex]["chain"][i], "name", new_name)

            chain_type_data.forward[vertex][chain_type_data.forward[vertex].index(old_name)] = new_name
        chain_type_data.backward[new_name] = chain_type_data.backward[old_name]
        chain_type_data.backward.pop(old_name)
        chain_type_data.forward[new_name] = chain_type_data.forward[old_name]
        chain_type_data.forward.pop(old_name)

        graphs = self._split_on_non_intersecting_graphs(
            sorted_vertecies=self._toposort(chain_type_data.backward),
            backward=chain_type_data.backward
        )
        self._chains_dependencies[chain_type] = SingleChainDependeciesInfo(
            graphs=graphs,
            backward=chain_type_data.backward,
            forward=chain_type_data.forward
        )

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


class CardGeneratorsChain(CardGeneratorProtocol):
    _scheme_docs: str
    _parser_info: TypedParserName
    _config: ChainConfig

    @property
    def scheme_docs(self) -> str:
        return self._scheme_docs

    @property
    def config(self) -> LoadableConfigProtocol:
        return self._config

    @property
    def parser_info(self) -> TypedParserName:
        return self._parser_info

    def __init__(self,
                 chain_name: str,
                 chain_data: CHAIN_INFO_T,
                 card_generator_getter: Callable[[TypedParserName, CHAIN_INFO_T], CardGeneratorProtocol]):
        self._parser_info = TypedParserName(parser_t=ParserType.chain, name=chain_name)
        self.enum_name2generator: dict[str, CardGeneratorProtocol] = {}

        parser_configs = []

        if (requested_chain_info := chain_data.get(chain_name)) is None:
            raise ValueError(f"{self.__class__.__name__}: {chain_name} not found")

        scheme_docs_list = []

        parser_data: TypedParserName
        enum_parser_name: str
        for parser_data, enum_parser_name in zip(requested_chain_info["chain"], 
                                                 get_enumerated_names(requested_chain_info["chain"])):
            generator = card_generator_getter(parser_data, chain_data)
            self.enum_name2generator[enum_parser_name] = generator
            parser_configs.append(generator.config)
            scheme_docs_list.append("{}\n{}".format(parser_data.full_name, generator.scheme_docs.replace("\n", "\n |\t")))

        self._config = ChainConfig(config_dir=str(CHAIN_WORD_PARSERS_DATA_DIR),
                                   config_name=requested_chain_info["config_name"],
                                   name_config_pairs=[(parser_name, config) for parser_name, config in
                                                       zip(requested_chain_info["chain"], parser_configs)])
        self._scheme_docs = "\n".join(scheme_docs_list)

    def get(self,
            query: str,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        res: list[GeneratorReturn[list[Card]]] = []
        for enum_name, generator in self.enum_name2generator.items():
            self._config.update_config(enum_name)
            current_generator_results = generator.get(query, additional_filter)
        
            for i, parser_result in enumerate(current_generator_results):
                if self.config["error verbosity"] == "silent":
                    object.__setattr__(parser_result, "error_message", "")
                elif self.config["error verbosity"] == "if found" and not parser_result.result and parser_result.error_message:
                    current_generator_results.pop(i)
                if generator.parser_info.parser_t == ParserType.chain:
                    hierarchical_name = f"::{enum_name}{parser_result.parser_info.name}"
                else: 
                    hierarchical_name = f"::{enum_name}"
                object.__setattr__(parser_result.parser_info, "name",  hierarchical_name)
            res.extend(current_generator_results)
            if self.config["query type"] == "first found" and res[0].result:
                break
        return res


BATCH_T = TypeVar("BATCH_T", bound=Sized)
class ChainOfGenerators(WrappedBatchGeneratorProtocol[BATCH_T]):
    _parser_info: TypedParserName
    _config: ChainConfig

    @property
    def config(self) -> LoadableConfigProtocol:
        return self._config

    @property
    def parser_info(self) -> TypedParserName:
        return self._parser_info

    def __init__(self,
                 chain_name: str,
                 chain_data: CHAIN_INFO_T,
                 config_dir: str,
                 generator_getter: Callable[[TypedParserName, CHAIN_INFO_T], WrappedBatchGeneratorProtocol]):
        if (requested_chain_info := chain_data.get(chain_name)) is None:
            raise ValueError(f"{self.__class__.__name__}: {chain_name} not found")
        self._parser_info = TypedParserName(parser_t=ParserType.chain, name=chain_name)

        self.enum_name2batch_generator: dict[str, WrappedBatchGeneratorProtocol] = {}
        parser_configs = []
        for parser_name, enum_name in zip(requested_chain_info["chain"], 
                                          get_enumerated_names(requested_chain_info["chain"])):
            batch_generator = generator_getter(parser_name, chain_data)
            self.enum_name2batch_generator[enum_name] = batch_generator
            parser_configs.append(batch_generator.config)
        self._config = ChainConfig(config_dir=config_dir,
                                   config_name=requested_chain_info["config_name"],
                                   name_config_pairs=[(parser_name, config) for parser_name, config in
                                                       zip(requested_chain_info["chain"], parser_configs)])

    def get(self, word: str, card_data: CardFormat) -> Generator[list[GeneratorReturn[BATCH_T]], int, list[GeneratorReturn[BATCH_T]]]:
        batch_size = yield  # type: ignore
        
        res: list[GeneratorReturn[BATCH_T]] = []
        total_length = 0
        yielded_once_flag = False
        for i, (enum_name, batch_generator) in enumerate(self.enum_name2batch_generator.items()):
            self._config.update_config(enum_name)
            generator = batch_generator.get(word, card_data)
            next(generator)  # it is guaranteed that it will start without errors

            threw_exception_flag = False
            while True: 
                try:
                    current_res = generator.send(batch_size - total_length)
                    threw_exception_flag = False
                except StopIteration as e:
                    current_res = e.value
                    threw_exception_flag = True
                
                for generator_result in current_res: 
                    if batch_generator.parser_info.parser_t == ParserType.chain:
                        hierarchical_name = f"::{enum_name}{generator_result.parser_info.name}"
                    else: 
                        hierarchical_name = f"::{enum_name}"
                    object.__setattr__(generator_result.parser_info, "name",  hierarchical_name)
                    res.append(generator_result)
                    total_length += len(generator_result.result)

                if total_length < batch_size:
                    if threw_exception_flag:
                        break
                    else:
                        continue

                if i == len(self.enum_name2batch_generator) - 1:
                    return res
                batch_size = yield res
                yielded_once_flag = True
                total_length = 0
                res = []
            if yielded_once_flag and self.config["query type"] == "first found":
                break
        return res

SentenceParsersChain = ChainOfGenerators[list[str]]
ImageParsersChain    = ChainOfGenerators[list[str]]
AudioGettersChain    = ChainOfGenerators[list[tuple[str, str]]]
