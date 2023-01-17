import json
import os
from dataclasses import dataclass, field
from typing import Callable, Generator, Generic, Optional, TypeVar, Literal
from ..consts import CardFormat, ParserType, TypedParserName
from ..plugins_management.config_management import LoadableConfig, LoadableConfigProtocol
from .cards import Card
from .parser_interfaces import (AudioGeneratorProtocol, CardGeneratorProtocol,
                                GeneratorReturn, ImageGeneratorProtocol,
                                SentenceGeneratorProtocol, Named, Configurable)

QUERY_T = str
GENERATOR_NAME_T = str
ERROR_MESSAGE_T = str


DICTIONARY_T = TypeVar("DICTIONARY_T")
LOCAL_DEFITION_FUNCTION_T = Callable[[QUERY_T, DICTIONARY_T], tuple[list[CardFormat], ERROR_MESSAGE_T]]

@dataclass(init=False, slots=True, frozen=True, eq=False, kw_only=True, order=False, repr=False, match_args=True, unsafe_hash=False)
class LocalCardGenerator(Generic[DICTIONARY_T], CardGeneratorProtocol):
    name:                     str
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
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "word_definition_function", word_definition_function)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "scheme_docs", scheme_docs)
        
        if not os.path.isfile(local_dict_path):
            raise FileNotFoundError(f"Local dictionary with path \"{local_dict_path}\" doesn't exist")

        with open(local_dict_path, "r", encoding="UTF-8") as f:
            object.__setattr__(self, "local_dictionary", json.load(f))

    def _get_search_subset(self, query: str) -> tuple[list[CardFormat], ERROR_MESSAGE_T]:
        return self.word_definition_function(query, self.local_dictionary)

    def get(self,
            query: QUERY_T,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        if additional_filter is None:
            additional_filter = lambda _: True

        results, error_message = self._get_search_subset(query)
        res: list[Card] = [Card(item) for item in results if additional_filter(item)]

        return [GeneratorReturn(generator_type=ParserType.local, 
                                name=self.name, 
                                result=res, 
                                error_message=error_message)]


WEB_DEFITION_FUNCTION_T = Callable[[QUERY_T], tuple[list[CardFormat], ERROR_MESSAGE_T]]


@dataclass(init=False, slots=True, frozen=True, eq=False, kw_only=True, order=False, repr=False, match_args=True, unsafe_hash=False)
class WebCardGenerator(CardGeneratorProtocol):
    name:                     str
    word_definition_function: WEB_DEFITION_FUNCTION_T
    config:                   LoadableConfig
    scheme_docs:              str

    def __init__(self,
                 word_definition_function: WEB_DEFITION_FUNCTION_T,
                 name: str,
                 config: LoadableConfig,
                 scheme_docs: str):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "word_definition_function", word_definition_function)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "scheme_docs", scheme_docs)

    def _get_search_subset(self, query: QUERY_T) -> tuple[list[CardFormat], ERROR_MESSAGE_T]:
        return self.word_definition_function(query)

    def get(self,
            query: str,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        if additional_filter is None:
            additional_filter = lambda _: True

        results, error_message = self._get_search_subset(query)
        res: list[Card] = [Card(item) for item in results if additional_filter(item)]

        return [GeneratorReturn(generator_type=ParserType.web, 
                                name=self.name, 
                                result=res, 
                                error_message=error_message)]


BATCH_REQUEST_T = int
BATCH_T =  TypeVar("BATCH_T")
GENERATOR_YIELD_T = tuple[BATCH_T, ERROR_MESSAGE_T]
WORD_T = str


class BatchGeneratorWrapper(Named, Configurable, Generic[BATCH_T]):
    """It is guaranteed that it will start"""
    name:                  str
    config:                LoadableConfigProtocol 
    generator_initializer: Callable[[WORD_T, CardFormat], 
                                     Generator[GENERATOR_YIELD_T, 
                                               BATCH_REQUEST_T, 
                                               GENERATOR_YIELD_T]]
    parser_type:            Literal[ParserType.web, ParserType.local]

    def __init__(self,
                 parser_info: TypedParserName,
                 config: LoadableConfigProtocol,
                 generator_initializer: Callable[[WORD_T, CardFormat], 
                                                 Generator[GENERATOR_YIELD_T, 
                                                           BATCH_REQUEST_T, 
                                                           GENERATOR_YIELD_T]]) -> None:
        object.__setattr__(self, "name", parser_info.name)
        object.__setattr__(self, "parser_type", parser_info.parser_t)
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "generator_initializer", generator_initializer)

    def get(self,
            word: str,
            card_data: CardFormat) -> Generator[GeneratorReturn[BATCH_T], 
                                                BATCH_REQUEST_T, 
                                                GeneratorReturn[BATCH_T]]:
        batch_size = yield  # type: ignore
        generator = self.generator_initializer(word, card_data)
        try:
            next(generator)
        except StopIteration as e:
            return GeneratorReturn(generator_type=ParserType.web,
                                   name=self.name,
                                   result=e.value[0],
                                   error_message=e.value[1]) 

        while True:
            try:
                batch_results, error_message = generator.send(batch_size)
                batch_size = yield GeneratorReturn(generator_type=self.parser_type,
                                                   name=self.name,
                                                   result=batch_results,
                                                   error_message=error_message)
            except StopIteration as e:
                return GeneratorReturn(generator_type=self.parser_type,
                                       name=self.name,
                                       result=batch_results,
                                       error_message=error_message)


GeneratorYieldType = TypeVar("GeneratorYieldType")
WRAPPED_EXTERNAL_DATA_GENERATOR_T = Generator[GeneratorReturn[GeneratorYieldType], 
                                              BATCH_REQUEST_T, 
                                              None]

@dataclass(slots=True)
class ExternalDataGenerator(Generic[GeneratorYieldType]):
    data_generator: BatchGeneratorWrapper

    _word:           str  = field(init=False, default="")
    _card_data:      dict = field(init=False, default_factory=dict)
    _update_status:  bool = field(init=False, default=False)
    _data_generator: WRAPPED_EXTERNAL_DATA_GENERATOR_T = field(init=False)

    def __post_init__(self):
        self._start()

    def _start(self):
        self._data_generator = self._get_data_generator()
        next(self._data_generator)

    def force_update(self, word: str, card_data: dict):
        self._word = word
        self._card_data = card_data
        self._update_status = True
        self._start()

    def _get_data_generator(self) -> WRAPPED_EXTERNAL_DATA_GENERATOR_T:
        batch_size = yield

        data_generator = self.data_generator.get(self._word, self._card_data)
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

    def get(self, word: str, card_data:dict, batch_size: int) -> Optional[GeneratorReturn[GeneratorYieldType]]:
        if self._word != word or self._card_data != card_data:
            self.force_update(word, card_data)

        try:
            return self._data_generator.send(batch_size)
        except StopIteration:
            return None
