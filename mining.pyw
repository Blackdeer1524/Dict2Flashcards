import copy
import itertools
import json
import os
from threading import Thread
import re
import time
import webbrowser
from collections import namedtuple
from datetime import datetime
from functools import partial
from tkinter import BooleanVar
from tkinter import Button, Menu
from tkinter import Checkbutton
from tkinter import Frame
from tkinter import Label
from tkinter import LabelFrame
from tkinter import PanedWindow
from tkinter import Toplevel
from tkinter import messagebox
from tkinter.filedialog import askopenfilename, askdirectory
from tkinter.font import Font
from tkinter.ttk import Treeview
from typing import Callable

from playsound import playsound
from tkinterdnd2 import Tk

from app_utils.audio_utils import AudioDownloader
from app_utils.cards import Card, Deck, SavedDataDeck, CardStatus
from app_utils.chaining_adapters import ImageParsersChain, CardGeneratorsChain, SentenceParsersChain, AudioGettersChain
from app_utils.plugin_wrappers import ExternalDataFetcherWrapper
from app_utils.error_handling import create_exception_message, error_handler
from app_utils.global_bindings import Binder
from app_utils.image_utils import ImageSearch
from app_utils.search_checker import ParsingException, get_card_filter
from app_utils.string_utils import remove_special_chars
from app_utils.widgets import TextWithPlaceholder as Text
from app_utils.widgets import EntryWithPlaceholder as Entry
from app_utils.widgets import ScrolledFrame
from app_utils.window_utils import get_option_menu, spawn_window_in_center
from consts import parser_types
from consts.card_fields import FIELDS
from consts.paths import *
from plugins_loading.containers import LanguagePackageContainer
from plugins_loading.factory import loaded_plugins
from plugins_management.config_management import LoadableConfig, Config
from plugins_management.parsers_return_types import AudioData


