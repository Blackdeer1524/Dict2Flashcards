from typing import Callable
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
            self.__cur_item_index = min(max(len(self.__deck) - 1, 0), current_deck_pointer)
        else:
            raise Exception("Invalid deck path!")
        self.__card_generator: CardGenerator = card_generator

    def set_card_generator(self, value: CardGenerator):
        assert (isinstance(value, CardGenerator))
        self.__card_generator = value

    def get_deck_pointer(self) -> int:
        return self.__cur_item_index

    def get_deck(self) -> list[dict]:
        return self.__deck

    def __len__(self):
        return len(self.__deck)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.__deck[item] if 0 <= item < len(self) else {}
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
        res = f"Deck\nLength: {len(self)}\nPointer position: {self.__cur_item_index}\n"
        for index, item in enumerate(self, 0):
            if not item:
                break
            res += "--> " if index == self.__cur_item_index else " " * 4
            res += f"{index}: {item}\n"
        return res

    def add_card_to_deck(self, query: str, **kwargs):
        """
        word_filter: Callable[[comparable: str, query_word: str], bool]
        additional_filter: Callable[[translated_word_data: dict], bool]
        """

        res: list[dict] = self.__card_generator.get(query, **kwargs)
        self.__deck = self[:self.__cur_item_index] + res + self[self.__cur_item_index:]

    def get_card(self) -> dict:
        cur_card = self[self.__cur_item_index]
        if cur_card:
            self.__cur_item_index += 1
        return cur_card

    def move(self, n: int) -> None:
        self.__cur_item_index = min(max(self.__cur_item_index + n, 0), len(self) - 1)


if __name__ == "__main__":
    from pprint import pprint

    def translate(word_dict: (str, dict)) -> list[dict]:
        """
        Adapt new parser to legacy code
        """
        word_list = []
        word, data = word_dict
        for pos in data:
            audio = data[pos].get("US_audio_link", "")
            for definition, examples, domain, labels_and_codes, level, \
                region, usage, image, alt_terms in zip(data[pos]["definitions"],
                                                       data[pos]["examples"],
                                                       data[pos]["domain"],
                                                       data[pos]["labels_and_codes"],
                                                       data[pos]["level"],
                                                       data[pos]["region"],
                                                       data[pos]["usage"],
                                                       data[pos]["image_links"],
                                                       data[pos]["alt_terms"]):
                # {"word": слово_n, "meaning": значение_n, "Sen_Ex": [пример_1, ..., пример_n]}
                current_word_dict = {"word": word.strip(), "meaning": definition,
                                     "Sen_Ex": examples, "domain": domain, "level": level, "region": region,
                                     "usage": usage, "pos": pos, "audio_link": audio, "image_link": image,
                                     "alt_terms": alt_terms}
                current_word_dict = {key: value for key, value in current_word_dict.items() if
                                     value not in ("", [])}
                word_list.append(current_word_dict)
        return word_list

    def find_with_alts(translated_card: dict) -> bool:
        if translated_card.get("pos") == "verb":
            return True
        return False

    def everywhere(comparable, query):
        return True if query in comparable else False

    cd = CardGenerator(local_dict_path="./media/cambridge.json", item_converter=translate)
    # pprint(cd.get("do", word_filter=everywhere, additional_filter=find_with_alts))

    # from parsers.word_parsers.web_cambridge_US import define
    # cd = CardGenerator(parsing_function=define, item_converter=translate)
    # pprint(cd.get("do", word_filter=everywhere, additional_filter=find_with_alts))

    d = Deck(json_deck_path="Words/custom.json", card_generator=cd, current_deck_pointer=0)

    while True:
        option = input("1: add_card\n2: display_deck\n3: next\n4: prev\n5: move (n)\n6: exit\n")
        if option == "1":
            word_query = input("Введите слово: ")
            d.add_card_to_deck(word_query)
        elif option == "2":
            print(d)
        elif option == "3":
            d.get_card()
        elif option == "4":
            d.move(-1)
        elif option == "5":
            n = int(input("На сколько сдвинуть: "))
            d.move(n)
        elif option == "6":
            break
        else:
            print("Error!")
