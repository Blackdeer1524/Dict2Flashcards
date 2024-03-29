import copy
import itertools
import json
import os
import re
import time
import webbrowser
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from threading import Thread
from tkinter import (BooleanVar, Button, Checkbutton, Frame, Label, LabelFrame,
                     Menu, PanedWindow, Toplevel, messagebox)
from tkinter.filedialog import askdirectory, askopenfilename
from tkinter.font import Font
from tkinter.ttk import Scrollbar, Treeview
from typing import Callable, Iterable, Literal

import requests
from playsound import playsound
from tkinterdnd2 import Tk

from .app_utils.audio_utils import AudioDownloader
from .app_utils.cards import Card
from .app_utils.decks import CardStatus, Deck, FrozenDict, SavedDataDeck
from .app_utils.error_handling import create_exception_message, error_handler
from .app_utils.global_bindings import Binder
from .app_utils.image_utils import ImageSearch
from .app_utils.query_language.exceptions import QueryLangException
from .app_utils.query_language.query_processing import get_card_filter
from .app_utils.string_utils import remove_special_chars
from .app_utils.widgets import EntryWithPlaceholder as Entry
from .app_utils.widgets import ScrolledFrame
from .app_utils.widgets import TextWithPlaceholder as Text
from .app_utils.window_utils import get_option_menu, spawn_window_in_center
from .consts import CardFields, ParserType, TypedParserName
from .consts.paths import *
from .plugins_loading.chaining import (ChainDataStorage, PossibleChainTypes, CHAIN_INFO_T)
from .plugins_loading.containers import LanguagePackageContainer
from .plugins_loading.factory import loaded_plugins
from .plugins_loading.wrappers import ExternalDataGenerator, GeneratorReturn
from .plugins_management.config_management import Config, LoadableConfig
from .plugins_management.parsers_return_types import (
    AUDIO_DATA_T, AUDIO_SCRAPPER_RETURN_T, IMAGE_DATA_T,
    IMAGE_SCRAPPER_RETURN_T, SENTENCE_DATA_T, SENTENCE_SCRAPPER_RETURN_T)