class App(Tk):
    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)

        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)

        if not os.path.exists(LOCAL_MEDIA_DIR):
            os.makedirs(LOCAL_MEDIA_DIR)

        if not os.path.exists(CARDS_DIR):
            os.makedirs(CARDS_DIR)

        if not os.path.exists(WORDS_DIR):
            os.makedirs(WORDS_DIR)

        # CHAINS
        if not os.path.exists(CHAIN_WORD_PARSERS_DATA_DIR):
            os.makedirs(CHAIN_WORD_PARSERS_DATA_DIR)

        if not os.path.exists(CHAIN_SENTENCE_PARSERS_DATA_DIR):
            os.makedirs(CHAIN_SENTENCE_PARSERS_DATA_DIR)

        if not os.path.exists(CHAIN_IMAGE_PARSERS_DATA_DIR):
            os.makedirs(CHAIN_IMAGE_PARSERS_DATA_DIR)

        if not os.path.exists(CHAIN_AUDIO_GETTERS_DATA_DIR):
            os.makedirs(CHAIN_AUDIO_GETTERS_DATA_DIR)

        if not os.path.exists(f"{WORDS_DIR}/custom.json"):
            with open(f"{WORDS_DIR}/custom.json", "w", encoding="UTF-8") as custom_file:
                json.dump([], custom_file)

        self.configurations, self.lang_pack, error_code = self.load_conf_file()
        if error_code:
            self.destroy()
            return
        self.configurations.save()
        self.history = App.load_history_file()
        self.chaining_data = self.load_chaining_data()
        self.chaining_data.save()

        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'}
        self.session_start = datetime.now()
        self.str_session_start = self.session_start.strftime("%d-%m-%Y-%H-%M-%S")

        if not self.history.get(self.configurations["directories"]["last_open_file"]):
            self.history[self.configurations["directories"]["last_open_file"]] = 0

        self.theme = loaded_plugins.get_theme(self.configurations["app"]["theme"])
        self.configure(**self.theme.root_cfg)
        self.Label    = partial(Label,    **self.theme.label_cfg)
        self.Button   = partial(Button,   **self.theme.button_cfg)
        self.Text     = partial(Text,     **self.theme.text_cfg)
        self.Entry    = partial(Entry,    **self.theme.entry_cfg)
        self.Toplevel = partial(Toplevel, **self.theme.toplevel_cfg)
        self.Frame    = partial(Frame,    **self.theme.frame_cfg)
        self.get_option_menu = partial(get_option_menu,
                                       option_menu_cfg=self.theme.option_menu_cfg,
                                       option_submenu_cfg=self.theme.option_submenus_cfg)

        wp_name = self.configurations["scrappers"]["word"]["name"]
        if (wp_type := self.configurations["scrappers"]["word"]["type"]) == parser_types.WEB:
            self.card_generator = loaded_plugins.get_web_card_generator(wp_name)
        elif wp_type == parser_types.LOCAL:
            self.card_generator = loaded_plugins.get_local_card_generator(wp_name)
        elif wp_type == parser_types.CHAIN:
            self.card_generator = CardGeneratorsChain(name=wp_name,
                                                      chain_data=self.chaining_data["word_parsers"][wp_name])
        else:
            raise NotImplemented("Unknown word_parser_type: {}!"
                                 .format(self.configurations["scrappers"]["word"]["type"]))
        self.typed_word_parser_name = f"[{wp_type}] {wp_name}"

        self.deck = Deck(deck_path=self.configurations["directories"]["last_open_file"],
                         current_deck_pointer=self.history[self.configurations["directories"]["last_open_file"]],
                         card_generator=self.card_generator)

        self.card_processor = loaded_plugins.get_card_processor("Anki")
        self.dict_card_data: dict = {}

        if self.configurations["scrappers"]["sentence"]["type"] == parser_types.WEB:
            self.sentence_parser = loaded_plugins.get_sentence_parser(self.configurations["scrappers"]["sentence"]["name"])
        elif self.configurations["scrappers"]["sentence"]["type"] == parser_types.CHAIN:
            self.sentence_parser = SentenceParsersChain(
                name=self.configurations["scrappers"]["sentence"]["name"],
                chain_data=self.chaining_data["sentence_parsers"][self.configurations["scrappers"]["sentence"]["name"]])

        self.external_sentence_fetcher = ExternalDataFetcherWrapper(data_fetcher=self.sentence_parser.get_sentences)

        if self.configurations["scrappers"]["image"]["type"] == parser_types.WEB:
            self.image_parser = loaded_plugins.get_image_parser(self.configurations["scrappers"]["image"]["name"])
        else:
            self.image_parser = ImageParsersChain(
                name=self.configurations["scrappers"]["image"]["name"],
                chain_data=self.chaining_data["image_parsers"][self.configurations["scrappers"]["image"]["name"]])

        if (audio_getter_name := self.configurations["scrappers"]["audio"]["name"]):
            if self.configurations["scrappers"]["audio"]["type"] == parser_types.LOCAL:
                self.audio_getter = loaded_plugins.get_local_audio_getter(audio_getter_name)
                self.external_audio_generator = ExternalDataFetcherWrapper(data_fetcher=self.audio_getter.get_audios)
            elif self.configurations["scrappers"]["audio"]["type"] == parser_types.WEB:
                self.audio_getter = loaded_plugins.get_web_audio_getter(audio_getter_name)
                self.external_audio_generator = ExternalDataFetcherWrapper(data_fetcher=self.audio_getter.get_audios)
            elif self.configurations["scrappers"]["audio"]["type"] == parser_types.CHAIN:
                self.audio_getter = AudioGettersChain(name=audio_getter_name,
                                                      chain_data=self.chaining_data["audio_getters"][audio_getter_name])
                self.external_audio_generator = ExternalDataFetcherWrapper(data_fetcher=self.audio_getter.get_audios)
            else:
                self.configurations["scrappers"]["audio"]["type"] = "default"
                self.configurations["scrappers"]["audio"]["name"] = ""
                self.audio_getter = None
                self.external_audio_generator = None
        else:
            self.audio_getter = None
            self.external_audio_generator = None

        self.saved_cards_data = SavedDataDeck()
        self.deck_saver = loaded_plugins.get_deck_saving_formats(self.configurations["deck"]["saving_format"])
        self.audio_saver = loaded_plugins.get_deck_saving_formats("json_deck_audio")
        self.buried_saver = loaded_plugins.get_deck_saving_formats("json_deck_cards")

        main_menu = Menu(self)
        file_menu = Menu(main_menu, tearoff=0)
        file_menu.add_command(label=self.lang_pack.create_file_menu_label, command=self.create_file_dialog)
        file_menu.add_command(label=self.lang_pack.open_file_menu_label, command=self.change_file)
        file_menu.add_command(label=self.lang_pack.save_files_menu_label, command=self.save_button)
        file_menu.add_separator()

        help_menu = Menu(file_menu, tearoff=0)
        help_menu.add_command(label=self.lang_pack.hotkeys_and_buttons_help_menu_label, command=self.help_command)
        help_menu.add_command(label=self.lang_pack.query_settings_language_label_text, command=self.get_query_language_help)
        file_menu.add_cascade(label=self.lang_pack.help_master_menu_label, menu=help_menu)

        file_menu.add_separator()
        file_menu.add_command(label=self.lang_pack.download_audio_menu_label,
                              command=partial(self.download_audio, choose_file=True))
        file_menu.add_separator()
        file_menu.add_command(label=self.lang_pack.change_media_folder_menu_label, command=self.change_media_dir)
        main_menu.add_cascade(label=self.lang_pack.file_master_menu_label, menu=file_menu)

        main_menu.add_command(label=self.lang_pack.add_card_menu_label, command=self.add_word_dialog)
        main_menu.add_command(label=self.lang_pack.search_inside_deck_menu_label, command=self.find_dialog)
        main_menu.add_command(label=self.lang_pack.statistics_menu_label, command=self.statistics_dialog)

        @error_handler(self.show_exception_logs)
        def settings_dialog():
            settings_window = self.Toplevel(self)
            settings_window.grid_columnconfigure(1, weight=1)
            settings_window.title(self.lang_pack.settings_menu_label)

            @error_handler(self.show_exception_logs)
            def change_theme(name: str):
                self.configurations["app"]["theme"] = name
                messagebox.showinfo(message=self.lang_pack.restart_app_text)

            theme_label = self.Label(settings_window, text=self.lang_pack.settings_themes_label_text)
            theme_label.grid(row=0, column=0, sticky="news")
            theme_option_menu = self.get_option_menu(settings_window,
                                                     init_text=self.configurations["app"]["theme"],
                                                     values=loaded_plugins.themes.loaded,
                                                     command=lambda theme_name:
                                                             change_theme(theme_name))
            theme_option_menu.grid(row=0, column=1, sticky="news")

            @error_handler(self.show_exception_logs)
            def change_language(name: str):
                self.configurations["app"]["language_package"] = name
                self.lang_pack = loaded_plugins.get_language_package(self.configurations["app"]["language_package"])
                messagebox.showinfo(message=self.lang_pack.restart_app_text)

            language_label = self.Label(settings_window, text=self.lang_pack.settings_language_label_text)
            language_label.grid(row=1, column=0, sticky="news")
            language_option_menu = self.get_option_menu(settings_window,
                                                        init_text=self.configurations["app"]["language_package"],
                                                        values=loaded_plugins.language_packages.loaded,
                                                        command=lambda language:
                                                                change_language(language))
            language_option_menu.grid(row=1, column=1, sticky="news")

            image_search_configuration_label = self.Label(settings_window,
                                                          text=self.lang_pack
                                                                   .settings_image_search_configuration_label_text)
            image_search_configuration_label.grid(row=2, column=0, sticky="news")

            image_search_conf_validation_scheme = copy.deepcopy(self.configurations.validation_scheme["image_search"])
            image_search_conf_validation_scheme.pop("starting_position", None)  # type: ignore
            image_search_conf_docs = """
timeout
    Image request timeout
    type: integer | float
    default: 1
    
max_request_tries
    Max image request retries per <Show more> rotation
    type: integer
    default: 5
    
n_images_in_row
    Maximum images in one row per <Show more> rotation
    type: integer
    default: 3
    
n_rows
    Maximum number of rows per <Show more> rotation
    type: integer
    default: 2
    
show_image_width
    Maximum button image width to which image would be scaled
    type: integer | null
    no scaling if null
    default: 250
    
show_image_height
    Maximum button image height to which image would be scaled
    type: integer | null
    no scaling if null
    
saving_image_width
    Maximum saving image width to which image would be scaled
    type: integer | null
    no scaling if null
    default: 300
    
saving_image_height
    Maximum saving image height to which image would be scaled
    type: integer | null
    no scaling if null
"""

            @error_handler(self.show_exception_logs)
            def get_image_search_conf() -> Config:
                image_search_conf = copy.deepcopy(self.configurations["image_search"])
                image_search_conf.pop("starting_position", None)
                conf = Config(validation_scheme=image_search_conf_validation_scheme,  # type: ignore
                              docs=image_search_conf_docs,
                              initial_value=image_search_conf)
                return conf

            @error_handler(self.show_exception_logs)
            def save_image_search_conf(config):
                for key, value in config.items():
                    self.configurations["image_search"][key] = value
            
            image_search_configuration_button = self.Button(settings_window,
                                                            text="</>",
                                                            command=lambda: self.call_configuration_window(
                                                                plugin_name=self.lang_pack
                                                                   .settings_image_search_configuration_label_text,
                                                                plugin_config=get_image_search_conf(),
                                                                plugin_load_function=lambda conf: None,
                                                                saving_action=lambda config:
                                                                    save_image_search_conf(config))
                                                            )
            image_search_configuration_button.grid(row=2, column=1, sticky="news")

            web_audio_downloader_configuration_label = self.Label(
                settings_window,
                text=self.lang_pack.setting_web_audio_downloader_configuration_label_text)
            web_audio_downloader_configuration_label.grid(row=3, column=0, sticky="news")

            web_audio_downloader_conf_validation_scheme = copy.deepcopy(self.configurations.validation_scheme["web_audio_downloader"])
            web_audio_downloader_conf_docs = """
timeout:
    Audio file request timeout
    type: integer    
    default: 1
    
request_delay:
    [Bulk donwload only] Delay between each request in milliseconds
    type: integer
    default: 3000
"""

            @error_handler(self.show_exception_logs)
            def get_web_audio_downloader_conf():
                web_audio_downloader_conf = copy.deepcopy(self.configurations["web_audio_downloader"])
                conf = Config(validation_scheme=web_audio_downloader_conf_validation_scheme,  # type: ignore
                              docs=web_audio_downloader_conf_docs,
                              initial_value=web_audio_downloader_conf)
                return conf

            @error_handler(self.show_exception_logs)
            def save_web_audio_downloader_conf(config):
                for key, value in config.items():
                    self.configurations["web_audio_downloader"][key] = value

            web_audio_downloader_configuration_button = self.Button(
                settings_window,
                text="</>",
                command=lambda: self.call_configuration_window(
                    plugin_name=self.lang_pack.setting_web_audio_downloader_configuration_label_text,
                    plugin_config=get_web_audio_downloader_conf(),
                    plugin_load_function=lambda conf: None,
                    saving_action=lambda config:
                    save_web_audio_downloader_conf(config))
                )
            web_audio_downloader_configuration_button.grid(row=3, column=1, sticky="news")

            extern_audio_placer_configuration_label = self.Label(
                settings_window,
                text=self.lang_pack.settings_extern_audio_placer_configuration_label_text)
            extern_audio_placer_configuration_label.grid(row=4, column=0, sticky="news")

            extern_audio_placer_conf_validation_scheme = copy.deepcopy(
                self.configurations.validation_scheme["extern_audio_placer"])
            extern_audio_placer_conf_docs = """
n_audios_per_batch:
    A number of external-source audios that would be placed per button click
    type: integer    
    default: 5
"""

            @error_handler(self.show_exception_logs)
            def get_extern_audio_placer_conf():
                extern_audio_placer_conf = copy.deepcopy(self.configurations["extern_audio_placer"])
                conf = Config(validation_scheme=extern_audio_placer_conf_validation_scheme,  # type: ignore
                              docs=extern_audio_placer_conf_docs,
                              initial_value=extern_audio_placer_conf)
                return conf

            @error_handler(self.show_exception_logs)
            def save_extern_audio_placer_conf(config):
                for key, value in config.items():
                    self.configurations["extern_audio_placer"][key] = value

            extern_audio_placer_configuration_button = self.Button(
                settings_window,
                text="</>",
                command=lambda: self.call_configuration_window(
                    plugin_name=self.lang_pack.settings_extern_audio_placer_configuration_label_text,
                    plugin_config=get_extern_audio_placer_conf(),
                    plugin_load_function=lambda conf: None,
                    saving_action=lambda config:
                    save_extern_audio_placer_conf(config))
            )
            extern_audio_placer_configuration_button.grid(row=4, column=1, sticky="news")

            extern_sentence_placer_configuration_label = self.Label(
                settings_window,
                text=self.lang_pack.settings_extern_sentence_placer_configuration_label)
            extern_sentence_placer_configuration_label.grid(row=5, column=0, sticky="news")

            extern_sentence_placer_conf_validation_scheme = copy.deepcopy(self.configurations.validation_scheme["extern_sentence_placer"])
            extern_sentence_placer_conf_docs = """
n_sentences_per_batch:
    A number of external-source sentences that would be placed per button click
    type: integer    
    default: 5
"""
            @error_handler(self.show_exception_logs)
            def get_extern_sentence_placer_conf():
                extern_sentence_placer_conf = copy.deepcopy(self.configurations["extern_sentence_placer"])
                conf = Config(validation_scheme=extern_sentence_placer_conf_validation_scheme,  # type: ignore
                              docs=extern_sentence_placer_conf_docs,
                              initial_value=extern_sentence_placer_conf)
                return conf
            
            @error_handler(self.show_exception_logs)
            def save_extern_sentence_placer_conf(config):
                for key, value in config.items():
                    self.configurations["extern_sentence_placer"][key] = value
                    
            extern_sentence_placer_configuration_button = self.Button(
                settings_window,
                text="</>",
                command=lambda: self.call_configuration_window(
                    plugin_name=self.lang_pack.settings_extern_sentence_placer_configuration_label,
                    plugin_config=get_extern_sentence_placer_conf(),
                    plugin_load_function=lambda conf: None,
                    saving_action=lambda config:
                        save_extern_sentence_placer_conf(config))
            )
            extern_sentence_placer_configuration_button.grid(row=5, column=1, sticky="news")

            card_processor_label = self.Label(settings_window,
                                              text=self.lang_pack.settings_card_processor_label_text)
            card_processor_label.grid(row=6, column=0, sticky="news")

            @error_handler(self.show_exception_logs)
            def choose_card_processor(name: str):
                self.configurations["deck"]["card_processor"] = name
                self.card_processor = loaded_plugins.get_card_processor(name)

            card_processor_option = self.get_option_menu(settings_window,
                                                         init_text=self.card_processor.name,
                                                         values=loaded_plugins.card_processors.loaded,
                                                         command=lambda processor: choose_card_processor(processor))
            card_processor_option.grid(row=6, column=1, sticky="news")

            format_processor_label = self.Label(settings_window,
                                                text=self.lang_pack.settings_format_processor_label_text)
            format_processor_label.grid(row=7, column=0, sticky="news")

            @error_handler(self.show_exception_logs)
            def choose_format_processor(name: str):
                self.configurations["deck"]["saving_format"] = name
                self.deck_saver = loaded_plugins.get_deck_saving_formats(name)

            format_processor_option = self.get_option_menu(settings_window,
                                                           init_text=self.deck_saver.name,
                                                           values=loaded_plugins.deck_saving_formats.loaded,
                                                           command=lambda format: choose_format_processor(format))
            format_processor_option.grid(row=7, column=1, sticky="news")

            audio_autopick_label = self.Label(settings_window,
                                              text=self.lang_pack.settings_audio_autopick_label_text)
            audio_autopick_label.grid(row=8, column=0, sticky="news")

            @error_handler(self.show_exception_logs)
            def save_audio_autochoose_option(option: str):
                if option == self.lang_pack.settings_audio_autopick_off:
                    raw_option = "off"
                elif option == self.lang_pack.settings_audio_autopick_first_default_audio:
                    raw_option = "first_default_audio"
                elif option == self.lang_pack.settings_audio_autopick_all_default_audios:
                    raw_option = "all_default_audios"
                elif option == self.lang_pack.settings_audio_autopick_first_available_audio:
                    raw_option = "first_available_audio"
                elif option == self.lang_pack.settings_audio_autopick_first_available_audio_source:
                    raw_option = "first_available_audio_source"
                elif option == self.lang_pack.settings_audio_autopick_all:
                    raw_option = "all"
                else:
                    raise NotImplementedError(f"Unknown audio autochoose option: {option}")
                self.configurations["app"]["audio_autochoose_mode"] = raw_option

            cur_mode = self.configurations["app"]["audio_autochoose_mode"]
            if cur_mode == "off":
                audio_autochoose_option_init_text = self.lang_pack.settings_audio_autopick_off
            elif cur_mode == "first_default_audio":
                audio_autochoose_option_init_text = self.lang_pack.settings_audio_autopick_first_default_audio
            elif cur_mode == "all_default_audios":
                audio_autochoose_option_init_text = self.lang_pack.settings_audio_autopick_all_default_audios
            elif cur_mode == "first_available_audio":
                audio_autochoose_option_init_text = self.lang_pack.settings_audio_autopick_first_available_audio
            elif cur_mode == "first_available_audio_source":
                audio_autochoose_option_init_text = self.lang_pack.settings_audio_autopick_first_available_audio_source
            elif cur_mode == "all":
                audio_autochoose_option_init_text = self.lang_pack.settings_audio_autopick_all
            else:
                raise NotImplementedError(f"Unknown audio autochoose CONF option: {cur_mode}")

            audio_autochoose_option_menu = self.get_option_menu(
                settings_window,
                init_text=audio_autochoose_option_init_text,
                values=[self.lang_pack.settings_audio_autopick_off,
                        self.lang_pack.settings_audio_autopick_first_default_audio,
                        self.lang_pack.settings_audio_autopick_all_default_audios,
                        self.lang_pack.settings_audio_autopick_first_available_audio,
                        self.lang_pack.settings_audio_autopick_first_available_audio_source,
                        self.lang_pack.settings_audio_autopick_all],
                command=save_audio_autochoose_option
            )
            audio_autochoose_option_menu.grid(row=8, column=1, sticky="news")

            @error_handler(self.show_exception_logs)
            def anki_dialog():
                anki_window = self.Toplevel(settings_window)

                @error_handler(self.show_exception_logs)
                def save_anki_settings_command():
                    self.configurations["anki"]["deck"] = anki_deck_entry.get().strip()
                    self.configurations["anki"]["field"] = anki_field_entry.get().strip()
                    anki_window.destroy()

                anki_window.title(self.lang_pack.anki_dialog_anki_window_title)
                anki_deck_entry = self.Entry(anki_window,
                                             placeholder=self.lang_pack.anki_dialog_anki_deck_entry_placeholder)
                anki_deck_entry.insert(0, self.configurations["anki"]["deck"])
                anki_deck_entry.fill_placeholder()

                anki_field_entry = self.Entry(anki_window,
                                              placeholder=self.lang_pack.anki_dialog_anki_field_entry_placeholder)
                anki_field_entry.insert(0, self.configurations["anki"]["field"])
                anki_field_entry.fill_placeholder()

                save_anki_settings_button = self.Button(anki_window,
                                                        text=self.lang_pack.anki_dialog_save_anki_settings_button_text,
                                                        command=save_anki_settings_command)

                padx = pady = 5
                anki_deck_entry.grid(row=0, column=0, sticky="we", padx=padx, pady=pady)
                anki_field_entry.grid(row=1, column=0, sticky="we", padx=padx, pady=pady)
                save_anki_settings_button.grid(row=2, column=0, sticky="ns", padx=padx)
                anki_window.bind("<Return>", lambda event: save_anki_settings_command())
                anki_window.bind("<Escape>", lambda event: anki_window.destroy())
                spawn_window_in_center(self, anki_window)
                anki_window.resizable(False, False)
                anki_window.grab_set()

            configure_anki_button = self.Button(settings_window,
                                                text=self.lang_pack.settings_configure_anki_button_text,
                                                command=anki_dialog)
            configure_anki_button.grid(row=9, column=0, columnspan=2, sticky="news")

            spawn_window_in_center(self, settings_window, desired_window_width=self.winfo_width())
            settings_window.resizable(False, False)
            settings_window.grab_set()
            settings_window.bind("<Escape>", lambda event: settings_window.destroy())
            settings_window.bind("<Return>", lambda event: settings_window.destroy())

        main_menu.add_command(label=self.lang_pack.settings_menu_label, command=settings_dialog)

        @error_handler(self.show_exception_logs)
        def chain_dialog():
            chain_type_window: Toplevel = self.Toplevel(self)
            chain_type_window.grid_columnconfigure(0, weight=1)
            chain_type_window.title(self.lang_pack.chain_management_menu_label)
            chain_type_window.bind("<Escape>", lambda event: chain_type_window.destroy())

            chaining_options = {self.lang_pack.chain_management_word_parsers_option     : "word_parsers",
                                self.lang_pack.chain_management_sentence_parsers_option : "sentence_parsers",
                                self.lang_pack.chain_management_image_parsers_option    : "image_parsers",
                                self.lang_pack.chain_management_audio_getters_option    : "audio_getters"}

            @error_handler(self.show_exception_logs)
            def select_chain_type(picked_value: str) -> None:
                close_chain_type_selection_button["state"] = call_chain_building_button["state"] = "normal"
                existing_chains_treeview.delete(*existing_chains_treeview.get_children())
                for i, (name, chain_data) in enumerate(self.chaining_data[chaining_options[picked_value]].items()):
                    existing_chains_treeview.insert(parent="", index=i,
                                                    values=(name, "->".join(chain_data["chain"])))

            chain_type_label = self.Label(chain_type_window,
                                          text=self.lang_pack.chain_management_chain_type_label_text,
                                          anchor="w")
            chain_type_label.grid(row=0, column=0, sticky="we", padx=10, pady=10)

            chain_type_option_menu = self.get_option_menu(master=chain_type_window,
                                                          init_text="",
                                                          values=chaining_options.keys(),
                                                          command=select_chain_type,
                                                          option_submenu_cfg=self.theme.option_submenus_cfg)
            chain_type_option_menu.configure(anchor='w')
            chain_type_option_menu.grid(row=1, column=0, sticky="we", padx=10, pady=(0, 10))

            existing_chains_treeview = Treeview(
                chain_type_window,
                columns=[self.lang_pack.chain_management_existing_chains_treeview_name_column,
                         self.lang_pack.chain_management_existing_chains_treeview_chain_column],
                         show="headings",
                         selectmode="browse")
            existing_chains_treeview.grid(row=2, column=0, sticky="news", padx=10, pady=(0, 10))
            chain_type_window.grid_rowconfigure(2, weight=1)

            existing_chains_treeview.heading(self.lang_pack.chain_management_existing_chains_treeview_name_column,
                                             text=self.lang_pack.chain_management_existing_chains_treeview_name_column)
            existing_chains_treeview.heading(self.lang_pack.chain_management_existing_chains_treeview_chain_column,
                                             text=self.lang_pack.chain_management_existing_chains_treeview_chain_column)

            existing_chains_treeview.column("#1", anchor="center", stretch=True)
            existing_chains_treeview.column("#2", anchor="center", stretch=True)

            @error_handler(self.show_exception_logs)
            def recreate_option_menus(chosen_parser_type: str):
                if chosen_parser_type == "word_parsers":
                    self.word_parser_option_menu.destroy()
                    self.word_parser_option_menu = self.get_option_menu(
                        self,
                        init_text=self.typed_word_parser_name,
                        values=[f"{parser_types.WEB_PREF} {item}" for item in loaded_plugins.web_word_parsers.loaded] +
                               [f"{parser_types.LOCAL_PREF} {item}" for item in
                                loaded_plugins.local_word_parsers.loaded] +
                               [f"{parser_types.CHAIN_PREF} {name}" for name in self.chaining_data["word_parsers"]],
                        command=lambda typed_parser: self.change_word_parser(typed_parser))
                    self.word_parser_option_menu.grid(row=0, column=3, columnspan=4, sticky="news",
                                                      pady=(self.text_pady, 0))

                elif chosen_parser_type == "sentence_parsers":
                    self.sentence_parser_option_menu.destroy()
                    if self.configurations["scrappers"]["sentence"]["type"] == parser_types.WEB:
                        typed_sentence_parser_name = self.sentence_parser.name
                    else:
                        typed_sentence_parser_name = f"[{parser_types.CHAIN}] {self.sentence_parser.name}"

                    self.sentence_parser_option_menu = self.get_option_menu(self,
                                                                            init_text=typed_sentence_parser_name,
                                                                            values=itertools.chain(
                                                                                loaded_plugins.web_sent_parsers.loaded,
                                                                                [f"[{parser_types.CHAIN}] {name}" for
                                                                                 name in
                                                                                 self.chaining_data[
                                                                                     "sentence_parsers"]]),
                                                                            command=lambda parser_name:
                                                                            self.change_sentence_parser(
                                                                                parser_name))
                    self.sentence_parser_option_menu.grid(row=8, column=3, columnspan=4, sticky="news")

                elif chosen_parser_type == "image_parsers":
                    self.image_parser_option_menu.destroy()
                    if self.configurations["scrappers"]["image"]["type"] == parser_types.WEB:
                        typed_image_parser_name = self.image_parser.name
                    else:
                        typed_image_parser_name = f"[{parser_types.CHAIN}] {self.image_parser.name}"

                    self.image_parser_option_menu = self.get_option_menu(self,
                                                                         init_text=typed_image_parser_name,
                                                                         values=itertools.chain(
                                                                             self.image_word_parsers_names,
                                                                             [f"[{parser_types.CHAIN}] {name}" for name
                                                                              in
                                                                              self.chaining_data["image_parsers"]]),
                                                                         command=lambda parser_name:
                                                                         self.change_image_parser(parser_name))
                    self.image_parser_option_menu.grid(row=3, column=3, columnspan=4, sticky="news",
                                                       padx=0, pady=self.text_pady)

                elif chosen_parser_type == "audio_getters":
                    self.audio_getter_option_menu.destroy()
                    self.audio_getter_option_menu = self.get_option_menu(
                        self,
                        init_text="default" if self.audio_getter is None
                                            else "[{}] {}".format(self.configurations["scrappers"]["audio"]["type"],
                                                                  self.audio_getter.name),
                        values=["default"] +
                               [f"{parser_types.WEB_PREF} {item}" for item in loaded_plugins.web_audio_getters.loaded] +
                               [f"{parser_types.LOCAL_PREF} {item}" for item in loaded_plugins.local_audio_getters.loaded] +
                               [f"{parser_types.CHAIN_PREF} {name}" for name in self.chaining_data["audio_getters"]],
                        command=lambda parser_name: self.change_audio_getter(parser_name))
                    self.audio_getter_option_menu.grid(row=5, column=3, columnspan=4, sticky="news",
                                                       pady=(self.text_pady, 0))
                else:
                    raise NotImplementedError(f"Unknown chosen parser type: {chosen_parser_type}")

            @error_handler(self.show_exception_logs)
            def remove_option(option: str):
                chosen_parser_type = chaining_options[chain_type_option_menu["text"]]
                self.chaining_data[chosen_parser_type].pop(option)
                recreate_option_menus(chosen_parser_type)

            @error_handler(self.show_exception_logs)
            def do_popup(event):
                if not existing_chains_treeview.focus():
                    return

                @error_handler(self.show_exception_logs)
                def edit_selected_chain():
                    selected_item_index = existing_chains_treeview.focus()
                    if not selected_item_index:
                        return
                    chain_name, _ = existing_chains_treeview.item(selected_item_index)["values"]
                    chain_data = self.chaining_data[chaining_options[chain_type_option_menu["text"]]][chain_name]

                    build_chain(chain_name=chain_name,
                                initial_chain=chain_data["chain"],
                                edit_mode=True)

                @error_handler(self.show_exception_logs)
                def remove_selected_chain():
                    selected_item_index = existing_chains_treeview.focus()
                    if not selected_item_index:
                        return
                    chain_name, _ = existing_chains_treeview.item(selected_item_index)["values"]
                    existing_chains_treeview.delete(selected_item_index)
                    remove_option(str(chain_name))

                m = Menu(root, tearoff=0)
                m.add_command(label=self.lang_pack.chain_management_pop_up_menu_edit_label,
                              command=edit_selected_chain)
                m.add_command(label=self.lang_pack.chain_management_pop_up_menu_remove_label,
                              command=remove_selected_chain)

                @error_handler(self.show_exception_logs)
                def popup_FocusOut():
                    m.grab_release()
                    m.destroy()

                m.bind("<FocusOut>", lambda event: popup_FocusOut())

                try:
                    m.tk_popup(event.x_root, event.y_root)
                finally:
                    m.grab_release()

            existing_chains_treeview.bind("<Button-3>", do_popup)

            command_panel: Frame = self.Frame(chain_type_window)
            command_panel.grid(row=3, column=0, sticky="we")

            @error_handler(self.show_exception_logs)
            def build_chain(chain_name: str,
                            initial_chain: list[str],
                            edit_mode: bool = False):
                pady = 2

                chain_type = chaining_options[chain_type_option_menu["text"]]

                ChoosingData = namedtuple("ChoosingData", ("name", "label", "select_button"))
                ChainData = namedtuple("ChainData", ("name", "label", "up_button", "deselect_button", "down_button"))

                @error_handler(self.show_exception_logs)
                def add_to_chain(placing_name: str):
                    new_chain_ind = len(chain_data) * 3
                    a = self.Label(built_chain_inner_frame, text=placing_name, justify='center',
                                   relief="ridge", borderwidth=2)
                    built_chain_main_frame.bind_scroll_wheel(a)

                    @error_handler(self.show_exception_logs)
                    def place_widget_to_chain(item: ChainData, next_3i: int):
                        item.label.grid(row=next_3i, column=0, sticky="news", rowspan=3, pady=pady)
                        item.up_button.grid(row=next_3i, column=1, sticky="news", pady=(pady, 0))
                        if next_3i:
                            item.up_button["state"] = "normal"
                            item.up_button.configure(
                                command=lambda ind=next_3i: swap_places(current_ind=ind // 3,
                                                                        direction=-1))
                        else:
                            item.up_button["state"] = "disabled"

                        item.deselect_button.grid(row=next_3i + 1, column=1, sticky="news", pady=0)
                        item.deselect_button.configure(command=lambda ind=next_3i: remove_from_chain(ind // 3))
                        item.down_button.grid(row=next_3i + 2, column=1, sticky="news", pady=(0, pady))

                        if next_3i == 3 * (len(chain_data) - 1):
                            item.down_button["state"] = "disabled"
                        else:
                            item.down_button["state"] = "normal"
                            item.down_button.configure(
                                command=lambda ind=next_3i: swap_places(current_ind=ind // 3,
                                                                        direction=1))

                    @error_handler(self.show_exception_logs)
                    def swap_places(current_ind: int, direction: int):
                        current = chain_data[current_ind]
                        operand = chain_data[current_ind + direction]

                        for i in range(1, len(chain_data[current_ind])):
                            current[i].grid_forget()
                            operand[i].grid_forget()

                        old_3 = 3 * current_ind
                        new_3 = old_3 + direction * 3
                        place_widget_to_chain(current, new_3)
                        place_widget_to_chain(operand, old_3)
                        chain_data[old_3 // 3], chain_data[new_3 // 3] = chain_data[new_3 // 3], chain_data[old_3 // 3]

                    @error_handler(self.show_exception_logs)
                    def remove_from_chain(ind: int):
                        for i in range(1, len(chain_data[ind])):
                            chain_data[ind][i].destroy()
                        chain_data.pop(ind)
                        for i in range(ind, len(chain_data)):
                            chain_data[i].label.grid_forget()
                            chain_data[i].label.grid(row=3 * i, column=0, sticky="news", pady=pady, rowspan=3)

                            chain_data[i].up_button.grid_forget()
                            chain_data[i].up_button.grid(row=3 * i, column=1, sticky="news", pady=(pady, 0))

                            chain_data[i].deselect_button.grid_forget()
                            chain_data[i].deselect_button.grid(row=3 * i + 1, column=1, sticky="news", pady=0)
                            chain_data[i].deselect_button.configure(command=lambda ind=i: remove_from_chain(ind))

                            chain_data[i].down_button.grid_forget()
                            chain_data[i].down_button.grid(row=3 * i + 2, column=1, sticky="news", pady=(0, pady))

                    up_button = self.Button(built_chain_inner_frame, text="∧")
                    built_chain_main_frame.bind_scroll_wheel(up_button)
                    deselect_button = self.Button(built_chain_inner_frame, text="✕",
                                       command=lambda ind=new_chain_ind: remove_from_chain(ind // 3))
                    built_chain_main_frame.bind_scroll_wheel(deselect_button)
                    down_button = self.Button(built_chain_inner_frame, text="∨")
                    built_chain_main_frame.bind_scroll_wheel(down_button)

                    if chain_data:
                        chain_data[-1].down_button["state"] = "normal"

                    chain_data.append(ChainData(name=placing_name,
                                                label=a,
                                                up_button=up_button,
                                                deselect_button=deselect_button,
                                                down_button=down_button))
                    place_widget_to_chain(chain_data[-1], new_chain_ind)

                chaining_window = self.Toplevel(chain_type_window)
                chaining_window.title(self.lang_pack.chain_management_menu_label)
                chaining_window.geometry(f"{self.winfo_screenwidth() // 3}x{self.winfo_screenheight() // 3}")
                chaining_window.bind("<Escape>", lambda event: chaining_window.destroy())
                chaining_window.bind("<Return>", lambda event: save_chain_sequence())
                chaining_window.grab_set()

                chaining_window.grid_columnconfigure(0, weight=1)
                chaining_window.grid_columnconfigure(1, weight=1)
                chaining_window.grid_rowconfigure(1, weight=1)

                chain_name_entry: Entry = self.Entry(
                    chaining_window,
                    placeholder=self.lang_pack.chain_management_chain_name_entry_placeholder)
                chain_name_entry.insert(0, chain_name)

                chain_name_entry.grid(row=0, column=0, columnspan=2, sticky="we", padx=10, pady=10)

                choosing_main_frame = ScrolledFrame(chaining_window, scrollbars="vertical",
                                                    canvas_bg=self.theme.frame_cfg.get("bg"))
                choosing_main_frame.grid(row=1, column=0, sticky="news", padx=10, pady=(0, 10))
                choosing_inner_frame = choosing_main_frame.display_widget(self.Frame,
                                                                  fit_width=True)
                choosing_main_frame.bind_scroll_wheel(choosing_inner_frame)
                choosing_inner_frame.grid_columnconfigure(0, weight=1)

                choosing_widgets_data: list[ChoosingData] = []
                chain_data: list[ChainData] = []

                if chain_type == "word_parsers":
                    displaying_options = \
                        itertools.chain(
                            (f"[{parser_types.WEB}] {name}" for name in loaded_plugins.web_word_parsers.loaded),
                            (f"[{parser_types.LOCAL}] {name}" for name in loaded_plugins.local_word_parsers.loaded))
                elif chain_type == "sentence_parsers":
                    displaying_options = loaded_plugins.web_sent_parsers.loaded
                elif chain_type == "image_parsers":
                    displaying_options = loaded_plugins.image_parsers.loaded
                elif chain_type == "audio_getters":
                    displaying_options = \
                        itertools.chain(
                            (f"[{parser_types.WEB}] {name}" for name in loaded_plugins.web_audio_getters.loaded),
                            (f"[{parser_types.LOCAL}] {name}" for name in loaded_plugins.local_audio_getters.loaded))
                else:
                    raise NotImplementedError(f"Unknown chain type: {chain_type}")

                for i, parser_name in enumerate(displaying_options):
                    a = self.Label(choosing_inner_frame, text=parser_name, justify='center',
                                   relief="ridge", borderwidth=2)
                    a.grid(row=i, column=0, sticky="news", pady=pady)
                    choosing_main_frame.bind_scroll_wheel(a)
                    b = self.Button(choosing_inner_frame, text=">",
                                    command=lambda name=parser_name: add_to_chain(name))
                    b.grid(row=i, column=1, sticky="news", pady=pady)
                    choosing_main_frame.bind_scroll_wheel(b)
                    choosing_widgets_data.append(ChoosingData(name=parser_name, label=a, select_button=b))

                built_chain_main_frame = ScrolledFrame(chaining_window, scrollbars="vertical",
                                                       canvas_bg=self.theme.frame_cfg.get("bg"))
                built_chain_main_frame.grid(row=1, column=1, sticky="news", padx=10, pady=(0, 10))
                built_chain_inner_frame = built_chain_main_frame.display_widget(self.Frame,
                                                                  fit_width=True)
                built_chain_main_frame.bind_scroll_wheel(built_chain_inner_frame)
                built_chain_inner_frame.grid_columnconfigure(0, weight=1)

                for name in initial_chain:
                    add_to_chain(name)

                command_frame: Frame = self.Frame(chaining_window, height=30)
                command_frame.grid(row=2, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 10))

                @error_handler(self.show_exception_logs)
                def save_chain_sequence():
                    new_chain_name = chain_name_entry.get().strip()
                    if not new_chain_name:
                        messagebox.showerror(title=self.lang_pack.error_title,
                                             message=self.lang_pack.chain_management_empty_chain_name_entry_message)
                        return

                    if self.chaining_data[chain_type].get(new_chain_name) is not None and \
                            (not edit_mode or chain_name != new_chain_name):
                        messagebox.showerror(title=self.lang_pack.error_title,
                                             message=self.lang_pack.chain_management_chain_already_exists_message)
                        return

                    chain = [item.name for item in chain_data]
                    chosen_chain_config = {"config_name": "{}_{}.json".format(remove_special_chars(new_chain_name, "_"),
                                                                              hash(time.time())),
                                           "chain": chain}
                    self.chaining_data[chain_type][new_chain_name] = chosen_chain_config

                    if edit_mode:
                        if chain_type == "word_parsers":
                            if chain_name == self.card_generator.name:
                                self.card_generator = CardGeneratorsChain(
                                    name=new_chain_name,
                                    chain_data=chosen_chain_config)
                                self.configurations["scrappers"]["word"]["name"] = new_chain_name

                        elif chain_type == "sentence_parsers":
                            if chain_name == self.sentence_parser.name:
                                self.sentence_parser = SentenceParsersChain(
                                    name=new_chain_name,
                                    chain_data=chosen_chain_config)
                                self.configurations["scrappers"]["sentence"]["name"] = new_chain_name

                        elif chain_type == "image_parsers":
                            if chain_name == self.image_parser.name:
                                self.sentence_parser = ImageParsersChain(
                                    name=new_chain_name,
                                    chain_data=chosen_chain_config)
                                self.configurations["scrappers"]["image"]["name"] = new_chain_name

                        elif chain_type == "audio_getters":
                            if self.audio_getter is not None:
                                if chain_name == self.audio_getter.name:
                                    old_get_all_val = self.audio_getter.config["get_all"]
                                    old_error_verbosity_val = self.audio_getter.config["error_verbosity"]
                                    self.audio_getter = AudioGettersChain(
                                        name=new_chain_name,
                                        chain_data=chosen_chain_config)
                                    self.external_audio_generator = ExternalDataFetcherWrapper(
                                        data_fetcher=self.audio_getter.get_audios)
                                    self.audio_getter.config["get_all"] = old_get_all_val
                                    self.audio_getter.config["error_verbosity"] = old_error_verbosity_val
                                    self.configurations["scrappers"]["audio"]["name"] = new_chain_name
                        else:
                            raise NotImplementedError(f"Unknown chosen parser type: {chain_type}")

                        if chain_name != new_chain_name:
                            remove_option(str(chain_name))
                        else:
                            recreate_option_menus(chain_type)

                        selected_item_index = existing_chains_treeview.focus()
                        existing_chains_treeview.set(selected_item_index, "#1", value=new_chain_name)
                        existing_chains_treeview.set(selected_item_index, "#2", value="->".join(chain))
                    else:
                        recreate_option_menus(chaining_options[chain_type_option_menu["text"]])
                        existing_chains_treeview.insert("", "end", values=(new_chain_name, "->".join(chain)))

                    chaining_window.destroy()

                save_chain_button = self.Button(
                    command_frame,
                    text=self.lang_pack.chain_management_save_chain_button_text,
                    command=save_chain_sequence)
                save_chain_button.pack(side="right", padx=5, pady=5)

                close_chain_building_button = self.Button(
                    command_frame,
                    text=self.lang_pack.chain_management_close_chain_building_button_text,
                    command=chaining_window.destroy)
                close_chain_building_button.pack(side="right", padx=5, pady=5)

            call_chain_building_button = self.Button(
                command_panel,
                text=self.lang_pack.chain_management_call_chain_building_button_text,
                command=lambda: build_chain(chain_name="",
                                            initial_chain=[]),
                                            state="disabled")
            call_chain_building_button.pack(side="right", padx=10, pady=(0, 10))

            close_chain_type_selection_button = self.Button(
                command_panel,
                text=self.lang_pack.chain_management_close_chain_type_selection_button,
                state="disabled",
                command=chain_type_window.destroy)
            close_chain_type_selection_button.pack(side="right", pady=(0, 10))

        main_menu.add_command(label=self.lang_pack.chain_management_menu_label, command=chain_dialog)
        main_menu.add_command(label=self.lang_pack.exit_menu_label, command=self.on_closing)
        self.config(menu=main_menu)

        self.text_padx = 10
        self.text_pady = 2

        for i in range(6):
            self.grid_columnconfigure(i, weight=1)
        self.grid_rowconfigure(9, weight=1)

        self.browse_button = self.Button(self,
                                         text=self.lang_pack.browse_button_text,
                                         command=self.web_search_command)
        self.browse_button.grid(row=0, column=0, sticky="news", columnspan=3,
                                padx=(self.text_padx, 0), pady=(self.text_pady, 0))

        self.word_parser_option_menu = self.get_option_menu(
            self,
            init_text=self.typed_word_parser_name,
            values=[f"{parser_types.WEB_PREF} {item}" for item in loaded_plugins.web_word_parsers.loaded] +
                   [f"{parser_types.LOCAL_PREF} {item}" for item in loaded_plugins.local_word_parsers.loaded] +
                   [f"{parser_types.CHAIN_PREF} {name}" for name in self.chaining_data["word_parsers"]],
            command=lambda typed_parser: self.change_word_parser(typed_parser))
        self.word_parser_option_menu.grid(row=0, column=3, columnspan=4, sticky="news",
                                          pady=(self.text_pady, 0))

        self.configure_word_parser_button = self.Button(self,
                                                        text="</>",
                                                        command=lambda: self.call_configuration_window(
                                                            plugin_name=self.card_generator.name,
                                                            plugin_config=self.card_generator.config,
                                                            plugin_load_function=lambda conf: conf.load(),
                                                            saving_action=lambda conf: conf.save()))
        self.configure_word_parser_button.grid(row=0, column=7, sticky="news",
                                               padx=(0, self.text_padx), pady=(self.text_pady, 0))

        self.word_text = self.Text(self, placeholder=self.lang_pack.word_text_placeholder, height=1)
        self.word_text.grid(row=1, column=0, columnspan=8, sticky="news",
                            padx=self.text_padx, pady=self.text_pady)

        self.special_field = self.Text(self, relief="ridge", state="disabled", height=1)
        self.special_field.grid(row=2, column=0, columnspan=8, sticky="news", padx=self.text_padx)

        self.image_word_parsers_names = loaded_plugins.image_parsers.loaded
        if self.configurations["scrappers"]["image"]["type"] == parser_types.WEB:
            typed_image_parser_name = self.image_parser.name
        else:
            typed_image_parser_name = f"[{parser_types.CHAIN}] {self.image_parser.name}"

        self.find_image_button = self.Button(self,
                                             text=self.lang_pack.find_image_button_normal_text,
                                             command=self.start_image_search)
        self.find_image_button.grid(row=3, column=0, columnspan=3, sticky="news", padx=(10, 0), pady=self.text_pady)

        self.image_parser_option_menu = self.get_option_menu(self,
                                                             init_text=typed_image_parser_name,
                                                             values=itertools.chain(
                                                                 self.image_word_parsers_names,
                                                                 [f"[{parser_types.CHAIN}] {name}" for name in self.chaining_data["image_parsers"]]),
                                                             command=lambda parser_name:
                                                             self.change_image_parser(parser_name))
        self.image_parser_option_menu.grid(row=3, column=3, columnspan=4, sticky="news",
                                           padx=0, pady=self.text_pady)

        self.configure_image_parser_button = self.Button(
            self,
            text="</>",
            command=lambda: self.call_configuration_window(
                plugin_name=self.image_parser.name if self.configurations["scrappers"]["image"]["type"] == parser_types.WEB
                                                   else f"[{parser_types.CHAIN}] {self.image_parser.name}",
                plugin_config=self.image_parser.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save()))
        self.configure_image_parser_button.grid(row=3, column=7, sticky="news",
                                                padx=(0, self.text_padx), pady=self.text_pady)

        self.definition_text = self.Text(self, placeholder=self.lang_pack.definition_text_placeholder, height=4)
        self.definition_text.grid(row=4, column=0, columnspan=8, sticky="news", padx=self.text_padx)

        # ======
        typed_audio_getter = "default" if self.audio_getter is None \
                                       else "[{}] {}".format(self.configurations["scrappers"]["audio"]["type"],
                                                             self.audio_getter.name)

        self.fetch_audio_data_button = self.Button(self,
                                                   text=self.lang_pack.fetch_audio_data_button_text,
                                                   command=lambda: self.display_audio_getter_results(show_errors=True))

        if typed_audio_getter == "default":
            self.fetch_audio_data_button["state"] = "disabled"

        self.fetch_audio_data_button.grid(row=5, column=0, columnspan=3,
                                          sticky="news",
                                          padx=(self.text_padx, 0), pady=(self.text_pady, 0))

        self.audio_getter_option_menu = self.get_option_menu(
            self,
            init_text=typed_audio_getter,
            values=["default"] +
                   [f"{parser_types.WEB_PREF} {item}" for item in loaded_plugins.web_audio_getters.loaded] +
                   [f"{parser_types.LOCAL_PREF} {item}" for item in loaded_plugins.local_audio_getters.loaded] +
                   [f"{parser_types.CHAIN_PREF} {name}" for name in self.chaining_data["audio_getters"]],
            command=lambda parser_name: self.change_audio_getter(parser_name))
        self.audio_getter_option_menu.grid(row=5, column=3, columnspan=4, sticky="news",
                                           pady=(self.text_pady, 0))

        self.configure_audio_getter_button = self.Button(self, text="</>")

        if self.audio_getter is not None:
            cmd = lambda: self.call_configuration_window(plugin_name=typed_audio_getter,
                                                         plugin_config=self.audio_getter.config,
                                                         plugin_load_function=lambda conf: conf.load(),
                                                         saving_action=lambda conf: conf.save())
            self.configure_audio_getter_button["command"] = cmd
        else:
            self.configure_audio_getter_button["state"] = "disabled"

        self.configure_audio_getter_button.grid(row=5, column=7, sticky="news",
                                                padx=(0, self.text_padx), pady=(self.text_pady, 0))

        self.sound_sf = ScrolledFrame(self, scrollbars="vertical",
                                      canvas_bg=self.theme.frame_cfg.get("bg"),
                                      height=110)

        self.sound_sf.grid(row=6, column=0, columnspan=8, sticky="news",
                                   padx=self.text_padx, pady=(0, self.text_pady))

        self.sound_inner_frame = self.sound_sf.display_widget(self.Frame, fit_width=True)
        self.sound_inner_frame.last_source = None
        self.sound_inner_frame.source_display_frame = None

        if self.configurations["scrappers"]["sentence"]["type"] == parser_types.WEB:
            typed_sentence_parser_name = self.sentence_parser.name
        else:
            typed_sentence_parser_name = f"[{parser_types.CHAIN}] {self.sentence_parser.name}"

        # ======
        a = self.Frame(self)
        a.grid(row=7, column=0, columnspan=8, padx=self.text_padx, pady=0, sticky="news")

        for i in range(3):
            a.columnconfigure(i, weight=1)

        self.prev_button = self.Button(a,
                                       text="🡰",
                                       command=lambda x=-1: self.replace_decks_pointers(x),
                                       font=Font(weight="bold"),
                                       state="disabled")
        self.prev_button.grid(row=0, column=0, sticky="news")

        self.bury_button = self.Button(a,
                                       text=self.lang_pack.bury_button_text,
                                       command=self.bury_command)
        self.bury_button.grid(row=0, column=1, sticky="news")

        self.skip_button = self.Button(a,
                                       text="🡲",
                                       command=self.skip_command,
                                       font=Font(weight="bold"))
        self.skip_button.grid(row=0, column=2, sticky="news")
        # ======
        self.add_sentences_button = self.Button(self,
                                                text=self.lang_pack.sentence_button_text,
                                                command=self.add_external_sentences)
        self.add_sentences_button.grid(row=8, column=0, columnspan=3, sticky="news", padx=(self.text_padx, 0))

        self.sentence_parser_option_menu = self.get_option_menu(self,
                                                                init_text=typed_sentence_parser_name,
                                                                values=itertools.chain(
                                                                    loaded_plugins.web_sent_parsers.loaded,
                                                                    [f"[{parser_types.CHAIN}] {name}" for name in self.chaining_data["sentence_parsers"]]),
                                                                command=lambda parser_name:
                                                                self.change_sentence_parser(parser_name))
        self.sentence_parser_option_menu.grid(row=8, column=3, columnspan=4, sticky="news")

        self.configure_sentence_parser_button = self.Button(
            self,
            text="</>",
            command=lambda: self.call_configuration_window(
                plugin_name=self.sentence_parser.name if self.configurations["scrappers"]["sentence"]["type"] == parser_types.WEB
                                                      else f"[{parser_types.CHAIN}] {self.sentence_parser.name}",
                plugin_config=self.sentence_parser.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save()),
            width=6)
        self.configure_sentence_parser_button.grid(row=8, column=7, sticky="news", padx=(0, self.text_padx))
        # ======

        self.sentence_texts = []

        self.text_widgets_sf = ScrolledFrame(self, scrollbars="vertical",
                                        canvas_bg=self.theme.frame_cfg.get("bg"))
        self.text_widgets_sf.grid(row=9, column=0, columnspan=8, sticky="news",
                                     padx=self.text_padx, pady=self.text_pady)

        self.text_widgets_frame = self.text_widgets_sf.display_widget(self.Frame, fit_width=True)
        self.text_widgets_sf.bind_scroll_wheel(self.text_widgets_frame)
        self.text_widgets_frame.grid_columnconfigure(0, weight=1)
        self.text_widgets_frame.last_source = None
        self.text_widgets_frame.source_display_frame = None

        # ======
        self.anki_button = self.Button(self,
                                       text=self.lang_pack.anki_button_text,
                                       command=self.open_anki_browser)
        # self.anki_button.grid(row=9, column=7, padx=self.text_padx, pady=self.text_pady, sticky="ns")

        self.user_tags_field = self.Entry(self, placeholder=self.lang_pack.user_tags_field_placeholder)
        self.user_tags_field.fill_placeholder()
        self.user_tags_field.grid(row=10, column=0, columnspan=6, sticky="news",
                                  padx=(self.text_padx, 0), pady=self.text_pady)

        self.tag_prefix_field = self.Entry(self, justify="center", width=8)
        self.tag_prefix_field.insert(0, self.configurations["deck"]["tags_hierarchical_pref"])
        self.tag_prefix_field.grid(row=10, column=7, columnspan=1, sticky="news",
                                   padx=(0, self.text_padx), pady=self.text_pady)

        self.dict_tags_field = self.Text(self, relief="ridge", state="disabled", height=2)
        self.dict_tags_field.grid(row=11, column=0, columnspan=8, sticky="news",
                                  padx=self.text_padx, pady=(0, self.text_padx))

        def focus_next_window(event):
            event.widget.tk_focusNext().focus()
            return "break"

        def focus_prev_window(event):
            event.widget.tk_focusPrev().focus()
            return "break"

        self.new_order = [self.browse_button, self.word_text, self.find_image_button, self.definition_text,
                          self.add_sentences_button] + self.sentence_texts + \
                         [self.user_tags_field] + [self.skip_button, self.prev_button,
                                                                       self.anki_button, self.bury_button,
                                                                       self.tag_prefix_field]

        for widget_index in range(len(self.new_order)):
            self.new_order[widget_index].lift()
            self.new_order[widget_index].bind("<Tab>", focus_next_window)
            self.new_order[widget_index].bind("<Shift-Tab>", focus_prev_window)

        self.bind("<Escape>", lambda event: self.on_closing())
        self.bind("<Control-Key-0>", lambda event: self.geometry("+0+0"))
        self.bind("<Control-d>", lambda event: self.skip_command())
        self.bind("<Control-q>", lambda event: self.bury_command())
        self.bind("<Control-s>", lambda event: self.save_button())
        self.bind("<Control-f>", lambda event: self.find_dialog())
        self.bind("<Control-e>", lambda event: self.statistics_dialog())
        self.bind("<Control-Shift_L><A>", lambda event: self.add_word_dialog())
        self.bind("<Control-z>", lambda event: self.replace_decks_pointers(-1))

        for i in range(0, 9):
            self.bind(f"<Control-Key-{i + 1}>", lambda event, index=i: self.choose_sentence(index))

        self.gb = Binder()
        self.gb.bind("Control", "c", "space",
                     action=lambda: self.define_word(word_query=self.clipboard_get(), additional_query="")
                     )

        @error_handler(self.show_exception_logs)
        def paste_in_sentence_field():
            clipboard_text = self.clipboard_get()
            self.add_sentence_field(source="<Control + c + Alt>", sentence=clipboard_text)

        self.gb.bind("Control", "c", "Alt", action=paste_in_sentence_field)
        self.gb.start()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.geometry(self.configurations["app"]["main_window_geometry"])

        AUTOSAVE_INTERVAL = 300_000  # time in milliseconds

        @error_handler(self.show_exception_logs)
        def autosave():
            self.save_files()
            self.after(AUTOSAVE_INTERVAL, autosave)

        self.after(AUTOSAVE_INTERVAL, autosave)

        self.tried_to_display_audio_getters_on_refresh = False
        self.already_waiting = False
        self.last_refresh_call_time = 0
        self.refresh()

    def show_window(self, title: str, text: str) -> Toplevel:
        text_window = self.Toplevel(self)
        text_window.title(title)
        message_display_text = self.Text(text_window, **self.theme.label_cfg)
        message_display_text.insert(1.0, text)
        message_display_text["state"] = "disabled"
        message_display_text.pack(expand=1, fill="both")
        message_display_text.update()
        text_window.config(width=min(self.winfo_screenwidth() // 3, message_display_text.winfo_width()),
                           height=min(self.winfo_screenheight() // 3, message_display_text.winfo_height()))
        text_window.bind("<Escape>", lambda event: text_window.destroy())
        return text_window

    def show_exception_logs(self, *args, **kwargs) -> None:
        error_log = create_exception_message()
        self.clipboard_clear()
        self.clipboard_append(error_log)
        error_window = self.show_window(title=self.lang_pack.error_title, text=error_log)
        error_window.grab_set()

    @error_handler(show_exception_logs)
    def load_conf_file(self) -> tuple[LoadableConfig, LanguagePackageContainer, bool]:
        validation_scheme = \
        {
            "scrappers": {
                "word": {
                    "type": (parser_types.WEB, [str], [parser_types.WEB, parser_types.LOCAL, parser_types.CHAIN]),
                    "name": ("cambridge", [str], [])
                },
                "sentence": {
                    "type": (parser_types.WEB, [str], [parser_types.WEB, parser_types.CHAIN]),
                    "name": ("sentencedict", [str], [])
                },
                "image": {
                    "type": (parser_types.WEB, [str], [parser_types.WEB, parser_types.CHAIN]),
                    "name": ("google", [str], [])
                },
                "audio": {
                    "type": ("default", [str], ["default", parser_types.WEB, parser_types.LOCAL, parser_types.CHAIN]),
                    "name": ("", [str], [])
                }
            },
            "anki": {
                "deck":  ("", [str], []),
                "field": ("", [str], [])
            },
            "directories": {
                "media_dir":      ("", [str], []),
                "last_open_file": ("", [str], []),
                "last_save_dir":  ("", [str], [])
            },
            "app": {
                "theme":                ("dark", [str], []),
                "main_window_geometry": ("500x800+0+0", [str], []),
                "language_package":     ("eng", [str], []),
                "audio_autochoose_mode":  ("off", [str], ["off",
                                                          "first_default_audio",
                                                          "all_default_audios",
                                                          "first_available_audio",
                                                          "first_available_audio_source",
                                                          "all"])
            },
            "image_search": {
                "starting_position":   ("+0+0", [str], []),
                "saving_image_width":  (300, [int, type(None)], []),
                "saving_image_height": (None, [int, type(None)], []),
                "max_request_tries":   (1, [int], []),
                "timeout":             (1, [int, float], []),
                "show_image_width":    (250, [int, type(None)], []),
                "show_image_height":   (None, [int, type(None)], []),
                "n_images_in_row":     (2, [int], []),
                "n_rows":              (2, [int], [])
            },
            "extern_sentence_placer": {
                "n_sentences_per_batch": (5, [int], [])
            },
            "extern_audio_placer": {
                "n_audios_per_batch": (5, [int], [])
            }
            ,
            "web_audio_downloader": {
                "timeout": (1, [int], []),
                "request_delay": (3000, [int], [])
            },
            "deck": {
                "tags_hierarchical_pref": ("", [str], []),
                "saving_format":          ("csv", [str], []),
                "card_processor":         ("Anki", [str], [])
            }
        }
        conf_file = LoadableConfig(config_location=os.path.dirname(__file__),
                                   validation_scheme=validation_scheme,  # type: ignore
                                   docs="")

        lang_pack = loaded_plugins.get_language_package(conf_file["app"]["language_package"])

        if not conf_file["directories"]["media_dir"] or not os.path.isdir(conf_file["directories"]["media_dir"]):
            conf_file["directories"]["media_dir"] = askdirectory(title=lang_pack.choose_media_dir_message,
                                                                 mustexist=True,
                                                                 initialdir=MEDIA_DOWNLOADING_LOCATION)
            if not conf_file["directories"]["media_dir"]:
                return (conf_file, lang_pack, True)

        if not conf_file["directories"]["last_open_file"] or not os.path.isfile(
                conf_file["directories"]["last_open_file"]):
            conf_file["directories"]["last_open_file"] = askopenfilename(title=lang_pack.choose_deck_file_message,
                                                                         filetypes=(("JSON", ".json"),),
                                                                         initialdir=ROOT_DIR)
            if not conf_file["directories"]["last_open_file"]:
                return (conf_file, lang_pack, True)

        if not conf_file["directories"]["last_save_dir"] or not os.path.isdir(
                conf_file["directories"]["last_save_dir"]):
            conf_file["directories"]["last_save_dir"] = askdirectory(title=lang_pack.choose_save_dir_message,
                                                                     mustexist=True,
                                                                     initialdir=ROOT_DIR)
            if not conf_file["directories"]["last_save_dir"]:
                return (conf_file, lang_pack, True)

        return (conf_file, lang_pack, False)

    @staticmethod
    def load_history_file() -> dict:
        if not os.path.exists(HISTORY_FILE_PATH):
            history_json = {}
        else:
            with open(HISTORY_FILE_PATH, "r", encoding="UTF-8") as f:
                history_json = json.load(f)
        return history_json

    @error_handler(show_exception_logs)
    def load_chaining_data(self) -> LoadableConfig:
        validation_scheme = \
        {
            "word_parsers":     ({}, [dict], []),
            "sentence_parsers": ({}, [dict], []),
            "image_parsers":    ({}, [dict], []),
            "audio_getters":    ({}, [dict], [])
        }
        chaining_data_file_dir = os.path.dirname(CHAIN_DATA_FILE_PATH)
        chaining_data_file_name = os.path.basename(CHAIN_DATA_FILE_PATH)

        chaining_data = LoadableConfig(validation_scheme=validation_scheme,
                                       docs="",
                                       config_location=chaining_data_file_dir,
                                       _config_file_name=chaining_data_file_name)
        return chaining_data

    @error_handler(show_exception_logs)
    def display_audio_getter_results(self, show_errors: bool):
        parser_results: list[tuple[tuple[str, str], AudioData]] = []

        def fill_parser_results() -> None:
            nonlocal parser_results

            assert self.audio_getter is not None, \
                "display_audio_getter_results cannot be called because self.audio_getter is None"

            word = self.word
            audio_getter_type = self.configurations["scrappers"]["audio"]["type"]

            if audio_getter_type in (parser_types.WEB, parser_types.LOCAL):
                typed_audio_getter_name = "[{}] {}".format(audio_getter_type,
                                                           self.configurations["scrappers"]["audio"]["name"])
                audio_data = self.external_audio_generator.get(
                    word=word,
                    card_data=self.dict_card_data,
                    batch_size=self.configurations["extern_audio_placer"]["n_audios_per_batch"])
                if audio_data is None:
                    parser_results = []
                    return
                parser_results = [((f"{typed_audio_getter_name}: {word}", audio_getter_type), audio_data)]
            elif audio_getter_type == parser_types.CHAIN:
                parser_results = self.external_audio_generator.get(
                    word=word,
                    card_data=self.dict_card_data,
                    batch_size=self.configurations["extern_audio_placer"]["n_audios_per_batch"])
                if parser_results is None:
                    parser_results = []
                    return
                parser_results = [((f"{typed_audio_getter_name}: {word}", audio_getter_type), audio_data) for
                                  (typed_audio_getter_name, audio_getter_type), audio_data in parser_results]
            else:
                raise NotImplementedError(f"Unknown audio getter type: {audio_getter_type}")

        def display_audio_if_done(thread: Thread):
            if thread.is_alive():
                self.after(100, lambda: display_audio_if_done(thread))
            else:
                self.display_audio_on_frame(word=self.word, parser_results=parser_results, show_errors=show_errors)

        th = Thread(target=fill_parser_results)
        th.start()
        display_audio_if_done(th)

    @error_handler(show_exception_logs)
    def display_audio_on_frame(self,
                               word: str,
                               parser_results: list[tuple[tuple[str, str], AudioData]],
                               show_errors: bool):
        @error_handler(self.show_exception_logs)
        def playsound_in_another_thread(audio_path: str):
            @error_handler(self.show_exception_logs)
            def quite_playsound(_audio_path: str):
                try:
                    playsound(_audio_path)
                except UnicodeDecodeError:
                    pass

            # cross-platform analog of playsound with block=False
            Thread(target=lambda: quite_playsound(audio_path)).start()

        @error_handler(self.show_exception_logs)
        def web_playsound(src: str):
            audio_name = self.card_processor.get_save_audio_name(word,
                                                                 self.typed_word_parser_name,
                                                                 "0",
                                                                 self.dict_card_data)

            temp_audio_path = os.path.join(os.getcwd(), "temp", audio_name)
            if os.path.exists(temp_audio_path):
                # you need to remove old file because Windows will raise permission denied error
                os.remove(temp_audio_path)

            def show_download_error(exc):
                messagebox.showerror(message=f"{self.lang_pack.error_title}\n{exc}")

            success = AudioDownloader.fetch_audio(url=src,
                                                  save_path=temp_audio_path,
                                                  timeout=self.configurations["web_audio_downloader"]["timeout"],
                                                  headers=self.headers,
                                                  exception_action=lambda exc: show_download_error(exc))
            if success:
                playsound_in_another_thread(temp_audio_path)

        if show_errors and not parser_results:
            audio_getter_type = self.configurations["scrappers"]["audio"]["type"]
            messagebox.showerror(
                title=self.audio_getter.name if audio_getter_type == parser_types.WEB
                else f"[{audio_getter_type}] {self.audio_getter.name}",
                message=self.lang_pack.display_audio_getter_results_audio_not_found_message
            )

        error_messages: list[tuple[str, str]] = []
        for (typed_audio_getter_name, audio_getter_type), ((audio_sources, additional_info), error_message) in parser_results:
            if error_message:
                error_messages.append((typed_audio_getter_name, error_message))
            if not audio_sources:
                continue

            if self.sound_inner_frame.last_source != typed_audio_getter_name:
                self.sound_inner_frame.last_source = typed_audio_getter_name
                self.sound_inner_frame.source_display_frame = LabelFrame(self.sound_inner_frame,
                                                                         text=typed_audio_getter_name,
                                                                         fg=self.theme.button_cfg.get("foreground"),
                                                                         **self.theme.frame_cfg)
                self.sound_sf.bind_scroll_wheel(self.sound_inner_frame.source_display_frame)
                self.sound_inner_frame.source_display_frame.grid_propagate(False)
                self.sound_inner_frame.source_display_frame.pack(side="top", fill="x", expand=True)

            if audio_getter_type == parser_types.WEB:
                play_sound_button_cmd = web_playsound
            elif audio_getter_type == parser_types.LOCAL:
                play_sound_button_cmd = playsound_in_another_thread
            else:
                raise NotImplementedError(f"Unknown audio getter type: {audio_getter_type}")

            for audio, info in zip(audio_sources, additional_info):
                audio_info_frame = self.Frame(self.sound_inner_frame.source_display_frame)
                audio_info_frame.pack(side="top", fill="x", expand=True)
                audio_info_frame.columnconfigure(2, weight=1)

                var = BooleanVar()
                var.set(False)
                pick_button = Checkbutton(audio_info_frame,
                                          variable=var,
                                          **self.theme.checkbutton_cfg)
                pick_button.grid(row=0, column=0, sticky="news")
                audio_info_frame.boolvar = var
                audio_info_frame.audio_data = (typed_audio_getter_name, audio_getter_type, audio)

                self.sound_sf.bind_scroll_wheel(pick_button)

                play_sound_button = self.Button(audio_info_frame,
                                                text="▶",
                                                command=lambda src=audio, a=play_sound_button_cmd: a(src))
                play_sound_button.grid(row=0, column=1, sticky="news")
                self.sound_sf.bind_scroll_wheel(play_sound_button)

                info_label = self.Label(audio_info_frame, text=info, relief="ridge")
                info_label.grid(row=0, column=2, sticky="news")
                self.sound_sf.bind_scroll_wheel(info_label)

        if show_errors and error_messages:
            self.show_window(title=self.lang_pack.error_title,
                             text="\n\n".join([f"{parser_name}\n{error}" for parser_name, error in error_messages]))

    @property
    @error_handler(show_exception_logs)
    def word(self):
        return self.word_text.get(1.0, "end").strip()

    @property
    @error_handler(show_exception_logs)
    def definition(self):
        return self.definition_text.get(1.0, "end").rstrip()

    @error_handler(show_exception_logs)
    def get_sentence(self, n: int):
        return self.sentence_texts[n].get(1.0, "end").rstrip()

    @error_handler(show_exception_logs)
    def change_file(self):
        new_file_path = askopenfilename(title=self.lang_pack.choose_deck_file_message,
                                   filetypes=(("JSON", ".json"),),
                                   initialdir=ROOT_DIR)
        if not new_file_path:
            return

        new_save_dir = askdirectory(title=self.lang_pack.choose_save_dir_message,
                                    initialdir=ROOT_DIR)
        if not new_save_dir:
            return

        self.save_files()
        self.session_start = datetime.now()
        self.str_session_start = self.session_start.strftime("%d-%m-%Y-%H-%M-%S")
        self.configurations["directories"]["last_save_dir"] = new_save_dir
        self.configurations["directories"]["last_open_file"] = new_file_path
        if self.history.get(new_file_path) is None:
            self.history[new_file_path] = -1

        self.deck = Deck(deck_path=self.configurations["directories"]["last_open_file"],
                         current_deck_pointer=self.history[self.configurations["directories"]["last_open_file"]],
                         card_generator=self.card_generator)
        self.saved_cards_data = SavedDataDeck()
        self.refresh()

    @error_handler(show_exception_logs)
    def create_file_dialog(self):
        @error_handler(self.show_exception_logs)
        def create_file():
            def foo():
                skip_var.set(True)
                copy_encounter.destroy()

            new_file_name = remove_special_chars(name_entry.get().strip(), sep="_")
            if not new_file_name:
                messagebox.showerror(title=self.lang_pack.error_title,
                                     message=self.lang_pack.create_file_no_file_name_was_given_message)
                return

            new_file_path = f"{new_file_dir}/{new_file_name}.json"
            skip_var = BooleanVar()
            skip_var.set(False)
            if os.path.exists(new_file_path):
                copy_encounter = self.Toplevel(create_file_win)
                copy_encounter.withdraw()
                message = self.lang_pack.create_file_file_already_exists_message
                encounter_label = self.Label(copy_encounter, text=message, relief="ridge")
                skip_encounter_button = self.Button(copy_encounter,
                                                    text=self.lang_pack.create_file_skip_encounter_button_text,
                                                    command=lambda: foo())
                rewrite_encounter_button = self.Button(copy_encounter,
                                                       text=self.lang_pack.create_file_rewrite_encounter_button_text,
                                                       command=lambda: copy_encounter.destroy())

                encounter_label.grid(row=0, column=0, padx=5, pady=5)
                skip_encounter_button.grid(row=1, column=0, padx=5, pady=5, sticky="news")
                rewrite_encounter_button.grid(row=2, column=0, padx=5, pady=5, sticky="news")
                copy_encounter.deiconify()
                spawn_window_in_center(self, copy_encounter)
                copy_encounter.resizable(False, False)
                copy_encounter.grab_set()
                create_file_win.wait_window(copy_encounter)

            create_file_win.destroy()

            if not skip_var.get():
                with open(new_file_path, "w", encoding="UTF-8") as new_file:
                    json.dump([], new_file)

            new_save_dir = askdirectory(title=self.lang_pack.choose_save_dir_message, initialdir=ROOT_DIR)
            if not new_save_dir:
                return

            self.save_files()
            self.session_start = datetime.now()
            self.str_session_start = self.session_start.strftime("%d-%m-%Y-%H-%M-%S")
            self.configurations["directories"]["last_save_dir"] = new_save_dir
            self.configurations["directories"]["last_open_file"] = new_file_path
            if self.history.get(new_file_path) is None:
                self.history[new_file_path] = -1

            self.deck = Deck(deck_path=new_file_path,
                             current_deck_pointer=self.history[new_file_path],
                             card_generator=self.card_generator)
            self.saved_cards_data = SavedDataDeck()
            self.refresh()

        new_file_dir = askdirectory(title=self.lang_pack.create_file_choose_dir_message, initialdir=ROOT_DIR)
        if not new_file_dir:
            return
        create_file_win = self.Toplevel(self)
        create_file_win.withdraw()
        name_entry = self.Entry(create_file_win,
                                placeholder=self.lang_pack.create_file_name_entry_placeholder,
                                justify="center")
        name_button = self.Button(create_file_win,
                                  text=self.lang_pack.create_file_name_button_placeholder,
                                  command=create_file)
        name_entry.grid(row=0, column=0, padx=5, pady=3, sticky="news")
        name_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
        create_file_win.deiconify()
        spawn_window_in_center(self, create_file_win)
        create_file_win.resizable(False, False)
        create_file_win.grab_set()
        name_entry.focus()
        create_file_win.bind("<Escape>", lambda event: create_file_win.destroy())
        create_file_win.bind("<Return>", lambda event: create_file())

    @error_handler(show_exception_logs)
    def save_files(self):
        self.configurations["app"]["main_window_geometry"] = self.geometry()
        self.configurations["deck"]["tags_hierarchical_pref"] = self.tag_prefix_field.get().strip()
        self.configurations.save()

        self.history[self.configurations["directories"]["last_open_file"]] = self.deck.get_pointer_position() - 1
        with open(HISTORY_FILE_PATH, "w") as saving_f:
            json.dump(self.history, saving_f, indent=4)

        self.chaining_data.save()
        self.deck.save()

        deck_name = os.path.basename(self.configurations["directories"]["last_open_file"]).split(sep=".")[0]
        saving_path = "{}/{}".format(self.configurations["directories"]["last_save_dir"], deck_name)
        self.deck_saver.save(self.saved_cards_data, CardStatus.ADD,
                             f"{saving_path}_{self.str_session_start}",
                             self.card_processor.get_card_image_name,
                             self.card_processor.get_card_audio_name)

        self.audio_saver.save(self.saved_cards_data, CardStatus.ADD,
                               f"{saving_path}_{self.str_session_start}_audios",
                               self.card_processor.get_card_image_name,
                               self.card_processor.get_card_audio_name)

        self.buried_saver.save(self.saved_cards_data, CardStatus.BURY,
                               f"{saving_path}_{self.str_session_start}_buried",
                               self.card_processor.get_card_image_name,
                               self.card_processor.get_card_audio_name)

    @error_handler(show_exception_logs)
    def help_command(self):
        mes = self.lang_pack.buttons_hotkeys_help_message
        self.show_window(title=self.lang_pack.buttons_hotkeys_help_window_title,
                         text=mes)

    @error_handler(show_exception_logs)
    def get_query_language_help(self):
        standard_fields = f"""
{FIELDS.word}: {self.lang_pack.word_field_help}
{FIELDS.special}: {self.lang_pack.special_field_help}
{FIELDS.definition}: {self.lang_pack.definition_field_help}
{FIELDS.sentences}: {self.lang_pack.sentences_field_help}
{FIELDS.img_links}: {self.lang_pack.img_links_field_help}
{FIELDS.audio_links}: {self.lang_pack.audio_links_field_help}
{FIELDS.dict_tags}: {self.lang_pack.dict_tags_field_help}
"""
        current_scheme = self.card_generator.scheme_docs
        lang_docs = self.lang_pack.query_language_docs

        self.show_window(self.lang_pack.query_language_window_title,
                         f"{self.lang_pack.general_scheme_label}:\n{standard_fields}\n"
                         f"{self.lang_pack.current_scheme_label}:\n{current_scheme}\n"
                         f"{self.lang_pack.query_language_label}:\n{lang_docs}")

    @error_handler(show_exception_logs)
    def download_audio(self, choose_file=False, closing=False):
        if choose_file:
            self.save_files()
            audio_file_name = askopenfilename(title=self.lang_pack.download_audio_choose_audio_file_title,
                                              filetypes=(("JSON", ".json"),),
                                              initialdir=ROOT_DIR)
            if not audio_file_name:
                return
            with open(audio_file_name, encoding="UTF-8") as audio_file:
                audio_links_list = json.load(audio_file)
        else:
            audio_links_list = self.saved_cards_data.get_audio_data(CardStatus.ADD)
        audio_downloader = AudioDownloader(master=self,
                                           headers=self.headers,
                                           timeout=self.configurations["web_audio_downloader"]["timeout"],
                                           request_delay=self.configurations["web_audio_downloader"]["request_delay"],
                                           temp_dir=TEMP_DIR,
                                           saving_dir=self.configurations["directories"]["media_dir"],
                                           toplevel_cfg=self.theme.toplevel_cfg,
                                           pb_cfg={"length": self.winfo_width()},
                                           label_cfg=self.theme.label_cfg,
                                           button_cfg=self.theme.button_cfg,
                                           checkbutton_cfg=self.theme.checkbutton_cfg,
                                           lang_pack=self.lang_pack)
        if closing:
            audio_downloader.bind("<Destroy>", lambda event: self.destroy() if isinstance(event.widget, Toplevel) else None)
        spawn_window_in_center(self, audio_downloader)
        audio_downloader.resizable(False, False)
        audio_downloader.grab_set()
        audio_downloader.download_audio(audio_links_list)

    @error_handler(show_exception_logs)
    def change_media_dir(self):
        media_dir =  askdirectory(title=self.lang_pack.choose_media_dir_message,
                                  mustexist=True,
                                  initialdir=MEDIA_DOWNLOADING_LOCATION)
        if media_dir:
            self.configurations["directories"]["media_dir"] = media_dir

    @error_handler(show_exception_logs)
    def save_button(self):
        self.save_files()
        messagebox.showinfo(message=self.lang_pack.save_files_message)

    @error_handler(show_exception_logs)
    def define_word(self, word_query: str, additional_query: str) -> bool:
        try:
            exact_pattern = re.compile(r"\b{}\b".format(word_query), re.IGNORECASE)
        except re.error:
            messagebox.showerror(title=self.lang_pack.error_title,
                                 message=self.lang_pack.define_word_wrong_regex_message)
            return True

        exact_word_filter = lambda comparable: re.search(exact_pattern, comparable)
        try:
            additional_filter = get_card_filter(additional_query) if additional_query else None
            if self.deck.add_card_to_deck(query=word_query,
                                          word_filter=exact_word_filter,
                                          additional_filter=additional_filter):
                self.refresh()
                return False
            messagebox.showerror(title=self.typed_word_parser_name,
                                 message=self.lang_pack.define_word_word_not_found_message)
        except ParsingException as e:
            messagebox.showerror(title=self.lang_pack.error_title,
                                 message=str(e))
        return True

    @error_handler(show_exception_logs)
    def add_word_dialog(self):
        @error_handler(self.show_exception_logs)
        def get_word():
            clean_word = add_word_entry.get().strip()
            additional_query = additional_filter_entry.get(1.0, "end").strip()
            if not self.define_word(clean_word, additional_query):
                add_word_window.destroy()
            else:
                add_word_window.withdraw()
                add_word_window.deiconify()

        add_word_window = self.Toplevel(self)
        add_word_window.withdraw()

        add_word_window.grid_columnconfigure(0, weight=1)
        add_word_window.title(self.lang_pack.add_word_window_title)

        add_word_entry = self.Entry(add_word_window,
                                    placeholder=self.lang_pack.add_word_entry_placeholder)
        add_word_entry.focus()
        add_word_entry.grid(row=0, column=0, padx=5, pady=3, sticky="we")

        additional_filter_entry = self.Text(add_word_window,
                                            placeholder=self.lang_pack.add_word_additional_filter_entry_placeholder,
                                            height=5)
        additional_filter_entry.grid(row=1, column=0, padx=5, pady=3, sticky="we")

        start_parsing_button = self.Button(add_word_window,
                                           text=self.lang_pack.add_word_start_parsing_button_text,
                                           command=get_word)
        start_parsing_button.grid(row=2, column=0, padx=5, pady=3, sticky="ns")

        add_word_window.bind("<Escape>", lambda event: add_word_window.destroy())
        add_word_window.bind("<Return>", lambda event: get_word())
        add_word_window.deiconify()
        spawn_window_in_center(master=self, toplevel_widget=add_word_window,
                                 desired_window_width=self.winfo_width())
        add_word_window.resizable(False, False)
        add_word_window.grab_set()

    @error_handler(show_exception_logs)
    def find_dialog(self):
        @error_handler(self.show_exception_logs)
        def go_to():
            find_query = find_text.get(1.0, "end").strip()
            if not find_query:
                messagebox.showerror(title=self.lang_pack.error_title,
                                     message=self.lang_pack.find_dialog_empty_query_message)
                return

            if find_query.startswith("->"):
                if not (move_quotient := find_query[2:]).lstrip("-").isdigit():
                    messagebox.showerror(title=self.lang_pack.error_title,
                                         message=self.lang_pack.find_dialog_wrong_move_message)
                else:
                    self.replace_decks_pointers(int(move_quotient))
                find_window.destroy()
                return

            try:
                searching_filter = get_card_filter(find_query)
            except ParsingException as e:
                messagebox.showerror(title=self.lang_pack.error_title,
                                     message=str(e))
                find_window.withdraw()
                find_window.deiconify()
                return

            if (move_list := self.deck.find_card(searching_func=searching_filter)):
                @error_handler(self.show_exception_logs)
                def rotate(n: int):
                    nonlocal move_list, found_item_number

                    found_item_number += n
                    rotate_window.title(f"{found_item_number}/{len(move_list) + 1}")

                    if n > 0:
                        current_offset = move_list.get_pointed_item()
                        move_list.move(n)
                    else:
                        move_list.move(n)
                        current_offset = -move_list.get_pointed_item()

                    left["state"] = "disabled" if not move_list.get_pointer_position() else "normal"
                    right["state"] = "disabled" if move_list.get_pointer_position() == len(move_list) else "normal"

                    self.replace_decks_pointers(current_offset)

                find_window.destroy()

                found_item_number = 1
                rotate_window = self.Toplevel(self)
                rotate_window.title(f"{found_item_number}/{len(move_list) + 1}")

                left = self.Button(rotate_window, text="🡰", command=lambda: rotate(-1),
                                   font=Font(weight="bold"))
                left["state"] = "disabled"
                left.grid(row=0, column=0, sticky="we")

                right = self.Button(rotate_window, text="🡲", command=lambda: rotate(1),
                                    font=Font(weight="bold"))
                right.grid(row=0, column=2, sticky="we")

                end_rotation_button = self.Button(rotate_window,
                                               text=self.lang_pack.find_dialog_end_rotation_button_text,
                                               command=lambda: rotate_window.destroy())
                end_rotation_button.grid(row=0, column=1, sticky="we")
                spawn_window_in_center(self, rotate_window)
                rotate_window.resizable(False, False)
                rotate_window.grab_set()
                rotate_window.bind("<Escape>", lambda _: rotate_window.destroy())
                return
            messagebox.showerror(title=self.lang_pack.error_title,
                                 message=self.lang_pack.find_dialog_nothing_found_message)
            find_window.withdraw()
            find_window.deiconify()

        find_window = self.Toplevel(self)
        find_window.withdraw()
        find_window.title(self.lang_pack.find_dialog_find_window_title)
        find_window.grid_columnconfigure(0, weight=1)
        find_text = self.Text(find_window, height=5)
        find_text.grid(row=0, column=0, padx=5, pady=3, sticky="we")
        find_text.focus()

        find_button = self.Button(find_window,
                                  text=self.lang_pack.find_dialog_find_button_text,
                                  command=go_to)
        find_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
        find_window.bind("<Return>", lambda _: go_to())
        find_window.bind("<Escape>", lambda _: find_window.destroy())
        find_window.deiconify()
        spawn_window_in_center(self, find_window, desired_window_width=self.winfo_width())
        find_window.resizable(False, False)
        find_window.grab_set()

    @error_handler(show_exception_logs)
    def statistics_dialog(self):
        statistics_window = self.Toplevel(self)
        statistics_window.withdraw()

        statistics_window.title(self.lang_pack.statistics_dialog_statistics_window_title)
        text_list = ((self.lang_pack.statistics_dialog_added_label,
                      self.lang_pack.statistics_dialog_buried_label,
                      self.lang_pack.statistics_dialog_skipped_label,
                      self.lang_pack.statistics_dialog_cards_left_label,
                      self.lang_pack.statistics_dialog_current_file_label,
                      self.lang_pack.statistics_dialog_saving_dir_label,
                      self.lang_pack.statistics_dialog_media_dir_label),
                     (self.saved_cards_data.get_card_status_stats(CardStatus.ADD),
                      self.saved_cards_data.get_card_status_stats(CardStatus.BURY),
                      self.saved_cards_data.get_card_status_stats(CardStatus.SKIP),
                      self.deck.get_n_cards_left(),
                      self.deck.deck_path,
                      self.configurations["directories"]["last_save_dir"],
                      self.configurations["directories"]["media_dir"]))

        scroll_frame = ScrolledFrame(statistics_window, scrollbars="horizontal")
        scroll_frame.pack()
        scroll_frame.bind_scroll_wheel(statistics_window)
        inner_frame = scroll_frame.display_widget(self.Frame)
        for row_index in range(len(text_list[0])):
            for column_index in range(2):
                info = self.Label(inner_frame, text=text_list[column_index][row_index], anchor="center",
                             relief="ridge")
                info.grid(column=column_index, row=row_index, sticky="news")

        statistics_window.bind("<Escape>", lambda _: statistics_window.destroy())
        statistics_window.update()
        current_frame_width = inner_frame.winfo_width()
        current_frame_height = inner_frame.winfo_height()
        scroll_frame.config(width=min(self.winfo_width(), current_frame_width),
                            height=min(self.winfo_height(), current_frame_height))
        statistics_window.deiconify()
        spawn_window_in_center(self, statistics_window)
        statistics_window.resizable(False, False)
        statistics_window.grab_set()

    @error_handler(show_exception_logs)
    def on_closing(self):
        if messagebox.askokcancel(title=self.lang_pack.on_closing_message_title,
                                  message=self.lang_pack.on_closing_message):
            self.save_files()
            self.gb.stop()
            self.download_audio(closing=True)

    @error_handler(show_exception_logs)
    def web_search_command(self):
        search_term = self.word
        definition_search_query = search_term + " definition"
        webbrowser.open_new_tab(f"https://www.google.com/search?q={definition_search_query}")
        sentence_search_query = search_term + " sentence examples"
        webbrowser.open_new_tab(f"https://www.google.com/search?q={sentence_search_query}")

    @error_handler(show_exception_logs)
    def call_configuration_window(self,
                                  plugin_name: str,
                                  plugin_config: Config,
                                  plugin_load_function: Callable[[Config], None],
                                  saving_action: Callable[[Config], None]):
        plugin_load_function(plugin_config)

        conf_window = self.Toplevel(self)
        conf_window.title(f"{plugin_name} {self.lang_pack.configuration_window_conf_window_title}")

        text_pane_win = PanedWindow(conf_window, **self.theme.frame_cfg)
        text_pane_win.pack(side="top", expand=1, fill="both", anchor="n")

        conf_sf = ScrolledFrame(text_pane_win, scrollbars="both",
                                canvas_bg=self.theme.frame_cfg.get("bg"))
        text_pane_win.add(conf_sf, stretch="always", sticky="news")
        conf_inner_frame = conf_sf.display_widget(self.Frame, fit_width=True)

        conf_text = self.Text(conf_inner_frame)
        conf_text.insert(1.0, json.dumps(plugin_config.data, indent=4))
        conf_text.pack(fill="both", expand=True)
        conf_sf.bind_scroll_wheel(conf_text)

        docs_pane_win = PanedWindow(text_pane_win, orient="vertical",
                                    showhandle=True, **self.theme.frame_cfg)

        docs_sf = ScrolledFrame(text_pane_win, scrollbars="both",
                                canvas_bg=self.theme.frame_cfg.get("bg"))
        docs_pane_win.add(docs_sf, stretch="always", sticky="news")
        docs_inner_frame = docs_sf.display_widget(self.Frame, fit_width=True)

        conf_docs_text = self.Text(docs_inner_frame)
        conf_docs_text.insert(1.0, plugin_config.docs)
        conf_docs_text["state"] = "disabled"
        conf_docs_text.pack(fill="both", expand=True)
        docs_sf.bind_scroll_wheel(conf_docs_text)

        text_pane_win.add(docs_pane_win, stretch="always")

        @error_handler(self.show_exception_logs)
        def restore_defaults():
            plugin_config.restore_defaults()
            conf_text.clear()
            conf_text.insert(1.0, json.dumps(plugin_config.data, indent=4))
            messagebox.showinfo(message=self.lang_pack.configuration_window_restore_defaults_done_message)

        conf_window_control_panel = self.Frame(conf_window)
        conf_window_control_panel.pack(side="bottom", fill="x", anchor="s")

        conf_restore_defaults_button = self.Button(
            conf_window_control_panel,
            text=self.lang_pack.configuration_window_restore_defaults_button_text,
            command=restore_defaults)
        conf_restore_defaults_button.pack(side="left")
        configuration_window_cancel_button = self.Button(
            conf_window_control_panel,
            text=self.lang_pack.configuration_window_cancel_button_text,
            command=conf_window.destroy)
        configuration_window_cancel_button.pack(side="right")

        @error_handler(self.show_exception_logs)
        def done():
            new_config = conf_text.get(1.0, "end")
            try:
                json_new_config = json.loads(new_config)
            except ValueError:
                messagebox.showerror(self.lang_pack.error_title,
                                     self.lang_pack.configuration_window_bad_json_scheme_message)
                return
            config_errors: LoadableConfig.SchemeCheckResults = \
                plugin_config.validate_config(json_new_config, plugin_config.validation_scheme)

            if not config_errors:
                plugin_config.data = json_new_config
                saving_action(plugin_config)
                conf_window.destroy()
                messagebox.showinfo(message=self.lang_pack.configuration_window_saved_message)
                return

            config_error_message = ""
            if config_errors.wrong_type:
                config_error_message += f"{self.lang_pack.configuration_window_wrong_type_field}:\n"
                wrong_type_message = "\n".join((f" * {error[0]}: {error[1]}. "
                                                f"{self.lang_pack.configuration_window_expected_prefix}: {error[2]}"
                                                for error in config_errors.wrong_type))
                config_error_message += wrong_type_message + "\n"

            if config_errors.wrong_value:
                config_error_message += f"{self.lang_pack.configuration_window_wrong_value_field}:\n"
                wrong_value_message = "\n".join((f" * {error[0]}: {error[1]}. "
                                                 f"{self.lang_pack.configuration_window_expected_prefix}: {error[2]}"
                                                 for error in config_errors.wrong_value))
                config_error_message += wrong_value_message + "\n"

            if config_errors.missing_keys:
                config_error_message += f"{self.lang_pack.configuration_window_missing_keys_field}:\n"
                missing_keys_message = "\n".join((f" * {missing_key}"
                                                  for missing_key in config_errors.missing_keys))
                config_error_message += missing_keys_message + "\n"

            if config_errors.unknown_keys:
                config_error_message += f"{self.lang_pack.configuration_window_unknown_keys_field}:\n"
                unknown_keys_message = "\n".join((f" * {unknown_key}"
                                                  for unknown_key in config_errors.unknown_keys))
                config_error_message += unknown_keys_message + "\n"
            self.show_window(title=self.lang_pack.error_title,
                             text=config_error_message)

        save_button = self.Button(conf_window_control_panel,
                                  text=self.lang_pack.configuration_window_save_button_text,
                                  command=done)
        save_button.pack(side="right")

        for i in range(3):
            conf_window.grid_columnconfigure(i, weight=1)

        conf_window.bind("<Escape>", lambda event: conf_window.destroy())
        conf_window.bind("<Return>", lambda event: done())
        spawn_window_in_center(self, conf_window,
                               desired_window_width=self.winfo_width())
        conf_window.grab_set()

    @error_handler(show_exception_logs)
    def change_word_parser(self, typed_parser: str):
        if typed_parser.startswith(parser_types.WEB_PREF):
            self.configurations["scrappers"]["word"]["type"] = parser_types.WEB
            raw_name = typed_parser[len(parser_types.WEB_PREF) + 1:]
            self.card_generator = loaded_plugins.get_web_card_generator(raw_name)
        elif typed_parser.startswith(parser_types.LOCAL_PREF):
            self.configurations["scrappers"]["word"]["type"] = parser_types.LOCAL
            raw_name = typed_parser[len(parser_types.LOCAL_PREF) + 1:]
            self.card_generator = loaded_plugins.get_local_card_generator(raw_name)
        elif typed_parser.startswith(parser_types.CHAIN_PREF):
            self.configurations["scrappers"]["word"]["type"] = parser_types.CHAIN
            raw_name = typed_parser[len(parser_types.CHAIN_PREF) + 1:]
            self.card_generator = CardGeneratorsChain(name=raw_name,
                                                      chain_data=self.chaining_data["word_parsers"][raw_name])
        else:
            raise NotImplementedError(f"Parser of unknown type: {typed_parser}")

        self.configurations["scrappers"]["word"]["name"] = raw_name
        self.typed_word_parser_name = typed_parser
        self.deck.update_card_generator(self.card_generator)

    @error_handler(show_exception_logs)
    def change_audio_getter(self, typed_getter: str):
        if typed_getter == "default":
            self.audio_getter = None
            self.external_audio_generator = None
            self.configurations["scrappers"]["audio"]["type"] = "default"
            self.configurations["scrappers"]["audio"]["name"] = ""
            self.fetch_audio_data_button["state"] = "disabled"
            self.configure_audio_getter_button["state"] = "disabled"
            return

        if typed_getter.startswith(parser_types.WEB_PREF):
            raw_name = typed_getter[len(parser_types.WEB_PREF) + 1:]
            self.audio_getter = loaded_plugins.get_web_audio_getter(raw_name)
            self.configurations["scrappers"]["audio"]["type"] = parser_types.WEB
        elif typed_getter.startswith(parser_types.LOCAL_PREF):
            raw_name = typed_getter[len(parser_types.LOCAL_PREF) + 1:]
            self.audio_getter = loaded_plugins.get_local_audio_getter(raw_name)
            self.configurations["scrappers"]["audio"]["type"] = parser_types.LOCAL
        elif typed_getter.startswith(parser_types.CHAIN_PREF):
            raw_name = typed_getter[len(parser_types.CHAIN_PREF) + 1:]
            self.audio_getter = AudioGettersChain(name=raw_name,
                                                  chain_data=self.chaining_data["audio_getters"][raw_name])
            self.configurations["scrappers"]["audio"]["type"] = parser_types.CHAIN
        else:
            raise NotImplementedError(f"Audio getter with unknown type: {typed_getter}")

        self.external_audio_generator = ExternalDataFetcherWrapper(data_fetcher=self.audio_getter.get_audios)
        self.configurations["scrappers"]["audio"]["name"] = raw_name
        self.fetch_audio_data_button["state"] = "normal"

        self.configure_audio_getter_button["state"] = "normal"
        self.configure_audio_getter_button["command"] = \
            lambda: self.call_configuration_window(
                plugin_name=typed_getter,
                plugin_config=self.audio_getter.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save())

    @error_handler(show_exception_logs)
    def change_image_parser(self, given_image_parser_name: str):
        if not given_image_parser_name.startswith(f"[{parser_types.CHAIN}]"):
            self.configurations["scrappers"]["image"]["type"] = parser_types.WEB
            self.configurations["scrappers"]["image"]["name"] = given_image_parser_name
            self.image_parser = loaded_plugins.get_image_parser(given_image_parser_name)
            return

        given_image_parser_name = given_image_parser_name[8:]
        self.configurations["scrappers"]["image"]["type"] = parser_types.CHAIN
        self.configurations["scrappers"]["image"]["name"] = given_image_parser_name
        chain_data = self.chaining_data["image_parsers"][given_image_parser_name]
        self.image_parser = ImageParsersChain(name=given_image_parser_name,
                                              chain_data=chain_data)

    @error_handler(show_exception_logs)
    def change_sentence_parser(self, given_sentence_parser_name: str):
        if given_sentence_parser_name.startswith(f"[{parser_types.CHAIN}]"):
            self.configurations["scrappers"]["sentence"]["type"] = parser_types.CHAIN
            given_sentence_parser_name = given_sentence_parser_name[8:]
            self.sentence_parser = SentenceParsersChain(
                name=given_sentence_parser_name,
                chain_data=self.chaining_data["sentence_parsers"][given_sentence_parser_name])
        else:
            self.configurations["scrappers"]["sentence"]["type"] = parser_types.WEB
            self.sentence_parser = loaded_plugins.get_sentence_parser(given_sentence_parser_name)
        self.external_sentence_fetcher = ExternalDataFetcherWrapper(data_fetcher=self.sentence_parser.get_sentences)
        self.configurations["scrappers"]["sentence"]["name"] = given_sentence_parser_name

    @error_handler(show_exception_logs)
    def choose_sentence(self, sentence_number: int):
        if sentence_number >= len(self.sentence_texts):
            return

        word = self.word
        self.dict_card_data[FIELDS.word] = word
        self.dict_card_data[FIELDS.definition] = self.definition

        picked_sentence = self.get_sentence(sentence_number)
        if not picked_sentence:
            picked_sentence = self.dict_card_data[FIELDS.word]
        self.dict_card_data[FIELDS.sentences] = [picked_sentence]

        additional = self.dict_card_data.get(SavedDataDeck.ADDITIONAL_DATA, {})
        additional[SavedDataDeck.AUDIO_DATA] = {}
        additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS] = []
        additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS_TYPE] = []
        additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SAVING_PATHS] = []

        user_tags = self.user_tags_field.get().strip()
        if user_tags:
            additional[SavedDataDeck.USER_TAGS] = user_tags

        @error_handler(self.show_exception_logs)
        def add_audio_data_to_card(getter_name: str, getter_type: str, audio_links: list[str], add_type_prefix: bool):
            if not audio_links:
                return

            additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS].extend(audio_links)
            additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS_TYPE].extend((getter_type for _ in range(len(audio_links))))
            additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SAVING_PATHS].extend((
                os.path.join(self.configurations["directories"]["media_dir"],
                             self.card_processor
                             .get_save_audio_name(
                                 word,
                                 "[{}] {}".format(getter_type, getter_name) if add_type_prefix else getter_name,
                                 str(i),
                                 self.dict_card_data))
                for i in range(len(audio_links))
            ))

        chosen_smth = False
        for labeled_frame in self.sound_inner_frame.winfo_children():
            for audio_frame in labeled_frame.winfo_children():
                if audio_frame.boolvar.get():
                    typed_audio_getter_name, audio_getter_type, audio = audio_frame.audio_data
                    chosen_smth = True
                    add_audio_data_to_card(getter_name=typed_audio_getter_name,
                                           getter_type=audio_getter_type,
                                           audio_links=[audio],
                                           add_type_prefix=False)

        if not chosen_smth and (audio_autochoose_mode := self.configurations["app"]["audio_autochoose_mode"]) != "off":
            if audio_autochoose_mode in ("first_default_audio", "first_available_audio"):
                choosing_slice = 1
            elif audio_autochoose_mode in ("all_default_audios", "first_available_audio_source", "all"):
                choosing_slice = 999
            else:
                raise NotImplementedError(f"Unknown audio autochoose mode: {audio_autochoose_mode}")

            audio_getter_type = self.configurations["scrappers"]["audio"]["type"]
            if (web_audios := self.dict_card_data.get(FIELDS.audio_links, [])):
                add_audio_data_to_card(getter_name=self.typed_word_parser_name,
                                       getter_type=parser_types.WEB,
                                       audio_links=web_audios[:choosing_slice],
                                       add_type_prefix=False)

            if self.audio_getter is not None and (audio_autochoose_mode == "all" or not web_audios and audio_autochoose_mode in ("first_available_audio", "first_available_audio_source")):
                if audio_getter_type in (parser_types.WEB, parser_types.LOCAL):
                    audio_data_pack = \
                        self.external_audio_generator.get(word=word,
                                                          card_data=self.dict_card_data,
                                                          batch_size=choosing_slice)
                    if audio_data_pack is not None:
                        ((audio_links, additional_info), error_message) = audio_data_pack
                        add_audio_data_to_card(getter_name=self.audio_getter.name,
                                               getter_type=audio_getter_type,
                                               audio_links=audio_links,
                                               add_type_prefix=True)
                elif audio_getter_type == parser_types.CHAIN:
                    audio_data_pack = self.external_audio_generator.get(word=word,
                                                                        card_data=self.dict_card_data,
                                                                        batch_size=choosing_slice)
                    if audio_data_pack is not None:
                        audio_gen = (i for i in audio_data_pack)
                        if audio_autochoose_mode in ("first_available_audio", "first_available_audio_source"):
                            ((getter_name, getter_type), ((audio_links, additional_info), error_message)) = next(audio_gen)
                            add_audio_data_to_card(
                                getter_name=f"extern_{getter_name}",
                                getter_type=getter_type,
                                audio_links=audio_links[:choosing_slice],
                                add_type_prefix=False
                            )
                        elif audio_autochoose_mode == "all":
                            for ((getter_name, getter_type), ((audio_links, additional_info), error_message)) in audio_gen:
                                add_audio_data_to_card(
                                    getter_name=f"extern_{getter_name}",
                                    getter_type=getter_type,
                                    audio_links=audio_links,
                                    add_type_prefix=False
                                )
                        else:
                            raise NotImplementedError(f"Unreachable audio_autochoose_mode: {audio_autochoose_mode}")
                else:
                    raise NotImplementedError(f"Unknown audio getter type: {audio_getter_type}")

        if (hierarchical_prefix := self.tag_prefix_field.get().strip()):
            additional[SavedDataDeck.HIERARCHICAL_PREFIX] = hierarchical_prefix

        if additional:
            self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA] = additional

        self.saved_cards_data.append(status=CardStatus.ADD, card_data=self.dict_card_data)
        if not self.deck.get_n_cards_left():
            self.deck.append(Card(self.dict_card_data))
        self.refresh()
    
    @error_handler(show_exception_logs)
    def skip_command(self):
        if self.deck.get_n_cards_left():
            self.saved_cards_data.append(CardStatus.SKIP)
        self.refresh()

    @error_handler(show_exception_logs)
    def replace_decks_pointers(self, n: int):
        self.saved_cards_data.move(min(n, self.deck.get_n_cards_left()))
        self.deck.move(n - 1)
        self.refresh()
    
    @error_handler(show_exception_logs)
    def open_anki_browser(self):
        @error_handler(self.show_exception_logs)
        def invoke(action, **params):
            def request_anki(action, **params):
                return {'action': action, 'params': params, 'version': 6}
            import requests

            request_json = json.dumps(request_anki(action, **params)).encode('utf-8')
            try:
                res = requests.get("http://localhost:8765", data=request_json, timeout=1)
                res.raise_for_status()
            except requests.ConnectionError:
                messagebox.showerror(title="Anki",
                                     message=self.lang_pack.request_anki_connection_error_message)
                return
            except requests.RequestException as e:
                messagebox.showerror(title="Anki",
                                     message=f"{self.lang_pack.request_anki_general_request_error_message_prefix}: {e}")
                return

            response = res.json()
            if response['error'] is not None:
                messagebox.showerror(title="Anki", message=response['error'])
            return response['result']

        word = self.word_text.get(1.0, "end").strip()
        query_list = []
        if self.configurations["anki"]["deck"]:
            query_list.append("deck:\"{}\"".format(self.configurations["anki"]["deck"]))
        if self.configurations["anki"]["field"]:
            query_list.append("\"{}:*{}*\"".format(self.configurations["anki"]["field"],
                                                   word))
        else:
            query_list.append(f"*{word}*")
        result_query = " and ".join(query_list)
        invoke('guiBrowse', query=result_query)
    
    @error_handler(show_exception_logs)
    def bury_command(self):
        self.saved_cards_data.append(status=CardStatus.BURY, card_data=self.dict_card_data)
        self.refresh()

    def add_sentence_field(self, source: str, sentence: str):
        OPTIMAL_TEXT_HEIGHT = 80

        next_index = len(self.sentence_texts) + 1

        if self.text_widgets_frame.last_source != source:
            self.text_widgets_frame.last_source = source
            self.text_widgets_frame.source_display_frame = LabelFrame(self.text_widgets_frame,
                                                                               text=source,
                                                                               fg=self.theme.button_cfg.get("foreground"),
                                                                               **self.theme.frame_cfg)
            self.text_widgets_sf.bind_scroll_wheel(self.text_widgets_frame.source_display_frame)
            self.text_widgets_frame.source_display_frame.grid_columnconfigure(0, weight=1)
            self.text_widgets_frame.source_display_frame.pack(side="top", fill="both")

        choose_frame = self.Frame(self.text_widgets_frame.source_display_frame, height=OPTIMAL_TEXT_HEIGHT)
        choose_frame.grid(row=len(self.sentence_texts), column=0, sticky="we", pady=(0, self.text_pady))
        self.text_widgets_sf.bind_scroll_wheel(choose_frame)
        
        choose_frame.grid_columnconfigure(0, weight=1)
        choose_frame.grid_rowconfigure(0, weight=1)
        choose_frame.grid_propagate(False)

        sentence_text = self.Text(
            choose_frame,
            placeholder=f"{self.lang_pack.sentence_text_placeholder_prefix} {next_index}")
        sentence_text.insert(1.0, sentence)
        sentence_text.grid(row=0, column=0, sticky="we")
        self.text_widgets_sf.bind_scroll_wheel(sentence_text)

        choose_button = self.Button(choose_frame,
                                                 text=f"{next_index}",
                                                 command=lambda x=len(self.sentence_texts): self.choose_sentence(x),
                                                 width=3)
        choose_button.grid(row=0, column=1, sticky="ns")
        self.text_widgets_sf.bind_scroll_wheel(choose_button)

        self.sentence_texts.append(sentence_text)

    @error_handler(show_exception_logs)
    def add_external_sentences(self) -> None:
        sentence_data = ([], "")

        def schedule_sentence_fetcher():
            nonlocal sentence_data

            try:
                sentence_data = self.external_sentence_fetcher.get(
                    word=self.word,
                    card_data=self.dict_card_data,
                    batch_size=self.configurations["extern_sentence_placer"]["n_sentences_per_batch"])
                if sentence_data is None:
                    sentence_data = ([], "")
                    return
            except StopIteration:
                sentence_data = ([], "")
                return

        def wait_sentence_fetcher(thread: Thread):
            if thread.is_alive():
                self.after(100, lambda: wait_sentence_fetcher(thread))
            else:
                sent_batch, error_message = sentence_data
                sentence_parser_type = self.configurations["scrappers"]["sentence"]["type"]
                if sentence_parser_type == parser_types.WEB:
                    typed_sentence_parser = self.sentence_parser.name
                elif sentence_parser_type == parser_types.CHAIN:
                    typed_sentence_parser = "[{}] {}".format(sentence_parser_type, self.sentence_parser.name)
                else:
                    raise NotImplementedError(f"Unknown sentence parser type: {sentence_parser_type}")

                for sentence in sent_batch:
                    self.add_sentence_field(
                        source=f"{typed_sentence_parser}: {self.word}",
                        sentence=sentence)

                if error_message:
                    messagebox.showerror(title=f"[{sentence_parser_type}] {self.sentence_parser.name}",
                                         message=error_message)

        place_sentences_thread = Thread(target=schedule_sentence_fetcher)
        place_sentences_thread.start()
        wait_sentence_fetcher(place_sentences_thread)

    @error_handler(show_exception_logs)
    def refresh(self) -> bool:
        @error_handler(self.show_exception_logs)
        def fill_additional_dict_data(widget: Text, text: str):
            widget["state"] = "normal"
            widget.clear()
            widget.insert(1.0, text)
            widget["state"] = "disabled"

        self.sentence_buffer = []
        self.dict_card_data = self.deck.get_card().to_dict()
        self.card_processor.process_card(self.dict_card_data)

        for child in self.sound_inner_frame.winfo_children():
            child.destroy()
        # self.sound_inner_frame = self.sound_sf.display_widget(self.Frame, fit_width=True)
        self.sound_inner_frame.last_source = None
        self.sound_inner_frame.source_display_frame = None

        self.sentence_texts.clear()
        for child in self.text_widgets_frame.winfo_children():
            child.destroy()
        # self.text_widgets_frame = self.text_widgets_sf.display_widget(self.Frame, fit_width=True)
        # self.text_widgets_sf.bind_scroll_wheel(self.text_widgets_frame)
        # self.text_widgets_frame.grid_columnconfigure(0, weight=1)
        self.text_widgets_frame.last_source = None
        self.text_widgets_frame.source_display_frame = None

        self.prev_button["state"] = "normal" if self.deck.get_pointer_position() != self.deck.get_starting_position() + 1 \
                                             else "disabled"

        self.title(f"{self.lang_pack.main_window_title_prefix}: {self.deck.get_n_cards_left()}")

        self.word_text.focus()
        self.word_text.clear()
        if (word_data := self.dict_card_data.get(FIELDS.word, "")):
            self.word_text.insert(1.0, word_data)

        fill_additional_dict_data(self.dict_tags_field, Card.get_str_dict_tags(self.dict_card_data))
        fill_additional_dict_data(self.special_field, " ".join(self.dict_card_data.get(FIELDS.special, [])))

        self.definition_text.clear()
        self.definition_text.insert(1.0, self.dict_card_data.get(FIELDS.definition, ""))
        self.definition_text.fill_placeholder()

        if (audio_sources := self.dict_card_data.get(FIELDS.audio_links)) is not None and audio_sources:
            additional_info = ("" for _ in range(len(audio_sources)))
            parser_results = [(("", parser_types.WEB), ((audio_sources, additional_info), ""))]
            self.display_audio_on_frame(word=self.word, parser_results=parser_results, show_errors=False)

        if not self.dict_card_data:
            # normal
            self.find_image_button["text"] = self.lang_pack.find_image_button_normal_text
            return False

        if self.dict_card_data.get(FIELDS.img_links, []):
            self.find_image_button["text"] = self.lang_pack.find_image_button_normal_text + \
                                             self.lang_pack.find_image_button_image_link_encountered_postfix
        else:
            self.find_image_button["text"] = self.lang_pack.find_image_button_normal_text

        self.already_waiting = False
        self.tried_to_display_audio_getters_on_refresh = False
        self.last_refresh_call_time = time.time()

        def display_audio_getters_results_on_refresh():
            if self.tried_to_display_audio_getters_on_refresh:
                return

            if (time.time() - self.last_refresh_call_time) > 0.1:
                self.display_audio_getter_results(show_errors=False)
                self.tried_to_display_audio_getters_on_refresh = True
                self.already_waiting = False
            else:
                if self.already_waiting:
                    return

                dict_sentences = self.dict_card_data.get(FIELDS.sentences, [""])
                for sentence in dict_sentences:
                    self.add_sentence_field(source="", sentence=sentence)

                self.after(300, display_audio_getters_results_on_refresh)
                self.already_waiting = True
        
        if word_data:
            display_audio_getters_results_on_refresh()
        return True
    
    @error_handler(show_exception_logs)
    def start_image_search(self):
        @error_handler(self.show_exception_logs)
        def connect_images_to_card(instance: ImageSearch):
            nonlocal word

            additional = self.dict_card_data.get(SavedDataDeck.ADDITIONAL_DATA)
            if additional is not None and \
                    (paths := additional.get(self.saved_cards_data.SAVED_IMAGES_PATHS)) is not None:
                for path in paths:
                    if os.path.isfile(path):
                        os.remove(path)

            names: list[str] = []
            for i in range(len(instance.working_state)):
                if instance.working_state[i]:
                    saving_name = "{}/{}"\
                        .format(self.configurations["directories"]["media_dir"],
                                self.card_processor
                                .get_save_image_name(word,
                                                     instance.images_source[i],
                                                     self.configurations["scrappers"]["image"]["name"],
                                                     self.dict_card_data))
                    instance.preprocess_image(img=instance.saving_images[i],
                                              width=self.configurations["image_search"]["saving_image_width"],
                                              height=self.configurations["image_search"]["saving_image_height"])\
                            .save(saving_name)
                    names.append(saving_name)

            if names:
                if additional is None:
                    self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA] = {}
                self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA][self.saved_cards_data.SAVED_IMAGES_PATHS] = names

            x, y = instance.geometry().split(sep="+")[1:]
            self.configurations["image_search"]["starting_position"] = f"+{x}+{y}"

        word = self.word
        button_pady = button_padx = 10
        height_lim = self.winfo_height() * 7 // 8
        image_finder = ImageSearch(master=self,
                                   main_params=self.theme.toplevel_cfg,
                                   search_term=word,
                                   saving_dir=self.configurations["directories"]["media_dir"],
                                   url_scrapper=self.image_parser.get_image_links,
                                   init_urls=self.dict_card_data
                                                 .get(FIELDS.img_links, []),
                                   local_images=self.dict_card_data
                                                    .get(SavedDataDeck.ADDITIONAL_DATA, {})
                                                    .get(self.saved_cards_data.SAVED_IMAGES_PATHS, []),
                                   headers=self.headers,
                                   timeout=self.configurations["image_search"]["timeout"],
                                   max_request_tries=self.configurations["image_search"]["max_request_tries"],
                                   n_images_in_row=self.configurations["image_search"]["n_images_in_row"],
                                   n_rows=self.configurations["image_search"]["n_rows"],
                                   show_image_width=self.configurations["image_search"]["show_image_width"],
                                   show_image_height=self.configurations["image_search"]["show_image_height"],
                                   button_padx=button_padx,
                                   button_pady=button_pady,
                                   window_height_limit=height_lim,
                                   on_closing_action=connect_images_to_card,
                                   command_button_params=self.theme.button_cfg,
                                   entry_params=self.theme.entry_cfg,
                                   frame_params=self.theme.frame_cfg,
                                   lang_pack=self.lang_pack)
        image_finder.grab_set()
        image_finder.geometry(self.configurations["image_search"]["starting_position"])
        image_finder.start()


if __name__ == "__main__":
    root = App()
    root.mainloop()
