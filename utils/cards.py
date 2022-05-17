import copy
from typing import Callable, Iterator
import os
import json


class CardGenerator:
    def __init__(self, **kwargs):
        """
        parsing_function: Callable[[str], list[(str, dict)]],
        local_dict_path: str = kwargs.get("local_dict_path", "")
        item_converter: Callable[[(str, dict)], dict]
        """
        parsing_function: Callable[[str], list[(str, dict)]] = kwargs.get("parsing_function")
        local_dict_path: str = kwargs.get("local_dict_path", "")
        self.item_converter: Callable[[(str, dict)], dict] = kwargs.get("item_converter")
        assert self.item_converter is not None

        if os.path.isfile(local_dict_path):
            self._is_local = True
            with open(local_dict_path, "r", encoding="UTF-8") as f:
                self.local_dictionary: list[(str, dict)] = json.load(f)
        elif parsing_function is not None:
            self._is_local = False
            self.parsing_function: Callable[[str], list[(str, dict)]] = parsing_function
            self.local_dictionary = []
        else:
            raise Exception("Wrong parameters for CardGenerator class!"
                            f"Check given parameters:",
                            kwargs)

    def get(self, query: str, **kwargs) -> list[dict]:
        """
        word_filter: Callable[[comparable: str, query_word: str], bool]
        additional_filter: Callable[[translated_word_data: dict], bool]
        """
        word_filter: Callable[[str, str], bool] = \
            kwargs.get("word_filter", lambda comparable, query_word: True if comparable == query_word else False)
        additional_filter: Callable[[dict], bool] = \
            kwargs.get("additional_filter", lambda card_data: True)

        source: list[(str, dict)] = self.local_dictionary if self._is_local else self.parsing_function(query)
        res: list[dict] = []
        for card in source:
            if word_filter(card[0], query):
                res.extend(self.item_converter(card))
        return [item for item in res if additional_filter(item)]


class Deck:
    def __init__(self, json_deck_path: str, current_deck_pointer: int, card_generator: CardGenerator):
        assert current_deck_pointer >= 0

        if os.path.isfile(json_deck_path):
            with open(json_deck_path, "r", encoding="UTF-8") as f:
                self.__deck = json.load(f)
            self.__pointer_position = self.__starting_position = min(max(len(self.__deck) - 1, 0), current_deck_pointer)
        else:
            raise Exception("Invalid deck path!")
        self.__cards_left = len(self) - self.__pointer_position
        self.__card_generator: CardGenerator = card_generator

    def set_card_generator(self, value: CardGenerator):
        assert (isinstance(value, CardGenerator))
        self.__card_generator = value

    def get_pointer_position(self) -> int:
        return self.__pointer_position

    def get_starting_position(self):
        return self.__starting_position

    def get_n_cards_left(self) -> int:
        return self.__cards_left

    def get_deck(self) -> list[dict]:
        return self.__deck

    def __len__(self):
        return len(self.__deck)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.__deck[item] if self.__starting_position <= item < len(self) else {}
        elif isinstance(item, slice):
            return self.__deck[item]

    def __add__(self, other):
        if isinstance(other, list):
            return self.__deck + other
        elif isinstance(other, Deck):
            return self.__deck + other.__deck
        else:
            raise Exception(f"Undefined addition for Deck class and {type(other)}!")

    def __repr__(self):
        res = f"Deck\nLength: {len(self)}\nPointer position: {self.__pointer_position}\nCards left: {self.__cards_left}\n"
        for index, item in enumerate(self, 0):
            if not item:
                break
            if index == self.__pointer_position or index == self.__starting_position:
                res += "C" if index == self.__pointer_position else " "
                res += "S" if index == self.__starting_position else " "

                res += " --> "
            else:
                res += " " * 7
            res += f"{index}: {item}\n"
        return res

    def add_card_to_deck(self, query: str, **kwargs):
        """
        word_filter: Callable[[comparable: str, query_word: str], bool]
        additional_filter: Callable[[translated_word_data: dict], bool]
        """

        res: list[dict] = self.__card_generator.get(query, **kwargs)
        self.__deck = self[:self.__pointer_position] + res + self[self.__pointer_position:]
        self.__cards_left += len(res)

    def get_card(self) -> dict:
        cur_card = self[self.__pointer_position]
        if cur_card:
            self.__pointer_position += 1
            self.__cards_left -= 1
        return cur_card

    def move(self, n: int) -> None:
        self.__pointer_position = min(max(self.__pointer_position + n, 0), len(self))
        self.__cards_left = len(self) - self.__pointer_position


class CardWrapper:
    def __init__(self, sent_fetcher: Callable[[str, int], Iterator[tuple[list[str], bool]]] = lambda *_: [[], True]):
        self.__card = {}
        self.__sentence_fetcher = sent_fetcher
        self.__local_sentences_flag = True
        self.__sentence_pointer = 0

    def __call__(self, card: dict):
        self.__local_sentences_flag = True
        self.__sentence_pointer = 0
        self.__card = copy.deepcopy(card)
        for str_key in ("word", "meaning"):
            if self.__card.get(str_key) is None:
                self.__card[str_key] = ""
        for list_key in ("Sen_Ex",):
            if self.__card.get(list_key) is None:
                self.__card[list_key] = ""

    def update_word(self, new_word: str):
        self.__card["word"] = new_word
        self.__local_sentences_flag = True

    def get_sentence_batch(self, batch_size: int = 5) -> Iterator[tuple[list[str], bool]]:
        """
        Yields: Sentence_batch, error_status
        """
        while True:
            if self.__local_sentences_flag:
                while self.__sentence_pointer < len(self.__card["Sen_Ex"]):
                    yield self.__card["Sen_Ex"][self.__sentence_pointer:self.__sentence_pointer + batch_size], False
                    self.__sentence_pointer += batch_size

            self.__local_sentences_flag = False
            for sentence_batch, error_status in self.__sentence_fetcher(self.__card["word"], batch_size):
                yield sentence_batch, error_status
                if self.__local_sentences_flag:  # can be changed by update_word method
                    break
            else:
                self.__local_sentences_flag = True
