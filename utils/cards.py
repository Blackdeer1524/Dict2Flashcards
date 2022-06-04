import abc
from typing import Callable, Iterator, Union, Any
import os
import json
from consts.card_fields import FIELDS
from enum import Enum
from utils.storages import PointerList, FrozenDict
from abc import ABC


class Card(FrozenDict):
    def __init__(self, card_fields: dict[str, Any] = None):
        if card_fields is None:
            super(Card, self).__init__(data={})
            return

        data = {}
        for field_name in FIELDS:
            if (field_value := card_fields.get(field_name)) is not None:
                data[field_name] = field_value
        super(Card, self).__init__(data=data)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):
        return self._data[item]

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return f"Card {self._data}"

    def __bool__(self):
        return bool(self._data)

    def to_dict(self):
        return self._data


class _CardJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Card):
            return o.to_dict()
        return super().default(o)


class CardGenerator(ABC):
    def __init__(self, item_converter: Callable[[(str, dict)], dict]):
        self.item_converter = item_converter

    @abc.abstractmethod
    def _get_search_subset(self, query: str) -> list[tuple[str, dict]]:
        pass

    def get(self, query: str, word_filter: Callable[[str], bool],
            additional_filter: Callable[[Card], bool] = None) -> list[Card]:
        if additional_filter is None:
            additional_filter = lambda _: True

        source: list[(str, dict)] = self._get_search_subset(query)
        res: list[Card] = []
        for card in source:
            if word_filter(card[0]):
                for item in self.item_converter(card):
                    if additional_filter(card := Card(item)):
                        res.append(card)
        return res


class LocalCardGenerator(CardGenerator):
    def __init__(self,
                 local_dict_path: str,
                 item_converter: Callable[[(str, dict)], dict]):
        """
        local_dict_path: str
        item_converter: Callable[[(str, dict)], dict]
        """
        super(LocalCardGenerator, self).__init__(item_converter)
        if not os.path.isfile(local_dict_path):
            raise Exception(f"Local dictionary with path {local_dict_path} doesn't exist")

        with open(local_dict_path, "r", encoding="UTF-8") as f:
            self.local_dictionary: list[(str, dict)] = json.load(f)

    def _get_search_subset(self, query: str) -> list[tuple[str, dict]]:
        return self.local_dictionary


class WebCardGenerator(CardGenerator):
    def __init__(self,
                 parsing_function: Callable[[str], list[(str, dict)]],
                 item_converter: Callable[[(str, dict)], dict]):
        """
        parsing_function: Callable[[str], list[(str, dict)]]
        item_converter: Callable[[(str, dict)], dict]
        """
        super(WebCardGenerator, self).__init__(item_converter)
        self.parsing_function = parsing_function

    def _get_search_subset(self, query: str) -> list[tuple[str, dict]]:
        return self.parsing_function(query)


class Deck(PointerList):
    def __init__(self, deck_path: str,
                 current_deck_pointer: int,
                 card_generator: CardGenerator):
        self.deck_path = deck_path
        if os.path.isfile(self.deck_path):
            with open(self.deck_path, "r", encoding="UTF-8") as f:
                deck: list[dict[str, Union[str, dict]]] = json.load(f)
            super(Deck, self).__init__(data=deck,
                                       starting_position=current_deck_pointer,
                                       default_return_value=Card())
        else:
            raise Exception("Invalid _deck path!")

        for i in range(len(self)):
            self._data[i] = Card(self._data[i])

        self._cards_left = len(self) - self._pointer_position
        self._card_generator: CardGenerator = card_generator

    def set_card_generator(self, value: CardGenerator):
        assert (isinstance(value, CardGenerator))
        self._card_generator = value

    def get_n_cards_left(self) -> int:
        return self._cards_left

    def move(self, n: int) -> None:
        super(Deck, self).move(n)
        self._cards_left = len(self) - self._pointer_position

    def find_card(self, searching_func: Callable[[Card], bool]) -> list[int]:
        move_list = []
        for current_index in range(self.get_pointer_position(), len(self)):
            if searching_func(self[current_index]):
                move_list.append(current_index - self.get_pointer_position())
        return move_list

    def add_card_to_deck(self, query: str, **kwargs) -> int:
        res: list[Card] = self._card_generator.get(query, **kwargs)
        self._data = self[:self._pointer_position] + res + self[self._pointer_position:]
        self._cards_left += len(res)
        return len(res)

    def get_card(self) -> Card:
        cur_card = self[self._pointer_position]
        if cur_card:
            self._pointer_position += 1
            self._cards_left -= 1
        return cur_card

    def get_deck(self) -> list[Card]:
        return self._data

    def save(self):
        with open(self.deck_path, "w", encoding="utf-8") as deck_file:
            json.dump(self._data, deck_file, cls=_CardJSONEncoder)

    
    
