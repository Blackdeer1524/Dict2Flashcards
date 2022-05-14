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

from parsers import image_parsers, word_parsers, sentence_parsers
from utils import ScrolledFrame, ImageSearch, AudioDownloader, TextWithPlaceholder, EntryWithPlaceholder
from utils import spawn_toplevel_in_center, get_option_menu
from utils import error_handler
from utils import get_save_audio_name, get_local_audio_path
from utils import SearchType, remove_special_chars, string_search
from utils import AUDIO_NAME_SPEC_CHARS


class App(Tk):
    class CardStatus(IntEnum):
        skip = 0
        add = 1
        delete = 2
    
    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)
        self.withdraw()

        # Create and load files
        if not os.path.exists("./temp/"):
            os.makedirs("./temp")
        
        self.LOCAL_DICTIONARIES_DIR = "./parsers/media/"
        if not os.path.exists(self.LOCAL_DICTIONARIES_DIR):
            os.makedirs(self.LOCAL_DICTIONARIES_DIR)
        
        if not os.path.exists("./Cards/"):
            os.makedirs("./Cards")

        if not os.path.exists("./Words/"):
            os.makedirs("./Words")

        self.custom_file_path = "./Words/custom.json"
        if not os.path.exists(self.custom_file_path):
            with open(self.custom_file_path, "w", encoding="UTF-8") as custom_file:
                json.dump([], custom_file)

        self.history_file_path = Path("./history.json")
        if self.history_file_path.is_file():
            with open(self.history_file_path, "r") as read_file:
                self.JSON_HISTORY_FILE = json.load(read_file)
        else:
            self.JSON_HISTORY_FILE = {}
            self.save_history_file()

        self.json_conf_file_path = Path("./config.json")
        if self.json_conf_file_path.is_file():
            with open(self.json_conf_file_path, "r") as read_file:
                self.JSON_CONF_FILE = json.load(read_file)
        else:
            self.JSON_CONF_FILE = {"app": {"theme": "dark",
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
            self.save_conf_file()

        if not self.JSON_CONF_FILE["app"]["main_window_position"]:
            self.JSON_CONF_FILE["app"]["main_window_position"] = "+0+0"

        self.geometry(self.JSON_CONF_FILE["app"]["main_window_position"])
        
        # Visuals
        if self.JSON_CONF_FILE["app"]["theme"] == "dark":
            self.button_bg = "#3a3a3a"
            self.text_bg = "#3a3a3a"
            self.widget_fg = "#FFFFFF"
            self.text_selectbackground = "#F0F0F0"
            self.text_selectforeground = "#000000"
            self.main_bg = "#2f2f31"

        elif self.JSON_CONF_FILE["app"]["theme"] == "white":
            self.button_bg = "#E1E1E1"
            self.text_bg = "#FFFFFF"
            self.widget_fg = "SystemWindowText"
            self.text_selectbackground = "SystemHighlight"
            self.text_selectforeground = "SystemHighlightText"
            self.main_bg = "#F0F0F0"
        
        self.label_cfg = {"background": self.main_bg, 
                             "foreground": self.widget_fg}
        self.button_cfg = {"background": self.button_bg,
                              "foreground": self.widget_fg,
                              "activebackground": self.button_bg,
                              "activeforeground": self.text_selectbackground}
        self.text_cfg = {"background": self.text_bg, 
                            "foreground": self.widget_fg,
                            "selectbackground": self.text_selectbackground,
                            "selectforeground": self.text_selectforeground, 
                            "insertbackground": self.text_selectbackground}
        self.entry_cfg = {"background": self.text_bg, "foreground": self.widget_fg,
                             "selectbackground": self.text_selectbackground,
                             "selectforeground": self.text_selectforeground,
                             "insertbackground": self.text_selectbackground}
        self.checkbutton_cfg = {"background": self.main_bg,
                                   "foreground": self.widget_fg,
                                   "activebackground": self.main_bg,
                                   "activeforeground": self.widget_fg,
                                   "selectcolor": self.main_bg}
        self.toplevel_cfg = {"bg": self.main_bg}

        self.Label = partial(Label, **self.label_cfg)
        self.Button = partial(Button,  **self.button_cfg)
        self.Text = partial(TextWithPlaceholder, **self.text_cfg)
        self.Entry = partial(EntryWithPlaceholder, **self.entry_cfg)
        self.Checkbutton = partial(Checkbutton, **self.checkbutton_cfg)
        self.Toplevel = partial(Toplevel, **self.toplevel_cfg)

        # Parsers
        def iter_namespace(ns_pkg):
            # Specifying the second argument (prefix) to iter_modules makes the
            # returned name an absolute name instead of a relative one. This allows
            # import_module to work without having to do additional modification to
            # the name.
            return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

        self.word_parsers_names = []
        self.LOCAL_DICT = {}
        self.non_pos_spec_search_var = BooleanVar()
        self.non_pos_spec_search_var.set(self.JSON_CONF_FILE["scrappers"]["non_pos_specific_search"])
        self.discovered_web_word_parsers = {}
        self.discovered_local_word_parsers = {}
        for finder, name, ispkg in iter_namespace(word_parsers):
            # [21:] чтобы убрать parsers.word_parsers.
            parser_trunc_name = name[21:]
            if name.startswith('parsers.word_parsers.web'):
                self.discovered_web_word_parsers[parser_trunc_name] = importlib.import_module(name)
                self.word_parsers_names.append(parser_trunc_name)
            elif name.startswith('parsers.word_parsers.local'):
                self.discovered_local_word_parsers[parser_trunc_name] = importlib.import_module(name)
                self.word_parsers_names.append(parser_trunc_name)

        self.media_folders = [folder for folder in os.listdir("./parsers/media") if
                              os.path.isdir(os.path.join("./parsers/media", folder))]

        self.discovered_web_sent_parsers = {}
        for finder, name, ispkg in iter_namespace(sentence_parsers):
            if name.startswith('parsers.sentence_parsers.web'):
                self.discovered_web_sent_parsers[name[25:]] = importlib.import_module(name)

        self.discovered_image_parsers = {}
        for finder, name, ispkg in iter_namespace(image_parsers):
            self.discovered_image_parsers[name[22:]] = importlib.import_module(name)

        self.CURRENT_AUDIO_LINK = ""
        self.DICT_IMAGE_LINK = ""
        self.SCREEN_WIDTH = self.winfo_screenwidth()
        self.SCREEN_HEIGHT = self.winfo_screenheight()

        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'}

        self.MEANING_TEXT_HEIGHT = 4
        self.SENTENCE_TEXT_HEIGHT = 4
        self.TOP_TEXT_FIELDS_WIDTH = 58  # ширина Text widget для слова и его значения
        self.BOTTOM_TEXT_FIELDS_WIDTH = 45  # ширина Text widget для предложений

        self.word_parser_name = self.JSON_CONF_FILE["scrappers"]["base_word_parser"]
        self.sentence_parser_name = self.JSON_CONF_FILE["scrappers"]["base_sentence_parser"]
        self.image_parser_name = self.JSON_CONF_FILE["scrappers"]["base_image_parser"]

        self.change_word_parser(self.word_parser_name)
        self.sentence_parser = self.discovered_web_sent_parsers[self.sentence_parser_name].get_sentence_batch
        self.image_parser = self.discovered_image_parsers[self.image_parser_name].get_image_links

        self.get_needed(True)
        self.NEXT_ITEM_INDEX = self.START_INDEX

        self.IMAGES = []

        # Создание меню
        main_menu = Menu(self)
        filemenu = Menu(main_menu, tearoff=0)
        filemenu.add_command(label="Создать", command=self.create_new_file)
        filemenu.add_command(label="Открыть", command=self.open_new_file)
        filemenu.add_command(label="Сохранить", command=self.save_button)
        filemenu.add_separator()
        filemenu.add_command(label="Справка", command=self.help_command)
        filemenu.add_separator()
        filemenu.add_command(label="Скачать аудио", command=lambda: self.download_audio(choose_file=True))
        filemenu.add_separator()
        filemenu.add_command(label="Сменить пользователя", command=self.change_media_dir)
        main_menu.add_cascade(label="Файл", menu=filemenu)

        self.domain_var = BooleanVar(name="domain")
        self.level_var = BooleanVar(name="level")
        self.region_var = BooleanVar(name="region")
        self.usage_var = BooleanVar(name="usage")
        self.pos_var = BooleanVar(name="pos")

        self.DICT_TAGS = {"domain": [[""], self.domain_var],
                          "level": [[""], self.level_var],
                          "region": [[""], self.region_var],
                          "usage": [[""], self.usage_var],
                          "pos": ["", self.pos_var]}

        self.domain_var.set(self.JSON_CONF_FILE["tags"]["include_domain"])
        self.level_var.set(self.JSON_CONF_FILE["tags"]["include_level"])
        self.region_var.set(self.JSON_CONF_FILE["tags"]["include_region"])
        self.usage_var.set(self.JSON_CONF_FILE["tags"]["include_usage"])
        self.pos_var.set(self.JSON_CONF_FILE["tags"]["include_pos"])

        tag_menu = Menu(main_menu, tearoff=0)
        tag_menu.add_checkbutton(label='domain', variable=self.domain_var)
        tag_menu.add_checkbutton(label='level', variable=self.level_var)
        tag_menu.add_checkbutton(label='region', variable=self.region_var)
        tag_menu.add_checkbutton(label='usage', variable=self.usage_var)
        tag_menu.add_checkbutton(label='pos', variable=self.pos_var)
        main_menu.add_cascade(label='Тэги', menu=tag_menu)

        main_menu.add_command(label="Добавить", command=lambda: self.call_second_window("call_parser"))
        main_menu.add_command(label="Перейти", command=lambda: self.call_second_window("find"))
        main_menu.add_command(label="Статистика", command=lambda: self.call_second_window("stat"))

        theme_menu = Menu(main_menu, tearoff=0)
        self.index2theme_map = {0: "white",
                                1: "dark"}
        self.theme2index_map = {value: key for key, value in self.index2theme_map.items()}

        self.theme_index_var = IntVar(value=self.theme2index_map[self.JSON_CONF_FILE["app"]["theme"]])
        theme_menu.add_radiobutton(label="Светлая", variable=self.theme_index_var, value=0, command=self.change_theme)
        theme_menu.add_radiobutton(label="Тёмная", variable=self.theme_index_var, value=1, command=self.change_theme)
        main_menu.add_cascade(label="Тема", menu=theme_menu)

        main_menu.add_command(label="Anki", command=lambda: self.call_second_window("anki"))
        main_menu.add_command(label="Выход", command=self.on_closing)

        self.config(menu=main_menu)

        def change_to_start_geometry():
            self.JSON_CONF_FILE["app"]["image_search_position"] = "+0+0"
            self.geometry("+0+0")

        self.bind("<Escape>", lambda event: self.on_closing())
        self.bind("<Control-Key-0>", lambda event: change_to_start_geometry())
        self.bind("<Control-d>", lambda event: self.delete_command())
        self.bind("<Control-q>", lambda event: self.skip_command())
        self.bind("<Control-s>", lambda event: self.save_button())
        self.bind("<Control-f>", lambda event: self.call_second_window("find"))
        self.bind("<Control-e>", lambda event: self.call_second_window("stat"))
        self.bind("<Control-Shift_L><A>", lambda event: self.call_second_window("call_parser"))
        self.bind("<Control-z>", lambda event: self.prev_command())
        self.bind("<Control-Key-1>", lambda event: self.choose_sentence(0))
        self.bind("<Control-Key-2>", lambda event: self.choose_sentence(1))
        self.bind("<Control-Key-3>", lambda event: self.choose_sentence(2))
        self.bind("<Control-Key-4>", lambda event: self.choose_sentence(3))
        self.bind("<Control-Key-5>", lambda event: self.choose_sentence(4))

        self.option_menu_conf = {"background": self.button_bg, "foreground": self.widget_fg,
                                 "activebackground": self.button_bg, "activeforeground": self.text_selectbackground,
                                 "highlightthickness": 0, "relief": "ridge"}
        self.option_submenu_params = {"background": self.button_bg,
                                      "foreground": self.widget_fg,
                                      "activebackground": self.text_selectbackground,
                                      "activeforeground": self.text_selectforeground}

        self.browse_button = self.Button(text="Найти в браузере", command=self.web_search_command)
        self.config_word_parser_button = self.Button(text="Настроить словарь", command=self.configure_dict)

        self.find_image_button = self.Button(text="Добавить изображение", command=lambda: self.start_image_search())
        self.image_word_parsers_names = list(self.discovered_image_parsers)
        self.image_parser_option_menu = get_option_menu(self,
                                                        init_text=self.image_parser_name,
                                                        values=self.image_word_parsers_names,
                                                        command=lambda parser_name:
                                                        self.change_image_parser(parser_name),
                                                        widget_configuration=self.option_menu_conf,
                                                        option_submenu_params=self.option_submenu_params)

        self.add_sentences_button = self.Button(text="Добавить предложения")
        self.sentence_parser_option_menu = get_option_menu(self,
                                                           init_text=self.sentence_parser_name,
                                                           values=list(self.discovered_web_sent_parsers),
                                                           command=lambda parser_name:
                                                           self.change_sentence_parser(parser_name),
                                                           widget_configuration=self.option_menu_conf,
                                                           option_submenu_params=self.option_submenu_params)

        self.word_text = self.Text(self, placeholder="Слово", height=2, width=self.TOP_TEXT_FIELDS_WIDTH)
        self.alt_terms_field = self.Text(self, height=1, width=self.TOP_TEXT_FIELDS_WIDTH,
                                         bg=self.button_bg, relief="ridge", state="disabled")
        self.meaning_text = self.Text(self, placeholder="Значение", height=self.MEANING_TEXT_HEIGHT, width=self.TOP_TEXT_FIELDS_WIDTH)

        self.sent_text_list = []
        self.buttons_list = []

        for i in range(5):
            self.sent_text_list.append(self.Text(self, placeholder=f"Предложение {i + 1}",
                                       height=self.SENTENCE_TEXT_HEIGHT,
                                       width=self.BOTTOM_TEXT_FIELDS_WIDTH))
            self.sent_text_list[-1].fill_placeholder()
            self.buttons_list.append(self.Button(text=f"{i + 1}", command=lambda x=i: self.choose_sentence(x), width=3))

        self.delete_button = self.Button(text="Del", command=self.delete_command, width=3)
        self.prev_button = self.Button(text="Prev", command=self.prev_command, state="disabled", width=3)
        self.sound_button = self.Button(text="Play", command=self.play_sound, width=3)
        self.anki_button = self.Button(text="Anki", command=self.anki_browser_command, width=3)
        self.skip_button = self.Button(text="Skip", command=self.skip_command, width=3)

        self.user_tags_field = self.Entry(self, placeholder="Тэги")
        self.user_tags_field.fill_placeholder()

        self.tag_prefix_field = self.Entry(self, width=1, justify="center")
        self.tag_prefix_field.insert(0, self.JSON_CONF_FILE["tags"]["hierarchical_pref"])
        self.dict_tags_field = self.Text(self, width=self.TOP_TEXT_FIELDS_WIDTH, height=2, relief="ridge",
                                         bg=self.button_bg, state="disabled")

        self.text_padx = 10
        self.text_pady = 2

        # Расстановка виджетов
        self.grid_columnconfigure(1, weight=1)

        self.browse_button.grid(row=0, column=0, padx=self.text_padx, pady=(self.text_pady, 0), sticky="news")
        self.config_word_parser_button.grid(row=0, column=1, padx=self.text_padx, pady=(self.text_pady, 0), columnspan=4, sticky="news")

        self.word_text.grid(row=1, column=0, padx=self.text_padx, pady=self.text_pady, columnspan=5, sticky="news")

        self.alt_terms_field.grid(row=2, column=0, padx=self.text_padx, columnspan=5, sticky="news")

        self.find_image_button.grid(row=3, column=0, padx=self.text_padx, pady=self.text_pady, sticky="news")
        self.image_parser_option_menu.grid(row=3, column=1, padx=self.text_padx, pady=self.text_pady, columnspan=4, sticky="news")

        self.meaning_text.grid(row=4, column=0, padx=self.text_padx, columnspan=5, sticky="news")

        self.sentence_parser_option_menu.grid(row=5, column=1, padx=self.text_padx, pady=self.text_pady, columnspan=4, sticky="news")
        self.add_sentences_button.grid(row=5, column=0, padx=self.text_padx, pady=self.text_pady, sticky="news")

        for i in range(5):
            c_pady = self.text_pady if i % 2 else 0
            self.sent_text_list[i].grid(row=5 + i + 1, column=0, columnspan=3, padx=self.text_padx, pady=c_pady,
                                        sticky="news")
            self.buttons_list[i].grid(row=5 + i + 1, column=3, padx=0, pady=c_pady, sticky="news")

        self.delete_button.grid(row=6, column=4, padx=self.text_padx, pady=0, sticky="news")
        self.prev_button.grid(row=7, column=4, padx=self.text_padx, pady=self.text_pady, sticky="news")
        self.sound_button.grid(row=8, column=4, padx=self.text_padx, pady=0, sticky="news")
        self.anki_button.grid(row=9, column=4, padx=self.text_padx, pady=self.text_pady, sticky="news")
        self.skip_button.grid(row=10, column=4, padx=self.text_padx, pady=0, sticky="news")

        self.user_tags_field.grid(row=11, column=0, padx=self.text_padx, pady=self.text_pady, columnspan=3, sticky="news")
        self.tag_prefix_field.grid(row=11, column=3, padx=(0, self.text_padx), pady=self.text_pady, columnspan=2, sticky="news")
        self.dict_tags_field.grid(row=12, column=0, padx=self.text_padx, pady=(0, self.text_pady), columnspan=5, sticky="news")

        self.configure(bg=self.main_bg)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Заставляет приложение вызваться поверх остальных окон
        # self.call('wm', 'attributes', '.', '-topmost', True)

        def focus_next_window(event):
            event.widget.tk_focusNext().focus()
            return ("break")

        def focus_prev_window(event):
            event.widget.tk_focusPrev().focus()
            return ("break")

        self.new_order = [self.browse_button, self.word_text, self.find_image_button, self.meaning_text, self.add_sentences_button] + self.sent_text_list + \
                    [self.user_tags_field] + self.buttons_list + [self.delete_button, self.prev_button, self.anki_button, self.skip_button, self.tag_prefix_field]

        for widget_index in range(len(self.new_order)):
            self.new_order[widget_index].lift()
            self.new_order[widget_index].bind("<Tab>", focus_next_window)
            self.new_order[widget_index].bind("<Shift-Tab>", focus_prev_window)

        self.bg = BindGlobal()
        self.bg.gbind("<Control-c-space>", lambda _: self.parse_word(self.clipboard_get()))

        self.resizable(0, 0)
        self.after(300_000, self.autosave)
        self.refresh()
        self.deiconify()
        self.WIDTH = self.winfo_width()
        self.HEIGHT = self.winfo_height()

    def change_theme(self):
        self.JSON_CONF_FILE["app"]["theme"] = self.index2theme_map[self.theme_index_var.get()]
        messagebox.showinfo(message="Изменения вступят в силу\nтолько после перезапуска программы")



    # Скраперы данных
    @error_handler(error_processing=show_errors)
    def change_word_parser(self, given_word_parser_name):
        given_word_parser_name = given_word_parser_name.strip()
        if given_word_parser_name.startswith("web"):
            self.parse = self.discovered_web_word_parsers[given_word_parser_name].define
            self.LOCAL_DICT = {}

        elif given_word_parser_name.startswith("local"):
            dict_name = self.discovered_local_word_parsers[given_word_parser_name].DICTIONARY_PATH
            with open(f"./parsers/media/{dict_name}.json", "r", encoding="utf-8") as dict_loader:
                self.LOCAL_DICT = json.load(dict_loader)
            self.parse = self.get_local_wrapper(given_word_parser_name)

        self.JSON_CONF_FILE["scrappers"]["base_word_parser"] = given_word_parser_name
        self.word_parser_name = given_word_parser_name

    @error_handler(error_processing=show_errors)
    def change_sentence_parser(self, given_sentence_parser_name):
        given_sentence_parser_name = given_sentence_parser_name.strip()
        if given_sentence_parser_name.startswith("web"):
            self.JSON_CONF_FILE["scrappers"]["base_sentence_parser"] = given_sentence_parser_name
            self.sentence_parser = self.discovered_web_sent_parsers[
                self.JSON_CONF_FILE["scrappers"]["base_sentence_parser"]].get_sentence_batch

    @error_handler(error_processing=show_errors)
    def change_image_parser(self, given_image_parser_name):
        given_image_parser_name = given_image_parser_name.strip()
        self.JSON_CONF_FILE["scrappers"]["base_image_parser"] = given_image_parser_name
        self.image_parser = self.discovered_image_parsers[self.JSON_CONF_FILE["scrappers"]["base_image_parser"]].get_image_links

    @error_handler(error_processing=show_errors)
    def start_image_search(self):
        def connect_images_to_card(instance):
            nonlocal word

            card_pattern = "<img src='{}.png'/>"
            saving_images_names = getattr(instance, "saving_images_names", [])
            saving_images_indices = getattr(instance, "saving_indices", [])

            for img_index in saving_images_indices:
                self.IMAGES.append(card_pattern.format(saving_images_names[img_index]))

            # получение координат на экране через instance.winfo_rootx(), instance.winfo_rooty() даёт некоторое смещение
            image_search_x = instance.winfo_rootx()
            image_search_y = instance.winfo_rooty() - 37  # compensate for title height
            self.JSON_CONF_FILE["app"]["image_search_position"] = f"+{image_search_x}+{image_search_y}"

        word = self.word_text.get(1.0, "end").strip()
        clean_word = remove_special_chars(word, sep='-')

        show_image_width = 250
        name_pattern = f"mined-{clean_word}" + "-{}"

        button_pady = button_padx = 10
        height_lim = self.winfo_height() * 7 // 8
        image_finder = ImageSearch(master=self, search_term=word, saving_dir=self.MEDIA_DIR,
                                   url_scrapper=self.image_parser, init_urls=[self.DICT_IMAGE_LINK],
                                   headers=self.headers,
                                   on_close_action=connect_images_to_card,
                                   show_image_width=show_image_width,
                                   saving_image_width=300, image_saving_name_pattern=name_pattern,
                                   button_padx=button_padx, button_pady=button_pady,
                                   window_height_limit=height_lim, window_bg=self.main_bg,
                                   command_button_params=self.button_cfg,
                                   entry_params=self.entry_cfg)
        image_finder.focus()
        image_finder.grab_set()
        image_finder.geometry(self.JSON_CONF_FILE["app"]["image_search_position"])
        image_finder.start()

    def save_history_file(self):
        with open("./history.json", "w") as saving_f:
            json.dump(self.JSON_HISTORY_FILE, saving_f, indent=3)

    def save_conf_file(self):
        with open(self.json_conf_file_path, "w") as f:
            json.dump(self.JSON_CONF_FILE, f, indent=3)

    def get_dict_local_audio_dir(self):
        return os.path.join(self.LOCAL_DICTIONARIES_DIR, self.JSON_CONF_FILE["scrappers"]["local_audio"])

    @error_handler(error_processing=show_errors)
    def play_sound(self):
        def show_download_error(exc):
            messagebox.showerror(message=f"Ошибка получения звука\n{exc}")

        pos = self.DICT_TAGS["pos"][0]

        if not self.JSON_CONF_FILE["scrappers"]["local_audio"]:
            word = remove_special_chars(self.word_text.get(1.0, "end").strip(), "-")
            audio_name = get_save_audio_name(word, pos, self.word_parser_name)
            temp_audio_path = os.path.join(os.getcwd(), "temp", audio_name)
            success = True
            if not os.path.exists(temp_audio_path):
                success = AudioDownloader.fetch_audio(self.CURRENT_AUDIO_LINK, temp_audio_path, self.headers, 5,
                                                      exception_action=lambda exc: show_download_error(exc))
            if success:
                playsound(temp_audio_path)
        else:
            word = remove_special_chars(self.word_text.get(1.0, "end").strip(), "-", AUDIO_NAME_SPEC_CHARS)
            a = self.get_dict_local_audio_dir()
            save_path = get_local_audio_path(word, pos, local_audio_folder_path=a)
            if save_path:
                playsound(save_path, block=True)
                return
            elif self.non_pos_spec_search_var.get():
                save_path = get_local_audio_path(word, local_audio_folder_path=a, with_pos=False)
                if save_path:
                    playsound(save_path, block=True)
                    return
            messagebox.showerror(message="Ошибка получения звука\nЛокальный файл не найден")

    @error_handler(error_processing=show_errors)
    def download_audio(self, choose_file=False, closing=False):
        if choose_file:
            self.save_files()
            audio_file_name = askopenfilename(title="Выберете JSON файл c аудио", filetypes=(("JSON", ".json"),),
                                              initialdir="./")
            if not audio_file_name:
                return
            with open(audio_file_name, encoding="UTF-8") as audio_file:
                audio_links_list = json.load(audio_file)
        else:
            audio_links_list = self.AUDIO_INFO
        audio_downloader = AudioDownloader(master=self, headers=self.headers, timeout=1, request_delay=3_000,
                                           temp_dir="./temp/", saving_dir=self.MEDIA_DIR,
                                           local_media_dir=self.LOCAL_DICTIONARIES_DIR,
                                           toplevel_cfg=self.toplevel_cfg,
                                           pb_cfg={"length": self.WIDTH - 2 * self.text_padx},
                                           label_cfg=self.label_cfg,
                                           button_cfg=self.button_cfg,
                                           checkbutton_cfg=self.checkbutton_cfg)
        if closing:
            audio_downloader.bind("<Destroy>", lambda event: self.destroy() if isinstance(event.widget, Toplevel) else None)
        spawn_toplevel_in_center(self, audio_downloader)
        audio_downloader.download_audio(audio_links_list)

    @error_handler(error_processing=show_errors)
    def save_skip_file(self):
        with open(self.SKIPPED_FILE_PATH, "w") as saving_f:
            json.dump(self.SKIPPED_FILE, saving_f, indent=3)

    @error_handler(error_processing=show_errors)
    def save_audio_file(self):
        if self.AUDIO_INFO:
            with open(self.AUDIO_INFO_PATH, "w", encoding="utf8") as audio_file:
                json.dump(self.AUDIO_INFO, audio_file, indent=1)

    @error_handler(error_processing=show_errors)
    def save_files(self):
        """
        Сохраняет файлы если они не пустые или есть изменения
        """
        # получение координат на экране через self.winfo_rootx(), self.winfo_rooty() даёт некоторое смещение
        rootx = self.winfo_rootx()
        rooty = int(self.winfo_rooty()) - 69  # compensate for menu and title heights respectively
        self.JSON_CONF_FILE["app"]["main_window_position"] = f"+{rootx}+{rooty}"
        self.JSON_CONF_FILE["tags"]["hierarchical_pref"] = self.tag_prefix_field.get()
        self.JSON_CONF_FILE["tags"]["include_domain"] = self.domain_var.get()
        self.JSON_CONF_FILE["tags"]["include_level"] = self.level_var.get()
        self.JSON_CONF_FILE["tags"]["include_region"] = self.region_var.get()
        self.JSON_CONF_FILE["tags"]["include_usage"] = self.usage_var.get()
        self.JSON_CONF_FILE["tags"]["include_pos"] = self.pos_var.get()
        self.save_conf_file()

        self.JSON_HISTORY_FILE[self.WORD_JSON_PATH] = self.NEXT_ITEM_INDEX - 1

        self.save_words()
        self.save_audio_file()

        self.save_history_file()

        if self.SKIPPED_FILE:
            self.save_skip_file()

    def autosave(self):
        self.save_files()
        self.after(300_000, self.autosave)  # time in milliseconds

    @error_handler(error_processing=show_errors)
    def on_closing(self):
        """
        Закрытие программы
        """
        if messagebox.askokcancel("Выход", "Вы точно хотите выйти?"):
            self.save_files()
            self.bg.stop()
            if self.AUDIO_INFO:
                self.download_audio(closing=True)
            else:
                self.destroy()

    @error_handler(error_processing=show_errors)
    def save_words(self):
        with open(self.WORD_JSON_PATH, "w", encoding="utf-8") as new_write_file:
            json.dump(self.WORDS, new_write_file, indent=4)

    @error_handler(error_processing=show_errors)
    def parse_word(self, word):
        """
        Парсит слово из словаря
        """
        word = remove_special_chars(word.strip())
        parsed_word = None
        try:
            parsed_word = self.parse(word)
        except ValueError:
            pass
        except requests.ConnectionError:
            messagebox.showerror("Ошибка", "Ошибка получения web-страницы!\nПроверьте подключение к интернету")
            return False

        word_blocks_list = parsed_word if parsed_word is not None else []
        # Добавляет только если блок не пуст
        if word_blocks_list:
            self.CARDS_LEFT += len(word_blocks_list) + 1
            self.NEXT_ITEM_INDEX -= 1
            # Ставит Полученный блок слов на место предыдущего слова
            self.WORDS = self.WORDS[:self.NEXT_ITEM_INDEX] + word_blocks_list + self.WORDS[self.NEXT_ITEM_INDEX:]
            self.refresh()
            return True
        messagebox.showerror("Ошибка", "Слово не найдено!")
        return False

    def change_media_dir(self, raise_error=True):
        new_media_dir = askdirectory(title="Выберете директорию collection.media в USERNAME/",
                                     initialdir="./")
        if not new_media_dir.endswith("collection.media"):
            if raise_error:
                messagebox.showerror("Ошибка", "Выбрана неверная директория!")
        elif len(new_media_dir) != 0:
            self.MEDIA_DIR = new_media_dir
            self.JSON_CONF_FILE["directories"]["media_dir"] = self.MEDIA_DIR
            return 1
        return 0

    def get_needed(self, is_start=False) -> bool:
        # Получение JSON файла со словами
        self.START_TIME = int(time.time())  # Получение времени начала работы программы. Нужно для имени файла с карточками
        last_open_file_path = self.JSON_CONF_FILE["directories"]["last_open_file"]
        last_save_dir_path = self.JSON_CONF_FILE["directories"]["last_save_dir"]
        media_dir_path = self.JSON_CONF_FILE["directories"]["media_dir"]
        self.AUDIO_INFO = []

        self.MEDIA_DIR = self.JSON_CONF_FILE["directories"]["media_dir"]
        if not (len(self.MEDIA_DIR) != 0 and os.path.isdir(media_dir_path)) and not self.change_media_dir(False):
            if is_start:
                quit()
            return True

        if is_start and os.path.isfile(last_open_file_path) and os.path.isdir(last_save_dir_path):
            self.WORD_JSON_PATH = self.JSON_CONF_FILE["directories"]["last_open_file"]
            self.SAVE_DIR = self.JSON_CONF_FILE["directories"]["last_save_dir"]
        else:
            picked_word_file = askopenfilename(title="Выберете JSON файл со словами", filetypes=(("JSON", ".json"),),
                                                  initialdir="./")
            if len(picked_word_file) == 0:
                if is_start:
                    quit()
                return True
            self.WORD_JSON_PATH = picked_word_file

            # Получение директории сохранения
            self.SAVE_DIR = askdirectory(title="Выберете директорию сохранения", initialdir="./")
            if len(self.SAVE_DIR) == 0:
                if is_start:
                    quit()
                return True

            self.JSON_CONF_FILE["directories"]["last_open_file"] = self.WORD_JSON_PATH
            self.JSON_CONF_FILE["directories"]["last_save_dir"] = self.SAVE_DIR

        self.FILE_NAME = os.path.split(self.WORD_JSON_PATH)[-1][:-5]
        PATH_PREFIX = f"{self.SAVE_DIR}/{remove_special_chars(self.FILE_NAME, sep='_')}"
        self.CARDS_PATH = f"{PATH_PREFIX}_cards_{self.START_TIME}.txt"
        self.AUDIO_INFO_PATH = f"{PATH_PREFIX}_audio_links_{self.START_TIME}.json"

        # Считывание файла со словами
        with open(self.WORD_JSON_PATH, "r", encoding="UTF-8") as read_file:
            self.WORDS = json.load(read_file)

        # Куча. skip - 0, add - 1, delete - 2
        self.CARDS_STATUSES = []
        self.SKIPPED_COUNTER = 0
        self.DEL_COUNTER = 0
        self.ADD_COUNTER = 0

        # Создание файла для пропускаемых карт
        self.SKIPPED_FILE_PATH = Path(f"{PATH_PREFIX}_skipped_cards_{self.START_TIME}.json")
        if self.SKIPPED_FILE_PATH.is_file():
            with open(self.SKIPPED_FILE_PATH, "r", encoding="UTF-8") as f:
                self.SKIPPED_FILE = json.load(f)
        else:
            self.SKIPPED_FILE = []

        # Получение места, где в последний раз остановился
        if self.JSON_HISTORY_FILE.get(self.WORD_JSON_PATH) is None:
            self.JSON_HISTORY_FILE[self.WORD_JSON_PATH] = self.START_INDEX = 0
        else:
            self.START_INDEX = min(len(self.WORDS), self.JSON_HISTORY_FILE[self.WORD_JSON_PATH])

        self.CARDS_LEFT = len(self.WORDS) - self.START_INDEX + 1
        return False

    @error_handler(error_processing=show_errors)
    def get_word_block(self, index):
        if index >= len(self.WORDS):
            raise StopIteration
        return self.WORDS[index]

    @error_handler(error_processing=show_errors)
    def replace_sentences(self, dict_sentence_list):
        word = self.word_text.get(1.0, "end").strip()
        for start_index in range(0, max(len(dict_sentence_list), 1), 5):
            self.add_sentences_button["text"] = f"Добавить предложения {start_index // 5 + 1}/{len(dict_sentence_list) // 5 + 1}"
            for current_sentence_index in range(start_index, start_index + 5):
                self.sent_text_list[current_sentence_index % 5].delete(1.0, "end")
                if len(dict_sentence_list) > current_sentence_index:
                    self.sent_text_list[current_sentence_index % 5]["foreground"] = self.sent_text_list[
                        current_sentence_index % 5].default_fg_color
                    self.sent_text_list[current_sentence_index % 5].insert(1.0, dict_sentence_list[current_sentence_index])
                elif not self.sent_text_list[current_sentence_index % 5].under_focus:
                    self.sent_text_list[current_sentence_index % 5].fill_placeholder()
            yield
            new_word = self.word_text.get(1.0, "end").strip()
            if word != new_word:
                word = new_word
                break

        sent_gen = self.sentence_parser(word)
        self.add_sentences_button["text"] = "Добавить предложения +"
        try:
            for batch in sent_gen:
                if word != self.word_text.get(1.0, "end").strip():
                    break
                if len(batch) == 0:
                    raise AttributeError
                for current_sentence_index in range(5):
                    self.sent_text_list[current_sentence_index].delete(1.0, "end")
                    if len(batch) > current_sentence_index:
                        self.sent_text_list[current_sentence_index]["foreground"] = self.sent_text_list[
                            current_sentence_index].default_fg_color
                        self.sent_text_list[current_sentence_index].insert(1.0, batch[current_sentence_index])
                    elif not self.sent_text_list[current_sentence_index % 5].under_focus:
                        self.sent_text_list[current_sentence_index % 5].fill_placeholder()
                yield
        except requests.ConnectionError:
            messagebox.showerror("Ошибка", "Ошибка получения web-страницы!\nПроверьте подключение к интернету")
        except AttributeError:
            messagebox.showerror("Ошибка", "Ошибка получения предложений!\nПроверьте написание слова")
        finally:
            new_gen = self.replace_sentences(dict_sentence_list)
            self.add_sentences_button["command"] = lambda x=new_gen: next(x)
            next(new_gen)
            yield

    @error_handler(error_processing=show_errors)
    def refresh(self):
        """
        Переход от старого блока слов к новому после выбора предложения
        """
        def fill_additional_dict_data(widget, text):
            """
            Заполняет тэги и альтернативные названия слов
            :param widget: виджет куда заполнять
            :param text: что заполлнять
            :return:
            """
            widget["state"] = "normal"
            widget.delete(1.0, "end")
            widget.insert(1.0, text)
            widget["state"] = "disabled"

        self.word_text.focus()
        self.word_text.update()
        # нужно для избжания двойного заполнения виджета загушкой
        self.IMAGES = []
        self.DICT_IMAGE_LINK = ""

        if self.NEXT_ITEM_INDEX == self.START_INDEX:
            self.prev_button["state"] = "disabled"
        else:
            self.prev_button["state"] = "normal"

        # Получение и обработка нового блока слов
        try:
            next_word = self.get_word_block(self.NEXT_ITEM_INDEX)
            self.NEXT_ITEM_INDEX += 1
            self.CARDS_LEFT -= 1
        except StopIteration:
            self.NEXT_ITEM_INDEX = len(self.WORDS) + 1
            self.CARDS_LEFT = 0

            self.word_text.delete(1.0, "end")
            self.meaning_text.delete(1.0, "end")
            self.meaning_text.fill_placeholder()

            for j in range(5):
                self.sent_text_list[j].delete(1.0, "end")

            self.DICT_TAGS["domain"][0] = [""]
            self.DICT_TAGS["level"][0] = [""]
            self.DICT_TAGS["region"][0] = [""]
            self.DICT_TAGS["usage"][0] = [""]
            self.DICT_TAGS["pos"][0] = ""
            fill_additional_dict_data(self.dict_tags_field, "")
            fill_additional_dict_data(self.alt_terms_field, "")

            self.find_image_button["text"] = "Добавить изображение"
            self.skip_button["state"] = "disabled"

            self.CURRENT_AUDIO_LINK = ""

            if not self.JSON_CONF_FILE["scrappers"]["local_audio"]:
                self.sound_button["state"] = "disabled"

            sentence_generator = self.replace_sentences([])
            next(sentence_generator)
            self.add_sentences_button["command"] = lambda x=sentence_generator: next(x)
            return
        finally:
            self.title(f"Поиск предложений для Anki. Осталось: {self.CARDS_LEFT} слов")

        self.DICT_TAGS["domain"][0] = next_word.get("domain", [""])
        self.DICT_TAGS["level"][0] = next_word.get("level", [""])
        self.DICT_TAGS["region"][0] = next_word.get("region", [""])
        self.DICT_TAGS["usage"][0] = next_word.get("usage", [""])
        self.DICT_TAGS["pos"][0] = next_word.get("pos", "")
        fill_additional_dict_data(self.dict_tags_field, self.get_dict_tags(include_prefix=False))

        # Обновление поля для слова
        self.word_text.delete(1.0, "end")
        if next_word["word"]:
            self.word_text["foreground"] = self.word_text.default_fg_color
            self.word_text.insert(1.0, next_word["word"])

        # Обновление поля для значения
        self.meaning_text.delete(1.0, "end")
        if next_word["meaning"]:
            self.meaning_text["foreground"] = self.meaning_text.default_fg_color
            self.meaning_text.insert(1.0, next_word["meaning"])
        else:
            self.meaning_text.fill_placeholder()

        alt_terms = " ".join(next_word.get("alt_terms", []))
        fill_additional_dict_data(self.alt_terms_field, alt_terms)

        self.DICT_IMAGE_LINK = next_word.get("image_link", "")
        if self.DICT_IMAGE_LINK:
            self.find_image_button["text"] = "Добавить изображение ★"
        else:
            self.find_image_button["text"] = "Добавить изображение"
        self.CURRENT_AUDIO_LINK = next_word.get("audio_link", "")

        if self.JSON_CONF_FILE["scrappers"]["local_audio"] or self.CURRENT_AUDIO_LINK:
            self.sound_button["state"] = "normal"
        else:
            self.sound_button["state"] = "disabled"

        self.skip_button["state"] = "normal"
        # Обновление полей для примеров предложений
        sentence_generator = self.replace_sentences(next_word["Sen_Ex"]) if next_word.get(
            "Sen_Ex") is not None else self.replace_sentences([])
        next(sentence_generator)
        self.add_sentences_button["command"] = lambda x=sentence_generator: next(x)

    @error_handler(error_processing=show_errors)
    def prepare_tags(self, tag_name, tag, list_tag=True, include_prefix=True):
        self.JSON_CONF_FILE["tags"]["hierarchical_pref"] = remove_special_chars(self.tag_prefix_field.get().strip(), "-")
        start_tag_pattern = self.JSON_CONF_FILE["tags"]["hierarchical_pref"] + "::" if\
                            include_prefix and self.JSON_CONF_FILE["tags"]["hierarchical_pref"] else ""
        if list_tag:
            if tag[0] == "":
                return ""
            result = ""
            for item in tag:
                item = item.replace(' ', '_')
                result += f"{start_tag_pattern}{tag_name}::{item} "
            return result
        else:
            if tag == "":
                return ""
            tag = tag.replace(' ', '_')
            return f"{start_tag_pattern}{tag_name}::{tag} "

    @error_handler(error_processing=show_errors)
    def get_dict_tags(self, include_prefix=True):
        str_dict_tags = ""
        for tag_tame in self.DICT_TAGS:
            tag, add_tag_flag = self.DICT_TAGS[tag_tame]
            if add_tag_flag.get():
                if tag_tame == "pos":
                    str_dict_tags += self.prepare_tags(tag_tame, tag, list_tag=False, include_prefix=include_prefix)
                else:
                    str_dict_tags += self.prepare_tags(tag_tame, tag, include_prefix=include_prefix)
        return str_dict_tags.strip()

    @error_handler(error_processing=show_errors)
    def choose_sentence(self, button_index):
        """
        Выбор предложения на выбор
        :param button_index: номер кнопки (0..4)
        """
        word = self.word_text.get(1.0, "end").strip()
        saving_word = word
        if not word:
            return

        meaning = self.meaning_text.get(1.0, "end").strip()
        sentence_example = self.sent_text_list[button_index].get(1.0, "end").rstrip()

        pos = self.DICT_TAGS["pos"][0]
        tags = self.user_tags_field.get().strip()
        images_path_str = "".join(self.IMAGES)
        # Если есть кастомные теги, то добавим пробел
        if tags:
            tags += " "
        tags += self.get_dict_tags()

        self.CARDS_STATUSES.append(App.CardStatus.add)
        self.ADD_COUNTER += 1

        save_audio_path = ""
        if not self.JSON_CONF_FILE["scrappers"]["local_audio"]:
            if self.CURRENT_AUDIO_LINK:
                save_audio_path = "[sound:{}]".format(get_save_audio_name(word, pos, self.word_parser_name))
            else:
                word = ""
        else:
            a = self.get_dict_local_audio_dir()
            if get_local_audio_path(word, pos, local_audio_folder_path=a):
                save_audio_path = "[sound:{}]".format(get_save_audio_name(word, pos, self.JSON_CONF_FILE["scrappers"]["local_audio"]))

            elif self.non_pos_spec_search_var.get() and get_local_audio_path(word, local_audio_folder_path=a, with_pos=False):
                save_audio_path = "[sound:{}]".format(get_save_audio_name(word, "", self.JSON_CONF_FILE["scrappers"]["local_audio"]))
            else:
                word = ""

        if not self.JSON_CONF_FILE["scrappers"]["local_audio"]:
            self.AUDIO_INFO.append([word, pos, self.word_parser_name, self.CURRENT_AUDIO_LINK])
        else:
            self.AUDIO_INFO.append([word, pos, self.JSON_CONF_FILE["scrappers"]["local_audio"], ""])

        if not sentence_example:
            sentence_example = saving_word
        with open(self.CARDS_PATH, 'a', encoding="UTF-8", newline='') as f:
            cards_writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            cards_writer.writerow([sentence_example, saving_word, meaning, images_path_str, save_audio_path, tags])
        if self.CARDS_LEFT == 0:
            user_created_word_block = {
                "word": saving_word,
                "meaning": meaning,
                "Sen_Ex": [sentence_example],
            }
            self.WORDS.append(user_created_word_block)
        self.refresh()

    @error_handler(error_processing=show_errors)
    def web_search_command(self):
        search_term = self.word_text.get(1.0, "end").strip()
        definition_search_query = search_term + " definition"
        webbrowser.open_new_tab(f"https://www.google.com/search?q={definition_search_query}")
        sentence_search_query = search_term + " sentence examples"
        webbrowser.open_new_tab(f"https://www.google.com/search?q={sentence_search_query}")

    @error_handler(error_processing=show_errors)
    def skip_command(self):
        """
        Откладывает карточку в файл
        """
        # Исправляет проблему срабатывания функции при выключенных кнопках
        if self.skip_button["state"] == "normal":
            word = self.word_text.get(1.0, "end").strip()
            meaning = self.meaning_text.get(1.0, "end").strip()
            sentences = []
            for sentence in self.sent_text_list:
                text = sentence.get(1.0, "end").rstrip()
                if text:
                    sentences.append(text)
            self.SKIPPED_FILE.append({"word": word, "meaning": meaning, "Sen_Ex": sentences})
            self.CARDS_STATUSES.append(App.CardStatus.skip)
            self.SKIPPED_COUNTER += 1
            self.refresh()

    @error_handler(error_processing=show_errors)
    def open_new_file(self, is_start=False):
        """
        Открывает новый файл слов
        """
        self.save_files()
        if self.get_needed(is_start):
            return
        self.NEXT_ITEM_INDEX = self.START_INDEX
        self.refresh()

    @error_handler(error_processing=show_errors)
    def create_new_file(self):
        def create_file():
            def foo():
                skip_var.set(True)
                copy_encounter.destroy()

            new_file_name = remove_special_chars(name_entry.get().strip(), sep="_")
            if not new_file_name:
                messagebox.showerror("Ошибка", "Не указано имя файла")
                return

            new_file_path = f"{new_file_dir}/{new_file_name}.json"
            skip_var = BooleanVar()
            skip_var.set(False)
            if os.path.exists(new_file_path):
                copy_encounter = self.Toplevel(create_file_win)
                copy_encounter.withdraw()
                message = f"Файл уже существует.\nВыберите нужную опцию:"
                encounter_label = self.Label(copy_encounter, text=message, relief="ridge")
                skip_encounter_button = self.Button(copy_encounter, text="Пропустить", command=lambda: foo())
                rewrite_encounter_button = self.Button(copy_encounter, text="Заменить", command=lambda: copy_encounter.destroy())

                encounter_label.grid(row=0, column=0, padx=self.text_padx, pady=self.text_pady)
                skip_encounter_button.grid(row=1, column=0, padx=self.text_padx, pady=self.text_pady, sticky="news")
                rewrite_encounter_button.grid(row=2, column=0, padx=self.text_padx, pady=self.text_pady, sticky="news")
                copy_encounter.deiconify()
                spawn_toplevel_in_center(self, copy_encounter)
                create_file_win.wait_window(copy_encounter)

            create_file_win.destroy()

            if not skip_var.get():
                with open(new_file_path, "w", encoding="UTF8") as new_file:
                    json.dump([], new_file)

            new_save_dir = askdirectory(title="Выберете директорию сохранения", initialdir="./")
            if len(new_save_dir) == 0:
                return

            self.JSON_CONF_FILE["directories"]["last_save_dir"] = new_save_dir
            self.JSON_CONF_FILE["directories"]["last_open_file"] = new_file_path
            self.open_new_file(True)

        new_file_dir = askdirectory(title="Выберете директорию для файла со словами", initialdir="./")
        if len(new_file_dir) == 0:
            return
        create_file_win = self.Toplevel()
        create_file_win.withdraw()
        name_entry = self.Entry(create_file_win, placeholder="Имя файла", justify="center")
        name_button = self.Button(create_file_win, text="Создать", command=create_file)
        name_entry.grid(row=0, column=0, padx=5, pady=3, sticky="news")
        name_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
        create_file_win.deiconify()
        spawn_toplevel_in_center(self, create_file_win)
        name_entry.focus()
        create_file_win.bind("<Escape>", lambda event: create_file_win.destroy())
        create_file_win.bind("<Return>", lambda event: create_file())
    
    @error_handler(error_processing=show_errors)
    def anki_browser_command(self):
        def invoke(action, **params):
            def request_anki(action, **params):
                return {'action': action, 'params': params, 'version': 6}

            request_json = json.dumps(request_anki(action, **params)).encode('utf-8')
            response = json.load(
                urllib.request.urlopen(urllib.request.Request('http://localhost:8765', request_json), timeout=1))
            if response['error'] is not None:
                messagebox.showerror("Ошибка", response['error'])
            return response['result']

        word = self.word_text.get(1.0, "end").strip()
        query_list = []
        if self.JSON_CONF_FILE["anki"]["anki_deck"]:
            query_list.append("deck:\"{}\"".format(self.JSON_CONF_FILE["anki"]["anki_deck"]))
        if self.JSON_CONF_FILE["anki"]["anki_field"]:
            query_list.append("\"{}:*{}*\"".format(self.JSON_CONF_FILE["anki"]["anki_field"],
                                                   word))
        else:
            query_list.append(f"*{word}*")
        result_query = " and ".join(query_list)
        invoke('guiBrowse', query=result_query)

    @error_handler(error_processing=show_errors)
    def save_button(self):
        messagebox.showinfo(message="Файлы сохранены")
        self.save_files()

    @error_handler(error_processing=show_errors)
    def delete_command(self):
        if self.CARDS_LEFT:
            self.CARDS_STATUSES.append(App.CardStatus.delete)
            self.DEL_COUNTER += 1
        else:
            self.NEXT_ITEM_INDEX -= 1
        self.refresh()

    @staticmethod
    def delete_last_line(txt_file_path):
        """
        Удаление последних двух строк файла
        """
        with open(txt_file_path, "rb+") as file:
            # https://stackoverflow.com/questions/1877999/delete-final-line-in-file-with-python
            # Move the pointer (similar to a cursor in a text editor) to the end of the file
            file.seek(0, os.SEEK_END)

            # This code means the following code skips the very last character in the file -
            # i.e. in the case the last line is null we delete the last line
            # and the penultimate one
            pos = file.tell() - 1

            # Read each character in the file one at a time from the penultimate
            # character going backwards, searching for a newline character
            # If we find a new line, exit the search
            while pos > 0 and file.read(1) != b"\n":
                pos -= 1
                file.seek(pos, os.SEEK_SET)

            # So long as we're not at the start of the file, delete all the characters ahead
            # of this position
            if pos > 0:
                file.seek(pos, os.SEEK_SET)
                file.truncate()
            else:
                # Если пришли в самое начало, то полностью стираем файл
                file.seek(0, os.SEEK_SET)
                file.truncate()

    @error_handler(error_processing=show_errors)
    def prev_command(self, n=1):
        # -2 т. к. при refresh прибавляется 1
        if self.NEXT_ITEM_INDEX - (n + 1) >= self.START_INDEX:
            self.NEXT_ITEM_INDEX -= n + 1
            self.CARDS_LEFT += n + 1
            for _ in range(n):
                decision = self.CARDS_STATUSES.pop()
                if decision == App.CardStatus.skip:
                    self.SKIPPED_COUNTER -= 1
                    self.SKIPPED_FILE.pop()
                elif decision == App.CardStatus.add:
                    self.ADD_COUNTER -= 1
                    self.delete_last_line(self.CARDS_PATH)
                    self.AUDIO_INFO.pop()
                else:
                    self.DEL_COUNTER -= 1
            self.refresh()

    @staticmethod
    def help_command():
        mes = "Программа для Sentence mining'a\n\n * Каждое поле полностью редактируемо!" + \
              "\n * Для выбора подходящего примера с предложением просто нажмите на кнопку, стоящую рядом с ним\n\n" + \
              "Назначения кнопок и полей:\n * Кнопки 1-5: кнопки выбора\nсоответствующих предложений\n" + \
              " * Кнопка \"Skip\": откладывает слово в\nотдельный файл для просмотра позднее\n" + \
              " * Кнопка \"Del\": удаляет слово\n * Самое нижнее окно ввода: поле для тэгов\n" + \
              " * Кнопка \"Prev\": возвращается к предущему блоку\n" + \
              " Ctrl + c + space: добавить выделенного слова в колоду\n" + \
              " Ctrl + Shift + a: вызов окна добавления слова в колоду\n" + \
              " Ctrl + z: возвращение к предыдущей карточке\n" + \
              " Ctrl + d: удалить карточку\n" + \
              " Ctrl + q: отложить карточку\n" + \
              " Ctrl + e: вызов окна статистики\n" + \
              " Ctrl + f: вызов окна перехода\n" + \
              " Ctrl + 1..5: быстрый выбор предложения\n" + \
              " Ctrl + 0: возврат прилодения на середину экрана\n(если оно застряло)"
        messagebox.showinfo("Справка", message=mes)

    @error_handler(error_processing=show_errors)
    def get_local_wrapper(self, local_parser_name):
        def get_local(word):
            nonlocal local_parser_name

            def fuzzy_word_search():
                result = []
                for found_word, word_dict in self.LOCAL_DICT:
                    if string_search(source=found_word, query=word,
                                     search_type=self.JSON_CONF_FILE["scrappers"]["local_search_type"],
                                     case_sencitive=False):
                        result.append((found_word, word_dict))
                if result:
                    result.sort(key=lambda x: len(x[0]))
                    return result
                return result

            raw_result = fuzzy_word_search()
            transformed = self.discovered_local_word_parsers[local_parser_name].translate(raw_result)
            return transformed

        return get_local

    @error_handler(error_processing=show_errors)
    def call_second_window(self, window_type):
        """
        :param window_type: call_parser, stat, find, anki
        :return:
        """
        second_window = self.Toplevel(self)
        if window_type == "call_parser":
            def define_word_button():
                clean_word = second_window_entry.get().strip()
                if self.parse_word(clean_word):
                    second_window.destroy()
                else:
                    second_window.withdraw()
                    second_window.deiconify()
                    
            second_window.title("Добавить")
            second_window_entry = self.Entry(second_window, justify="center")
            second_window_entry.focus()
            second_window_entry.bind('<Return>', lambda event: define_word_button())

            second_window_entry.grid(row=0, column=0, padx=5, pady=3, sticky="news")
            start_parsing_button = self.Button(second_window, text="Добавить", command=define_word_button)
            start_parsing_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
        elif window_type == "find":
            def go_to():
                word = second_window_entry.get().strip().lower()
                skip_count = 0
                if word.startswith("->"):
                    # [3:] чекает кейс с отрицат числами
                    if word[2:].isdigit() or word[3:].isdigit():
                        skip_count = int(word[2:])
                    else:
                        messagebox.showerror("Ошибка", "Неверно задано число перехода!")
                        second_window.withdraw()
                        second_window.deiconify()
                        return
                else:
                    pattern = re.compile(word)
                    for skip_count in range(1, len(self.WORDS) - self.NEXT_ITEM_INDEX + 1):
                        block = self.WORDS[self.NEXT_ITEM_INDEX + skip_count - 1]
                        prepared_word_in_block = block["word"].rstrip().lower()
                        if re_search.get():
                            search_condition = re.search(pattern, prepared_word_in_block)
                        else:
                            search_condition = prepared_word_in_block == word
                        if search_condition:
                            break
                    else:
                        messagebox.showerror("Ошибка", "Слово не найдено!")
                        second_window.withdraw()
                        second_window.deiconify()
                        return
                skip_count = max(-len(self.CARDS_STATUSES), min(skip_count, self.CARDS_LEFT))
                if skip_count >= 0:
                    self.NEXT_ITEM_INDEX = self.NEXT_ITEM_INDEX + skip_count - 1
                    self.CARDS_LEFT = self.CARDS_LEFT - skip_count + 1
                    self.CARDS_STATUSES.extend([App.CardStatus.delete for _ in range(skip_count)])
                    self.DEL_COUNTER += skip_count
                    self.refresh()
                else:
                    self.prev_command(n=-skip_count)
                second_window.destroy()

            second_window.title("Перейти")
            second_window_entry = self.Entry(second_window, justify="center")
            second_window_entry.focus()
            second_window_entry.bind('<Return>', lambda event: go_to())

            start_parsing_button = self.Button(second_window, text="Перейти", command=go_to)

            re_search = BooleanVar()
            re_search.set(False)
            second_window_re = self.Checkbutton(second_window, variable=re_search, text="RegEx search")

            second_window_entry.grid(row=0, column=0, padx=5, pady=3, sticky="news")
            start_parsing_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
            second_window_re.grid(row=2, column=0, sticky="news")

        elif window_type == "stat":
            second_window.title("Статистика")
            text_list = (('Добавлено', 'Пропущено', 'Удалено', 'Осталось', "Файл", "Директория сохранения", "Медиа"),
                         (self.ADD_COUNTER, self.SKIPPED_COUNTER, self.DEL_COUNTER, self.CARDS_LEFT, self.WORD_JSON_PATH, self.SAVE_DIR, self.MEDIA_DIR))

            scroll_frame = ScrolledFrame(second_window, scrollbars="horizontal")
            scroll_frame.pack()
            scroll_frame.bind_scroll_wheel(second_window)
            inner_frame = scroll_frame.display_widget(partial(Frame, bg=self.main_bg))
            for row_index in range(len(text_list[0])):
                for column_index in range(2):
                    info = self.Label(inner_frame, text=text_list[column_index][row_index], anchor="center", relief="ridge")
                    info.grid(column=column_index, row=row_index, sticky="news")

            second_window.update()
            current_frame_width = inner_frame.winfo_width()
            current_frame_height = inner_frame.winfo_height()
            scroll_frame.config(width=min(self.winfo_width(), current_frame_width),
                                height=min(self.winfo_height(), current_frame_height))

        elif window_type == "anki":
            def save_anki_settings_command():
                deck = anki_deck_entry.get().strip()
                field = anki_field_entry.get().strip()
                self.JSON_CONF_FILE["anki"]["anki_deck"] = deck if deck != 'Колода поиска' else ""
                self.JSON_CONF_FILE["anki"]["anki_field"] = field if field != 'Поле поиска' else ""
                second_window.destroy()

            second_window.title("Настройки Anki")
            anki_deck_entry = self.Entry(second_window, placeholder='Колода поиска')
            anki_deck_entry.insert(0, self.JSON_CONF_FILE["anki"]["anki_deck"])
            anki_field_entry = self.Entry(second_window, placeholder='Поле поиска')
            anki_field_entry.insert(0, self.JSON_CONF_FILE["anki"]["anki_field"])

            save_anki_settings_button = self.Button(second_window, text="Сохранить", command=save_anki_settings_command)

            padx = pady = 5
            anki_deck_entry.grid(row=0, column=0, sticky="we", padx=padx, pady=pady)
            anki_field_entry.grid(row=1, column=0, sticky="we", padx=padx, pady=pady)
            save_anki_settings_button.grid(row=2, column=0, sticky="ns", padx=padx)
            second_window.bind("<Return>", lambda event: save_anki_settings_command())

        spawn_toplevel_in_center(self, second_window)
        second_window.bind("<Escape>", lambda event: second_window.destroy())

    def configure_dict(self):
        dict_configuration_toplevel = self.Toplevel(self)
        dict_configuration_toplevel.withdraw()

        fetch_directly_from_dict = "Из словаря"

        word_parser_option_menu = get_option_menu(dict_configuration_toplevel,
                                                  init_text=self.word_parser_name,
                                                  values=self.word_parsers_names,
                                                  command=lambda parser_name:
                                                  self.change_word_parser(parser_name),
                                                  widget_configuration=self.option_menu_conf,
                                                  option_submenu_params=self.option_submenu_params)

        def change_search_type(str_search_type):
            self.JSON_CONF_FILE["scrappers"]["local_search_type"] = SearchType[str_search_type].value

        search_type_option_menu = get_option_menu(dict_configuration_toplevel,
                                                  init_text=SearchType(self.JSON_CONF_FILE["scrappers"]
                                                                                          ["local_search_type"]).name,
                                                  values=[search_type.name for search_type in SearchType],
                                                  command=lambda str_search_type:
                                                  change_search_type(str_search_type),
                                                  widget_configuration=self.option_menu_conf,
                                                  option_submenu_params=self.option_submenu_params)

        def save_local_audio_location(location):
            nonlocal fetch_directly_from_dict
            if location != fetch_directly_from_dict:
                self.JSON_CONF_FILE["scrappers"]["local_audio"] = location
                self.sound_button["state"] = "normal"
            else:
                self.JSON_CONF_FILE["scrappers"]["local_audio"] = ""
                if not self.CURRENT_AUDIO_LINK:
                    self.sound_button["state"] = "disabled"

        audio_init_val = self.JSON_CONF_FILE["scrappers"]["local_audio"] \
                             if self.JSON_CONF_FILE["scrappers"]["local_audio"] \
                             else fetch_directly_from_dict
        audio_fetching_method = get_option_menu(dict_configuration_toplevel,
                                                init_text=audio_init_val,
                                                values=[fetch_directly_from_dict] + self.media_folders,
                                                command=lambda location:
                                                save_local_audio_location(location),
                                                widget_configuration=self.option_menu_conf,
                                                option_submenu_params=self.option_submenu_params)

        dict_configuration_toplevel.grid_columnconfigure(1, weight=1)
        self.Label(dict_configuration_toplevel, text="Словарь", relief="ridge").grid(
                                     row=0, column=0, padx=(self.text_padx, 0), pady=(self.text_pady, 0), sticky="news")
        word_parser_option_menu.grid(row=0, column=1, padx=(0, self.text_padx), pady=(self.text_pady, 0), sticky="news")

        self.Label(dict_configuration_toplevel, text="Тип локального поиска", relief="ridge").grid(
                                     row=1, column=0, padx=(self.text_padx, 0), sticky="news")
        search_type_option_menu.grid(row=1, column=1, padx=(0, self.text_padx), sticky="news")

        self.Label(dict_configuration_toplevel, text="Источник аудио", relief="ridge").grid(
                                   row=2, column=0, padx=(self.text_padx, 0), sticky="news")
        audio_fetching_method.grid(row=2, column=1, padx=(0, self.text_padx), sticky="news")

        def update_var():
            self.JSON_CONF_FILE["scrappers"]["non_pos_specific_search"] = self.non_pos_spec_search_var.get()

        self.Checkbutton(dict_configuration_toplevel, text="Полный поиск аудио",
                         variable=self.non_pos_spec_search_var,
                         command=update_var).grid(row=3, column=0, columnspan=2, padx=self.text_padx, sticky="news")
        self.Button(dict_configuration_toplevel, text="Ok", command=dict_configuration_toplevel.destroy).grid(
                                                  row=4, column=0, columnspan=2, padx=self.text_padx, sticky="news",
                                                                                 pady=(0, self.text_pady))

        dict_configuration_toplevel.deiconify()
        spawn_toplevel_in_center(self, dict_configuration_toplevel)
        dict_configuration_toplevel.bind("<Escape>", lambda event: dict_configuration_toplevel.destroy())
        dict_configuration_toplevel.bind("<Return>", lambda event: dict_configuration_toplevel.destroy())


root = App()
root.mainloop()
