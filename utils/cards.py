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


class SentenceFetcher:
    def __init__(self,
                 sent_fetcher: Callable[[str, int], Iterator[tuple[list[str], bool]]] = lambda *_: [[], True],
                 sentence_batch_size=5):
        self.__word: str
        self.__sentences: list[str]
        self.__sentence_fetcher: Callable[[str, int], Iterator[tuple[list[str], bool]]] = sent_fetcher
        self.__batch_size: int = sentence_batch_size
        self.__sentence_pointer: int = 0
        self.__sent_batch_generator: Iterator[tuple[list[str], str]] = self.__get_sent_batch_generator()
        self.__local_sentences_flag: bool = True
        self.__update_status: bool = False

    def __call__(self, base_word, base_sentences):
        self.__word = base_word
        # REFERENCE!!!
        self.__sentences = base_sentences
        self.__local_sentences_flag = True
        self.__sentence_pointer = 0

    def update_word(self, new_word: str):
        if self.__word != new_word:
            self.__word = new_word
            self.__update_status = True

    def __get_sent_batch_generator(self) -> Iterator[tuple[list[str], str]]:
        """
        Yields: Sentence_batch, error_message
        """
        while True:
            if self.__local_sentences_flag:
                while self.__sentence_pointer < len(self.__sentences):
                    # checks for update even before the first iteration
                    if self.__update_status:
                        break
                    yield self.__sentences[self.__sentence_pointer:self.__sentence_pointer + self.__batch_size], ""
                    self.__sentence_pointer += self.__batch_size
                self.__sentence_pointer = 0
                self.__local_sentences_flag = False
                # __sentence_fetcher doesn't need update before it's first iteration
                # because of its first argument
                self.__update_status = False

            for sentence_batch, error_message in self.__sentence_fetcher(self.__word, self.__batch_size):
                yield sentence_batch, error_message
                if self.__update_status:
                    self.__update_status = False
                    break
                if self.__local_sentences_flag or error_message:
                    break
            else:
                self.__local_sentences_flag = True

    def get_sentence_batch(self, word: str) -> tuple[list[str], str]:
        self.update_word(word)
        return next(self.__sent_batch_generator)
