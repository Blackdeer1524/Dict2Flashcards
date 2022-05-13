import importlib
import json
import os
import re
import sys
import csv
import pkgutil
import time
import traceback
import urllib.request
import webbrowser
from functools import partial
from pathlib import Path

from tkinter import Label, Button, Checkbutton, Toplevel, Menu, Frame, BooleanVar, IntVar
from tkinter import messagebox
from tkinterdnd2 import Tk
from tkinter.filedialog import askopenfilename, askdirectory
from enum import IntEnum

import requests
from playsound import playsound
from bindglobal import BindGlobal
from typing import Callable

from parsers import image_parsers, word_parsers, sentence_parsers
from utils import ScrolledFrame, ImageSearch, AudioDownloader, TextWithPlaceholder, EntryWithPlaceholder
from utils import spawn_toplevel_in_center, get_option_menu
from utils import error_handler
from utils import get_save_audio_name, get_local_audio_path
from utils import SearchType, remove_special_chars, string_search
from utils import AUDIO_NAME_SPEC_CHARS

from CONSTS import *


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
            raise Exception("Wrong parameters for CardGenerator class!")

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
                self._deck = json.load(f)
                self._next_item_index = min(current_deck_pointer, max(len(self._deck) - 1, 0))
        else:
            raise Exception("Invalid deck path!")
        self._card_generator: CardGenerator = card_generator

    def __len__(self):
        return len(self._deck)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._deck[item] if 0 <= item < len(self) else {}
        elif isinstance(item, slice):
            return self._deck[item]

    def __add__(self, other):
        if isinstance(other, list):
            return self._deck + other
        elif isinstance(other, Deck):
            return self._deck + other._deck
        else:
            raise Exception(f"Undefined addition for Deck class and {type(other)}!")

    def add_card_to_deck(self, query: str, **kwargs):
        """
        word_filter: Callable[[comparable: str, query_word: str], bool]
        additional_filter: Callable[[translated_word_data: dict], bool]
        """

        res: list[dict] = self._card_generator.get(query, **kwargs)
        self._deck = self[:self._next_item_index] + res + self[self._next_item_index:]

    def get_card(self) -> dict:
        cur_card = self[self._next_item_index]
        if cur_card:
            self._next_item_index += 1
        return cur_card

    def move(self, n) -> None:
        self._next_item_index = min(max(self._next_item_index + n, 0), len(self) - 1)


class App(Tk):
    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)
        self.HISTORY = App.load_history_file()
        self.CONFIG, error_code = App.load_conf_file()
        if error_code:
            self.destroy()

        
    @staticmethod
    def load_history_file() -> dict:
        if not os.path.exists(HISTORY_FILE_PATH):
            history_json = {}
        else:
            with open(HISTORY_FILE_PATH, "r", encoding="UTF-8") as f:
                history_json = json.load(f)
        return history_json

    @staticmethod
    def load_conf_file() -> (dict, bool):
        standard_conf_file = {"app": {"theme": "dark",
                                      "main_window_position": "",
                                      "image_search_position": "+0+0"},
                              "scrappers": {"base_sentence_parser": "web_sentencedict",
                                            "base_word_parser": "web_cambridge_UK",
                                            "base_image_parser": "google",
                                            "local_search_type": 0,
                                            "local_audio": "",
                                            "non_pos_specific_search": False},
                              "directories": {"media_dir": "",
                                              "last_open_file": "",
                                              "last_save_dir": ""},
                              "tags": {"hierarchical_pref": "eng",
                                       "include_domain": True,
                                       "include_level": True,
                                       "include_region": True,
                                       "include_usage": True,
                                       "include_pos": True},
                              "anki": {"anki_deck": "",
                                       "anki_field": ""}
                              }

        if not os.path.exists(CONFIG_FILE_PATH):
            conf_file = {}
        else:
            with open(CONFIG_FILE_PATH, "r", encoding="UTF-8") as f:
                conf_file = json.load(f)

        check_queue = [(standard_conf_file, conf_file)]
        for (src, dst) in check_queue:
            for checking_key in src:
                if dst.get(checking_key) is None:
                    dst[checking_key] = src[checking_key]
                elif type(dst[checking_key]) == dict:
                    check_queue.append((src[checking_key], dst[checking_key]))

        if not conf_file["directories"]["media_dir"]:
            conf_file["directories"]["media_dir"] = askdirectory(title="Выберете директорию для медиа файлов",
                                                                 mustexist=True,
                                                                 initialdir=STANDARD_ANKI_MEDIA)
            if not conf_file["directories"]["media_dir"]:
                return conf_file, 1
                        
        if not conf_file["directories"]["last_open_file"]:
            new_word_file = askopenfilename(title="Выберете JSON файл со словами", 
                                               filetypes=(("JSON", ".json"),),
                                               initialdir="./")
            if not conf_file["directories"]["media_dir"]:
                return conf_file, 1
            
        if not conf_file["directories"]["last_save_dir"]:
            saving_location = askdirectory(title="Выберете директорию сохранения", 
                                           mustexist=True,
                                           initialdir="./")
            if not conf_file["directories"]["media_dir"]:
                return conf_file, 1
        return conf_file, 0


if __name__ == "__main__":
    from pprint import pprint

    def translate(word_dict):
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

    cd = CardGenerator(local_dict_path="./parsers/media/cambridge.json", item_converter=translate)
    # pprint(cd.get("do", word_filter=everywhere, additional_filter=find_with_alts))

    # from parsers.word_parsers.web_cambridge_US import define
    # cd = CardGenerator(parsing_function=define, item_converter=translate)
    # pprint(cd.get("do", word_filter=everywhere, additional_filter=find_with_alts))

    # d = Deck(json_deck_path="Words/custom.json", card_generator=cd, current_deck_pointer=0)
    # d.add_card_to_deck("do")

    input()