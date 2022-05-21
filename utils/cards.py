from typing import Callable, Iterator, Union
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


class CardStorage:
    def __init__(self):
        self._deck = []
        self._pointer_position = 0

    def get_pointer_position(self) -> int:
        return self._pointer_position

    def get_deck(self) -> list[dict]:
        return self._deck

    def __len__(self):
        return len(self._deck)

    def move(self, n: int) -> None:
        self._pointer_position = min(max(self._pointer_position + n, 0), len(self))


class Deck(CardStorage):
    def __init__(self, json_deck_path: str, current_deck_pointer: int, card_generator: CardGenerator):
        super().__init__()
        if os.path.isfile(json_deck_path):
            with open(json_deck_path, "r", encoding="UTF-8") as f:
                self._deck = json.load(f)
            self._pointer_position = self._starting_position = min(max(len(self._deck) - 1, 0),
                                                                     max(0, current_deck_pointer))
        else:
            raise Exception("Invalid _deck path!")
        self._cards_left = len(self) - self._pointer_position
        self._card_generator: CardGenerator = card_generator

    def set_card_generator(self, value: CardGenerator):
        assert (isinstance(value, CardGenerator))
        self._card_generator = value

    def get_starting_position(self):
        return self._starting_position

    def get_n_cards_left(self) -> int:
        return self._cards_left

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._deck[item] if self._starting_position <= item < len(self) else {}
        elif isinstance(item, slice):
            return self._deck[item]

    def move(self, n: int) -> None:
        super().move(n)
        self._cards_left = len(self) - self._pointer_position

    def __repr__(self):
        res = f"Deck\nLength: {len(self)}\n" \
              f"Pointer position: {self._pointer_position}\n" \
              f"Cards left: {self._cards_left}\n"
        for index, item in enumerate(self, 0):
            if not item:
                break
            if index == self._pointer_position or index == self._starting_position:
                res += "C" if index == self._pointer_position else " "
                res += "S" if index == self._starting_position else " "

                res += " --> "
            else:
                res += " " * 7
            res += f"{index}: {item}\n"
        return res

    def add_card_to_deck(self, query: str, **kwargs):
        res: list[dict] = self._card_generator.get(query, **kwargs)
        self._deck = self[:self._pointer_position] + res + self[self._pointer_position:]
        self._cards_left += len(res)

    def get_card(self) -> dict:
        cur_card = self[self._pointer_position]
        if cur_card:
            self._pointer_position += 1
            self._cards_left -= 1
        return cur_card


class SavedDeck(CardStorage):
    def __init__(self):
        super().__init__()

    def append(self, item: dict[str, Union[str, list[str]]]):
        self._deck.append(item)
        self._pointer_position += 1

    def move(self, n: int) -> None:
        super().move(n)
        del self._deck[self._pointer_position:]

    def __repr__(self):
        res = f"Deck\nLength: {len(self)}\n" \
              f"Pointer position: {self._pointer_position}\n"
        for index, item in enumerate(self._deck, 0):
            if not item:
                break
            res += "L --> " if index == self._pointer_position else " " * 6
            res += f"{index}: {item}\n"
        res += "L --> " if len(self) == self._pointer_position else " " * 6
        return res

class SentenceFetcher:
    def __init__(self,
                 sent_fetcher: Callable[[str, int], Iterator[tuple[list[str], bool]]] = lambda *_: [[], True],
                 sentence_batch_size=5):
        self._word: str = ""
        self._sentences: list[str] = []
        self._sentence_fetcher: Callable[[str, int], Iterator[tuple[list[str], bool]]] = sent_fetcher
        self._batch_size: int = sentence_batch_size
        self._sentence_pointer: int = 0
        self._sent_batch_generator: Iterator[tuple[list[str], str]] = self._get_sent_batch_generator()
        self._local_sentences_flag: bool = True
        self._update_status: bool = False

    def __call__(self, base_word, base_sentences):
        self._word = base_word
        # REFERENCE!!!
        self._sentences = base_sentences
        self._local_sentences_flag = True
        self._sentence_pointer = 0

    def update_word(self, new_word: str):
        if self._word != new_word:
            self._word = new_word
            self._update_status = True

    def __get_sent_batch_generator(self) -> Iterator[tuple[list[str], str]]:
        """
        Yields: Sentence_batch, error_message
        """
        while True:
            if self._local_sentences_flag:
                while self._sentence_pointer < len(self._sentences):
                    # checks for update even before the first iteration
                    if self._update_status:
                        break
                    yield self._sentences[self._sentence_pointer:self._sentence_pointer + self._batch_size], ""
                    self._sentence_pointer += self._batch_size
                self._sentence_pointer = 0
                self._local_sentences_flag = False
                # __sentence_fetcher doesn't need update before it's first iteration
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

    def get_sentence_batch(self, word: str) -> tuple[list[str], str]:
        self.update_word(word)
        return next(self._sent_batch_generator)
