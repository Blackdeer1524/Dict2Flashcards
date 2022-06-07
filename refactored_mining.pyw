import json
import os
import re
from tkinter import Button, Menu, IntVar
from tkinter import Frame
from tkinter import Label
from tkinter import Toplevel
from tkinter import messagebox
from tkinter.filedialog import askopenfilename, askdirectory
from typing import Any

from tkinterdnd2 import Tk

from consts.card_fields import FIELDS
from consts.paths import *
from utils.cards import Deck, SentenceFetcher, SavedDeck, CardStatus
from utils.error_handling import create_exception_message
from utils.plugins import plugins
from utils.search_checker import ParsingException
from utils.search_checker import get_card_filter
from utils.storages import validate_json
from utils.widgets import EntryWithPlaceholder as Entry
from utils.widgets import ScrolledFrame
from utils.widgets import TextWithPlaceholder as Text
from utils.window_utils import get_option_menu
from utils.window_utils import spawn_toplevel_in_center
from utils.cards import Card
from utils.image_utils import ImageSearch
from utils.string_utils import remove_special_chars


class App(Tk):
    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)
        self.configurations, error_code = App.load_conf_file()
        if error_code:
            self.destroy()
            return

        self.save_conf_file()

        self.history = App.load_history_file()
        if not self.history.get(self.configurations["directories"]["last_open_file"]):
            self.history[self.configurations["directories"]["last_open_file"]] = 0

        if self.configurations["scrappers"]["word_parser_type"] == "web":
            cd = plugins.get_web_card_generator(self.configurations["scrappers"]["word_parser_name"])
        elif self.configurations["scrappers"]["word_parser_type"] == "local":
            cd = plugins.get_local_card_generator(self.configurations["scrappers"]["word_parser_name"])
        else:
            raise NotImplemented("Unknown word_parser_type: {}!".format(self.configurations["scrappers"]["word_parser_type"]))

        self.deck = Deck(deck_path=self.configurations["directories"]["last_open_file"],
                         current_deck_pointer=self.history[self.configurations["directories"]["last_open_file"]],
                         card_generator=cd)
        self.dict_card_data: dict = {}
        self.sentence_parser = plugins.get_sentence_parser(self.configurations["scrappers"]["base_sentence_parser"])
        self.image_parser = plugins.get_image_parser(self.configurations["scrappers"]["base_image_parser"])

        self.sentence_batch_size = 5
        self.sentence_fetcher = SentenceFetcher(sent_fetcher=self.sentence_parser,
                                                sentence_batch_size=self.sentence_batch_size)


        deck_name = os.path.basename(self.configurations["directories"]["last_open_file"]).split(sep=".")[0]
        saving_path = "{}/{}".format(self.configurations["directories"]["last_save_dir"], deck_name + ".csv")
        self.saved_cards = SavedDeck(saving_path=saving_path)

        main_menu = Menu(self)
        filemenu = Menu(main_menu, tearoff=0)
        filemenu.add_command(label="Создать", command=App.func_placeholder)
        filemenu.add_command(label="Открыть", command=App.func_placeholder)
        filemenu.add_command(label="Сохранить", command=App.func_placeholder)
        filemenu.add_separator()
        filemenu.add_command(label="Справка", command=App.func_placeholder)
        filemenu.add_separator()
        filemenu.add_command(label="Скачать аудио", command=App.func_placeholder)
        filemenu.add_separator()
        filemenu.add_command(label="Сменить пользователя", command=App.func_placeholder)
        main_menu.add_cascade(label="Файл", menu=filemenu)

        main_menu.add_command(label="Добавить", command=self.add_word_dialog)
        main_menu.add_command(label="Перейти", command=self.find_dialog)
        main_menu.add_command(label="Статистика", command=self.statistics_dialog)

        theme_menu = Menu(main_menu, tearoff=0)
        self.index2theme_map = {0: "white",
                                1: "dark"}
        self.theme2index_map = {value: key for key, value in self.index2theme_map.items()}

        self.theme_index_var = IntVar(value=self.theme2index_map[self.configurations["app"]["theme"]])
        theme_menu.add_radiobutton(label="Светлая", variable=self.theme_index_var, value=0, command=App.func_placeholder)
        theme_menu.add_radiobutton(label="Тёмная", variable=self.theme_index_var, value=1, command=App.func_placeholder)
        main_menu.add_cascade(label="Тема", menu=theme_menu)

        main_menu.add_command(label="Anki", command=App.func_placeholder)
        main_menu.add_command(label="Выход", command=App.func_placeholder)
        self.config(menu=main_menu)

        self.browse_button = Button(self, text="Найти в браузере", command=App.func_placeholder)
        self.configurations_word_parser_button = Button(self, text="Настроить словарь", command=App.func_placeholder)
        self.find_image_button = Button(self, text="Добавить изображение", command=self.start_image_search)
        self.image_word_parsers_names = list(plugins.image_parsers)
        
        self.image_word_parser_name = self.configurations["scrappers"]["base_image_parser"]
        self.image_parser_option_menu = get_option_menu(self,
                                                        init_text=self.image_word_parser_name,
                                                        values=self.image_word_parsers_names,
                                                        command=App.func_placeholder,
                                                        widget_configuration={},
                                                        option_submenu_params={})
        self.sentence_button_text = "Добавить предложения"
        self.add_sentences_button = Button(self, text=self.sentence_button_text,
                                           command=self.replace_sentences)
        self.sentence_word_parser_name = self.configurations["scrappers"]["base_sentence_parser"]
        self.sentence_parser_option_menu = get_option_menu(self,
                                                           init_text=self.sentence_word_parser_name,
                                                           values=list(plugins.web_sent_parsers),
                                                           command=App.func_placeholder,
                                                           widget_configuration={},
                                                           option_submenu_params={})

        self.word_text = Text(self, placeholder="Слово", height=2)
        self.alt_terms_field = Text(self, relief="ridge", state="disabled", height=1)
        self.definition_text = Text(self, placeholder="Значение")

        self.sent_text_list = []
        self.sent_button_list = []
        button_width = 3
        for i in range(5):
            self.sent_text_list.append(Text(self, placeholder=f"Предложение {i + 1}"))
            self.sent_text_list[-1].fill_placeholder()
            self.sent_button_list.append(Button(self,
                                                text=f"{i + 1}",
                                                command=lambda x=i: self.choose_sentence(x),
                                                width=button_width))

        self.delete_button = Button(self, text="Del", command=self.delete_command, width=button_width)
        self.prev_button = Button(self, text="Prev", command=self.prev_command, state="disabled", width=button_width)
        self.sound_button = Button(self, text="Play", command=App.func_placeholder, width=button_width)
        self.anki_button = Button(self, text="Anki", command=App.func_placeholder, width=button_width)
        self.bury_button = Button(self, text="Bury", command=App.func_placeholder, width=button_width)

        self.user_tags_field = Entry(self, placeholder="Тэги")
        self.user_tags_field.fill_placeholder()

        self.tag_prefix_field = Entry(self, justify="center", width=8)
        self.tag_prefix_field.insert(0, self.configurations["tags"]["hierarchical_pref"])
        self.dict_tags_field = Text(self, relief="ridge", state="disabled", height=2)

        Text_padx = 10
        Text_pady = 2
        # Расстановка виджетов
        self.browse_button.grid(row=0, column=0, padx=(Text_padx, 0), pady=(Text_pady, 0), sticky="news", columnspan=4)
        self.configurations_word_parser_button.grid(row=0, column=4, padx=(0, Text_padx), pady=(Text_pady, 0),
                                            columnspan=4, sticky="news")

        self.word_text.grid(row=1, column=0, padx=Text_padx, pady=Text_pady, columnspan=8, sticky="news")

        self.alt_terms_field.grid(row=2, column=0, padx=Text_padx, columnspan=8, sticky="news")

        self.find_image_button.grid(row=3, column=0, padx=(Text_padx, 0), pady=Text_pady, sticky="news", columnspan=4)
        self.image_parser_option_menu.grid(row=3, column=4, padx=(0, Text_padx), pady=Text_pady, columnspan=4,
                                           sticky="news")

        self.definition_text.grid(row=4, column=0, padx=Text_padx, columnspan=8, sticky="news")

        self.add_sentences_button.grid(row=5, column=0, padx=(Text_padx, 0), pady=Text_pady, sticky="news", columnspan=4)
        self.sentence_parser_option_menu.grid(row=5, column=4, padx=(0, Text_padx), pady=Text_pady, columnspan=4,
                                              sticky="news")

        for i in range(5):
            c_pady = Text_pady if i % 2 else 0
            self.sent_text_list[i].grid(row=6 + i, column=0, columnspan=6, padx=Text_padx, pady=c_pady, sticky="news")
            self.sent_button_list[i].grid(row=6 + i, column=6, padx=0, pady=c_pady, sticky="ns")

        self.delete_button.grid(row=6, column=7, padx=Text_padx, pady=0, sticky="ns")
        self.prev_button.grid(row=7, column=7, padx=Text_padx, pady=Text_pady, sticky="ns")
        self.sound_button.grid(row=8, column=7, padx=Text_padx, pady=0, sticky="ns")
        self.anki_button.grid(row=9, column=7, padx=Text_padx, pady=Text_pady, sticky="ns")
        self.bury_button.grid(row=10, column=7, padx=Text_padx, pady=0, sticky="ns")

        self.user_tags_field.grid(row=11, column=0, padx=Text_padx, pady=Text_pady, columnspan=6,
                                  sticky="news")
        self.tag_prefix_field.grid(row=11, column=6, padx=(0, Text_padx), pady=Text_pady, columnspan=2,
                                   sticky="news")
        self.dict_tags_field.grid(row=12, column=0, padx=Text_padx, pady=(0, Text_padx), columnspan=8,
                                  sticky="news")
        for i in range(6):
            self.grid_columnconfigure(i, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(6, weight=1)
        self.grid_rowconfigure(7, weight=1)
        self.grid_rowconfigure(8, weight=1)
        self.grid_rowconfigure(9, weight=1)
        self.grid_rowconfigure(10, weight=1)

        def focus_next_window(event):
            event.widget.tk_focusNext().focus()
            return "break"

        def focus_prev_window(event):
            event.widget.tk_focusPrev().focus()
            return "break"

        self.new_order = [self.browse_button, self.word_text, self.find_image_button, self.definition_text,
                          self.add_sentences_button] + self.sent_text_list + \
                         [self.user_tags_field] + self.sent_button_list + [self.delete_button, self.prev_button,
                                                                       self.anki_button, self.bury_button,
                                                                       self.tag_prefix_field]

        for widget_index in range(len(self.new_order)):
            self.new_order[widget_index].lift()
            self.new_order[widget_index].bind("<Tab>", focus_next_window)
            self.new_order[widget_index].bind("<Shift-Tab>", focus_prev_window)

        self.bind("<Escape>", lambda event: self.on_closing())
        self.bind("<Control-Key-0>", lambda event: self.geometry("+0+0"))
        self.bind("<Control-d>", lambda event: self.delete_command())
        self.bind("<Control-q>", lambda event: self.func_placeholder())
        self.bind("<Control-s>", lambda event: self.save_button())
        self.bind("<Control-f>", lambda event: self.find_dialog())
        self.bind("<Control-e>", lambda event: self.statistics_dialog())
        self.bind("<Control-Shift_L><A>", lambda event: self.add_word_dialog())
        self.bind("<Control-z>", lambda event: self.prev_command())
        self.bind("<Control-Key-1>", lambda event: self.choose_sentence(0))
        self.bind("<Control-Key-2>", lambda event: self.choose_sentence(1))
        self.bind("<Control-Key-3>", lambda event: self.choose_sentence(2))
        self.bind("<Control-Key-4>", lambda event: self.choose_sentence(3))
        self.bind("<Control-Key-5>", lambda event: self.choose_sentence(4))

        self.minsize(500, 0)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.refresh()
        self.geometry(self.configurations["app"]["main_window_geometry"])
        self.configure()

    def show_errors(self, *args, **kwargs):
        error_log = create_exception_message()

        error_handler_toplevel = Toplevel(self)
        error_handler_toplevel.title("Ошибка")
        sf = ScrolledFrame(error_handler_toplevel, scrollbars="both")
        sf.pack(side="top", expand=1, fill="both")
        sf.bind_scroll_wheel(error_handler_toplevel)
        inner_frame = sf.display_widget(Frame)
        label = Label(inner_frame, text=error_log, justify="left")
        label.pack()
        label.update()
        sf.config(width=min(1000, label.winfo_width()), height=min(500, label.winfo_height()))
        error_handler_toplevel.resizable(False, False)
        error_handler_toplevel.bind("<Escape>", lambda event: error_handler_toplevel.destroy())
        error_handler_toplevel.grab_set()

        self.clipboard_clear()
        self.clipboard_append(error_log)

    def delete_command(self):
        if self.deck.get_n_cards_left():
            self.saved_cards.append(CardStatus.DELETE)
        self.refresh()

    def prev_command(self):
        self.deck.move(-2)
        self.saved_cards.move(-1)
        self.refresh()

    @staticmethod
    def func_placeholder():
        return 0

    @staticmethod
    def load_history_file() -> dict:
        if not os.path.exists(HISTORY_FILE_PATH):
            history_json = {}
        else:
            with open(HISTORY_FILE_PATH, "r", encoding="UTF-8") as f:
                history_json = json.load(f)
        return history_json

    def save_conf_file(self):
        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(self.configurations, f, indent=3)

    @staticmethod
    def load_conf_file() -> tuple[dict[str, dict], bool]:
        standard_conf_file = {"app": {"theme": "dark",
                                      "main_window_geometry": "500x800+0+0",
                                      "image_search_position": "+0+0"},
                              "scrappers": {"base_sentence_parser": "web_sentencedict",
                                            "word_parser_type": "web",
                                            "word_parser_name": "cambridge_US",
                                            "base_image_parser": "google",
                                            "local_dict_search_type": 0,
                                            "deck_search_type": 0,
                                            "local_audio": "",
                                            "non_pos_specific_search": False},
                              "tags": {"hierarchical_pref": ""},
                              "directories": {"media_dir": "",
                                              "last_open_file": "",
                                              "last_save_dir": ""},
                              "anki": {"anki_deck": "",
                                       "anki_field": ""}
                              }

        conf_file: dict[str, dict[str, Any]]
        if not os.path.exists(CONFIG_FILE_PATH):
            conf_file = {}  # type: ignore
        else:
            with open(CONFIG_FILE_PATH, "r", encoding="UTF-8") as f:
                conf_file = json.load(f)

        validate_json(checking_scheme=conf_file, default_scheme=standard_conf_file)

        if not conf_file["directories"]["media_dir"] or not os.path.isdir(conf_file["directories"]["media_dir"]):
            conf_file["directories"]["media_dir"] = askdirectory(title="Выберете директорию для медиа файлов",
                                                                 mustexist=True,
                                                                 initialdir=MEDIA_DOWNLOADING_LOCATION)
            if not conf_file["directories"]["media_dir"]:
                return (conf_file, True)
                        
        if not conf_file["directories"]["last_open_file"] or not os.path.isfile(conf_file["directories"]["last_open_file"]):
            conf_file["directories"]["last_open_file"] = askopenfilename(title="Выберете JSON файл со словами",
                                                                         filetypes=(("JSON", ".json"),),
                                                                         initialdir="./")
            if not conf_file["directories"]["last_open_file"]:
                return (conf_file, True)
            
        if not conf_file["directories"]["last_save_dir"] or not os.path.isdir(conf_file["directories"]["last_save_dir"]):
            conf_file["directories"]["last_save_dir"] = askdirectory(title="Выберете директорию сохранения",
                                                                     mustexist=True,
                                                                     initialdir="./")
            if not conf_file["directories"]["last_save_dir"]:
                return (conf_file, True)

        return (conf_file, False)

    def save_files(self):
        """
        Сохраняет файлы если они не пустые или есть изменения
        """
        # получение координат на экране через self.winfo_rootx(), self.winfo_rooty() даёт некоторое смещение
        self.configurations["app"]["main_window_geometry"] = self.geometry()
        self.configurations["tags"]["hierarchical_pref"] = self.tag_prefix_field.get()
        self.save_conf_file()

        self.history[self.configurations["directories"]["last_open_file"]] = self.deck.get_pointer_position() - 1

        self.deck.save()
        with open(HISTORY_FILE_PATH, "w") as saving_f:
            json.dump(self.history, saving_f, indent=4)

        # if self.SKIPPED_FILE:
        #     self.save_skip_file()
    
    def on_closing(self):
        """
        Закрытие программы
        """
        if messagebox.askokcancel("Выход", "Вы точно хотите выйти?"):
            self.save_files()
            # self.bg.stop()
            # if self.AUDIO_INFO:
            #     self.download_audio(closing=True)
            # else:
            #     self.destroy()
            self.destroy()

    def save_button(self):
        messagebox.showinfo(message="Файлы сохранены")
        self.save_files()

    def get_word(self):
        return self.word_text.get(1.0, "end").strip()
    
    def get_definition(self):
        return self.definition_text.get(1.0, "end").rstrip()
    
    def get_sentence(self, n: int):
        return self.sent_text_list[n].get(1.0, "end").rstrip()
    
    def replace_sentences(self) -> None:
        sent_batch, error_message, local_flag = self.sentence_fetcher.get_sentence_batch(self.get_word())
        for text_field in self.sent_text_list:
            text_field.clear()
            text_field.fill_placeholder()
        for i in range(len(sent_batch)):
            self.sent_text_list[i].remove_placeholder()
            self.sent_text_list[i].insert(1.0, sent_batch[i])
        if error_message:
            messagebox.showerror(title="Replace sentences", message=error_message)
        self.add_sentences_button["text"] = self.sentence_button_text if local_flag else self.sentence_button_text + " +"

    def refresh(self) -> bool:
        def fill_dict_tags(text: str):
            self.dict_tags_field["state"] = "normal"
            self.dict_tags_field.clear()
            self.dict_tags_field.insert(1.0, text)
            self.dict_tags_field["state"] = "disabled"

        current_card = self.deck.get_card()
        self.dict_card_data = current_card.to_dict()
        self.prev_button["state"] = "normal" if self.deck.get_pointer_position() != self.deck.get_starting_position() + 1 \
                                             else "disabled"

        self.title(f"Поиск предложений для Anki. Осталось: {self.deck.get_n_cards_left()} слов")

        self.word_text.clear()
        self.word_text.insert(1.0, current_card.get(FIELDS.word, ""))
        self.word_text.focus()

        self.definition_text.clear()
        self.definition_text.insert(1.0, current_card.get(FIELDS.definition, ""))
        self.definition_text.fill_placeholder()

        self.sentence_fetcher(self.get_word(), current_card.get(FIELDS.sentences, []))
        self.replace_sentences()
        if not current_card:
            self.find_image_button["text"] = "Добавить изображение"
            if not self.configurations["scrappers"]["local_audio"]:
                self.sound_button["state"] = "disabled"
            fill_dict_tags("")
            return False
        fill_dict_tags(current_card.get_str_dict_tags())

        # Обновление поля для слова
        alt_terms = " ".join(current_card.get("alt_terms", []))
        self.DICT_IMAGE_LINK = current_card.get("image_link", "")
        if self.DICT_IMAGE_LINK:
            self.find_image_button["text"] = "Добавить изображение ★"
        else:
            self.find_image_button["text"] = "Добавить изображение"
        self.CURRENT_AUDIO_LINK = current_card.get("audio_link", "")

        if self.configurations["scrappers"]["local_audio"] or self.CURRENT_AUDIO_LINK:
            self.sound_button["state"] = "normal"
        else:
            self.sound_button["state"] = "disabled"
        return True

    def add_word_dialog(self):
        def define_word_button():
            clean_word = add_word_entry.get().strip()
            pattern = re.compile(clean_word)
            word_filter = lambda comparable: re.search(pattern, comparable)

            additional_query = additional_filter_entry.get(1.0, "end").strip()
            try:
                additional_filter = get_card_filter(additional_query) if additional_query else None
                if self.deck.add_card_to_deck(query=clean_word, word_filter=word_filter,
                                              additional_filter=additional_filter):
                    add_word_frame.destroy()
                    self.refresh()
                    return
                messagebox.showerror(title="Ошибка!", message="Слово не найдено!")
                add_word_frame.withdraw()
                add_word_frame.deiconify()
            except ParsingException as e:
                messagebox.showerror("Ошибка запроса", str(e))
                add_word_frame.withdraw()
                add_word_frame.deiconify()

        add_word_frame = Toplevel(self)
        add_word_frame.withdraw()

        add_word_frame.grid_columnconfigure(0, weight=1)
        add_word_frame.title("Добавить")

        add_word_entry = Entry(add_word_frame, placeholder="Слово")
        add_word_entry.focus()
        add_word_entry.grid(row=0, column=0, padx=5, pady=3, sticky="we")

        additional_filter_entry = Text(add_word_frame, placeholder="Дополнительный фильтр", height=5)
        additional_filter_entry.grid(row=1, column=0, padx=5, pady=3, sticky="we")

        start_parsing_button = Button(add_word_frame, text="Добавить", command=define_word_button)
        start_parsing_button.grid(row=2, column=0, padx=5, pady=3, sticky="ns")

        add_word_frame.bind_all("<Escape>", lambda event: add_word_frame.destroy())
        add_word_frame.bind_all("<Return>", lambda event: define_word_button())
        add_word_frame.deiconify()
        spawn_toplevel_in_center(master=self, toplevel_widget=add_word_frame,
                                 desired_toplevel_width=self.winfo_width())

    def find_dialog(self):
        def go_to():
            find_query = find_entry.get(1.0, "end").strip()
            if not find_query:
                messagebox.showerror("Ошибка запроса", "Пустой запрос!")
                return

            try:
                searching_filter = get_card_filter(find_query)
            except ParsingException as e:
                messagebox.showerror("Ошибка запроса", str(e))
                find_frame.withdraw()
                find_frame.deiconify()
                return

            if (move_list := self.deck.find_card(searching_func=searching_filter)):
                def rotate(n: int):
                    nonlocal move_list, found_item_number

                    found_item_number += n
                    rotate_frame.title(f"{found_item_number}/{len(move_list) + 1}")

                    if n > 0:
                        current_offset = move_list.get_pointed_item()
                        move_list.move(n)
                    else:
                        move_list.move(n)
                        current_offset = -move_list.get_pointed_item()


                    left["state"] = "disabled" if not move_list.get_pointer_position() else "normal"
                    right["state"] = "disabled" if move_list.get_pointer_position() == len(move_list) else "normal"

                    self.deck.move(current_offset - 1)
                    self.saved_cards.move(current_offset)
                    self.refresh()

                find_frame.destroy()

                found_item_number = 1
                rotate_frame = Toplevel(self)
                rotate_frame.title(f"{found_item_number}/{len(move_list) + 1}")

                left = Button(rotate_frame, text="<", command=lambda: rotate(-1))
                left["state"] = "disabled"
                left.grid(row=0, column=0)

                right = Button(rotate_frame, text=">", command=lambda: rotate(1))
                right.grid(row=0, column=2)

                done = Button(rotate_frame, text="Готово", command=lambda: rotate_frame.destroy())
                done.grid(row=0, column=1)
                spawn_toplevel_in_center(self, rotate_frame)
                rotate_frame.bind_all("<Escape>", lambda _: rotate_frame.destroy())
                return
            messagebox.showerror("Ошибка запроса", "Ничего не найдено!")
            find_frame.withdraw()
            find_frame.deiconify()

        find_frame = Toplevel(self)
        find_frame.withdraw()
        find_frame.title("Перейти")
        find_frame.grid_columnconfigure(0, weight=1)

        find_entry = Text(find_frame, height=5)
        find_entry.grid(row=0, column=0, padx=5, pady=3, sticky="we")
        find_entry.focus()

        find_button = Button(find_frame, text="Перейти", command=go_to)
        find_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
        find_frame.bind_all("<Return>", lambda _: go_to())
        find_frame.bind_all("<Escape>", lambda _: find_frame.destroy())
        find_frame.deiconify()
        spawn_toplevel_in_center(self, find_frame)

    def statistics_dialog(self):
        statistics_window = Toplevel(self)
        statistics_window.withdraw()

        statistics_window.title("Статистика")
        text_list = (('Добавлено', 'Пропущено', 'Удалено', 'Осталось', "Файл", "Директория сохранения", "Медиа"),
                     (self.saved_cards.get_n_added(), self.saved_cards.get_n_buried(), self.saved_cards.get_n_deleted(),
                      self.deck.get_n_cards_left(), self.deck.deck_path,
                      self.configurations["directories"]["last_save_dir"],
                      self.configurations["directories"]["media_dir"]))

        scroll_frame = ScrolledFrame(statistics_window, scrollbars="horizontal")
        scroll_frame.pack()
        scroll_frame.bind_scroll_wheel(statistics_window)
        inner_frame = scroll_frame.display_widget(Frame)
        for row_index in range(len(text_list[0])):
            for column_index in range(2):
                info = Label(inner_frame, text=text_list[column_index][row_index], anchor="center",
                             relief="ridge")
                info.grid(column=column_index, row=row_index, sticky="news")

        statistics_window.bind_all("<Escape>", lambda _: statistics_window.destroy())
        statistics_window.update()
        current_frame_width = inner_frame.winfo_width()
        current_frame_height = inner_frame.winfo_height()
        scroll_frame.config(width=min(self.winfo_width(), current_frame_width),
                            height=min(self.winfo_height(), current_frame_height))
        spawn_toplevel_in_center(self, statistics_window)
        statistics_window.deiconify()

    def choose_sentence(self, sentence_number: int):
        self.dict_card_data[FIELDS.word] = self.get_word()
        self.dict_card_data[FIELDS.definition] = self.get_definition()
        self.dict_card_data[FIELDS.sentences] = [self.get_sentence(sentence_number)]
        self.saved_cards.append(status=CardStatus.ADD, card_data=self.dict_card_data)
        if not self.deck.get_n_cards_left():
            self.deck.append(Card(self.dict_card_data))
        self.refresh()

    def start_image_search(self):
        def connect_images_to_card(instance: ImageSearch):
            nonlocal word

            clean_word = remove_special_chars(word, sep='-')
            name_pattern = f"mined-{clean_word}" + "-{}.png"

            names: list[str] = []
            for i in range(len(instance.working_state)):
                if instance.working_state[i]:
                    saving_name = "{}/{}"\
                        .format(self.configurations["directories"]["media_dir"],
                                name_pattern.format(hash(instance.images_source[i])))
                    instance.saving_images[i].save(saving_name)
                    names.append(saving_name)

            if (paths := self.dict_card_data.get(self.saved_cards.IMAGES_DATA)) is not None:
                for path in paths:
                    if os.path.isfile(path):
                        os.remove(path)

            if names:
                self.dict_card_data[self.saved_cards.IMAGES_DATA] = names

            x, y = instance.geometry().split(sep="+")[1:]
            self.configurations["app"]["image_search_position"] = f"+{x}+{y}"

        word = self.get_word()

        show_image_width = 250


        button_pady = button_padx = 10
        height_lim = self.winfo_height() * 7 // 8
        image_finder = ImageSearch(master=self,
                                   search_term=word,
                                   saving_dir=self.configurations["directories"]["media_dir"],
                                   url_scrapper=self.image_parser,
                                   init_urls=self.dict_card_data.get(FIELDS.img_links, []),
                                   local_images=self.dict_card_data.get(self.saved_cards.IMAGES_DATA, []),
                                   # headers=self.headers,
                                   on_close_action=connect_images_to_card,
                                   show_image_width=show_image_width,
                                   saving_image_width=300,
                                   button_padx=button_padx, button_pady=button_pady,
                                   window_height_limit=height_lim,
                                   on_closing_action=connect_images_to_card,
                                   #window_bg=self.main_bg,
                                   #command_button_params=self.button_cfg,
                                   #entry_params=self.entry_cfg
                                   )
        image_finder.focus()
        image_finder.grab_set()
        image_finder.geometry(self.configurations["app"]["image_search_position"])
        image_finder.start()


if __name__ == "__main__":
    root = App()
    root.mainloop()
