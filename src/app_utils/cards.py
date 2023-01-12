import json
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Protocol, Union, runtime_checkable, NoReturn, Generator, Optional

from ..consts.card_fields import CardFields
from ..plugins_management.config_management import LoadableConfig
from ..plugins_management.parsers_return_types import DictionaryFormat
from .storages import FrozenDict, FrozenDictJSONEncoder, PointerList


class Card(FrozenDict):
    __slots__ = ()

    def __init__(self, card_fields: dict[str, Any] | None = None):
        if card_fields is None:
            super(Card, self).__init__(data={})
            return

        super(Card, self).__init__(data=card_fields)

    def __repr__(self):
        return f"Card {self._data}"

    @staticmethod
    def get_str_dict_tags(card_data: Union[dict, "Card"],
                          prefix: str = "",
                          sep: str = "::",
                          tag_processor: Callable[[str], str] = lambda x: x) -> str:
        if (dictionary_tags := card_data.get(CardFields.dict_tags)) is None:
            return ""

        def traverse_tags_dict(res_container: list[str], current_item: dict, cur_stage_prefix: str = ""):
            nonlocal sep

            for key in current_item:
                cur_prefix = f"{cur_stage_prefix}{tag_processor(key)}{sep}"

                if isinstance((value := current_item[key]), dict):
                    traverse_tags_dict(res_container, value, cur_prefix)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            traverse_tags_dict(res_container, item, cur_prefix)
                        else:
                            res_container.append(f"{cur_prefix}{tag_processor(item)}")
                else:
                    res_container.append(f"{cur_prefix}{tag_processor(value)}")

        tags_container = []
        p = f"{prefix}{sep}" if prefix else ""
        traverse_tags_dict(tags_container, dictionary_tags, cur_stage_prefix=p)
        return " ".join(tags_container)


@runtime_checkable
class CardGeneratorProtocol(Protocol):
    name: str
    config: LoadableConfig
    scheme_docs: str

    def get(self,
            query: str,
            word_filter: Callable[[str], bool],
            additional_filter: Callable[[Card], bool] | None = None) -> tuple[list[Card], str]:
        ...


class CardGenerator(ABC):
    def __init__(self,
                 name: str,
                 item_converter: Callable[[str, dict], list[dict]],
                 config: LoadableConfig,
                 scheme_docs: str):
        self.name = name
        self.item_converter = item_converter
        self.config = config
        self.scheme_docs = scheme_docs

    @abstractmethod
    def _get_search_subset(self, query: str) -> tuple[DictionaryFormat, str]:
        pass

    def get(self,
            query: str,
            word_filter: Callable[[str], bool],
            additional_filter: Callable[[Card], bool] | None = None) -> tuple[list[Card], str]:
        if additional_filter is None:
            additional_filter = lambda _: True

        source, error_message = self._get_search_subset(query)
        res: list[Card] = []
        for word, word_data in source:
            if word_filter(word):
                for item in self.item_converter(word, word_data):
                    if additional_filter(card := Card(item)):
                        res.append(card)

        def sorting_key(card: Card) -> tuple[int, int, str]:
            word = card[CardFields.word]
            return len(word.split()), len(word), word

        return sorted(res, key=sorting_key), error_message


class LocalCardGenerator(CardGenerator):
    def __init__(self,
                 name: str,
                 local_dict_path: str,
                 item_converter: Callable[[str, dict], list[dict]],
                 config: LoadableConfig,
                 scheme_docs: str):
        super(LocalCardGenerator, self).__init__(name=name,
                                                 item_converter=item_converter,
                                                 config=config,
                                                 scheme_docs=scheme_docs)

        if not os.path.isfile(local_dict_path):
            raise FileNotFoundError(f"Local dictionary with path \"{local_dict_path}\" doesn't exist")

        with open(local_dict_path, "r", encoding="UTF-8") as f:
            self.local_dictionary: DictionaryFormat = json.load(f)

    def _get_search_subset(self, query: str) -> tuple[DictionaryFormat, str]:
        return self.local_dictionary, ""


class WebCardGenerator(CardGenerator):
    def __init__(self,
                 name: str,
                 parsing_function: Callable[[str], tuple[DictionaryFormat, str]],
                 item_converter: Callable[[str, dict], list[dict]],
                 config: LoadableConfig,
                 scheme_docs: str):
        super(WebCardGenerator, self).__init__(name=name,
                                               item_converter=item_converter,
                                               config=config,
                                               scheme_docs=scheme_docs)
        self.parsing_function = parsing_function

    def _get_search_subset(self, query: str) -> tuple[DictionaryFormat, str]:
        return self.parsing_function(query)


