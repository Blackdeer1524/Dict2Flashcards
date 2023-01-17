from abc import ABC, abstractmethod, abstractproperty
from dataclasses import dataclass
from typing import Callable, Generator, Generic, Literal, TypeVar

from ..consts import ParserType, TypedParserName
from ..consts.card_fields import CardFormat
from ..plugins_management.config_management import LoadableConfig
from .cards import Card


class Named(ABC):
    @abstractproperty
    def name(self) -> str:
        ...


class Configurable(ABC):
    @abstractproperty
    def config(self) -> LoadableConfig:
        ...


ERROR_MESSAGE_T = str
T = TypeVar("T")

@dataclass(init=False, slots=True, frozen=True, eq=False, kw_only=True, order=False, repr=False, match_args=True, unsafe_hash=False)
class GeneratorReturn(Generic[T]):
    parser_info: TypedParserName
    result: T
    error_message: ERROR_MESSAGE_T

    def __init__(self, 
                 generator_type: Literal[ParserType.web, ParserType.local],
                 name: str,
                 result: T,
                 error_message: ERROR_MESSAGE_T) -> None:
        object.__setattr__(self, "parser_info", TypedParserName(parser_t=generator_type, name=name))
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "error_message", error_message)


class CardGeneratorProtocol(Named, Configurable, ABC):
    @abstractproperty
    def scheme_docs(self) -> str:
        ...

    @abstractmethod
    def get(self,
            query: str,
            additional_filter: Callable[[CardFormat], bool] | None = None) -> list[GeneratorReturn[list[Card]]]:
        ...


SENTENCE_BATCH_T = list[str]

class SentenceGeneratorProtocol(Named, Configurable, ABC):
    @abstractmethod
    def get(self, word: str, card_data: CardFormat) -> Generator[GeneratorReturn[SENTENCE_BATCH_T], 
                                                                 int, 
                                                                 GeneratorReturn[SENTENCE_BATCH_T]]:
        ...
        

AUDIO_T = list[str]
AUDIO_INFO_T = list[str]  
AUDIO_DATA_T = tuple[AUDIO_T, AUDIO_INFO_T]

class AudioGeneratorProtocol(Named, Configurable, ABC):
    @abstractmethod
    def get(self, word: str, card_data: CardFormat) -> Generator[GeneratorReturn[AUDIO_DATA_T], 
                                                                 int, 
                                                                 GeneratorReturn[AUDIO_DATA_T]]:
        ...



IMAGE_BATCH_T = list[str]

class ImageGeneratorProtocol(Named, Configurable, ABC):
    @abstractmethod
    def get(self, word: str, card_data: CardFormat) -> Generator[GeneratorReturn[IMAGE_BATCH_T], 
                                                                 int, 
                                                                 GeneratorReturn[IMAGE_BATCH_T]]:
        ...