class App(Tk):
    @dataclass(slots=True, frozen=True)
    class AudioGetterInfo:
        parser_info: TypedParserName
        fetching_word: str

    def __init__(self, *args, **kwargs) -> None:
        super(App, self).__init__(*args, **kwargs)

        if not os.path.exists(f"{WORDS_DIR}/custom.json"):
            with open(f"{WORDS_DIR}/custom.json", "w", encoding="UTF-8") as custom_file:
                json.dump([], custom_file)
        
        self.configurations, self.lang_pack, error_code = self.load_conf_file()
        if error_code:
            self.destroy()
            return
        self.configurations.save()

        self.theme = loaded_plugins.get_theme(self.configurations["app"]["theme"])
        self.configure(**self.theme.root_cfg)
        self.Label = partial(Label, **self.theme.label_cfg)
        self.Button = partial(Button, **self.theme.button_cfg)
        self.Text = partial(Text, **self.theme.text_cfg)
        self.Entry = partial(Entry, **self.theme.entry_cfg)
        self.Toplevel = partial(Toplevel, **self.theme.toplevel_cfg)
        self.Frame = partial(Frame, **self.theme.frame_cfg)
        self.get_option_menu = partial(get_option_menu,
                                       option_menu_cfg=self.theme.option_menu_cfg,
                                       option_submenu_cfg=self.theme.option_submenus_cfg)
        
        self.history = App.load_history_file()
        self.chaining_data = self.load_chaining_data()
        self.chaining_data.save()

        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'}
        self.session_start = datetime.now()

        if SYSTEM == "Windows":
            self.str_session_start = self.session_start.strftime("%Y-%m-%d %H-%M-%S")
        else:
            self.str_session_start = self.session_start.strftime("%Y-%m-%d %H:%M:%S")

        if not self.history.get(self.configurations["directories"]["last_open_file"]):
            self.history[self.configurations["directories"]["last_open_file"]] = 0

        wp_name = self.configurations["scrappers"]["word"]["name"]
        wp_type = self.configurations["scrappers"]["word"]["type"]
        self.card_generator = loaded_plugins.get_card_generator(
            parser_info=TypedParserName(parser_t=ParserType(wp_type), 
                                        name=wp_name),
            chain_data=self.chaining_data["word_parsers"])
        self.deck = Deck(deck_path=self.configurations["directories"]["last_open_file"],
                         current_deck_pointer=self.history[self.configurations["directories"]["last_open_file"]],
                         card_generator=self.card_generator)

        self.card_processor = loaded_plugins.get_card_processor(self.configurations["deck"]["card_processor"])
        
        self.current_card_parser_name = ""
        self.dict_card_data: dict = {}

        sentence_parser = loaded_plugins.get_sentence_parser(
            parser_info=TypedParserName(parser_t=ParserType(self.configurations["scrappers"]["sentence"]["type"]),
                                        name=self.configurations["scrappers"]["sentence"]["name"]),
            chain_data=self.chaining_data["sentence_parsers"]
        )
        self.external_sentence_fetcher: ExternalDataGenerator[list[str]] = ExternalDataGenerator(
            data_generator=sentence_parser)

        image_parser = loaded_plugins.get_image_parser(
            parser_info=TypedParserName(parser_t=ParserType(self.configurations["scrappers"]["image"]["type"]),
                                        name=self.configurations["scrappers"]["image"]["name"]),
            chain_data=self.chaining_data["image_parsers"]
        )
        self.external_image_generator: ExternalDataGenerator[list[str]] = ExternalDataGenerator(
            data_generator=image_parser
        )

        if (self.configurations["scrappers"]["audio"]["name"]):
            if self.configurations["scrappers"]["audio"]["type"] in (ParserType.web,
                                                                     ParserType.local,
                                                                     ParserType.chain):
                audio_getter = loaded_plugins.get_audio_getter(
                    parser_info=TypedParserName(parser_t=ParserType(self.configurations["scrappers"]["audio"]["type"]),
                                                name=self.configurations["scrappers"]["audio"]["name"]),
                    chain_data=self.chaining_data["audio_getters"]
                )
                self.external_audio_generator: ExternalDataGenerator[list[tuple[str, str]]] | None = ExternalDataGenerator(data_generator=audio_getter)
            else:
                self.configurations["scrappers"]["audio"]["type"] = "default"
                self.configurations["scrappers"]["audio"]["name"] = ""
                self.external_audio_generator = None
        else:
            self.external_audio_generator = None

        self.saved_cards_data = SavedDataDeck()
        self.deck_saver = loaded_plugins.get_deck_saving_formats(self.configurations["deck"]["saving_format"])
        self.audio_saver = loaded_plugins.get_deck_saving_formats("json_deck_audio")
        self.buried_saver = loaded_plugins.get_deck_saving_formats("json_deck_cards")

        self.text_padx = 5
        self.text_pady = 5

        for i in range(6):
            self.grid_columnconfigure(i, weight=1)

        additional_search_frame = self.Frame(self)
        additional_search_frame.grid_propagate(False)
        additional_search_frame.columnconfigure(0, weight=1)
        additional_search_frame.columnconfigure(1, weight=1)
        additional_search_frame.grid(row=0, column=0, sticky="news", columnspan=3,
                                     padx=(self.text_padx, 0), pady=(self.text_pady, 0))

        self.anki_button = self.Button(additional_search_frame,
                                       text=self.lang_pack.anki_button_text,
                                       command=lambda: self.open_anki_browser(self.word_text.get(1.0, "end").strip()))
        self.anki_button.grid(row=0, column=0, sticky="news")

        self.browse_button = self.Button(additional_search_frame,
                                         text=self.lang_pack.browse_button_text,
                                         command=lambda: self.web_search_command(self.word))
        self.browse_button.grid(row=0, column=1, sticky="news")

        self.word_parser_option_menu = self.get_option_menu(
            self,
            init_text=self.card_generator.parser_info.full_name,
            values=[ParserType.merge_into_full_name(ParserType.web, item) for item in loaded_plugins.web_word_parsers.loaded] +
                   [ParserType.merge_into_full_name(ParserType.local, item) for item in loaded_plugins.local_word_parsers.loaded] +
                   [ParserType.merge_into_full_name(ParserType.chain, item) for item in self.chaining_data["word_parsers"]],
            command=lambda typed_parser: self.change_word_parser(typed_parser))
        self.word_parser_option_menu.grid(row=0, column=3, columnspan=4, sticky="news",
                                          pady=(self.text_pady, 0))

        self.configure_word_parser_button = self.Button(self,
                                                        text="</>",
                                                        command=lambda: self.call_configuration_window(
                                                            plugin_name=self.card_generator.parser_info.name,
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

        self.definition_text = self.Text(self, placeholder=self.lang_pack.definition_text_placeholder, height=4)
        self.definition_text.grid(row=3, column=0, columnspan=8, sticky="news",
                                  padx=self.text_padx, pady=(self.text_pady, 0))

        self.dict_tags_field = self.Text(self, relief="ridge", state="disabled", height=2)
        self.dict_tags_field.grid(row=4, column=0, columnspan=8, sticky="news",
                                  padx=self.text_padx, pady=self.text_pady)

        def save_images_paths(paths: list[str]):
            if self.dict_card_data.get(SavedDataDeck.ADDITIONAL_DATA) is None:
                self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA] = {SavedDataDeck.SAVED_IMAGES_PATHS: []}
            elif self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA].get(SavedDataDeck.SAVED_IMAGES_PATHS) is None:
                self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.SAVED_IMAGES_PATHS] = []

            saving_dst = self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.SAVED_IMAGES_PATHS]
            saving_dst.clear()
            saving_dst.extend(paths)

        self.fetch_images_button = self.Button(
            self,
            text=self.lang_pack.fetch_images_button_normal_text,
            command=lambda: self.start_image_search(
                word=self.word_text.get(1.0, "end").strip(),
                card_data=self.dict_card_data,
                init_urls=self.dict_card_data.get(CardFields.img_links),
                init_local_images_paths=self.dict_card_data.get(SavedDataDeck.ADDITIONAL_DATA, {})
                    .get(self.saved_cards_data.SAVED_IMAGES_PATHS, []),
                image_path_saving_method=save_images_paths
            )
        )
        self.fetch_images_button.grid(row=5, column=0, columnspan=3, sticky="news",
                                      padx=(self.text_padx, 0), pady=(0, self.text_pady))

        typed_image_parser_name = self.external_image_generator.parser_info.full_name
        self.image_parsers_option_menu = self.get_option_menu(
            self,
            init_text=typed_image_parser_name,
            values=[ParserType.merge_into_full_name(ParserType.web, name) for name in loaded_plugins.web_image_parsers.loaded] +
                   [ParserType.merge_into_full_name(ParserType.chain, name) for name in self.chaining_data["image_parsers"]],
            command=lambda parser_name: self.change_image_parser(parser_name))
        self.image_parsers_option_menu.grid(row=5, column=3, columnspan=4, sticky="news",
                                           padx=0, pady=(0, self.text_pady))

        self.configure_image_parser_button = self.Button(
            self,
            text="</>",
            command=lambda: self.call_configuration_window(
                plugin_name=self.external_image_generator.parser_info.full_name,
                plugin_config=self.external_image_generator.data_generator.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save()))
        self.configure_image_parser_button.grid(row=5, column=7, sticky="news",
                                                padx=(0, self.text_padx), pady=(0, self.text_pady))

        typed_audio_getter = "default" if self.external_audio_generator is None \
            else self.external_audio_generator.parser_info.full_name

        def display_audio_getter_results_on_button_click():
            self.fill_search_fields()
            self.waiting_for_audio_display = True
            self.display_audio_getter_results(
                word=self.audio_search_entry.get(),
                card_data=self.dict_card_data,
                show_errors=True,
                audio_sf=self.audio_sf,
                audio_inner_frame=self.audio_inner_frame
            )

        self.fetch_audio_data_button = self.Button(self,
                                                   text=self.lang_pack.fetch_audio_data_button_text,
                                                   command=display_audio_getter_results_on_button_click)

        if typed_audio_getter == "default":
            self.fetch_audio_data_button["state"] = "disabled"

        self.fetch_audio_data_button.grid(row=6, column=0, columnspan=3,
                                          sticky="news",
                                          padx=(self.text_padx, 0), pady=0)

        self.audio_getter_option_menu = self.get_option_menu(
            self,
            init_text=typed_audio_getter,
            values=["default"] +
                   [ParserType.merge_into_full_name(ParserType.web, item) for item in loaded_plugins.web_audio_getters.loaded] +
                   [ParserType.merge_into_full_name(ParserType.local, item) for item in loaded_plugins.local_audio_getters.loaded] +
                   [ParserType.merge_into_full_name(ParserType.chain, item) for item in self.chaining_data["audio_getters"]],
            command=lambda parser_name: self.change_audio_getter(parser_name))
        self.audio_getter_option_menu.grid(row=6, column=3, columnspan=4, sticky="news",
                                           padx=0, pady=0)

        self.configure_audio_getter_button = self.Button(self, text="</>")

        if self.external_audio_generator is not None:
            cmd = lambda: self.call_configuration_window(plugin_name=typed_audio_getter,
                                                         plugin_config=self.external_audio_generator.data_generator.config,
                                                         plugin_load_function=lambda conf: conf.load(),
                                                         saving_action=lambda conf: conf.save())
            self.configure_audio_getter_button["command"] = cmd
        else:
            self.configure_audio_getter_button["state"] = "disabled"

        self.configure_audio_getter_button.grid(row=6, column=7, sticky="news",
                                                padx=(0, self.text_padx), pady=0)

        self.audio_search_entry = self.Entry(self, placeholder=self.lang_pack.audio_search_entry_text)
        self.audio_search_entry.grid(row=7, column=0, columnspan=8, sticky="news",
                                     padx=self.text_padx, pady=0)

        self.audio_sf = ScrolledFrame(self, scrollbars="vertical",
                                      canvas_bg=self.theme.frame_cfg.get("bg"),
                                      height=110)

        self.audio_sf.grid(row=8, column=0, columnspan=8, sticky="news",
                           padx=self.text_padx, pady=(0, self.text_pady))

        self.audio_inner_frame = self.audio_sf.display_widget(self.Frame, fit_width=True)
        self.audio_sf.bind_scroll_wheel(self.audio_inner_frame)
        self.audio_inner_frame.last_getter_label = None
        self.audio_inner_frame.source_display_frame = None

        a = self.Frame(self)
        a.grid(row=9, column=0, columnspan=8, padx=self.text_padx, pady=0, sticky="news")

        for i in range(4):
            a.columnconfigure(i, weight=1)

        self.prev_button = self.Button(a,
                                       text="<",
                                       command=lambda: self.move_decks_pointers(-1),
                                       font=Font(weight="bold"))
        self.prev_button.grid(row=0, column=0, sticky="news")

        self.bury_button = self.Button(a,
                                       text=self.lang_pack.bury_button_text,
                                       command=self.bury_command)
        self.bury_button.grid(row=0, column=1, sticky="news")

        self.skip_button = self.Button(a,
                                       text=">",
                                       command=lambda: self.move_decks_pointers(1),
                                       font=Font(weight="bold"))
        self.skip_button.grid(row=0, column=2, sticky="news")

        self.skip_all_button = self.Button(a,
                                           text=">>>",
                                           command=lambda: self.move_decks_pointers(self.deck.get_n_cards_left()),
                                           font=Font(weight="bold"))
        self.skip_all_button.grid(row=0, column=3, sticky="news")

        @error_handler(self.show_exception_logs)
        def fetch_external_sentences() -> None:
            results: list[GeneratorReturn[list[str]]] | None = None

            self.fill_search_fields()

            def schedule_sentence_fetcher():
                nonlocal results
                results = self.external_sentence_fetcher.get(
                    word=self.sentence_search_entry.get(),
                    card_data=self.dict_card_data,
                    batch_size=self.configurations["extern_sentence_placer"]["n_sentences_per_batch"])

            def wait_sentence_fetcher(thread: Thread) -> None:
                if thread.is_alive():
                    self.after(100, lambda: wait_sentence_fetcher(thread))
                    return

                nonlocal results
                if results is None:
                    return

                for generator_result in results:
                    for sentence in generator_result.result:
                        self.add_sentence_field(
                                source=f"{generator_result.parser_info.full_name}: {self.sentence_search_entry.get()}",
                                sentence=sentence,
                                text_widgets_frame=self.text_widgets_frame,
                                text_widgets_sf=self.text_widgets_sf,
                                sentence_text_widgets_list=self.sentence_texts,
                                choose_sentence_action=self.choose_sentence)

                    if generator_result.error_message:
                        messagebox.showerror(
                            title=f"{generator_result.parser_info.full_name}",
                            message=generator_result.error_message)

            place_sentences_thread = Thread(target=schedule_sentence_fetcher)
            place_sentences_thread.start()
            wait_sentence_fetcher(place_sentences_thread)

        self.fetch_ext_sentences_button = self.Button(self,
                                                      text=self.lang_pack.fetch_ext_sentences_button,
                                                      command=fetch_external_sentences)
        self.fetch_ext_sentences_button.grid(row=10, column=0, columnspan=3, sticky="news",
                                             padx=(self.text_padx, 0), pady=(self.text_pady, 0))

        typed_sentence_parser_name = self.external_sentence_fetcher.parser_info.full_name
        self.sentence_parsers_option_menu = self.get_option_menu(
            self,
            init_text=typed_sentence_parser_name,
            values=[ParserType.merge_into_full_name(ParserType.web, name) for name in loaded_plugins.web_sent_parsers.loaded] +
                   [ParserType.merge_into_full_name(ParserType.chain, name) for name in self.chaining_data["sentence_parsers"]],
            command=lambda parser_name: self.change_sentence_parser(parser_name))
        self.sentence_parsers_option_menu.grid(row=10, column=3, columnspan=4, sticky="news",
                                              pady=(self.text_pady, 0))

        self.configure_sentence_parser_button = self.Button(
            self,
            text="</>",
            command=lambda: self.call_configuration_window(
                plugin_name=self.external_sentence_fetcher.parser_info.full_name,
                plugin_config=self.external_sentence_fetcher.data_generator.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save()),
            width=6)
        self.configure_sentence_parser_button.grid(row=10, column=7, sticky="news",
                                                   padx=(0, self.text_padx), pady=(self.text_pady, 0))
        # ======
        self.sentence_search_entry = self.Entry(self, placeholder=self.lang_pack.sentence_search_entry_text)
        self.sentence_search_entry.grid(row=11, column=0, columnspan=8, sticky="news",
                                        padx=self.text_padx, pady=(0, 0))

        self.sentence_texts: list[Text] = []
        self.choosing_buttons: list[Button] = []

        self.text_widgets_sf = ScrolledFrame(self, scrollbars="vertical",
                                             canvas_bg=self.theme.frame_cfg.get("bg"))
        
        self.grid_rowconfigure(12, weight=1)
        self.text_widgets_sf.grid(row=12, column=0, columnspan=7, sticky="news",
                                  padx=(self.text_padx, 0), pady=(0, self.text_pady))
        self.save_and_refresh_button = self.Button(text="=>",
                                                   command=self.save_and_refresh)
        self.save_and_refresh_button.grid(row=12, column=7, sticky="news",
                                          padx=(0, self.text_padx), pady=(0, self.text_pady))

        self.text_widgets_frame = self.text_widgets_sf.display_widget(self.Frame, fit_width=True)
        self.text_widgets_sf.bind_scroll_wheel(self.text_widgets_frame)
        self.text_widgets_frame.last_getter_label = None
        self.text_widgets_frame.source_display_frame = None

        self.user_tags_field = self.Entry(self, placeholder=self.lang_pack.user_tags_field_placeholder)
        self.user_tags_field.fill_placeholder()
        self.user_tags_field.grid(row=13, column=0, columnspan=6, sticky="news",
                                  padx=(self.text_padx, 0), pady=(0, self.text_pady))

        self.tag_prefix_field = self.Entry(self, justify="center", width=8)
        self.tag_prefix_field.insert(0, self.configurations["deck"]["tags_hierarchical_pref"])
        self.tag_prefix_field.grid(row=13, column=7, columnspan=1, sticky="news",
                                   padx=(0, self.text_padx), pady=(0, self.text_pady))

        main_menu = Menu(self)
        file_menu = Menu(main_menu, tearoff=0)
        file_menu.add_command(label=self.lang_pack.create_file_menu_label, command=self.create_file_dialog)
        file_menu.add_command(label=self.lang_pack.open_file_menu_label, command=self.change_file)
        file_menu.add_command(label=self.lang_pack.save_files_menu_label, command=self.save_button)
        file_menu.add_separator()

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
            theme_option_menu.grid(row=0, column=1, columnspan=2, sticky="news")

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
            language_option_menu.grid(row=1, column=1, columnspan=2, sticky="news")

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
            image_search_configuration_button.grid(row=2, column=1, columnspan=2, sticky="news")

            web_audio_downloader_configuration_label = self.Label(
                settings_window,
                text=self.lang_pack.setting_web_audio_downloader_configuration_label_text)
            web_audio_downloader_configuration_label.grid(row=3, column=0, sticky="news")

            web_audio_downloader_conf_validation_scheme = copy.deepcopy(
                self.configurations.validation_scheme["web_audio_downloader"])
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
            web_audio_downloader_configuration_button.grid(row=3, column=1, columnspan=2, sticky="news")

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
            extern_audio_placer_configuration_button.grid(row=4, column=1, columnspan=2, sticky="news")

            extern_sentence_placer_configuration_label = self.Label(
                settings_window,
                text=self.lang_pack.settings_extern_sentence_placer_configuration_label)
            extern_sentence_placer_configuration_label.grid(row=5, column=0, sticky="news")

            extern_sentence_placer_conf_validation_scheme = copy.deepcopy(
                self.configurations.validation_scheme["extern_sentence_placer"])
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
            extern_sentence_placer_configuration_button.grid(row=5, column=1, columnspan=2, sticky="news")

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
            card_processor_option.grid(row=6, column=1, columnspan=2, sticky="news")

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

            format_processor_configuration_button = self.Button(
                settings_window,
                text="</>",
                command=lambda: self.call_configuration_window(
                    plugin_name=self.lang_pack.settings_format_processor_configuration_label,
                    plugin_config=self.deck_saver.config,
                    plugin_load_function=lambda conf: None,
                    saving_action=lambda config: self.deck_saver.config.save())
            )
            format_processor_configuration_button.grid(row=7, column=2, sticky="news")

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
            audio_autochoose_option_menu.grid(row=8, column=1, columnspan=2, sticky="news")

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
            configure_anki_button.grid(row=9, column=0, columnspan=3, sticky="news")

            spawn_window_in_center(self, settings_window, desired_window_width=self.winfo_width())
            settings_window.resizable(False, False)
            settings_window.grab_set()
            settings_window.bind("<Escape>", lambda event: settings_window.destroy())
            settings_window.bind("<Return>", lambda event: settings_window.destroy())

        file_menu.add_command(label=self.lang_pack.settings_menu_label, command=settings_dialog)
        file_menu.add_separator()

        help_menu = Menu(file_menu, tearoff=0)
        help_menu.add_command(label=self.lang_pack.hotkeys_and_buttons_help_menu_label, command=self.help_command)
        help_menu.add_command(label=self.lang_pack.query_settings_language_label_text,
                              command=self.get_query_language_help)
        file_menu.add_cascade(label=self.lang_pack.help_master_menu_label, menu=help_menu)

        file_menu.add_separator()
        file_menu.add_command(label=self.lang_pack.download_audio_menu_label,
                              command=partial(self.download_audio, choose_file=True))
        file_menu.add_separator()
        file_menu.add_command(label=self.lang_pack.change_media_folder_menu_label, command=self.change_media_dir)
        main_menu.add_cascade(label=self.lang_pack.file_master_menu_label, menu=file_menu)

        main_menu.add_command(label=self.lang_pack.add_card_menu_label, command=self.add_word_dialog)
        main_menu.add_command(label=self.lang_pack.search_inside_deck_menu_label, command=self.find_dialog)
        main_menu.add_command(label=self.lang_pack.added_cards_browser_menu_label, command=self.added_cards_browser)
        main_menu.add_command(label=self.lang_pack.statistics_menu_label, command=self.statistics_dialog)

        @error_handler(self.show_exception_logs)
        def chain_dialog():
            chain_type_window: Toplevel = self.Toplevel(self)
            chain_type_window.grid_columnconfigure(0, weight=1)
            chain_type_window.title(self.lang_pack.chain_management_menu_label)
            chain_type_window.bind("<Escape>", lambda event: chain_type_window.destroy())

            chaining_options = {self.lang_pack.chain_management_word_parsers_option: "word_parsers",
                                self.lang_pack.chain_management_sentence_parsers_option: "sentence_parsers",
                                self.lang_pack.chain_management_image_parsers_option: "image_parsers",
                                self.lang_pack.chain_management_audio_getters_option: "audio_getters"}

            @error_handler(self.show_exception_logs)
            def select_chain_type(picked_value: str) -> None:
                close_chain_type_selection_button["state"] = call_chain_building_button["state"] = "normal"
                existing_chains_treeview.delete(*existing_chains_treeview.get_children())
                for i, (name, chain_data) in enumerate(self.chaining_data[chaining_options[picked_value]].items()):
                    existing_chains_treeview.insert(parent="", index=i,
                                                    values=(name, "->".join((item.full_name for item in chain_data["chain"]))))

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
                        init_text=self.card_generator.parser_info.full_name,
                        values=[ParserType.merge_into_full_name(ParserType.web, item)   for item in loaded_plugins.web_word_parsers.loaded] +
                               [ParserType.merge_into_full_name(ParserType.local, item) for item in loaded_plugins.local_word_parsers.loaded] +
                               [ParserType.merge_into_full_name(ParserType.chain, item) for item in self.chaining_data["word_parsers"]],
                        command=lambda typed_parser: self.change_word_parser(typed_parser))
                    self.word_parser_option_menu.grid(row=0, column=3, columnspan=4, sticky="news",
                                                      pady=(self.text_pady, 0))

                elif chosen_parser_type == "sentence_parsers":
                    self.sentence_parsers_option_menu.destroy()
                    typed_sentence_parser_name = self.external_sentence_fetcher.parser_info.full_name
                    self.sentence_parsers_option_menu = self.get_option_menu(
                        self,
                        init_text=typed_sentence_parser_name,
                        values=[ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_sent_parsers.loaded] +
                               [ParserType.merge_into_full_name(ParserType.chain, name) for name in self.chaining_data["sentence_parsers"]],
                        command=lambda parser_name: self.change_sentence_parser(parser_name))
                    self.sentence_parsers_option_menu.grid(row=10, column=3, columnspan=4, sticky="news",
                                                          pady=(self.text_pady, 0))

                elif chosen_parser_type == "image_parsers":
                    self.image_parsers_option_menu.destroy()
                    typed_image_parser_name = self.external_image_generator.parser_info.full_name
                    self.image_parsers_option_menu = self.get_option_menu(
                        self,
                        init_text=typed_image_parser_name,
                        values=[ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_image_parsers.loaded] +
                               [ParserType.merge_into_full_name(ParserType.chain, name) for name in self.chaining_data["image_parsers"]],
                        command=lambda parser_name: self.change_image_parser(parser_name))
                    self.image_parsers_option_menu.grid(row=5, column=3, columnspan=4, sticky="news",
                                                       padx=0, pady=(0, self.text_pady))

                elif chosen_parser_type == "audio_getters":
                    self.audio_getter_option_menu.destroy()
                    self.audio_getter_option_menu = self.get_option_menu(
                        self,
                        init_text="default" if self.external_audio_generator is None else self.external_audio_generator.parser_info.full_name,
                        values=["default"] +
                               [ParserType.merge_into_full_name(ParserType.web, item)   for item in loaded_plugins.web_audio_getters.loaded] +
                               [ParserType.merge_into_full_name(ParserType.local, item) for item in loaded_plugins.local_audio_getters.loaded] +
                               [ParserType.merge_into_full_name(ParserType.chain, item) for item in self.chaining_data["audio_getters"]],
                        command=lambda parser_name: self.change_audio_getter(parser_name))
                    self.audio_getter_option_menu.grid(row=6, column=3, columnspan=4, sticky="news",
                                                       padx=0, pady=0)
                else:
                    raise NotImplementedError(f"Unknown chosen parser type: {chosen_parser_type}")

            @error_handler(self.show_exception_logs)
            def remove_option(option: str):
                chosen_parser_type = chaining_options[chain_type_option_menu["text"]]
                self.chaining_data[chosen_parser_type].pop(option)
                self.chaining_data.compute_chains_dependencies()
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
                    chain_name = str(chain_name)
                    chain_data = self.chaining_data[chaining_options[chain_type_option_menu["text"]]][chain_name]

                    build_chain(chain_name=chain_name,
                                initial_chain=chain_data["chain"],
                                edit_mode=True)
                    self.chaining_data.compute_chains_dependencies()

                @error_handler(self.show_exception_logs)
                def remove_selected_chain():
                    selected_item_index = existing_chains_treeview.focus()
                    if not selected_item_index:
                        return
                    chain_name, _ = existing_chains_treeview.item(selected_item_index)["values"]
                    chain_name = str(chain_name)
                    chosen_parser_type = chaining_options[chain_type_option_menu["text"]]
                    conflicting_chains = self.chaining_data.get_dependent_chains(chosen_parser_type, chain_name)

                    if not conflicting_chains or conflicting_chains and messagebox.askokcancel(
                        title=self.lang_pack.on_closing_message_title, 
                        message="There are other chains that depend on this chain: ({}). "
                                "If you delete this chain, other also will be deleted. Continue?".format(", ".join(conflicting_chains))):
                        rm_list = []
                        for conflict in conflicting_chains:
                            self.chaining_data[chosen_parser_type].pop(conflict)
                            for each in existing_chains_treeview.get_children():
                                row_chain, _ = existing_chains_treeview.item(each)['values']
                                if row_chain == conflict:
                                    rm_list.append(each)
                                    break
                        rm_list.sort(reverse=True)
                        for rm in rm_list:
                            existing_chains_treeview.delete(rm)

                        remove_option(chain_name)
                        existing_chains_treeview.delete(selected_item_index)    

                m = Menu(self, tearoff=0)
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
                            initial_chain: list[TypedParserName],
                            edit_mode: bool = False) -> None:
                pady = 2

                chain_type = chaining_options[chain_type_option_menu["text"]]

                ChoosingData = namedtuple("ChoosingData", ("name", "label", "select_button"))
                
                from typing import NamedTuple
                class ChainData(NamedTuple):
                    parser_info:      TypedParserName
                    displaying_label: Label
                    up_button:        Button
                    deselect_button:  Button
                    down_button:      Button

                    def destroy(self) -> None:
                        self.displaying_label.destroy()
                        self.up_button.destroy()
                        self.deselect_button.destroy()
                        self.down_button.destroy()

                    def grid_forget(self) -> None:
                        self.displaying_label.grid_forget()
                        self.up_button.grid_forget()
                        self.deselect_button.grid_forget()
                        self.down_button.grid_forget()

                # ChainData = namedtuple("ChainData", ("name", "label", "up_button", "deselect_button", "down_button"))

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
                    displaying_options: Iterable[str] = \
                        itertools.chain(
                            (ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_word_parsers.loaded),
                            (ParserType.merge_into_full_name(ParserType.local, name) for name in loaded_plugins.local_word_parsers.loaded),
                            (ParserType.merge_into_full_name(parser_type=ParserType.chain, parser_name=name) for name in 
                             (self.chaining_data.get_non_dependent_chains(chain_type=chain_type, chain_name=chain_name) if edit_mode else self.chaining_data[chain_type]))
                            )
                elif chain_type == "sentence_parsers":
                    displaying_options = \
                        itertools.chain(
                            (ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_sent_parsers.loaded),
                            (ParserType.merge_into_full_name(parser_type=ParserType.chain, parser_name=name) for name in 
                             (self.chaining_data.get_non_dependent_chains(chain_type=chain_type, chain_name=chain_name) if edit_mode else self.chaining_data[chain_type]))
                        )
                elif chain_type == "image_parsers":
                    displaying_options = \
                        itertools.chain(
                            (ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_image_parsers.loaded),
                            (ParserType.merge_into_full_name(parser_type=ParserType.chain, parser_name=name) for name in 
                             (self.chaining_data.get_non_dependent_chains(chain_type=chain_type, chain_name=chain_name) if edit_mode else self.chaining_data[chain_type]))
                        )
                elif chain_type == "audio_getters":
                    displaying_options = \
                        itertools.chain(
                            (ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_audio_getters.loaded),
                            (ParserType.merge_into_full_name(ParserType.local, name) for name in loaded_plugins.local_audio_getters.loaded),
                            (ParserType.merge_into_full_name(parser_type=ParserType.chain, parser_name=name) for name in 
                             (self.chaining_data.get_non_dependent_chains(chain_type=chain_type, chain_name=chain_name) if edit_mode else self.chaining_data[chain_type]))
                        )
                else:
                    raise NotImplementedError(f"Unknown chain type: {chain_type}")

                built_chain_main_frame = ScrolledFrame(chaining_window, scrollbars="vertical",
                                                       canvas_bg=self.theme.frame_cfg.get("bg"))
                built_chain_main_frame.grid(row=1, column=1, sticky="news", padx=10, pady=(0, 10))
                built_chain_inner_frame = built_chain_main_frame.display_widget(self.Frame,
                                                                                fit_width=True)
                built_chain_main_frame.bind_scroll_wheel(built_chain_inner_frame)
                built_chain_inner_frame.grid_columnconfigure(0, weight=1)

                @error_handler(self.show_exception_logs)
                def add_to_chain(placing_name: TypedParserName) -> None:
                    new_chain_ind = len(chain_data) * 3
                    a = self.Label(built_chain_inner_frame, text=placing_name.full_name, justify='center',
                                   relief="ridge", borderwidth=2)
                    built_chain_main_frame.bind_scroll_wheel(a)

                    @error_handler(self.show_exception_logs)
                    def place_widget_to_chain(item: ChainData, next_3i: int):
                        item.displaying_label.grid(row=next_3i, column=0, sticky="news", rowspan=3, pady=pady)
                        item.up_button.grid(row=next_3i, column=1, sticky="news", pady=(pady, 0))
                        if next_3i:
                            item.up_button["state"] = "normal"
                            item.up_button.configure(
                                command=lambda ind=next_3i: swap_places(current_ind=ind // 3, direction=-1))
                        else:
                            item.up_button["state"] = "disabled"

                        item.deselect_button.grid(row=next_3i + 1, column=1, sticky="news", pady=0)
                        item.deselect_button.configure(command=lambda ind=next_3i: remove_from_chain(ind // 3))
                        item.down_button.grid(row=next_3i + 2, column=1, sticky="news", pady=(0, pady))

                        if next_3i == 3 * (len(chain_data) - 1):
                            item.down_button["state"] = "disabled"
                        else:
                            item.down_button["state"] = "normal"
                            item.down_button.configure(command=lambda ind=next_3i: swap_places(current_ind=ind // 3, direction=1))

                    @error_handler(self.show_exception_logs)
                    def swap_places(current_ind: int, direction: int):
                        current = chain_data[current_ind]
                        operand = chain_data[current_ind + direction]

                        current.grid_forget()
                        operand.grid_forget()

                        old_3 = 3 * current_ind
                        new_3 = old_3 + direction * 3
                        place_widget_to_chain(current, new_3)
                        place_widget_to_chain(operand, old_3)
                        chain_data[old_3 // 3], chain_data[new_3 // 3] = chain_data[new_3 // 3], chain_data[old_3 // 3]

                    @error_handler(self.show_exception_logs)
                    def remove_from_chain(ind: int):
                        chain_data.pop(ind).destroy()
                        for i in range(ind, len(chain_data)):
                            chain_data[i].grid_forget()
                            chain_data[i].displaying_label.grid(row=3 * i, column=0, sticky="news", pady=pady, rowspan=3)
                            chain_data[i].up_button.grid(row=3 * i, column=1, sticky="news", pady=(pady, 0))
                            chain_data[i].deselect_button.grid(row=3 * i + 1, column=1, sticky="news", pady=0)
                            chain_data[i].deselect_button.configure(command=lambda ind=i: remove_from_chain(ind))
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

                    chain_data.append(ChainData(parser_info=placing_name,
                                                displaying_label=a,
                                                up_button=up_button,
                                                deselect_button=deselect_button,
                                                down_button=down_button))
                    place_widget_to_chain(chain_data[-1], new_chain_ind)

                for name in initial_chain:
                    add_to_chain(name)

                for i, parser_name in enumerate(displaying_options):
                    a = self.Label(choosing_inner_frame, text=parser_name, justify='center',
                                   relief="ridge", borderwidth=2)
                    a.grid(row=i, column=0, sticky="news", pady=pady)
                    choosing_main_frame.bind_scroll_wheel(a)
                    b = self.Button(choosing_inner_frame, text=">",
                                    command=lambda name=parser_name: add_to_chain(TypedParserName.split_full_name(name)))
                    b.grid(row=i, column=1, sticky="news", pady=pady)
                    choosing_main_frame.bind_scroll_wheel(b)
                    choosing_widgets_data.append(ChoosingData(name=parser_name, label=a, select_button=b))

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

                    chain = [item.parser_info for item in chain_data]
                    chosen_chain_config = {"config_name": "{}_{}.json".format(remove_special_chars(new_chain_name, "_"),
                                                                              abs(hash(time.time()))),
                                           "chain": chain}
                    self.chaining_data[chain_type][new_chain_name] = chosen_chain_config

                    if edit_mode:
                        if chain_type == "word_parsers":
                            if chain_name == self.card_generator.parser_info.name:
                                self.card_generator = loaded_plugins.get_card_generator(
                                    parser_info=TypedParserName(parser_t=ParserType.chain,
                                                                name=new_chain_name),
                                    chain_data=self.chaining_data["word_parsers"])
                                self.configurations["scrappers"]["word"]["name"] = new_chain_name
                                self.deck.update_card_generator(self.card_generator)

                        elif chain_type == "sentence_parsers":
                            if chain_name == self.external_sentence_fetcher.data_generator.parser_info.name:
                                sentence_parser = loaded_plugins.get_sentence_parser(
                                    parser_info=TypedParserName(parser_t=ParserType.chain,
                                                                name=new_chain_name),
                                    chain_data=self.chaining_data["sentence_parsers"])
                                self.external_sentence_fetcher = \
                                    ExternalDataGenerator(data_generator=sentence_parser)
                                self.configurations["scrappers"]["sentence"]["name"] = new_chain_name

                        elif chain_type == "image_parsers":
                            if chain_name == self.external_image_generator.parser_info.name:
                                image_parser = loaded_plugins.get_image_parser(
                                    parser_info=TypedParserName(parser_t=ParserType.chain,
                                                                name=new_chain_name),
                                    chain_data=self.chaining_data["image_parsers"])
                                self.external_image_generator = ExternalDataGenerator(data_generator=image_parser)
                                self.configurations["scrappers"]["image"]["name"] = new_chain_name

                        elif chain_type == "audio_getters":
                            if self.external_audio_generator is not None and \
                                    chain_name == self.external_audio_generator.data_generator.parser_info.name:
                                self.configurations["scrappers"]["audio"]["name"] = new_chain_name
                                self.external_audio_generator = ExternalDataGenerator(
                                    data_generator=loaded_plugins.get_audio_getter(
                                        parser_info=TypedParserName(parser_t=ParserType.chain,
                                                                    name=new_chain_name),
                                        chain_data=self.chaining_data["audio_getters"]))
                        else:
                            raise NotImplementedError(f"Unknown chosen parser type: {chain_type}")

                        if chain_name != new_chain_name:
                            self.chaining_data.rename_chain(chain_type, chain_name, new_chain_name)
                            remove_option(chain_name)
                        else:
                            recreate_option_menus(chain_type)

                        existing_chains_treeview.delete(*existing_chains_treeview.get_children())
                        for i, (name, data) in enumerate(self.chaining_data[chain_type].items()):
                            existing_chains_treeview.insert(parent="", index=i,
                                                            values=(name, "->".join((item.full_name for item in data["chain"]))))

                    else:
                        recreate_option_menus(chaining_options[chain_type_option_menu["text"]])
                        existing_chains_treeview.insert(
                            "", 
                            "end", 
                            values=(new_chain_name, "->".join((name.full_name for name in chain))))
                    self.chaining_data.compute_chains_dependencies()
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

        def focus_next_window(event, focusout_action: Callable[[], None] | None = None):
            event.widget.tk_focusNext().focus()
            if focusout_action is not None:
                focusout_action()
            return "break"

        def focus_prev_window(event, focusout_action: Callable[[], None] | None = None):
            event.widget.tk_focusPrev().focus()
            if focusout_action is not None:
                focusout_action()
            return "break"

        self.new_order = [(self.anki_button, None),
                          (self.browse_button, None),
                          (self.word_parser_option_menu, None),
                          (self.configure_word_parser_button, None),

                          (self.word_text, self.fill_search_fields),

                          (self.special_field, None),

                          (self.definition_text, None),

                          (self.dict_tags_field, None),

                          (self.fetch_images_button, None),
                          (self.image_parsers_option_menu, None),
                          (self.configure_image_parser_button, None),

                          (self.fetch_audio_data_button, None),
                          (self.audio_getter_option_menu, None),
                          (self.configure_audio_getter_button, None),

                          (self.audio_search_entry, None),

                          (self.prev_button, None),
                          (self.bury_button, None),
                          (self.skip_button, None),
                          (self.skip_all_button, None),

                          (self.fetch_ext_sentences_button, None),
                          (self.sentence_parsers_option_menu, None),
                          (self.configure_sentence_parser_button, None),

                          (self.sentence_search_entry, None),

                          (self.user_tags_field, None),
                          (self.tag_prefix_field, None),
                          ]

        self.word_text.bind("<FocusOut>", lambda event: self.fill_search_fields(), add=True)
        for widget, action in self.new_order:
            widget.lift()
            widget.bind("<Tab>", partial(focus_next_window, focusout_action=action))
            widget.bind("<Shift-Tab>", partial(focus_prev_window, focusout_action=action))

        self.chosen_sentences: dict[int, str] = {}
        def bind_hotkeys():
            self.bind("<Control-quoteleft>",  lambda event: self.save_and_refresh())
            self.bind("<Control-Return>",     lambda event: self.save_and_refresh())
            self.bind("<Escape>",             lambda event: self.on_closing())
            self.bind("<Control-Key-0>",      lambda event: self.geometry("+0+0"))
            self.bind("<Control-z>",          lambda event: self.move_decks_pointers(-1))
            self.bind("<Control-q>",          lambda event: self.bury_command())
            self.bind("<Control-d>",          lambda event: self.move_decks_pointers(1))
            self.bind("<Control-Shift_L><D>", lambda event: self.move_decks_pointers(self.deck.get_n_cards_left()))
            self.bind("<Control-s>",          lambda event: self.save_button())
            self.bind("<Control-Shift_L><A>", lambda event: self.add_word_dialog())
            self.bind("<Control-f>",          lambda event: self.find_dialog())
            self.bind("<Control-e>",          lambda event: self.statistics_dialog())
            self.bind("<Control-b>",          lambda event: self.added_cards_browser())

            for i in range(0, 9):
                self.bind(f"<Control-Key-{i + 1}>", lambda event, index=i: self.choose_sentence(self.choosing_buttons[min(index, len(self.choosing_buttons) - 1)], index))
        
        def unbind_hotkeys():
            self.unbind("<Control-quoteleft>")
            self.unbind("<Control-Return>")
            self.unbind("<Escape>")
            self.unbind("<Control-Key-0>")
            self.unbind("<Control-z>")
            self.unbind("<Control-q>")
            self.unbind("<Control-d>")
            self.unbind("<Control-Shift_L><D>")
            self.unbind("<Control-s>")
            self.unbind("<Control-Shift_L><A>")
            self.unbind("<Control-f>")
            self.unbind("<Control-e>")
            self.unbind("<Control-b>")

            for i in range(0, 9):
                self.unbind(f"<Control-Key-{i + 1}>")

        bind_hotkeys()

        def define_word_with_window_lock():
            def disableChildren(parent):
                for child in parent.winfo_children():
                    wtype = child.winfo_class()
                    if wtype not in ('Frame','Labelframe','TFrame','TLabelframe'):
                        child.configure(state='disable')
                    else:
                        disableChildren(child)

            def enableChildren(parent):
                for child in parent.winfo_children():
                    wtype = child.winfo_class()
                    if wtype not in ('Frame','Labelframe','TFrame','TLabelframe'):
                        child.configure(state='normal')
                    else:
                        enableChildren(child)

            self.global_binder.stop()
            unbind_hotkeys()
            
            last = main_menu.index("end")
            for i in range(last+1):
                main_menu.entryconfigure(i, state="disabled")
            
            self.skip_all_button["state"] = "disabled"
            self.skip_button["state"] = "disabled"
            self.bury_button["state"] = "disabled"
            self.prev_button["state"] = "disabled"
            self.save_and_refresh_button["state"] = "disabled"
            disableChildren(self.text_widgets_frame)
            
            self.define_word(word_query=self.clipboard_get(),
                             additional_query="")
            
            self.skip_all_button["state"] = "normal"
            self.skip_button["state"] = "normal"
            self.bury_button["state"] = "normal"
            self.prev_button["state"] = "normal"
            self.save_and_refresh_button["state"] = "normal"
            enableChildren(self.text_widgets_frame)

            for i in range(last+1):
                main_menu.entryconfigure(i, state="normal")

            self.global_binder.start()
            bind_hotkeys()

        self.global_binder = Binder()
        self.global_binder.bind("Control", "c", "space",
                     action=define_word_with_window_lock) 

        @error_handler(self.show_exception_logs)
        def paste_in_sentence_field():
            clipboard_text = self.clipboard_get()
            self.add_sentence_field(
                source="<Control + c + Alt>",
                sentence=clipboard_text,
                text_widgets_frame=self.text_widgets_frame,
                text_widgets_sf=self.text_widgets_sf,
                sentence_text_widgets_list=self.sentence_texts,
                choose_sentence_action=self.choose_sentence
            )

        self.global_binder.bind("Control", "c", "Alt", action=paste_in_sentence_field)
        self.global_binder.start()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.geometry(self.configurations["app"]["main_window_geometry"])

        AUTOSAVE_INTERVAL = 300_000  # time in milliseconds

        @error_handler(self.show_exception_logs)
        def autosave():
            self.save_files()
            self.after(AUTOSAVE_INTERVAL, autosave)

        self.after(AUTOSAVE_INTERVAL, autosave)

        self.tried_to_display_audio_getters_on_refresh = False
        self.waiting_for_audio_display = False
        self.last_refresh_call_time = 0.0

        self.refresh()

    def fill_search_fields(self):
        word = self.word
        if not self.audio_search_entry.get():
            self.audio_search_entry.insert(0, word)
        if not self.sentence_search_entry.get():
            self.sentence_search_entry.insert(0, word)

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
                    "type": (ParserType.web, [str], [ParserType.web, ParserType.local, ParserType.chain]),
                    "name": ("cambridge", [str], [])
                },
                "sentence": {
                    "type": (ParserType.web, [str], [ParserType.web, ParserType.chain]),
                    "name": ("sentencedict", [str], [])
                },
                "image": {
                    "type": (ParserType.web, [str], [ParserType.web, ParserType.chain]),
                    "name": ("google", [str], [])
                },
                "audio": {
                    "type": (ParserType.web, [str], ["default", ParserType.web, ParserType.local, ParserType.chain]),
                    "name": ("forvo", [str], [])
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
                "audio_autochoose_mode":  ("first_available_audio_source", [str], ["off",
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
                "n_images_in_row":     (3, [int], []),
                "n_rows":              (2, [int], [])
            },
            "extern_sentence_placer": {
                "n_sentences_per_batch": (5, [int], [])
            },
            "extern_audio_placer": {
                "n_audios_per_batch": (5, [int], [])
            },
            "web_audio_downloader": {
                "timeout": (1, [int], []),
                "request_delay": (3000, [int], [])
            },
            "deck": {
                "tags_hierarchical_pref": ("", [str], []),
                "saving_format":          ("anki_package", [str], []),
                "card_processor":         ("Anki", [str], [])
            }
        }
        conf_file = LoadableConfig(config_location=os.path.dirname(CONFIG_FILE_PATH),
                                   validation_scheme=validation_scheme,  # type: ignore
                                   docs="")

        lang_pack = loaded_plugins.get_language_package(conf_file["app"]["language_package"])

        if not conf_file["directories"]["media_dir"] or not os.path.isdir(conf_file["directories"]["media_dir"]):
            conf_file["directories"]["media_dir"] = askdirectory(title=lang_pack.choose_media_dir_message,
                                                                 mustexist=True,
                                                                 initialdir=MEDIA_DOWNLOADED_LOCATION)
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

    def added_cards_browser(self) -> None:
        added_cards_browser_window = self.Toplevel(self)
        added_cards_browser_window.grab_set()

        def close_added_cards_browser():
            table_selected_items = items_table.selection()
            if table_selected_items:
                save_progress(table_selected_items[0])
            added_cards_browser_window.destroy()

        added_cards_browser_window.bind("<Escape>", lambda event: close_added_cards_browser())
        added_cards_browser_window.protocol("WM_DELETE_WINDOW", close_added_cards_browser)
        
        main_paned_window = PanedWindow(added_cards_browser_window, showhandle=True, orient="horizontal")
        main_paned_window.pack(fill="both", expand=True, padx=5, pady=5)

        table_view_frame = self.Frame(added_cards_browser_window)
        main_paned_window.add(table_view_frame, stretch="always", sticky="news")
        table_view_frame.rowconfigure(0, weight=1)
        table_view_frame.columnconfigure(0, weight=1)

        columns = ("#1", "#2", "#3")
        items_table = Treeview(table_view_frame, show="headings", columns=columns)
        items_table.grid(row=0, column=0, sticky="news")
        items_table.heading("#1", text=self.lang_pack.word_text_placeholder)
        items_table.heading("#2", text=self.lang_pack.definition_text_placeholder)
        items_table.heading("#3", text=self.lang_pack.sentence_text_placeholder_prefix)
        items_table.column("#1", anchor="w", stretch=False, minwidth=200)
        items_table.column("#2", anchor="w", stretch=False, minwidth=200)
        items_table.column("#3", anchor="w", stretch=True, minwidth=200)

        ysb = Scrollbar(table_view_frame, orient="vertical", command=items_table.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        items_table.configure(yscroll=ysb.set)

        xsb = Scrollbar(table_view_frame, orient="horizontal", command=items_table.xview)
        xsb.grid(row=1, column=0, columnspan=2, sticky="ew")
        items_table.configure(xscroll=xsb.set)

        full_saved_card_data: FrozenDict = {}
        editor_card_data: Card = {}
        added_cards_list = []

        for i, saved_card_data in enumerate(self.saved_cards_data):
            if saved_card_data[SavedDataDeck.CARD_STATUS] != CardStatus.ADD:
                continue
            added_cards_list.append(saved_card_data)
            main_card_data = saved_card_data[SavedDataDeck.CARD_DATA]

            word = main_card_data.get(CardFields.word, "").replace("\n", " ")
            definition = main_card_data.get(CardFields.definition, "").replace("\n", " ")
            sentence = main_card_data.get(CardFields.sentences, [""])[0].replace("\n", " ")
            items_table.insert("", "end", values=(word, definition, sentence, i))

        item_editor_frame = self.Frame(added_cards_browser_window)
        main_paned_window.add(item_editor_frame, stretch="never")

        # =======================================
        editor_text_padx = 5
        editor_text_pady = 5

        for i in range(6):
            item_editor_frame.grid_columnconfigure(i, weight=1)

        additional_search_frame = self.Frame(item_editor_frame)
        additional_search_frame.columnconfigure(0, weight=1)
        additional_search_frame.columnconfigure(1, weight=1)
        additional_search_frame.grid(row=0, column=0, sticky="news", columnspan=8,
                                     padx=(editor_text_padx), pady=(editor_text_pady, 0))

        editor_anki_button = self.Button(additional_search_frame,
                                         text=self.lang_pack.anki_button_text,
                                         command=lambda: self.open_anki_browser(
                                             editor_word_text.get(1.0, "end").rstrip()))
        editor_anki_button.grid(row=0, column=0, sticky="news")

        editor_browse_button = self.Button(additional_search_frame,
                                           text=self.lang_pack.browse_button_text,
                                           command=lambda: self.web_search_command(
                                               editor_word_text.get(1.0, "end").rstrip()))
        editor_browse_button.grid(row=0, column=1, sticky="news")

        editor_word_text = self.Text(item_editor_frame, placeholder=self.lang_pack.word_text_placeholder, height=1)
        editor_word_text.grid(row=1, column=0, columnspan=8, sticky="news",
                              padx=editor_text_padx, pady=editor_text_pady)

        editor_special_field = self.Text(item_editor_frame, relief="ridge", state="disabled", height=1)
        editor_special_field.grid(row=2, column=0, columnspan=8, sticky="news", padx=editor_text_padx)

        editor_definition_text = self.Text(item_editor_frame, placeholder=self.lang_pack.definition_text_placeholder,
                                           height=4)
        editor_definition_text.grid(row=3, column=0, columnspan=8, sticky="news",
                                    padx=editor_text_padx, pady=(editor_text_pady, 0))

        editor_dict_tags_field = self.Text(item_editor_frame, relief="ridge", state="disabled", height=2)
        editor_dict_tags_field.grid(row=4, column=0, columnspan=8, sticky="news",
                                    padx=editor_text_padx, pady=editor_text_pady)

        def edit_saved_images(new_image_urls: list[str]):
            if full_saved_card_data.get(SavedDataDeck.ADDITIONAL_DATA) is None:
                full_saved_card_data._data[SavedDataDeck.ADDITIONAL_DATA] = {SavedDataDeck.SAVED_IMAGES_PATHS: []}
            elif full_saved_card_data._data[SavedDataDeck.ADDITIONAL_DATA].get(
                    SavedDataDeck.SAVED_IMAGES_PATHS) is None:
                full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA]._data[SavedDataDeck.SAVED_IMAGES_PATHS] = []

            saving_dst = full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.SAVED_IMAGES_PATHS]
            saving_dst.clear()
            saving_dst.extend(new_image_urls)

        editor_fetch_images_button = self.Button(
            item_editor_frame,
            text=self.lang_pack.fetch_images_button_normal_text,
            command=lambda: self.start_image_search(
                word=editor_word_text.get(1.0, "end").rstrip(),
                card_data=editor_card_data,
                init_urls=[],
                init_local_images_paths=full_saved_card_data.get(SavedDataDeck.ADDITIONAL_DATA, {}) \
                    .get(SavedDataDeck.SAVED_IMAGES_PATHS, []),
                image_path_saving_method=edit_saved_images
            )
        )
        editor_fetch_images_button.grid(row=5, column=0, columnspan=3, sticky="news",
                                        padx=(editor_text_padx, 0), pady=0)

        def global_change_image_parser(parser_name):
            self.change_image_parser(parser_name)
            self.image_parsers_option_menu.destroy()
            typed_image_parser_name = self.external_image_generator.parser_info.full_name
            self.image_parsers_option_menu = self.get_option_menu(
                self,
                init_text=typed_image_parser_name,
                values=[ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_image_parsers.loaded] +
                       [ParserType.merge_into_full_name(ParserType.chain, name) for name in self.chaining_data["image_parsers"]],
                command=lambda parser_name: self.change_image_parser(parser_name))
            self.image_parsers_option_menu.grid(row=5, column=3, columnspan=4, sticky="news",
                                               padx=0, pady=(0, self.text_pady))

        typed_image_parser_name = self.external_image_generator.parser_info.full_name
        editor_image_parsers_option_menu = self.get_option_menu(
            item_editor_frame,
            init_text=typed_image_parser_name,
            values=[ParserType.merge_into_full_name(ParserType.web, name)   for name in loaded_plugins.web_image_parsers.loaded] +
                   [ParserType.merge_into_full_name(ParserType.chain, name) for name in self.chaining_data["image_parsers"]],
            command=global_change_image_parser)
        editor_image_parsers_option_menu.grid(row=5, column=3, columnspan=4, sticky="news",
                                           padx=0, pady=0)

        editor_configure_image_parser_button = self.Button(
            item_editor_frame,
            text="</>",
            command=lambda: self.call_configuration_window(
                plugin_name=self.external_image_generator.parser_info.full_name,
                plugin_config=self.external_image_generator.data_generator.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save()))
        editor_configure_image_parser_button.grid(row=5, column=7, sticky="news", padx=(0, editor_text_padx), pady=0)

        def display_audio_getter_results_on_button_click():
            editor_fill_search_fields()
            self.waiting_for_audio_display = True
            self.display_audio_getter_results(
                word=editor_audio_search_entry.get(),
                card_data=editor_card_data,
                show_errors=True,
                audio_sf=editor_audio_sf,
                audio_inner_frame=editor_audio_inner_frame
            )

        editor_fetch_audio_data_button = self.Button(item_editor_frame,
                                                     text=self.lang_pack.fetch_audio_data_button_text,
                                                     command=display_audio_getter_results_on_button_click)

        typed_audio_getter = "default" if self.external_audio_generator is None else self.external_audio_generator.parser_info.full_name

        if typed_audio_getter == "default":
            editor_fetch_audio_data_button["state"] = "disabled"

        editor_fetch_audio_data_button.grid(row=6, column=0, columnspan=3,
                                            sticky="news",
                                            padx=(editor_text_padx, 0), pady=0)

        def global_change_audio_getter(parser_name):
            self.change_audio_getter(parser_name)
            self.audio_getter_option_menu.destroy()
            typed_audio_getter = "default" if self.external_audio_generator is None else self.external_audio_generator.parser_info.full_name
            if typed_audio_getter == "default":
                editor_fetch_audio_data_button["state"] = "disabled"
                editor_configure_audio_getter_button["state"] = "disabled"
            else:
                editor_fetch_audio_data_button["state"] = "normal"
                editor_configure_audio_getter_button["state"] = "normal"

            self.audio_getter_option_menu = self.get_option_menu(
                self,
                init_text=typed_audio_getter,
                values=["default"] +
                       [ParserType.merge_into_full_name(ParserType.web, item)   for item in loaded_plugins.web_audio_getters.loaded] +
                       [ParserType.merge_into_full_name(ParserType.local, item) for item in loaded_plugins.local_audio_getters.loaded] +
                       [ParserType.merge_into_full_name(ParserType.chain, item) for item in self.chaining_data["audio_getters"]],
                command=lambda parser_name: self.change_audio_getter(parser_name))
            self.audio_getter_option_menu.grid(row=6, column=3, columnspan=4, sticky="news",
                                               padx=0, pady=0)

        editor_audio_getter_option_menu = self.get_option_menu(
            item_editor_frame,
            init_text=typed_audio_getter,
            values=["default"] +
                   [ParserType.merge_into_full_name(ParserType.web, item)   for item in loaded_plugins.web_audio_getters.loaded] +
                   [ParserType.merge_into_full_name(ParserType.local, item) for item in loaded_plugins.local_audio_getters.loaded] +
                   [ParserType.merge_into_full_name(ParserType.chain, item) for item in self.chaining_data["audio_getters"]],
            command=global_change_audio_getter)
        editor_audio_getter_option_menu.grid(row=6, column=3, columnspan=4, sticky="news",
                                             padx=0, pady=0)

        editor_configure_audio_getter_button = self.Button(item_editor_frame, text="</>")

        if self.external_audio_generator is not None:
            cmd = lambda: self.call_configuration_window(plugin_name=typed_audio_getter,
                                                         plugin_config=self.external_audio_generator.data_generator.config,
                                                         plugin_load_function=lambda conf: conf.load(),
                                                         saving_action=lambda conf: conf.save())
            editor_configure_audio_getter_button["command"] = cmd
        else:
            editor_configure_audio_getter_button["state"] = "disabled"

        editor_configure_audio_getter_button.grid(row=6, column=7, sticky="news",
                                                  padx=(0, editor_text_padx), pady=0)

        editor_audio_search_entry = self.Entry(item_editor_frame, placeholder=self.lang_pack.audio_search_entry_text)
        editor_audio_search_entry.grid(row=7, column=0, columnspan=8, sticky="news",
                                       padx=editor_text_padx, pady=0)

        editor_audio_sf = ScrolledFrame(item_editor_frame, scrollbars="vertical",
                                        canvas_bg=self.theme.frame_cfg.get("bg"),
                                        height=110)

        editor_audio_sf.grid(row=8, column=0, columnspan=8, sticky="news",
                             padx=editor_text_padx, pady=(0, editor_text_pady))

        editor_audio_inner_frame = editor_audio_sf.display_widget(self.Frame, fit_width=True)
        editor_audio_sf.bind_scroll_wheel(editor_audio_inner_frame)
        editor_audio_inner_frame.last_getter_label = None
        editor_audio_inner_frame.source_display_frame = None

        editor_chosen_sentences: dict[int, str] = {}

        def edit_picked_sentence(pressed_button: Button, sentence_number: int):
            nonlocal editor_chosen_sentences
            selected_item = items_table.selection()
            if not selected_item:
                return

            text_widget = editor_sentence_texts[sentence_number]
            picked_sentence = editor_sentence_texts[sentence_number].get(1.0, "end").rstrip()
            if editor_chosen_sentences.get(sentence_number) is None:
                editor_chosen_sentences[sentence_number] = picked_sentence
                pressed_button["background"] = "red"
                text_widget["state"] = "disabled"
                text_widget["fg"] = text_widget.placeholder_fg_color
            else:
                editor_chosen_sentences.pop(sentence_number)
                pressed_button["background"] = self.theme.button_cfg.get("background", "SystemButtonFace")
                text_widget["state"] = "normal"
                text_widget["fg"] = text_widget.default_fg_color


        @error_handler(self.show_exception_logs)
        def editor_fetch_external_sentences() -> None:
            generators_results: list[GeneratorReturn[list[str]]] | None = None

            editor_fill_search_fields()

            def schedule_sentence_fetcher() -> None:
                nonlocal generators_results, editor_card_data
                generators_results = self.external_sentence_fetcher.get(
                    word=editor_sentence_search_entry.get(),
                    card_data=editor_card_data,
                    batch_size=self.configurations["extern_sentence_placer"]["n_sentences_per_batch"])

            def wait_sentence_fetcher(thread: Thread):
                if thread.is_alive():
                    self.after(100, lambda: wait_sentence_fetcher(thread))
                    return

                nonlocal generators_results
                if generators_results is None: 
                    return

                for parser_result in generators_results:
                    for sentence in parser_result.result:
                        self.add_sentence_field(
                                source=f"{parser_result.parser_info.full_name}: {editor_sentence_search_entry.get()}",
                                sentence=sentence,
                                text_widgets_frame=editor_text_widgets_frame,
                                text_widgets_sf=editor_text_widgets_sf,
                                sentence_text_widgets_list=editor_sentence_texts,
                                choose_sentence_action=edit_picked_sentence)

                    if parser_result.error_message:
                        messagebox.showerror(
                            title=parser_result.parser_info.full_name,
                            message=parser_result.error_message)

            place_sentences_thread = Thread(target=schedule_sentence_fetcher)
            place_sentences_thread.start()
            wait_sentence_fetcher(place_sentences_thread)

        editor_fetch_ext_sentences_button = self.Button(item_editor_frame,
                                                        text=self.lang_pack.fetch_ext_sentences_button,
                                                        command=editor_fetch_external_sentences)
        editor_fetch_ext_sentences_button.grid(row=9, column=0, columnspan=3, sticky="news",
                                               padx=(editor_text_padx, 0), pady=(editor_text_pady, 0))

        def global_change_sentence_parser(parser_name):
            self.change_sentence_parser(parser_name)
            self.sentence_parsers_option_menu.destroy()
            typed_sentence_parser_name = self.external_sentence_fetcher.parser_info.full_name
            self.sentence_parsers_option_menu = self.get_option_menu(
                self,
                init_text=typed_sentence_parser_name,
                values=[ParserType.merge_into_full_name(parser_type=ParserType.web, parser_name=name)   for name in loaded_plugins.web_sent_parsers.loaded] +
                       [ParserType.merge_into_full_name(parser_type=ParserType.chain, parser_name=name) for name in self.chaining_data["sentence_parsers"]],
                command=lambda parser_name: self.change_sentence_parser(parser_name))
            self.sentence_parsers_option_menu.grid(row=10, column=3, columnspan=4, sticky="news",
                                                  pady=(self.text_pady, 0))

        typed_sentence_parser_name = self.external_sentence_fetcher.parser_info.full_name
        editor_sentence_parsers_option_menu = self.get_option_menu(
            item_editor_frame,
            init_text=typed_sentence_parser_name,
            values=[ParserType.merge_into_full_name(parser_type=ParserType.web, parser_name=name)   for name in loaded_plugins.web_sent_parsers.loaded] +
                   [ParserType.merge_into_full_name(parser_type=ParserType.chain, parser_name=name) for name in self.chaining_data["sentence_parsers"]],
            command=global_change_sentence_parser)
        editor_sentence_parsers_option_menu.grid(row=9, column=3, columnspan=4, sticky="news",
                                              pady=(editor_text_pady, 0))

        editor_configure_sentence_parser_button = self.Button(
            item_editor_frame,
            text="</>",
            command=lambda: self.call_configuration_window(
                plugin_name=self.external_sentence_fetcher.parser_info.full_name,
                plugin_config=self.external_sentence_fetcher.data_generator.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save()),
            width=6)
        editor_configure_sentence_parser_button.grid(row=9, column=7, sticky="news",
                                                     padx=(0, editor_text_padx), pady=(editor_text_pady, 0))
        # ======
        editor_sentence_search_entry = self.Entry(item_editor_frame,
                                                  placeholder=self.lang_pack.sentence_search_entry_text)
        editor_sentence_search_entry.grid(row=10, column=0, columnspan=8, sticky="news",
                                          padx=editor_text_padx, pady=(0, 0))

        editor_sentence_texts: list[Text] = []

        editor_text_widgets_sf = ScrolledFrame(item_editor_frame, scrollbars="vertical",
                                               canvas_bg=self.theme.frame_cfg.get("bg"))
        editor_text_widgets_sf.grid(row=11, column=0, columnspan=8, sticky="news",
                                    padx=(editor_text_padx, 0), pady=(0, editor_text_pady))
        item_editor_frame.grid_rowconfigure(11, weight=1)

        editor_text_widgets_frame = editor_text_widgets_sf.display_widget(self.Frame, fit_width=True)
        editor_text_widgets_sf.bind_scroll_wheel(editor_text_widgets_frame)

        editor_text_widgets_frame.last_getter_label = None
        editor_text_widgets_frame.source_display_frame = None

        editor_user_tags_field = self.Entry(item_editor_frame, placeholder=self.lang_pack.user_tags_field_placeholder)
        editor_user_tags_field.fill_placeholder()
        editor_user_tags_field.grid(row=13, column=0, columnspan=6, sticky="news",
                                    padx=(editor_text_padx, 0), pady=(0, editor_text_pady))

        editor_tag_prefix_field = self.Entry(item_editor_frame, justify="center", width=8)
        editor_tag_prefix_field.insert(
            0,
            full_saved_card_data.get(SavedDataDeck.ADDITIONAL_DATA, {}).get(SavedDataDeck.HIERARCHICAL_PREFIX, ""))
        editor_tag_prefix_field.grid(row=13, column=7, columnspan=1, sticky="news",
                                     padx=(0, editor_text_padx), pady=(0, editor_text_pady))

        def focus_next_window(event, focusout_action: Callable[[], None] | None = None):
            event.widget.tk_focusNext().focus()
            if focusout_action is not None:
                focusout_action()
            return "break"

        def focus_prev_window(event, focusout_action: Callable[[], None] | None = None):
            event.widget.tk_focusPrev().focus()
            if focusout_action is not None:
                focusout_action()
            return "break"

        def editor_fill_search_fields():
            word = editor_word_text.get(1.0, "end").rstrip()
            if not editor_audio_search_entry.get():
                editor_audio_search_entry.insert(0, word)
            if not editor_sentence_search_entry.get():
                editor_sentence_search_entry.insert(0, word)

        editor_new_order = [(editor_anki_button, None),
                            (editor_browse_button, None),

                            (editor_word_text, editor_fill_search_fields),

                            (editor_special_field, None),

                            (editor_definition_text, None),
                            
                            (editor_dict_tags_field, None),

                            (editor_fetch_images_button, None),
                            (editor_image_parsers_option_menu, None),
                            (editor_configure_image_parser_button, None),

                            (editor_fetch_audio_data_button, None),
                            (editor_audio_getter_option_menu, None),
                            (editor_configure_audio_getter_button, None),

                            (editor_audio_search_entry, None),

                            (editor_fetch_ext_sentences_button, None),
                            (editor_sentence_parsers_option_menu, None),
                            (editor_configure_sentence_parser_button, None),

                            (editor_sentence_search_entry, None),

                            (editor_user_tags_field, None),
                            (editor_tag_prefix_field, None),
                            ]

        editor_word_text.bind("<FocusOut>", lambda event: editor_fill_search_fields(), add=True)
        for widget, action in editor_new_order:
            widget.lift()
            widget.bind("<Tab>", partial(focus_next_window, focusout_action=action))
            widget.bind("<Shift-Tab>", partial(focus_prev_window, focusout_action=action))

        # =======================================

        @error_handler(self.show_exception_logs)
        def save_progress(selection_index: str) -> None:
            nonlocal editor_chosen_sentences

            if not full_saved_card_data:
                return

            editor_card_data._data[CardFields.word] = editor_word_text.get(1.0, "end").rstrip()
            items_table.set(selection_index, "#1", editor_card_data[CardFields.word].replace("\n", " "))
            editor_card_data._data[CardFields.definition] = editor_definition_text.get(1.0, "end").rstrip()
            items_table.set(selection_index, "#2", editor_card_data[CardFields.definition].replace("\n", " "))

            user_tags = editor_user_tags_field.get().strip()
            editor_user_tags_field.clear()
            hierarchical_prefix = editor_tag_prefix_field.get().strip()
            editor_tag_prefix_field.clear()

            if user_tags or hierarchical_prefix:
                if full_saved_card_data.get(SavedDataDeck.ADDITIONAL_DATA) is None:
                    full_saved_card_data._data[SavedDataDeck.ADDITIONAL_DATA] = {}
                if user_tags:
                    full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA]._data[SavedDataDeck.USER_TAGS] = user_tags
                if hierarchical_prefix:
                    full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA]._data[
                        SavedDataDeck.HIERARCHICAL_PREFIX] = hierarchical_prefix

            editor_card_data._data[CardFields.sentences] = []
            for sentence in editor_chosen_sentences.values():
                editor_card_data._data[CardFields.sentences].append(sentence)

            items_table.set(selection_index, "#3", " | ".join((i.replace("\n", " ") for i in editor_chosen_sentences.values())))

            @error_handler(self.show_exception_logs)
            def add_audio_data_to_card(audio_getter_info: App.AudioGetterInfo, audio_links: list[str]):
                if not audio_links:
                    return

                if full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA].get(SavedDataDeck.AUDIO_DATA) is None:
                    full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.AUDIO_DATA]._data = {
                        SavedDataDeck.AUDIO_SRCS: [],
                        SavedDataDeck.AUDIO_SRCS_TYPE: [],
                        SavedDataDeck.AUDIO_SAVING_PATHS: []
                    }

                full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.AUDIO_DATA][
                    SavedDataDeck.AUDIO_SRCS].extend(audio_links)
                full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.AUDIO_DATA][
                    SavedDataDeck.AUDIO_SRCS_TYPE].extend(
                    (audio_getter_info.parser_info.parser_t for _ in range(len(audio_links))))
                full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.AUDIO_DATA][
                    SavedDataDeck.AUDIO_SAVING_PATHS].extend((
                        os.path.join(self.configurations["directories"]["media_dir"],
                                    self.card_processor
                                    .get_save_audio_name(
                                        word=editor_word_text.get(1.0, "end").rstrip(),
                                        audio_provider=audio_getter_info.parser_info.full_name,
                                        uniqueness_postfix=str(abs(hash(link)))[:8],
                                        card_data=editor_card_data))
                        for link in audio_links))

            last_audio_getter_data: App.AudioGetterInfo | None = None
            audio_getters_audios: list[str] = []
            for labeled_frame in editor_audio_inner_frame.winfo_children():
                current_audio_getter_data = labeled_frame.audio_getter_data
                if last_audio_getter_data != current_audio_getter_data:
                    if audio_getters_audios:
                        add_audio_data_to_card(audio_getter_info=last_audio_getter_data,
                                               audio_links=audio_getters_audios)
                    last_audio_getter_data = current_audio_getter_data
                    audio_getters_audios = []

                for i, audio_frame in reversed(list(enumerate(labeled_frame.winfo_children()))):
                    if not current_audio_getter_data.parser_info.name:  # chosen previously
                        if not audio_frame.boolvar.get():
                            full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.AUDIO_DATA][
                                SavedDataDeck.AUDIO_SRCS].pop(i)
                            full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.AUDIO_DATA][
                                SavedDataDeck.AUDIO_SRCS_TYPE].pop(i)
                            full_saved_card_data[SavedDataDeck.ADDITIONAL_DATA][SavedDataDeck.AUDIO_DATA][
                                SavedDataDeck.AUDIO_SAVING_PATHS].pop(i)
                    elif audio_frame.boolvar.get():
                        audio_getters_audios.append(audio_frame.audio_data)

            if audio_getters_audios:
                add_audio_data_to_card(audio_getter_info=last_audio_getter_data,
                                       audio_links=audio_getters_audios)

        previously_selected_item: str = ""

        def display_card_in_editor(event) -> bool:
            nonlocal \
                previously_selected_item, \
                full_saved_card_data, \
                editor_card_data, \
                editor_audio_inner_frame, \
                editor_text_widgets_frame, \
                editor_chosen_sentences

            selected_item_index = items_table.focus()
            if not selected_item_index:
                return False

            if previously_selected_item:
                save_progress(previously_selected_item)
            previously_selected_item = selected_item_index

            *_, added_card_index = items_table.item(selected_item_index)["values"]
            full_saved_card_data = self.saved_cards_data[added_card_index]
            if full_saved_card_data is None:
                str_selection_index = items_table.selection()[0]
                items_table.delete(str_selection_index)
                return False

            editor_card_data = full_saved_card_data[SavedDataDeck.CARD_DATA]
            # ====

            editor_audio_inner_frame.destroy()
            editor_audio_inner_frame = editor_audio_sf.display_widget(self.Frame, fit_width=True)
            editor_audio_sf.bind_scroll_wheel(editor_audio_inner_frame)
            editor_audio_inner_frame.last_getter_label = None
            editor_audio_inner_frame.source_display_frame = None

            editor_sentence_texts.clear()
            editor_text_widgets_frame.destroy()
            editor_text_widgets_frame = editor_text_widgets_sf.display_widget(self.Frame, fit_width=True)
            editor_text_widgets_sf.bind_scroll_wheel(editor_text_widgets_frame)
            editor_text_widgets_frame.last_getter_label = None
            editor_text_widgets_frame.source_display_frame = None

            editor_word_text.clear()
            editor_audio_search_entry.clear()
            editor_sentence_search_entry.clear()

            if (word_data := editor_card_data.get(CardFields.word, "")):
                editor_word_text.insert(1.0, word_data)
                editor_audio_search_entry.insert(0, word_data)
                editor_sentence_search_entry.insert(0, word_data)
            else:
                editor_word_text.fill_placeholder()
                editor_audio_search_entry.fill_placeholder()
                editor_sentence_search_entry.fill_placeholder()

            self.external_sentence_fetcher.force_update(word_data, editor_card_data)
            dict_sentences = editor_card_data.get(CardFields.sentences, [""])

            editor_chosen_sentences = {}
            for index, sentence in enumerate(dict_sentences):
                b = self.add_sentence_field(
                        source="",
                        sentence=sentence,
                        text_widgets_frame=editor_text_widgets_frame,
                        text_widgets_sf=editor_text_widgets_sf,
                        sentence_text_widgets_list=editor_sentence_texts,
                        choose_sentence_action=edit_picked_sentence)
                editor_chosen_sentences[index] = sentence
                b["background"] = "red"
                
                sentence_text_widget = editor_sentence_texts[index]
                sentence_text_widget["state"] = "disabled"
                sentence_text_widget["fg"] = sentence_text_widget.placeholder_fg_color

            @error_handler(self.show_exception_logs)
            def fill_additional_dict_data(widget: Text, text: str):
                widget["state"] = "normal"
                widget.clear()
                widget.insert(1.0, text)
                widget["state"] = "disabled"

            fill_additional_dict_data(editor_dict_tags_field, Card.get_str_dict_tags(editor_card_data))
            fill_additional_dict_data(editor_special_field, " ".join(editor_card_data.get(CardFields.special, [])))

            editor_definition_text.clear()
            editor_definition_text.insert(1.0, editor_card_data.get(CardFields.definition, "").rstrip())
            editor_definition_text.fill_placeholder()

            additional_data = full_saved_card_data.get(SavedDataDeck.ADDITIONAL_DATA, {})

            editor_user_tags_field.insert(0, additional_data.get(SavedDataDeck.USER_TAGS, ""))
            editor_tag_prefix_field.insert(0, additional_data.get(SavedDataDeck.HIERARCHICAL_PREFIX, ""))

            picked_audio_data = additional_data.get(SavedDataDeck.AUDIO_DATA, {})
            if picked_audio_data:
                parser_results: list[GeneratorReturn[list[tuple[str, str]]]] = []
                for audio_src, audio_srcs_type, saving_path in zip(picked_audio_data[SavedDataDeck.AUDIO_SRCS], 
                                                                   picked_audio_data[SavedDataDeck.AUDIO_SRCS_TYPE],
                                                                   picked_audio_data[SavedDataDeck.AUDIO_SAVING_PATHS]):
                    parser_results.append(GeneratorReturn(generator_type=ParserType.web if audio_srcs_type == ParserType.web else ParserType.local,
                                                          error_message="",
                                                          name="",
                                                          result=[(audio_src, self.card_processor.get_card_audio_name(saving_path))]))
                self.display_audio_on_frame(
                    word=word_data,
                    card_data=editor_card_data,
                    generator_results=parser_results,
                    audio_sf=editor_audio_sf,
                    audio_inner_frame=editor_audio_inner_frame,
                    show_errors=False,
                    is_picked=True,
                )

            if not editor_card_data:
                editor_fetch_images_button["text"] = self.lang_pack.fetch_images_button_normal_text
                return False

            if additional_data.get(SavedDataDeck.SAVED_IMAGES_PATHS, []):
                editor_fetch_images_button["text"] = self.lang_pack.fetch_images_button_normal_text + \
                                                     self.lang_pack.fetch_images_button_image_link_encountered_postfix
            else:
                editor_fetch_images_button["text"] = self.lang_pack.fetch_images_button_normal_text

            if self.external_audio_generator is not None and word_data:
                self.external_audio_generator.force_update(word_data, editor_card_data)
            return True

        items_table.bind("<<TreeviewSelect>>", display_card_in_editor)

    @error_handler(show_exception_logs)
    def load_chaining_data(self) -> ChainDataStorage:
        return ChainDataStorage()

    @error_handler(show_exception_logs)
    def display_audio_getter_results(self,
                                     word: str,
                                     card_data: dict,
                                     show_errors: bool,
                                     audio_sf,
                                     audio_inner_frame):
        parser_results: list[GeneratorReturn[list[tuple[str, str]]]] | None = []

        def fill_parser_results() -> None:
            nonlocal parser_results, word

            assert self.external_audio_generator is not None, \
                "display_audio_getter_results cannot be called because self.external_audio_generator is None"

            parser_results = self.external_audio_generator.get(
                word=word,
                card_data=card_data,
                batch_size=self.configurations["extern_audio_placer"]["n_audios_per_batch"])

        def display_audio_if_done(thread: Thread):
            if not self.waiting_for_audio_display:
                return

            if thread.is_alive():
                self.after(100, lambda: display_audio_if_done(thread))
            else:
                self.display_audio_on_frame(word=word,
                                            card_data=card_data,
                                            generator_results=parser_results,
                                            audio_sf=audio_sf,
                                            audio_inner_frame=audio_inner_frame,
                                            show_errors=show_errors,
                                            is_picked=False
                                            )

        th = Thread(target=fill_parser_results)
        th.start()
        display_audio_if_done(th)

    @error_handler(show_exception_logs)
    def display_audio_on_frame(self,
                               word: str,
                               card_data: dict,
                               generator_results: list[GeneratorReturn[list[tuple[str, str]]]] | None,
                               audio_sf,
                               audio_inner_frame,
                               show_errors: bool,
                               is_picked: bool) -> None:
        @error_handler(self.show_exception_logs)
        def playsound_in_another_thread(audio_path: str):
            @error_handler(self.show_exception_logs)
            def quite_playsound(_audio_path: str):
                playsound(os.path.relpath(_audio_path, ROOT_DIR))

            # cross-platform analog of playsound with block=False
            Thread(target=lambda: quite_playsound(audio_path)).start()

        @error_handler(self.show_exception_logs)
        def web_playsound(audio_url: str, src: str) -> None:
            audio_name = self.card_processor.get_save_audio_name(
                word=word, 
                audio_provider=src, 
                uniqueness_postfix=str(abs(hash(audio_url)))[:8],
                card_data=card_data)

            temp_audio_path = os.path.join(TEMP_DIR, audio_name)
            if os.path.exists(temp_audio_path):
                # you need to remove old file because Windows will raise permission denied error
                os.remove(temp_audio_path)

            def show_download_error(exc):
                messagebox.showerror(message=f"{self.lang_pack.error_title}\n{exc}")

            success = AudioDownloader.fetch_audio(url=audio_url,
                                                  save_path=temp_audio_path,
                                                  timeout=self.configurations["web_audio_downloader"]["timeout"],
                                                  headers=self.headers,
                                                  exception_action=lambda exc: show_download_error(exc))
            if success:
                playsound_in_another_thread(temp_audio_path)

        error_messages: list[tuple[str, str]] = []    
        if generator_results is None: 
            generator_results = []

        for scrapper_result in generator_results:
            getter_label = f"{scrapper_result.parser_info.full_name}: {word}"
            if not scrapper_result.result:
                continue
            
            # can be destroyed while this cycle is stiil working
            if not audio_inner_frame.winfo_exists():
                return

            if scrapper_result.error_message:
                error_messages.append((getter_label, scrapper_result.error_message))
            
            if audio_inner_frame.last_getter_label != getter_label:
                audio_inner_frame.last_getter_label = getter_label
                audio_inner_frame.source_display_frame = LabelFrame(
                    audio_inner_frame,
                    text=getter_label,
                    fg=self.theme.button_cfg.get("foreground"),
                    **self.theme.frame_cfg)
                audio_inner_frame.source_display_frame.audio_getter_data = App.AudioGetterInfo(
                    parser_info=scrapper_result.parser_info,
                    fetching_word=word)  
                audio_sf.bind_scroll_wheel(audio_inner_frame.source_display_frame)
                audio_inner_frame.source_display_frame.grid_propagate(False)
                audio_inner_frame.source_display_frame.pack(side="top", fill="x", expand=True)

            if scrapper_result.parser_info.parser_t == ParserType.web:
                play_audio_button_cmd = partial(web_playsound, src=getter_label)
            elif scrapper_result.parser_info.parser_t == ParserType.local:
                play_audio_button_cmd = playsound_in_another_thread
            else:
                raise NotImplementedError(f"Unknown audio getter type: {scrapper_result.parser_info.parser_t}")

            for audio, info in scrapper_result.result:
                audio_info_frame = self.Frame(audio_inner_frame.source_display_frame)
                audio_info_frame.pack(side="top", fill="x", expand=True)
                audio_info_frame.columnconfigure(2, weight=1)

                var = BooleanVar()
                var.set(is_picked)
                pick_button = Checkbutton(audio_info_frame,
                                          variable=var,
                                          **self.theme.checkbutton_cfg)
                pick_button.grid(row=0, column=0, sticky="news")
                audio_info_frame.boolvar = var
                audio_info_frame.audio_data = audio

                audio_sf.bind_scroll_wheel(pick_button)

                play_audio_button = self.Button(audio_info_frame,
                                                text="▶",
                                                command=lambda audio_url=audio, a=play_audio_button_cmd: a(audio_url))
                play_audio_button.grid(row=0, column=1, sticky="news")
                audio_sf.bind_scroll_wheel(play_audio_button)

                info_label = self.Label(audio_info_frame, text=info, relief="ridge")
                info_label.bind('<Configure>', lambda e, label=info_label: label.config(wraplength=label.winfo_width() * 7 // 8), add=True)
                info_label.grid(row=0, column=2, sticky="news")
                audio_sf.bind_scroll_wheel(info_label)

        if show_errors:
            if not generator_results:
                messagebox.showerror(
                    title=self.lang_pack.error_title,
                    message=self.lang_pack.display_audio_getter_results_audio_not_found_message
                )
            elif error_messages:
                self.show_window(title=self.lang_pack.error_title,
                                 text="\n\n".join([f"{parser_name}\n{error}" for parser_name, error in error_messages]))

    @property
    @error_handler(show_exception_logs)
    def word(self):
        return self.word_text.get(1.0, "end").rstrip()

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
        if SYSTEM == "Windows":
            self.str_session_start = self.session_start.strftime("%Y-%m-%d %H-%M-%S")
        else:
            self.str_session_start = self.session_start.strftime("%Y-%m-%d %H:%M:%S")
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
            cancel_flag = rewrite_flag = False

            def cancel_creation_if_already_exists():
                nonlocal cancel_flag
                cancel_flag = True
                copy_encounter.destroy()

            def rewrite_if_already_exists():
                nonlocal rewrite_flag
                rewrite_flag = True
                copy_encounter.destroy()
            
            new_file_name = name_entry.get()
            if SYSTEM == "Windows":
                new_file_name = remove_special_chars(new_file_name.strip(), sep="_", special_chars="<>:\"/\\|?*").strip("_")
            else:
                new_file_name = remove_special_chars(new_file_name.strip(), sep="|", special_chars="/").strip("|")
            if not new_file_name:
                messagebox.showerror(title=self.lang_pack.error_title,
                                     message=self.lang_pack.create_file_no_file_name_was_given_message)
                return

            new_file_path = f"{new_file_dir}/{new_file_name}.json"
            if os.path.exists(new_file_path):
                copy_encounter = self.Toplevel(create_file_win)
                copy_encounter.withdraw()
                encounter_label = self.Label(copy_encounter,
                                             text=self.lang_pack.create_file_file_already_exists_message,
                                             relief="ridge")
                skip_encounter_button = self.Button(copy_encounter,
                                                    text=self.lang_pack.create_file_skip_encounter_button_text,
                                                    command=cancel_creation_if_already_exists)
                rewrite_encounter_button = self.Button(copy_encounter,
                                                       text=self.lang_pack.create_file_rewrite_encounter_button_text,
                                                       command=rewrite_if_already_exists)

                encounter_label.grid(row=0, column=0, padx=5, pady=5)
                skip_encounter_button.grid(row=1, column=0, padx=5, pady=5, sticky="news")
                rewrite_encounter_button.grid(row=2, column=0, padx=5, pady=5, sticky="news")
                copy_encounter.deiconify()
                spawn_window_in_center(self, copy_encounter)
                copy_encounter.resizable(False, False)
                copy_encounter.grab_set()
                create_file_win.wait_window(copy_encounter)

            create_file_win.destroy()
            if cancel_flag:
                return

            new_save_dir = askdirectory(title=self.lang_pack.choose_save_dir_message, initialdir=ROOT_DIR)
            if not new_save_dir:
                return

            with open(new_file_path, "w", encoding="UTF-8") as new_file:
                json.dump([], new_file)

            self.save_files(not rewrite_flag)
            self.session_start = datetime.now()
            if SYSTEM == "Windows":
                self.str_session_start = self.session_start.strftime("%Y-%m-%d %H-%M-%S")
            else:
                self.str_session_start = self.session_start.strftime("%Y-%m-%d %H:%M:%S")
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
    def save_files(self, card_deck_saving_flag=True):
        self.configurations["app"]["main_window_geometry"] = self.geometry()
        self.configurations["deck"]["tags_hierarchical_pref"] = self.tag_prefix_field.get().strip()
        self.configurations.save()

        self.chaining_data.save()

        if card_deck_saving_flag:
            self.history[self.configurations["directories"]["last_open_file"]] = self.deck.get_pointer_position() - 1
            with open(HISTORY_FILE_PATH, "w") as saving_f:
                json.dump(self.history, saving_f, indent=4)

            self.deck.save()

        deck_name = os.path.basename(self.configurations["directories"]["last_open_file"]).split(sep=".")[0]
        saving_path = "{}/{}".format(self.configurations["directories"]["last_save_dir"], deck_name)
        self.deck_saver.save(self.saved_cards_data,
                             CardStatus.ADD,
                             f"{saving_path} {self.str_session_start}",
                             self.card_processor.get_card_image_name,
                             self.card_processor.get_card_audio_name)

        self.audio_saver.save(self.saved_cards_data,
                              CardStatus.ADD,
                              f"{saving_path} {self.str_session_start} audios",
                              self.card_processor.get_card_image_name,
                              self.card_processor.get_card_audio_name)

        self.buried_saver.save(self.saved_cards_data,
                               CardStatus.BURY,
                               f"{saving_path} {self.str_session_start} buried",
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
{CardFields.word}: {self.lang_pack.word_field_help}
{CardFields.special}: {self.lang_pack.special_field_help}
{CardFields.definition}: {self.lang_pack.definition_field_help}
{CardFields.sentences}: {self.lang_pack.sentences_field_help}
{CardFields.img_links}: {self.lang_pack.img_links_field_help}
{CardFields.audio_links}: {self.lang_pack.audio_links_field_help}
{CardFields.dict_tags}: {self.lang_pack.dict_tags_field_help}
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
            audio_downloader.bind("<Destroy>",
                                  lambda event: self.destroy() if isinstance(event.widget, Toplevel) else None)
        spawn_window_in_center(self, audio_downloader)
        audio_downloader.resizable(False, False)
        audio_downloader.grab_set()
        audio_downloader.download_audio(audio_links_list)

    @error_handler(show_exception_logs)
    def change_media_dir(self):
        media_dir = askdirectory(title=self.lang_pack.choose_media_dir_message,
                                 mustexist=True,
                                 initialdir=MEDIA_DOWNLOADED_LOCATION)
        if media_dir:
            self.configurations["directories"]["media_dir"] = media_dir

    @error_handler(show_exception_logs)
    def save_button(self):
        self.save_files()
        messagebox.showinfo(message=self.lang_pack.save_files_message)

    @error_handler(show_exception_logs)
    def define_word(self, word_query: str, additional_query: str) -> bool:
        try:
            additional_filter = get_card_filter(additional_query) if additional_query else None

            n_definitions_pending = self.deck.card2deck_gen.send((word_query, additional_filter))

            card_insertion_limit_exceeded = n_definitions_pending >= 2000
            if not card_insertion_limit_exceeded or \
                    card_insertion_limit_exceeded and messagebox.askokcancel(
                        title=self.lang_pack.card_insertion_limit_exceed_title,
                        message=self.lang_pack.card_insertion_limit_exceed_message.format(n_definitions_pending)):
                
                if error_message := self.deck.card2deck_gen.send(True):
                    self.show_window(title=self.lang_pack.error_title,
                                     text=str(error_message))

                if not n_definitions_pending:
                    messagebox.showerror(title=self.lang_pack.error_title,
                                         message=self.lang_pack.define_word_word_not_found_message)
                    return True

                self.refresh()
                return False

            self.deck.card2deck_gen.send(False)
        except QueryLangException as e:
            self.show_window(title=self.lang_pack.error_title,
                             text=str(e))
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
                    self.move_decks_pointers(int(move_quotient))
                find_window.destroy()
                return

            try:
                searching_filter = get_card_filter(find_query)
            except QueryLangException as e:
                messagebox.showerror(title=self.lang_pack.error_title,
                                     message=str(e))
                find_window.withdraw()
                find_window.deiconify()
                return

            if (move_list := self.deck.find_card(searching_func=searching_filter)):
                @error_handler(self.show_exception_logs)
                def rotate(n: int):
                    nonlocal move_list, found_item_number, current_rotation_index_label

                    found_item_number += n
                    current_rotation_index_label["text"] = f"{found_item_number}/{len(move_list) + 1}"
                    if n > 0:
                        current_offset = move_list.get_pointed_item()
                        move_list.move(n)
                    else:
                        move_list.move(n)
                        current_offset = -move_list.get_pointed_item()

                    left["state"] = "disabled" if not move_list.get_pointer_position() else "normal"
                    right["state"] = "disabled" if move_list.get_pointer_position() == len(move_list) else "normal"

                    self.move_decks_pointers(current_offset)

                find_window.destroy()

                found_item_number = 1
                rotate_window = self.Toplevel(self)
                rotate_window.title("")
                rotate_window.columnconfigure(0, weight=1)

                current_rotation_index_label = self.Label(rotate_window,
                                                          text=f"{found_item_number}/{len(move_list) + 1}")
                current_rotation_index_label.grid(row=0, column=0, sticky="news")

                rotation_buttons_frame = self.Frame(rotate_window)
                rotation_buttons_frame.grid(row=1, column=0)
                rotation_buttons_frame.columnconfigure(1, weight=1)

                left = self.Button(rotation_buttons_frame, text="<", command=lambda: rotate(-1),
                                   font=Font(weight="bold"))
                left["state"] = "disabled"
                left.grid(row=0, column=0, sticky="we")

                right = self.Button(rotation_buttons_frame, text=">", command=lambda: rotate(1),
                                    font=Font(weight="bold"))
                right.grid(row=0, column=2, sticky="we")

                end_rotation_button = self.Button(rotation_buttons_frame,
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
        statistics_window.title(self.lang_pack.statistics_dialog_statistics_window_title)
        statistics_window.columnconfigure(1, weight=1)
        text_list = (
            (self.lang_pack.statistics_dialog_added_label,        self.saved_cards_data.get_card_status_stats(CardStatus.ADD)), 
            (self.lang_pack.statistics_dialog_buried_label,       self.saved_cards_data.get_card_status_stats(CardStatus.BURY)), 
            (self.lang_pack.statistics_dialog_skipped_label,      self.saved_cards_data.get_card_status_stats(CardStatus.SKIP)), 
            (self.lang_pack.statistics_dialog_cards_left_label,   self.deck.get_n_cards_left()), 
            (self.lang_pack.statistics_dialog_current_file_label, self.deck.deck_path), 
            (self.lang_pack.statistics_dialog_saving_dir_label,   self.configurations["directories"]["last_save_dir"]), 
            (self.lang_pack.statistics_dialog_media_dir_label,    self.configurations["directories"]["media_dir"]), 
        )

        statistics_window.rowconfigure(4, weight=1)
        statistics_window.rowconfigure(5, weight=1)
        statistics_window.rowconfigure(6, weight=1)
        statistics_window.maxsize(self.winfo_screenwidth() // 2 , self.winfo_screenheight())

        def copy_label_text(label: Label):
            self.clipboard_clear()
            self.clipboard_append(label["text"])
            placeholder = label["text"]
            label["text"] = self.lang_pack.statistics_dialog_copied_text                
            self.after(1000, lambda: label.configure(text=placeholder) if label.winfo_exists() else None)

        for row_index in range(len(text_list)):
            info = self.Label(
                statistics_window,
                text=text_list[row_index][0],
                anchor="center",
                relief="ridge")
            info.grid(column=0, row=row_index, sticky="news")
            
            data_text = self.Label(
                statistics_window,
                text=text_list[row_index][1],
                anchor="center", 
                relief="ridge")

            data_text.bind("<Button-1>", lambda e, label=data_text: copy_label_text(label))
            data_text.grid(column=1, row=row_index, sticky="news")
            data_text.update()
            data_text.config(wraplength=data_text.winfo_width(), width=data_text.winfo_width())

        statistics_window.bind("<Escape>", lambda _: statistics_window.destroy())
        statistics_window.resizable(False, False)
        statistics_window.grab_set()

    @error_handler(show_exception_logs)
    def on_closing(self):
        if messagebox.askokcancel(title=self.lang_pack.on_closing_message_title,
                                  message=self.lang_pack.on_closing_message):
            self.save_files()
            self.global_binder.stop()
            self.download_audio(closing=True)

    @error_handler(show_exception_logs)
    def web_search_command(self, word: str):
        definition_search_query = word + " definition"
        webbrowser.open_new_tab(f"https://www.google.com/search?q={definition_search_query}")
        sentence_search_query = word + " sentence examples"
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

        text_pane_win = PanedWindow(conf_window, orient="horizontal", **self.theme.frame_cfg)
        text_pane_win.pack(side="top", expand=1, fill="both", anchor="n")

        conf_sf = ScrolledFrame(text_pane_win, scrollbars="both",
                                canvas_bg=self.theme.frame_cfg.get("bg"))
        text_pane_win.add(conf_sf, stretch="always", sticky="news")
        conf_inner_frame = conf_sf.display_widget(self.Frame, fit_width=True, fit_height=True)

        conf_text = self.Text(conf_inner_frame)
        conf_text.insert(1.0, json.dumps(plugin_config.data, indent=4))
        conf_text.pack(fill="both", expand=True)
        conf_sf.bind_scroll_wheel(conf_text)

        docs_sf = ScrolledFrame(text_pane_win, scrollbars="both",
                                canvas_bg=self.theme.frame_cfg.get("bg"))
        text_pane_win.add(docs_sf, stretch="always", sticky="news")
        docs_inner_frame = docs_sf.display_widget(self.Frame, fit_width=True, fit_height=True)

        conf_docs_text = self.Text(docs_inner_frame)
        conf_docs_text.insert(1.0, plugin_config.docs)
        conf_docs_text["state"] = "disabled"
        conf_docs_text.pack(fill="both", expand=True)
        docs_sf.bind_scroll_wheel(conf_docs_text)

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
        conf_window.grab_set()

    @error_handler(show_exception_logs)
    def change_word_parser(self, typed_parser_name: str):
        resolved_typed_parser_name = TypedParserName.split_full_name(typed_parser_name)
        self.configurations["scrappers"]["word"]["type"] = resolved_typed_parser_name.parser_t
        self.card_generator = loaded_plugins.get_card_generator(
             parser_info=resolved_typed_parser_name,
            chain_data=self.chaining_data["word_parsers"])
        self.configurations["scrappers"]["word"]["name"] = resolved_typed_parser_name.name
        self.deck.update_card_generator(self.card_generator)

    @error_handler(show_exception_logs)
    def change_audio_getter(self, typed_parser_name: str):
        if typed_parser_name == "default":
            self.external_audio_generator = None
            self.configurations["scrappers"]["audio"]["type"] = "default"
            self.configurations["scrappers"]["audio"]["name"] = ""
            self.fetch_audio_data_button["state"] = "disabled"
            self.configure_audio_getter_button["state"] = "disabled"
            return

        resolved_typed_parser_name = TypedParserName.split_full_name(typed_parser_name)
        self.configurations["scrappers"]["audio"]["type"] = resolved_typed_parser_name.parser_t

        audio_getter = loaded_plugins.get_audio_getter(
            parser_info=resolved_typed_parser_name,
            chain_data=self.chaining_data["audio_getters"])
        self.external_audio_generator = ExternalDataGenerator(data_generator=audio_getter)
        self.configurations["scrappers"]["audio"]["name"] = resolved_typed_parser_name.name
        self.fetch_audio_data_button["state"] = "normal"

        self.configure_audio_getter_button["state"] = "normal"
        self.configure_audio_getter_button["command"] = \
            lambda: self.call_configuration_window(
                plugin_name=self.external_audio_generator.parser_info.full_name,
                plugin_config=self.external_audio_generator.data_generator.config,
                plugin_load_function=lambda conf: conf.load(),
                saving_action=lambda conf: conf.save())

    @error_handler(show_exception_logs)
    def change_image_parser(self, typed_parser_name: str):
        resolved_typed_parser_name = TypedParserName.split_full_name(typed_parser_name)
        self.configurations["scrappers"]["image"]["type"] = resolved_typed_parser_name.parser_t
        self.configurations["scrappers"]["image"]["name"] = resolved_typed_parser_name.name
        image_parser = loaded_plugins.get_image_parser(
            parser_info=resolved_typed_parser_name,
            chain_data=self.chaining_data["image_parsers"])
        self.external_image_generator = ExternalDataGenerator(data_generator=image_parser)

    @error_handler(show_exception_logs)
    def change_sentence_parser(self, typed_parser_name: str):
        resolved_typed_parser_name = TypedParserName.split_full_name(typed_parser_name)
        self.configurations["scrappers"]["sentence"]["type"] = resolved_typed_parser_name.parser_t
        self.configurations["scrappers"]["sentence"]["name"] = resolved_typed_parser_name.name
        sentence_parser = loaded_plugins.get_sentence_parser(
            parser_info=resolved_typed_parser_name,
            chain_data=self.chaining_data["sentence_parsers"]
        )
        self.external_sentence_fetcher = ExternalDataGenerator(data_generator=sentence_parser)

    def save_and_refresh(self):
        if not self.chosen_sentences:
            self.refresh()
            return

        self.dict_card_data[CardFields.word] = self.word
        self.dict_card_data[CardFields.definition] = self.definition

        additional = self.dict_card_data.get(SavedDataDeck.ADDITIONAL_DATA, {})
        additional[SavedDataDeck.AUDIO_DATA] = {}
        additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS] = []
        additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS_TYPE] = []
        additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SAVING_PATHS] = []

        user_tags = self.user_tags_field.get().strip()
        if user_tags:
            additional[SavedDataDeck.USER_TAGS] = user_tags

        @error_handler(self.show_exception_logs)
        def add_audio_data_to_card(audio_getter_info: App.AudioGetterInfo, audio_links: list[str]):
            if not audio_links:
                return

            additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS].extend(audio_links)
            additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SRCS_TYPE].extend(
                (audio_getter_info.parser_info.parser_t for _ in range(len(audio_links))))
            additional[SavedDataDeck.AUDIO_DATA][SavedDataDeck.AUDIO_SAVING_PATHS].extend((
                os.path.join(self.configurations["directories"]["media_dir"],
                             self.card_processor
                             .get_save_audio_name(
                                 word=audio_getter_info.fetching_word,
                                 audio_provider=audio_getter_info.parser_info.full_name,
                                 uniqueness_postfix=str(abs(hash(link)))[:8],
                                 card_data=self.dict_card_data))
                for link in audio_links
            ))

        chosen_smth = False
        last_audio_getter_data: App.AudioGetterInfo
        audio_getters_audios: list[str] = []
        for labeled_frame in self.audio_inner_frame.winfo_children():
            current_audio_getter_data: App.AudioGetterInfo = labeled_frame.audio_getter_data
            if audio_getters_audios:
                add_audio_data_to_card(audio_getter_info=last_audio_getter_data,
                                       audio_links=audio_getters_audios)  # dictionary audios go without any labels
            last_audio_getter_data = current_audio_getter_data
            audio_getters_audios = []

            for audio_frame in labeled_frame.winfo_children():
                if audio_frame.boolvar.get():
                    chosen_smth = True
                    audio_getters_audios.append(audio_frame.audio_data)

        if audio_getters_audios:
            add_audio_data_to_card(audio_getter_info=last_audio_getter_data,
                                   audio_links=audio_getters_audios)

        audio_autochoose_mode: Literal["off",
                                       "first_default_audio",
                                       "all_default_audios",
                                       "first_available_audio",
                                       "first_available_audio_source",
                                       "all"]
        if not chosen_smth and (audio_autochoose_mode := self.configurations["app"]["audio_autochoose_mode"]) != "off":
            # if audio_autochoose_mode in ("all", "first_default_audio", "all_default_audios"):
            dictionary_audio_links = self.dict_card_data.get(CardFields.audio_links, [])
            add_audio_data_to_card(
                audio_getter_info=App.AudioGetterInfo(
                    parser_info=TypedParserName(
                        parser_t=ParserType.web, 
                        name=f"dict! {TypedParserName.split_full_name(self.current_card_parser_name).name}" if self.current_card_parser_name else ""),
                    fetching_word=self.word),
                audio_links=dictionary_audio_links[:1 if audio_autochoose_mode in ("first_default_audio", "first_available_audio") else 9999])
                
            word_for_audio_query = self.audio_search_entry.get()
            already_found_first_source = dictionary_audio_links and audio_autochoose_mode in ("first_available_audio", "first_available_audio_source")
            if self.external_audio_generator is not None and not already_found_first_source and (audio_autochoose_mode in ("all", "first_available_audio", "first_available_audio_source")):
                self.external_audio_generator.force_update(word_for_audio_query, self.dict_card_data)
                audio_data_pack = self.external_audio_generator.get(word=word_for_audio_query,
                                                                    card_data=self.dict_card_data,
                                                                    batch_size=1 if audio_autochoose_mode == "first_available_audio" else 9999)
                if audio_data_pack is not None:
                    for generator_results in audio_data_pack[:1 if audio_autochoose_mode in ("first_default_audio", "first_available_audio_source") else 9999]:
                        add_audio_data_to_card(
                            audio_getter_info=App.AudioGetterInfo(
                                parser_info=TypedParserName(
                                    parser_t=generator_results.parser_info.parser_t, 
                                    name=generator_results.parser_info.name),
                                fetching_word=self.word),
                            audio_links=[link for (link, _) in generator_results.result])

        if (hierarchical_prefix := self.tag_prefix_field.get().strip()):
            additional[SavedDataDeck.HIERARCHICAL_PREFIX] = hierarchical_prefix

        if additional:
            self.dict_card_data[SavedDataDeck.ADDITIONAL_DATA] = additional

        self.dict_card_data[CardFields.sentences] = list(self.chosen_sentences.values())
        
        self.saved_cards_data.append(status=CardStatus.ADD, card_data=self.dict_card_data)
        if not self.deck.get_n_cards_left():
            self.deck.append((ParserType.custom.prefix(), Card(self.dict_card_data)))
        self.refresh()

    @error_handler(show_exception_logs)
    def choose_sentence(self, pressed_button: Button, sentence_number: int):
        if sentence_number >= len(self.sentence_texts):
            return
 
        self.fill_search_fields()

        self.dict_card_data[CardFields.word] = self.word
        self.dict_card_data[CardFields.definition] = self.definition

        picked_sentence = self.get_sentence(sentence_number)
        if not picked_sentence:
            picked_sentence = self.dict_card_data[CardFields.word]
        
        text_widget = self.sentence_texts[sentence_number]
        if self.chosen_sentences.get(sentence_number) is None:
            self.chosen_sentences[sentence_number] = picked_sentence
            pressed_button["background"] = "red"
            text_widget["state"] = "disabled"
            text_widget["fg"] = text_widget.placeholder_fg_color
        else:
            self.chosen_sentences.pop(sentence_number)
            pressed_button["background"] = self.theme.button_cfg.get("background", "SystemButtonFace")
            text_widget["state"] = "normal"
            text_widget["fg"] = text_widget.default_fg_color

    @error_handler(show_exception_logs)
    def move_decks_pointers(self, n: int):
        self.saved_cards_data.move(min(n, self.deck.get_n_cards_left()))
        self.deck.move(n - 1)
        self.refresh()

    @error_handler(show_exception_logs)
    def open_anki_browser(self, word: str):
        @error_handler(self.show_exception_logs)
        def invoke(action, **params):
            def request_anki(action, **params):
                return {'action': action, 'params': params, 'version': 6}

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

    def add_sentence_field(self,
                           source: str,
                           sentence: str,
                           text_widgets_frame,
                           text_widgets_sf,
                           sentence_text_widgets_list,
                           choose_sentence_action: Callable[[Button, int], None]) -> Button:
        OPTIMAL_TEXT_HEIGHT = 80

        next_index = len(sentence_text_widgets_list) + 1

        if text_widgets_frame.last_getter_label != source:
            text_widgets_frame.last_getter_label = source
            text_widgets_frame.source_display_frame = LabelFrame(text_widgets_frame,
                                                                 text=source,
                                                                 fg=self.theme.button_cfg.get("foreground"),
                                                                 **self.theme.frame_cfg)
            text_widgets_sf.bind_scroll_wheel(text_widgets_frame.source_display_frame)
            text_widgets_frame.source_display_frame.grid_columnconfigure(0, weight=1)
            text_widgets_frame.source_display_frame.pack(side="top", fill="both")

        choose_frame = self.Frame(text_widgets_frame.source_display_frame, height=OPTIMAL_TEXT_HEIGHT)
        choose_frame.grid(row=len(sentence_text_widgets_list), column=0, sticky="we", pady=(0, self.text_pady))
        text_widgets_sf.bind_scroll_wheel(choose_frame)

        choose_frame.grid_columnconfigure(0, weight=1)
        choose_frame.grid_rowconfigure(0, weight=1)
        choose_frame.grid_propagate(False)

        sentence_text = self.Text(
            choose_frame,
            placeholder=f"{self.lang_pack.sentence_text_placeholder_prefix} {next_index}")
        sentence_text.insert(1.0, sentence)
        sentence_text.grid(row=0, column=0, sticky="we")
        text_widgets_sf.bind_scroll_wheel(sentence_text)

        choose_button = self.Button(choose_frame,
                                    text=f"{next_index}",
                                    width=3)
        choose_button["command"] = lambda button=choose_button, index=len(sentence_text_widgets_list): choose_sentence_action(button, index)
        choose_button.grid(row=0, column=1, sticky="ns")
        text_widgets_sf.bind_scroll_wheel(choose_button)

        sentence_text_widgets_list.append(sentence_text)
        return choose_button

    @error_handler(show_exception_logs)
    def refresh(self) -> bool:
        self.last_refresh_call_time = time.time()
        self.waiting_for_audio_display = False
        self.tried_to_display_audio_getters_on_refresh = False

        self.current_card_parser_name, dict_card_data = self.deck.get_card()
        self.chosen_sentences = {}
        self.dict_card_data = dict_card_data.to_dict()
        self.card_processor.process_card(self.dict_card_data)

        self.audio_inner_frame.destroy()
        self.audio_inner_frame = self.audio_sf.display_widget(self.Frame, fit_width=True)
        self.audio_sf.bind_scroll_wheel(self.audio_inner_frame)
        self.audio_inner_frame.last_getter_label = None
        self.audio_inner_frame.source_display_frame = None

        self.sentence_texts.clear()
        self.choosing_buttons.clear()
        self.text_widgets_frame.destroy()
        self.text_widgets_frame = self.text_widgets_sf.display_widget(self.Frame, fit_width=True)
        self.text_widgets_sf.bind_scroll_wheel(self.text_widgets_frame)
        self.text_widgets_frame.last_getter_label = None
        self.text_widgets_frame.source_display_frame = None

        title = f"{self.lang_pack.main_window_cards_left}: {self.deck.get_n_cards_left()}"
        self.title(f"{self.current_card_parser_name}. " + title if self.current_card_parser_name else title)

        self.word_text.focus()
        self.word_text.clear()
        self.audio_search_entry.clear()
        self.sentence_search_entry.clear()

        if (word_data := self.dict_card_data.get(CardFields.word, "")):
            self.word_text.insert(1.0, word_data)
            self.audio_search_entry.insert(0, word_data)
            self.sentence_search_entry.insert(0, word_data)
        else:
            self.audio_search_entry.fill_placeholder()
            self.sentence_search_entry.fill_placeholder()

        self.external_sentence_fetcher.force_update(word_data, self.dict_card_data)
        if self.dict_card_data.get(CardFields.sentences) is None: 
            self.dict_card_data[CardFields.sentences] = []

        dict_sentences = self.dict_card_data[CardFields.sentences]
        dict_sentences.append("")
        for sentence in dict_sentences:
            self.choosing_buttons.append(
                self.add_sentence_field(
                    source="",
                    sentence=sentence,
                    text_widgets_frame=self.text_widgets_frame,
                    text_widgets_sf=self.text_widgets_sf,
                    sentence_text_widgets_list=self.sentence_texts,
                    choose_sentence_action=self.choose_sentence)
            )

        @error_handler(self.show_exception_logs)
        def fill_additional_dict_data(widget: Text, text: str):
            widget["state"] = "normal"
            widget.clear()
            widget.insert(1.0, text)
            widget["state"] = "disabled"

        fill_additional_dict_data(self.dict_tags_field, 
                                  Card.get_str_dict_tags(card_data=self.dict_card_data,
                                                         tag_processor=lambda x:x.replace(" ", "_")))
        fill_additional_dict_data(self.special_field, " ".join(self.dict_card_data.get(CardFields.special, [])))

        self.definition_text.clear()
        self.definition_text.insert(1.0, self.dict_card_data.get(CardFields.definition, ""))
        self.definition_text.fill_placeholder()

        if (audio_sources := self.dict_card_data.get(CardFields.audio_links)) is not None and audio_sources:
            self.display_audio_on_frame(
                word=self.word,
                card_data=self.dict_card_data,
                generator_results=[GeneratorReturn(generator_type=ParserType.web,
                                                   name=f"dict! {TypedParserName.split_full_name(self.current_card_parser_name).name}",
                                                   error_message="",
                                                   result=[(audio_link, "") for audio_link in audio_sources])],
                show_errors=False,
                audio_sf=self.audio_sf,
                audio_inner_frame=self.audio_inner_frame,
                is_picked=False,
            )

        if not self.dict_card_data:
            self.fetch_images_button["text"] = self.lang_pack.fetch_images_button_normal_text
            return False

        if self.dict_card_data.get(CardFields.img_links, []):
            self.fetch_images_button["text"] = self.lang_pack.fetch_images_button_normal_text + \
                                               self.lang_pack.fetch_images_button_image_link_encountered_postfix
        else:
            self.fetch_images_button["text"] = self.lang_pack.fetch_images_button_normal_text

        def display_audio_getters_results_on_refresh():
            if self.tried_to_display_audio_getters_on_refresh:
                return

            if (time.time() - self.last_refresh_call_time) > 0.1:
                self.waiting_for_audio_display = True
                self.tried_to_display_audio_getters_on_refresh = True
                self.display_audio_getter_results(
                    word=self.word,
                    card_data=self.dict_card_data,
                    show_errors=False,
                    audio_sf=self.audio_sf,
                    audio_inner_frame=self.audio_inner_frame
                )
            else:
                if self.waiting_for_audio_display:
                    return

                self.after(300, display_audio_getters_results_on_refresh)
                self.waiting_for_audio_display = True

        if self.external_audio_generator is not None and word_data:
            self.external_audio_generator.force_update(word_data, self.dict_card_data)
            display_audio_getters_results_on_refresh()
        return True

    @error_handler(show_exception_logs)
    def start_image_search(self,
                           word: str,
                           card_data: dict,
                           init_urls: list[str],
                           init_local_images_paths: list[str],
                           image_path_saving_method: Callable[[list[str]], None]):
        @error_handler(self.show_exception_logs)
        def connect_images_to_card(instance: ImageSearch):
            for path in init_local_images_paths:
                if os.path.isfile(path):
                    os.remove(path)

            names: list[str] = []
            for i in range(len(instance.working_state)):
                if instance.working_state[i]:
                    saving_name = "{}/{}" \
                        .format(self.configurations["directories"]["media_dir"],
                                self.card_processor
                                .get_save_image_name(word,
                                                     instance.images_source[i],
                                                     self.configurations["scrappers"]["image"]["name"],
                                                     card_data))
                    instance.preprocess_image(img=instance.saving_images[i],
                                              width=self.configurations["image_search"]["saving_image_width"],
                                              height=self.configurations["image_search"]["saving_image_height"]) \
                        .save(saving_name)
                    names.append(saving_name)

            image_path_saving_method(names)

            x, y = instance.geometry().split(sep="+")[1:]
            self.configurations["image_search"]["starting_position"] = f"+{x}+{y}"

        button_pady = button_padx = 10
        height_lim = self.winfo_height() * 7 // 8
        image_finder = ImageSearch(master=self,
                                   main_params=self.theme.toplevel_cfg,
                                   search_term=word,
                                   saving_dir=self.configurations["directories"]["media_dir"],
                                   url_scrapper=self.external_image_generator,
                                   init_urls=init_urls,
                                   local_images=init_local_images_paths,
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