class Deck(PointerList):
    __slots__ = "deck_path", "_card_generator", "_cards_left", \
                "card_addition_limit", "card2deck_gen"

    def __init__(self, deck_path: str,
                 current_deck_pointer: int,
                 card_generator: CardGeneratorProtocol):
        if not os.path.isfile(deck_path):
            raise Exception("Invalid _deck path!")

        self.deck_path = deck_path

        self._card_generator: CardGeneratorProtocol = card_generator
        self.card2deck_gen = self._launch_card_to_deck_generator()
        next(self.card2deck_gen)

        with open(self.deck_path, "r", encoding="UTF-8") as f:
            deck: list[dict[str, str | dict]] = json.load(f)
        super(Deck, self).__init__(data=deck,
                                    starting_position=min(current_deck_pointer, len(deck) - 1),
                                    default_return_value=Card())

        for i in range(len(self)):
            self._data[i] = Card(self._data[i])
        self._cards_left = max(0, len(self) - self._pointer_position)

        
    def update_card_generator(self, cd: CardGeneratorProtocol):
        if not isinstance(cd, CardGeneratorProtocol):
            raise TypeError(f"{cd} does not implement CardGenerator Protocol")
        self._card_generator = cd
        self.card2deck_gen = self._launch_card_to_deck_generator()
        next(self.card2deck_gen)

    def get_n_cards_left(self) -> int:
        return self._cards_left

    def move(self, n: int) -> None:
        super(Deck, self).move(n)
        self._cards_left = max(0, len(self) - self._pointer_position)

    def find_card(self, searching_func: Callable[[Card], bool]) -> PointerList:
        move_list = []
        last_found = self.get_pointer_position()
        for current_index in range(self.get_pointer_position() + 1, len(self)):
            if searching_func(self[current_index]):
                move_list.append(current_index - last_found)
                last_found = current_index
        return PointerList(data=move_list)

    def _launch_card_to_deck_generator(self) -> \
        Generator[int | str, 
                  bool | tuple[str, 
                               Callable[[Card], bool], 
                               Optional[Callable[[Card], bool]]], 
                  NoReturn]:
        error_message = ""
        while True:
            get_params = yield error_message
            try:
                res, error_message = self._card_generator.get(*get_params)  # type: ignore
            except Exception as e:
                res = []
                error_message = str(e)

            cont_flag = yield len(res)
            if not (cont_flag):
                continue

            self._data = self[:self._pointer_position] + res + self[self._pointer_position:]
            if res:
                self._pointer_position = self._pointer_position - 1
                self._cards_left += len(res)    

            yield error_message

    def append(self, card: Card):
        self._data = self[:self._pointer_position] + [card] + self[self._pointer_position:]
        self.move(1)

    def get_card(self) -> Card:
        self.move(1)
        return self.get_pointed_item()

    def get_deck(self) -> list[Card]:
        return self._data

    def save(self):
        with open(self.deck_path, "w", encoding="utf-8") as deck_file:
            json.dump(self._data, deck_file, cls=FrozenDictJSONEncoder)


class CardStatus(Enum):
    ADD = 0
    SKIP = 1
    BURY = 2


class SavedDataDeck(PointerList):
    CARD_STATUS         = "status"               # 0
    CARD_DATA           = "card"                 # 0
    ADDITIONAL_DATA     = "additional"           # 0
    USER_TAGS           =   "user_tags"            # 1
    HIERARCHICAL_PREFIX =   "hierarchical_prefix"  # 1
    SAVED_IMAGES_PATHS  =   "local_images"         # 1
    AUDIO_DATA          =   "audio_data"           # 1
    AUDIO_SRCS          =       "audio_src"            # 2
    AUDIO_SRCS_TYPE     =       "audio_src_type"       # 2
    AUDIO_SAVING_PATHS  =       "audio_saving_paths"   # 2

    __slots__ = "_statistics"

    def __init__(self):
        super(SavedDataDeck, self).__init__()
        self._statistics = [0, 0, 0]

    def get_card_status_stats(self, status: CardStatus):
        return self._statistics[status.value]

    def append(self, status: CardStatus, card_data: dict[str, str | list[str]] | None = None):
        if card_data is None:
            card_data = {}

        res = {SavedDataDeck.CARD_STATUS: status}
        if status != CardStatus.SKIP:
            additional_data = card_data.pop(SavedDataDeck.ADDITIONAL_DATA, {})
            saving_card = Card(card_data)
            res[SavedDataDeck.CARD_DATA] = saving_card
            if additional_data:
                res[SavedDataDeck.ADDITIONAL_DATA] = additional_data

        self._data.append(FrozenDict(res))
        self._pointer_position += 1
        self._statistics[status.value] += 1

    def move(self, n: int) -> None:
        if n < 0:
            super(SavedDataDeck, self).move(n)
            for i in range(self.get_pointer_position(), len(self)):
                self._statistics[self[i][SavedDataDeck.CARD_STATUS].value] -= 1
            del self._data[self.get_pointer_position():]
            return
        self._data.extend((FrozenDict({SavedDataDeck.CARD_STATUS: CardStatus.SKIP}) for _ in range(n)))
        self._pointer_position = len(self)
        self._statistics[CardStatus.SKIP.value] += n

    def get_audio_data(self, saving_card_status: CardStatus) -> list[FrozenDict]:
        if not self.get_card_status_stats(saving_card_status):
            return []

        saving_object = []
        for card_page in self:
            if card_page[SavedDataDeck.CARD_STATUS] != saving_card_status:
                continue
            if (additional := card_page.get(SavedDataDeck.ADDITIONAL_DATA)) is not None and \
                    (audio_data := additional.get(SavedDataDeck.AUDIO_DATA)):
                saving_object.append(audio_data)
        return saving_object

    def get_card_data(self, saving_card_status: CardStatus) -> list[FrozenDict]:
        if not self.get_card_status_stats(saving_card_status):
            return []

        saving_object = []
        for card_page in self:
            if card_page[SavedDataDeck.CARD_STATUS] != saving_card_status:
                continue
            saving_object.append(card_page[SavedDataDeck.CARD_DATA])
        return saving_object
