import json
import os
from abc import ABC, abstractmethod, abstractproperty
from dataclasses import dataclass, field
from typing import Callable, Generator, Generic, Literal, Optional, TypeVar

from ..consts import CardFormat, ParserType, TypedParserName
from ..plugins_management.config_management import (HasConfigFile,
                                                    LoadableConfig,
                                                    LoadableConfigProtocol)
from ..app_utils.cards import Card

T = TypeVar("T")
@dataclass(init=False, slots=True, frozen=True, eq=False, kw_only=True, order=False, match_args=True, unsafe_hash=False)
class GeneratorReturn(Generic[T]):
    parser_info: TypedParserName
    result: T
    error_message: str

    def __init__(self, 
                 generator_type: Literal[ParserType.web, ParserType.local],
                 name: str,
                 result: T,
                 error_message: str) -> None:
        object.__setattr__(self, "parser_info", TypedParserName(parser_t=generator_type, name=name))
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "error_message", error_message)


class TypedParser(ABC):
    @abstractproperty
    def parser_info(self) -> TypedParserName:
        ...


class CardGeneratorProtocol(TypedParser, HasConfigFile, ABC):
    @abstractproperty
    def scheme_docs(self) -> str:
        ...

    @abstractmethod
    def get(self,
            query: str,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        ...


WEB_DEFITION_FUNCTION_T = Callable[[str], tuple[list[CardFormat], str]]
@dataclass(init=False, slots=True, frozen=True, eq=False, kw_only=True, order=False, repr=False, match_args=True, unsafe_hash=False)
class WebCardGenerator(CardGeneratorProtocol):
    parser_info:              TypedParserName
    word_definition_function: WEB_DEFITION_FUNCTION_T
    config:                   LoadableConfig
    scheme_docs:              str

    def __init__(self,
                 word_definition_function: WEB_DEFITION_FUNCTION_T,
                 name: str,
                 config: LoadableConfig,
                 scheme_docs: str):
        object.__setattr__(self, "parser_info", TypedParserName(parser_t=ParserType.web, name=name))
        object.__setattr__(self, "word_definition_function", word_definition_function)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "scheme_docs", scheme_docs)

    def _get_search_subset(self, query: str) -> tuple[list[CardFormat], str]:
        return self.word_definition_function(query)

    def get(self,
            query: str,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        if additional_filter is None:
            additional_filter = lambda _: True

        results, error_message = self._get_search_subset(query)
        res: list[Card] = [Card(item) for item in results if additional_filter(item)]

        return [GeneratorReturn(generator_type=ParserType.web, 
                                name=self.parser_info.name, 
                                result=res, 
                                error_message=error_message)]



DICTIONARY_T = TypeVar("DICTIONARY_T")
LOCAL_DEFITION_FUNCTION_T = Callable[[str, DICTIONARY_T], tuple[list[CardFormat], str]]
@dataclass(init=False, slots=True, frozen=True, eq=False, kw_only=True, order=False, repr=False, match_args=True, unsafe_hash=False)
class LocalCardGenerator(Generic[DICTIONARY_T], CardGeneratorProtocol):
    parser_info:              TypedParserName
    word_definition_function: LOCAL_DEFITION_FUNCTION_T
    config:                   LoadableConfig
    scheme_docs:              str
    local_dictionary:         DICTIONARY_T

    def __init__(self,
                 word_definition_function: LOCAL_DEFITION_FUNCTION_T,
                 name: str,
                 local_dict_path: str,
                 config: LoadableConfig,
                 scheme_docs: str):
        object.__setattr__(self, "parser_info", TypedParserName(parser_t=ParserType.local, name=name))
        object.__setattr__(self, "word_definition_function", word_definition_function)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "scheme_docs", scheme_docs)
        
        if not os.path.isfile(local_dict_path):
            raise FileNotFoundError(f"Local dictionary with path \"{local_dict_path}\" doesn't exist")

        with open(local_dict_path, "r", encoding="UTF-8") as f:
            object.__setattr__(self, "local_dictionary", json.load(f))

    def _get_search_subset(self, query: str) -> tuple[list[CardFormat], str]:
        return self.word_definition_function(query, self.local_dictionary)

    def get(self,
            query: str,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        if additional_filter is None:
            additional_filter = lambda _: True

        results, error_message = self._get_search_subset(query)
        res: list[Card] = [Card(item) for item in results if additional_filter(item)]

        return [GeneratorReturn(generator_type=ParserType.local, 
                                name=self.parser_info.name, 
                                result=res, 
                                error_message=error_message)]


S = TypeVar("S")
class WrappedBatchGeneratorProtocol(TypedParser, HasConfigFile, ABC, Generic[S]):
    @abstractmethod
    def get(self, *arg, **kwargs) -> Generator[list[GeneratorReturn[S]], int, list[GeneratorReturn[S]]]:
        ...


BATCH_T =  TypeVar("BATCH_T")
class BatchGeneratorWrapper(WrappedBatchGeneratorProtocol[BATCH_T]):
    """It is guaranteed that it will start"""
    _parser_type:          Literal[ParserType.web, ParserType.local]
    generator_initializer: Callable[..., 
                                    Generator[tuple[BATCH_T, str], 
                                              int, 
                                              tuple[BATCH_T, str]]]
    _parser_info: TypedParserName
    _config: LoadableConfigProtocol

    @property
    def config(self) -> LoadableConfigProtocol:
        return self._config

    @property
    def parser_info(self) -> TypedParserName:
        return self._parser_info

    def __init__(self,
                 parser_type: Literal[ParserType.web, ParserType.local],
                 parser_name: str,
                 config: LoadableConfigProtocol,
                 generator_initializer: Callable[[str, CardFormat], 
                                                 Generator[tuple[BATCH_T, str], 
                                                           int, 
                                                           tuple[BATCH_T, str]]]) -> None:
        self._parser_info = TypedParserName(parser_t=parser_type, name=parser_name)
        self._parser_type = parser_type
        self._config = config
        self.generator_initializer = generator_initializer

    def get(self, *arg, **kwargs) -> Generator[list[GeneratorReturn[BATCH_T]], 
                                               int, 
                                               list[GeneratorReturn[BATCH_T]]]:
        batch_size = yield  # type: ignore
        generator = self.generator_initializer(*arg, **kwargs)
        try:
            next(generator)
        except StopIteration as e:
            return [GeneratorReturn(generator_type=self._parser_type,
                                    name=self.parser_info.name,
                                    result=e.value[0],
                                    error_message=e.value[1])] 

        while True:
            try:
                batch_results, error_message = generator.send(batch_size)
                batch_size = yield [GeneratorReturn(generator_type=self._parser_type,
                                                    name=self.parser_info.name,
                                                    result=batch_results,
                                                    error_message=error_message)]
            except StopIteration as e:
                return [GeneratorReturn(generator_type=self._parser_type,
                                        name=self.parser_info.name,
                                        result=e.value[0],
                                        error_message=e.value[1])]


BATCH_V = TypeVar("BATCH_V")
@dataclass(slots=True)
class ExternalDataGenerator(TypedParser, Generic[BATCH_V]):
    data_generator: WrappedBatchGeneratorProtocol

    parser_info:     TypedParserName = field(init=False)
    _args_params:    list = field(init=False, default_factory=list)
    _kwargs_param:   dict = field(init=False, default_factory=dict)
    _update_status:  bool = field(init=False, default=False)
    _data_generator: Generator[list[GeneratorReturn[BATCH_V]], int, None] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "parser_info", self.data_generator.parser_info)
        self._start()

    def _start(self):
        self._data_generator = self._get_data_generator()
        next(self._data_generator)

    def force_update(self, *args, **kwargs):
        self._args_params = args
        self._kwargs_param = kwargs
        self._update_status = True
        self._start()

    def _get_data_generator(self) -> Generator[list[GeneratorReturn[BATCH_V]], int, None]:
        batch_size = yield  # type: ignore

        data_generator = self.data_generator.get(*self._args_params, **self._kwargs_param)
        try:
            next(data_generator)
        except StopIteration as e:
            yield e.value
            return

        self._update_status = False
        while True:
            try:
                batch_size = yield data_generator.send(batch_size)
                if self._update_status :
                    break
            except StopIteration as e:
                yield e.value
                return

    def get(self, batch_size: int, *args, **kwargs) -> Optional[list[GeneratorReturn[BATCH_V]]]:
        if self._args_params != args or self._kwargs_param != kwargs:
            self.force_update(*args, **kwargs)

        try:
            res = self._data_generator.send(batch_size)
            if self.data_generator.parser_info.parser_t == ParserType.chain:
                for i in range(len(res)):
                    object.__setattr__(res[i].parser_info, 
                                       "name", 
                                       f"{self.data_generator.parser_info.full_name}{res[i].parser_info.name}")
            return res
        except StopIteration:
            return None
