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

import parsers.image_parsers
import parsers.word_parsers.local
import parsers.word_parsers.web
import parsers.sentence_parsers

from CONSTS import *
from utils.cards import *


class App(Tk):
    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)
        self.CONFIG, error_code = App.load_conf_file()
        self.HISTORY = App.load_history_file()
        if not self.HISTORY.get(self.CONFIG["directories"]["last_open_file"]):
            self.HISTORY[self.CONFIG["directories"]["last_open_file"]] = 0

        if error_code:
            self.destroy()

        self.web_word_parsers = App.get_web_word_parsers()
        self.local_word_parsers = App.get_local_word_parsers()
        self.web_sent_parsers = App.get_sentence_parsers()
        self.image_parsers = App.get_image_parsers()

        if self.CONFIG["scrappers"]["parser_type"] == "web":
            cd = CardGenerator(
                parsing_function=self.web_word_parsers[self.CONFIG["scrappers"]["parser_name"]].define,
                item_converter=self.web_word_parsers[self.CONFIG["scrappers"]["parser_name"]].translate)
        elif self.CONFIG["scrappers"]["parser_type"] == "local":
            cd = CardGenerator(
                local_dict_path="./media/{}.json".format(
                    self.web_word_parsers[self.CONFIG["scrappers"]["parser_name"]].DICTIONARY_PATH),
                item_converter=self.web_word_parsers[self.CONFIG["scrappers"]["parser_name"]].translate)
        else:
            raise NotImplemented("Unknown parser_type: {}!".format(self.CONFIG["scrappers"]["parser_type"]))

        self.deck = Deck(json_deck_path=self.CONFIG["directories"]["last_open_file"],
                         current_deck_pointer=self.HISTORY[self.CONFIG["directories"]["last_open_file"]],
                         card_generator=cd)

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
                                            "parser_type": "web",
                                            "parser_name": "cambridge_US",
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

    @staticmethod
    def iter_namespace(ns_pkg):
        # Specifying the second argument (prefix) to iter_modules makes the
        # returned name an absolute name instead of a relative one. This allows
        # import_module to work without having to do additional modification to
        # the name.
        return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

    @staticmethod
    def get_web_word_parsers() -> dict:
        web_word_parsers = {}
        for finder, name, ispkg in App.iter_namespace(parsers.word_parsers.local):
            parser_trunc_name = name.split(sep=".")[-1]
            if name.startswith('parsers.word_parsers.web'):
                web_word_parsers[parser_trunc_name] = importlib.import_module(name)
        return web_word_parsers

    @staticmethod
    def get_local_word_parsers() -> dict:
        local_word_parsers = {}
        for finder, name, ispkg in App.iter_namespace(parsers.word_parsers.local):
            parser_trunc_name = name.split(sep=".")[-1]
            if name.startswith('parsers.word_parsers.local'):
                local_word_parsers[parser_trunc_name] = importlib.import_module(name)
        return local_word_parsers

    @staticmethod
    def get_sentence_parsers() -> dict:
        web_sent_parsers = {}
        for finder, name, ispkg in App.iter_namespace(parsers.sentence_parsers):
            parser_trunc_name = name.split(sep=".")[-1]
            if name.startswith('parsers.sentence_parsers.web'):
                web_sent_parsers[parser_trunc_name] = importlib.import_module(name)
        return web_sent_parsers

    @staticmethod
    def get_image_parsers() -> dict:
        image_parsers = {}
        for finder, name, ispkg in App.iter_namespace(parsers.image_parsers):
            parser_trunc_name = name.split(sep=".")[-1]
            image_parsers[parser_trunc_name] = importlib.import_module(name)
        return image_parsers