class CardStatus(Enum):
    ADD = 0
    SKIP = 1
    BURY = 2


class SavedDeck(PointerList):
    def __init__(self):
        super(SavedDeck, self).__init__()

    def append(self, status: CardStatus, kwargs: dict[str, Union[str, list[str]]] = None):
        if kwargs is None:
            kwargs = {}
        res = {"status": status}
        if status != CardStatus.SKIP:
            saving_card = Card(kwargs)
            res["card"] = saving_card
        self._data.append(res)
        self._pointer_position += 1

    def move(self, n: int) -> None:
        super(SavedDeck, self).move(n)
        del self._data[self._pointer_position:]
    
    def save(self, saving_path: str):
        with open(saving_path, "w", encoding="utf-8") as deck_file:
            json.dump(self._data, deck_file, cls=_CardJSONEncoder)
            

class SentenceFetcher:
    def __init__(self,
                 sent_fetcher: Callable[[str, int], Iterator[tuple[list[str], str]]] = lambda *_: [[], True],
                 sentence_batch_size=5):
        self._word: str = ""
        self._sentences: list[str] = []
        self._sentence_fetcher: Callable[[str, int], Iterator[tuple[list[str], str]]] = sent_fetcher
        self._batch_size: int = sentence_batch_size
        self._sentence_pointer: int = 0
        self._sent_batch_generator: Iterator[tuple[list[str], str]] = self._get_sent_batch_generator()
        self._local_sentences_flag: bool = True
        self._update_status: bool = False

    def is_local(self):
        return self._local_sentences_flag

    def __call__(self, base_word, base_sentences):
        self._word = base_word
        self._sentences = base_sentences  # REFERENCE!!!
        self._local_sentences_flag = True
        self._sentence_pointer = 0
        self._update_status = False

    def update_word(self, new_word: str):
        if self._word != new_word:
            self._word = new_word
            self._update_status = True

    def _get_sent_batch_generator(self) -> Iterator[tuple[list[str], str]]:
        """
        Yields: Sentence_batch, error_message
        """
        while True:
            if self._local_sentences_flag:
                self._sentence_pointer = 0
                # Always do the first iteration (not considering update condition)
                while not self._update_status:
                    self._sentence_pointer += self._batch_size
                    yield self._sentences[self._sentence_pointer - self._batch_size:self._sentence_pointer], ""
                    if self._sentence_pointer and self._sentence_pointer >= len(self._sentences):
                        break
                self._local_sentences_flag = False
                # _sentence_fetcher doesn't need update before it's first iteration
                # because of its first argument
                self._update_status = False

            for sentence_batch, error_message in self._sentence_fetcher(self._word, self._batch_size):
                yield sentence_batch, error_message
                if self._update_status:
                    self._update_status = False
                    break
                if self._local_sentences_flag or error_message:
                    break
            else:
                self._local_sentences_flag = True

    def get_sentence_batch(self, word: str) -> tuple[list[str], str, bool]:
        self.update_word(word)
        sentences, error_message = next(self._sent_batch_generator)
        return sentences, error_message, self._local_sentences_flag
