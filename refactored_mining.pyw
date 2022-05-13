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
        parsing_function: Callable[[str], list[dict]] = kwargs.get("parsing_function")
        local_dict_path: str = kwargs.get("local_dict_path", "")

        if os.path.isfile(local_dict_path):
            self._is_local = True
            with open(local_dict_path, "r", encoding="UTF-8") as f:
                self.local_dictionary = json.load(f)
        elif parsing_function is not None:
            self._is_local = False
            self.parsing_function: Callable[[str], list[dict]] = parsing_function
            self.local_dictionary = {}
        else:
            raise Exception("Wrong parameters for CardGenerator class!")

    def get(self, query: str, **kwargs) -> list[dict]:
        getting_function: Callable[[dict], bool] = kwargs.get("getting_function",
                                                              lambda card: True if card.get("word") == query else False)
        source = self.local_dictionary if self._is_local else self.parsing_function(query)
        return [card for card in source if getting_function(card)]


class Deck:
    def __init__(self, json_deck_path: str, current_deck_pointer: int, ):
        if os.path.exists(json_deck_path):
            with open(json_deck_path, "r", encoding="UTF-8") as f:
                self._deck = json.load(f)
                self._deck_pointer = min(current_deck_pointer, len(self._deck) - 1)
        else:
            self._deck = []
            self._deck_pointer = -1

    def __len__(self):
        return len(self._deck)

    def __getitem__(self, item: int) -> dict:
        return self._deck[item] if -1 <= item < len(self) else {}

    def add_card_to_deck(self, query):
        pass

    def get_card(self) -> dict:
        cur_card = self[self._deck_pointer]
        if cur_card:
            self._deck_pointer += 1
        return cur_card

    def move(self, n) -> None:
        self._deck_pointer = min(max(self._deck_pointer + n, 0), len(self) - 1)


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




root = App()
root.mainloop()