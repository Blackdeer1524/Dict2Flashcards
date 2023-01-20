import json
import os
from enum import Enum
from typing import Callable, Generator, NoReturn, Optional

from ..plugins_loading.wrappers import CardGeneratorProtocol

from .cards import Card
from .storages import FrozenDict, FrozenDictJSONEncoder, PointerList

class Deck(PointerList[tuple[str, Card], tuple[str, Card]]):
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
            deck: list[tuple[str, Card]] = [(i[0], Card(i[1])) for i in json.load(f)]
        super(Deck, self).__init__(data=deck,
                                   starting_position=min(current_deck_pointer, len(deck) - 1),
                                   default_return_value=("", Card()))

        self._cards_left = max(0, len(self) - self._pointer_position)

    def update_card_generator(self, cd: CardGeneratorProtocol):
        if not isinstance(cd, CardGeneratorProtocol):
            raise TypeError(f"{cd} does not implement CardGeneratorProtocol Protocol")
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
            if searching_func(self[current_index][1]):
                move_list.append(current_index - last_found)
                last_found = current_index
        return PointerList(data=move_list)

    def _launch_card_to_deck_generator(self) -> \
        Generator[int | str, 
                  bool | tuple[str, Optional[Callable[[Card], bool]]], 
                  NoReturn]:
        error_message = ""
        while True:
            (query, additional_filter) = yield error_message 
            try:
                res = self._card_generator.get(query, additional_filter)
            except Exception as e:
                res = []
                error_message = str(e)

            parser_card_pairs = [(generator_result.parser_info.full_name, card) for generator_result in res for card in generator_result.result]
            continuation_flag = yield len(parser_card_pairs)
            if not (continuation_flag):
                continue
            
            self._data = self[:self._pointer_position] + parser_card_pairs + self[self._pointer_position:]
            if res:
                self._pointer_position = self._pointer_position - 1
                self._cards_left += len(parser_card_pairs)    

            yield error_message

    def append(self, card: Card) -> None:
        self._data = self[:self._pointer_position] + [card] + self[self._pointer_position:]
        self.move(1)

    def get_card(self) -> tuple[str, Card]:
        self.move(1)
        return self.get_pointed_item()

    def get_deck(self) -> list[tuple[str, Card]]:
        return self._data

    def save(self) -> None:
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
