import importlib
import json
import os
import re
import sys
import csv
import string
import pkgutil
import time
import traceback
from functools import partial
from pathlib import Path
from pprint import pprint
from tkinter import Tk, Label, Button, Checkbutton, Toplevel, OptionMenu, Menu, Frame, \
    BooleanVar, StringVar, IntVar, END, NORMAL, DISABLED
from tkinter import messagebox
from tkinter import ttk
from tkinter.filedialog import askopenfilename, askdirectory

import requests
from playsound import playsound
from pydub import AudioSegment
from requests.exceptions import Timeout, ConnectionError, RequestException

from parsers import image_parsers, word_parsers, sentence_parsers
from utils import ScrolledFrame, ImageSearch, TextWithPlaceholder, EntryWithPlaceholder


def save_history_file():
    with open("./history.json", "w") as saving_f:
        json.dump(JSON_HISTORY_FILE, saving_f, indent=3)


def save_conf_file():
    with open(CONF_FILE, "w") as f:
        json.dump(JSON_CONF_FILE, f, indent=3)


if not os.path.exists("./temp/"):
    os.makedirs("./temp")

if not os.path.exists("./Cards/"):
    os.makedirs("./Cards")

if not os.path.exists("./Words/"):
    os.makedirs("./Words")

custom_file_path = "./Words/custom.json"
if not os.path.exists(custom_file_path):
    with open(custom_file_path, "w", encoding="UTF-8") as custom_file:
        json.dump([], custom_file)

HISTORY_FILE = Path("./history.json")
if HISTORY_FILE.is_file():
    with open(HISTORY_FILE, "r") as read_file:
        JSON_HISTORY_FILE = json.load(read_file)
else:
    JSON_HISTORY_FILE = {}
    save_history_file()

CONF_FILE = Path("./config.json")
if CONF_FILE.is_file():
    with open(CONF_FILE, "r") as read_file:
        JSON_CONF_FILE = json.load(read_file)
else:
    JSON_CONF_FILE = {"theme": "dark",
                      "main_window_position": "",
                      "image_search_position": "+0+0",
                      "base_sentence_parser": "web_sentencedict",
                      "base_word_parser": "web_cambridge_UK",
                      "base_image_parser": "google",
                      "media_dir": "",
                      "last_open_file": "",
                      "last_save_dir": "",
                      "hierarchical_pref": "eng",
                      "include_domain": True,
                      "include_level": True,
                      "include_region": True,
                      "include_usage": True,
                      "include_pos": True,
                      "is_hierarchical": True,
                      "anki_deck": "",
                      "anki_field": ""}
    save_conf_file()

if JSON_CONF_FILE["theme"] == "dark":
    button_bg = "#3a3a3a"
    text_bg = "#3a3a3a"
    widget_fg = "#FFFFFF"
    text_selectbackground = "#F0F0F0"
    text_selectforeground = "#000000"
    main_bg = "#2f2f31"

elif JSON_CONF_FILE["theme"] == "white":
    button_bg = "#E1E1E1"
    text_bg = "#FFFFFF"
    widget_fg = "SystemWindowText"
    text_selectbackground = "SystemHighlight"
    text_selectforeground = "SystemHighlightText"
    main_bg = "#F0F0F0"

button_params = {"background": button_bg, "foreground": widget_fg,
                     "activebackground": button_bg, "activeforeground": text_selectbackground}
entry_params = {"background": text_bg, "foreground": widget_fg, "selectbackground": text_selectbackground,
                   "selectforeground": text_selectforeground, "insertbackground": text_selectbackground}

Label = partial(Label, background=main_bg, foreground=widget_fg)
Button = partial(Button, **button_params)
Text = partial(TextWithPlaceholder, background=text_bg, foreground=widget_fg, selectbackground=text_selectbackground,
               selectforeground=text_selectforeground, insertbackground=text_selectbackground)
Entry = partial(EntryWithPlaceholder, **entry_params)
Checkbutton = partial(Checkbutton, background=main_bg, foreground=widget_fg,
                      activebackground=main_bg, activeforeground=widget_fg, selectcolor=main_bg)
Toplevel = partial(Toplevel, bg=main_bg)


def error_handler(callback=None):
    def error_decorator(func):
        def function_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if callback is None:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    error_log = ''.join(lines)
                    pprint(error_log)
                else:
                    callback(e)
        return function_wrapper
    return error_decorator


def show_errors(exception):
    # Для работы функций, которые вызывают StopIteration
    if type(exception) != StopIteration:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        error_log = ''.join(lines)

        error_handler_toplevel = Toplevel(root)
        error_handler_toplevel.title("Ошибка")
        sf = ScrolledFrame(error_handler_toplevel, scrollbars="both")
        sf.pack(side="top", expand=1, fill="both")
        sf.bind_scroll_wheel(error_handler_toplevel)
        inner_frame = sf.display_widget(partial(Frame, bg=main_bg))
        label = Label(inner_frame, text=error_log, justify="left")
        label.pack()
        label.update()
        sf.config(width=min(1000, label.winfo_width()), height=min(500, label.winfo_height()))
        error_handler_toplevel.resizable(0, 0)
        error_handler_toplevel.bind("<Escape>", lambda event: error_handler_toplevel.destroy())
        error_handler_toplevel.grab_set()

        root.clipboard_clear()
        root.clipboard_append(error_log)
    else:
        raise StopIteration


def remove_special_chars(text, sep=" ", special_chars=string.punctuation):
    """
    :param text: to to clean
    :param sep: replacement for special chars
    :param special_chars: special characters to remove

    chars: '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'

    :return:
    """
    for char in special_chars + " ":
        text = text.replace(char, sep)
    text = re.sub(f"({sep})+", text, sep)
    return text.strip(sep)


@error_handler(callback=show_errors)
def get_center_spawn_conf(width, height):
    """
    :param width: current window width
    :param height: current window height
    :return: window spawn conf
    """
    # получение координат на экране через root.winfo_rootx(), root.winfo_rooty() даёт некоторое смещение
    root_x, root_y = root.winfo_geometry().split(sep="+")[1:]
    root_center_x = int(root_x) + WIDTH // 2
    root_center_y = int(root_y) + HEIGHT // 2
    window_size = f"{width}x{height}"
    spawn_cords = f"+{root_center_x - width // 2}+{root_center_y - height // 2}"
    return window_size + spawn_cords


def spawn_toplevel(toplevel_widget, w=0, h=0):
    toplevel_widget.update()
    width = w if w else toplevel_widget.winfo_width()
    height = h if h else toplevel_widget.winfo_height()
    progress_spawn_conf = get_center_spawn_conf(width, height)
    toplevel_widget.geometry(progress_spawn_conf)
    toplevel_widget.resizable(0, 0)
    toplevel_widget.grab_set()


def fetch_audio(audio_url, audio_save_path, callback=None):
    r = requests.get(audio_url, timeout=1, headers=headers)
    if r.status_code == 200:
        audio_bin = r.content
        with open(audio_save_path, "wb") as audio_file:
            audio_file.write(audio_bin)
    elif callback is not None:
        callback(audio_url, r.status_code)


@error_handler(callback=show_errors)
def download_audio(choose_file=False, closing=False):
    def record_error(error_type, audio_name):
        if errors["error_types"].get(error_type) is None:
            errors["error_types"][error_type] = 1
        else:
            errors["error_types"][error_type] += 1
        errors["missing_audios"].append(audio_name)

    @error_handler(callback=show_errors)
    def write_audio(audio_url, audio_save_path, label_audio_name=""):
        try:
            fetch_audio(audio_url, audio_save_path, callback=lambda _, status_code: record_error(f"Code {status_code}",
                                                                                                 label_audio_name))
        except RequestException as e:
            exception_type = str(e)
            record_error(exception_type, label_audio_name)

    if choose_file:
        save_files()
        audio_file_name = askopenfilename(title="Выберете JSON файл c аудио", filetypes=(("JSON", ".json"),),
                                          initialdir="./")
        if not audio_file_name:
            return
        with open(audio_file_name, encoding="UTF-8") as audio_file:
            audio_links_list = json.load(audio_file)
    else:
        audio_links_list = AUDIO_LINKS

    progress_toplevel = Toplevel(root)
    progress_toplevel.withdraw()
    progress_toplevel.title("Скачивание аудио...")
    pb = ttk.Progressbar(progress_toplevel,
                         orient='horizontal',
                         mode='determinate',
                         length=WIDTH - 2 * text_padx)
    pb.grid(column=0, row=0, columnspan=2, padx=text_padx, pady=text_pady)
    current_word_label = Label(progress_toplevel)
    current_word_label.grid(column=0, row=1, columnspan=2, sticky="news")

    spawn_toplevel(progress_toplevel)
    progress_toplevel.deiconify()

    length = len(audio_links_list)
    errors = {"error_types": {}, "missing_audios": []}

    def get_next_batch(clear_audio_dict):
        for index, (word, pos, wp_name, current_url) in enumerate(clear_audio_dict, 1):
            yield index, word, pos, wp_name, current_url

    def step(index: int, word: str, pos: str, wp_name: str, current_url: str, skip_copies: bool = False,
             rewrite_copies: bool = False, seen_audios: set = None):
        """
        :param seen_audios:
        :param index:
        :param word:
        :param pos:
        :param wp_name:
        :param current_url:
        :param skip_copies:
        :param rewrite_copies:
        :return:
        """
        nonlocal batch_generator, current_word_label, pb, progress_toplevel

        if seen_audios is None:
            seen_audios = set()

        pb["value"] = min(100.0, round(index / length * 100, 2))
        label_audio_name = f"{word} - {pos}"
        current_word_label["text"] = label_audio_name
        progress_toplevel.update()

        temp_audio_name = get_audio_file_name(word, pos, wp_name)
        temp_audio_path = f"./temp/{temp_audio_name}"
        save_audio_name = temp_audio_name.replace('_', '-')
        save_audio_path = f"{MEDIA_DIR}/{save_audio_name}"

        wait_before_next_batch = True
        if save_audio_name not in seen_audios:
            seen_audios.add(save_audio_name)
            if os.path.exists(temp_audio_path):
                os.rename(temp_audio_path, save_audio_path)
                wait_before_next_batch = False
            elif not os.path.exists(save_audio_path) or rewrite_copies:
                write_audio(current_url, save_audio_path, label_audio_name)
            elif skip_copies:
                wait_before_next_batch = False
            else:
                def skip_encounter():
                    nonlocal skip_copies, wait_before_next_batch
                    if apply_to_all_var.get():
                        skip_copies = True
                    wait_before_next_batch = False
                    copy_encounter_tl.destroy()

                def rewrite_encounter():
                    nonlocal rewrite_copies
                    if apply_to_all_var.get():
                        rewrite_copies = True
                    copy_encounter_tl.destroy()
                    progress_toplevel.grab_set()
                    write_audio(current_url, save_audio_path, label_audio_name)

                apply_to_all_var = BooleanVar()

                copy_encounter_tl = Toplevel(progress_toplevel)
                copy_encounter_tl.withdraw()

                message = f"Файл\n  {save_audio_name}  \nуже существует.\nВыберите нужную опцию:"

                encounter_label = Label(copy_encounter_tl, text=message, relief="ridge",
                                        wraplength=progress_toplevel.winfo_width() * 2 // 3,
                                        width=BOTTOM_TEXT_FIELDS_WIDTH)

                skip_encounter_button = Button(copy_encounter_tl, text="Пропустить", command=skip_encounter)
                rewrite_encounter_button = Button(copy_encounter_tl, text="Заменить", command=rewrite_encounter)
                apply_to_all_button = Checkbutton(copy_encounter_tl, variable=apply_to_all_var, text="Применить ко всем")

                encounter_label.grid(row=0, column=0, padx=text_padx, pady=text_pady, sticky="news")
                skip_encounter_button.grid(row=1, column=0, padx=text_padx, pady=text_pady, sticky="news")
                rewrite_encounter_button.grid(row=2, column=0, padx=text_padx, pady=text_pady, sticky="news")
                apply_to_all_button.grid(row=3, column=0, padx=text_padx, pady=text_pady, sticky="news")

                spawn_toplevel(copy_encounter_tl)

                copy_encounter_tl.deiconify()
                copy_encounter_tl.bind("<Escape>", lambda event: copy_encounter_tl.destroy())
                progress_toplevel.wait_window(copy_encounter_tl)
                progress_toplevel.grab_set()
        else:
            wait_before_next_batch = False

        delay = 3_000 if wait_before_next_batch else 0
        try:
            next_index, next_word, next_pos, next_wp_name, next_current_url = next(batch_generator)
            root.after(delay, lambda: step(next_index, next_word, next_pos, next_wp_name, next_current_url,
                                           skip_copies, rewrite_copies, seen_audios))
        except StopIteration:
            if errors["missing_audios"]:
                absent_audio_words = ", ".join(errors['missing_audios'])
                n_errors = f"Количество необработаных слов: {len(errors['missing_audios'])}\n"
                for error_type in errors["error_types"]:
                    n_errors += f"{error_type}: {errors['error_types'][error_type]}\n"

                error_message = f"{n_errors}\n\n{absent_audio_words}"
                messagebox.showerror(message=error_message)
            progress_toplevel.destroy()
            if closing:
                root.destroy()

    clear_audio_dict = [audio_block for audio_block in audio_links_list if audio_block[-1]]
    if clear_audio_dict:
        batch_generator = get_next_batch(clear_audio_dict)
        start_index, start_word, start_pos, start_wp_name, start_current_url = next(batch_generator)
        step(start_index, start_word, start_pos, start_wp_name, start_current_url)
    else:
        progress_toplevel.destroy()
        if closing:
            root.destroy()


def get_audio_file_name(word: str, pos: str, wp_name: str, sep: str = "-") -> str:
    raw_audio_name = f"{remove_special_chars(word, sep=sep)}{sep}{remove_special_chars(pos, sep=sep)}"
    prepared_word_parser_name = remove_special_chars(wp_name, sep=sep)
    audio_name = f"mined{sep}{raw_audio_name}{sep}{prepared_word_parser_name}.mp3"
    return audio_name


def play_sound_file(audio_file_path):
    # возикает ошибка при использовании файлов с "-" или "_" в навании (либо проблема в длине, тут хз)
    wav_path = Path("./temp/placeholder.wav").absolute()
    AudioSegment.from_mp3(audio_file_path).export(wav_path, format="wav")
    playsound(str(wav_path).replace("\\", "/"), block=True)


@error_handler(callback=show_errors)
def play_sound():
    def show_download_error(status_code):
        messagebox.showerror(message=f"Ошибка получения звука\nКод с сервера: {status_code}")

    global word_parser_name
    word = remove_special_chars(word_text.get(1.0, "end").strip())
    pos = DICT_TAGS["pos"][0]

    audio_name = get_audio_file_name(word, pos, word_parser_name)
    save_path = r"{}/temp/{}".format(os.getcwd().replace("\\", "/"), audio_name)
    if not os.path.exists(save_path):
        try:
            fetch_audio(CURRENT_AUDIO_LINK, save_path, callback=lambda _, status_code: show_download_error(status_code))
        except Timeout:
            messagebox.showerror(message="Ошибка получения звука\nПревышено время ожиания.")
        except ConnectionError:
            messagebox.showerror(message="Ошибка получения звука\nПроверьте подключение к интернету.")
    play_sound_file(save_path)


@error_handler(callback=show_errors)
def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


discovered_web_parsers = {}
for finder, name, ispkg in iter_namespace(word_parsers):
    if name.startswith('parsers.word_parsers.web'):
        # [21:] чтобы убрать parsers.word_parsers.
        discovered_web_parsers[name[21:]] = importlib.import_module(name)

LOCAL_DICT = {}
discovered_local_parsers = {}
for item in os.listdir("parsers/word_parsers/"):
    if item.startswith("local"):
        discovered_local_parsers[item] = importlib.import_module(f"parsers.word_parsers.{item}.translate")

discovered_web_sent_parsers = {}
for finder, name, ispkg in iter_namespace(sentence_parsers):
    if name.startswith('parsers.sentence_parsers.web'):
        discovered_web_sent_parsers[name[25:]] = importlib.import_module(name)

discovered_image_parsers = {}
for finder, name, ispkg in iter_namespace(image_parsers):
    discovered_image_parsers[name[22:]] = importlib.import_module(name)

def save_skip_file():
    with open(SKIPPED_FILE_PATH, "w") as saving_f:
        json.dump(SKIPPED_FILE, saving_f, indent=3)


@error_handler(callback=show_errors)
def save_audio_file():
    if AUDIO_LINKS:
        with open(AUDIO_LINKS_PATH, "w", encoding="utf8") as audio_file:
            json.dump(AUDIO_LINKS, audio_file, indent=1)


@error_handler(callback=show_errors)
def save_files():
    """
    Сохраняет файлы если они не пустые или есть изменения
    """
    # получение координат на экране через root.winfo_rootx(), root.winfo_rooty() даёт некоторое смещение
    root_pos = root.winfo_geometry().split(sep="+")[1:]
    JSON_CONF_FILE["main_window_position"] = f"+{root_pos[0]}+{root_pos[1]}"
    JSON_CONF_FILE["hierarchical_pref"] = tag_prefix_field.get()
    JSON_CONF_FILE["include_domain"] = domain_var.get()
    JSON_CONF_FILE["include_level"] = level_var.get()
    JSON_CONF_FILE["include_region"] = region_var.get()
    JSON_CONF_FILE["include_usage"] = usage_var.get()
    JSON_CONF_FILE["include_pos"] = pos_var.get()
    save_conf_file()

    JSON_HISTORY_FILE[WORD_JSON_PATH] = LAST_ITEM - 1

    save_words()
    save_audio_file()

    if LAST_ITEM != 0:
        save_history_file()

    if len(SKIPPED_FILE) != 0:
        save_skip_file()


def autosave():
    save_files()
    root.after(300_000, autosave)  # time in milliseconds


def on_closing():
    """
    Закрытие программы
    """
    if messagebox.askokcancel("Выход", "Вы точно хотите выйти?"):
        save_files()
        if AUDIO_LINKS:
            download_audio(closing=True)
        else:
            root.destroy()


@error_handler(callback=show_errors)
def prepare_tags(tag_name, tag, list_tag=True, include_prefix=True):
    JSON_CONF_FILE['hierarchical_pref'] = remove_special_chars(tag_prefix_field.get().strip(), "-")
    start_tag_pattern = f"{JSON_CONF_FILE['hierarchical_pref']}::" if include_prefix and JSON_CONF_FILE['hierarchical_pref'] else ""
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


@error_handler(callback=show_errors)
def save_words():
    global WORDS
    with open(WORD_JSON_PATH, "w", encoding="utf-8") as new_write_file:
        json.dump(WORDS, new_write_file, indent=4)


@error_handler(callback=show_errors)
def parse_word(word):
    """
    Парсит слово из словаря
    """
    global WORDS, SIZE, LAST_ITEM

    word = remove_special_chars(word.strip())
    parsed_word = None
    try:
        parsed_word = parse(word)
    except ValueError:
        pass
    except requests.ConnectionError:
        messagebox.showerror("Ошибка", "Ошибка получения web-страницы!\nПроверьте подключение к интернету.")
        return False

    word_blocks_list = parsed_word if parsed_word is not None else []
    # Добавляет только если блок не пуст
    if word_blocks_list:
        SIZE += len(word_blocks_list) + 1
        LAST_ITEM -= 1
        # Ставит Полученный блок слов на место предыдущего слова
        WORDS = WORDS[:LAST_ITEM] + word_blocks_list + WORDS[LAST_ITEM:]
        refresh()
        return True
    messagebox.showerror("Ошибка", "Слово не найдено!")
    return False


def get_needed(is_start=False):
    # Получение JSON файла со словами
    START_TIME = int(time.time())  # Получение времени начала работы программы. Нужно для имени файла с карточками
    last_open_file_path = Path(JSON_CONF_FILE["last_open_file"])
    last_save_dir_path = Path(JSON_CONF_FILE["last_save_dir"])
    media_dir_path = Path(JSON_CONF_FILE["media_dir"])
    AUDIO_LINKS = []

    MEDIA_DIR = "/storage/emulated/0/AnkiDroid/collection.media"

    if is_start and last_open_file_path.is_file() and last_save_dir_path.is_dir():
        WORD_JSON_PATH = JSON_CONF_FILE["last_open_file"]
        SAVE_DIR = JSON_CONF_FILE["last_save_dir"]
    else:
        WORD_JSON_PATH = askopenfilename(title="Выберете JSON файл со словами", filetypes=(("JSON", ".json"),),
                                         initialdir="./")
        if len(WORD_JSON_PATH) == 0:
            if is_start:
                quit()
            return None

        # Получение директории сохранения
        SAVE_DIR = askdirectory(title="Выберете директорию сохранения", initialdir="./")
        if len(SAVE_DIR) == 0:
            if is_start:
                quit()
            return None

        JSON_CONF_FILE["last_open_file"] = WORD_JSON_PATH
        JSON_CONF_FILE["last_save_dir"] = SAVE_DIR

    FILE_NAME = os.path.split(WORD_JSON_PATH)[-1][:-5]
    PATH_PREFIX = f"{SAVE_DIR}/{remove_special_chars(FILE_NAME, sep='_')}"
    CARDS_PATH = f"{PATH_PREFIX}_cards_{START_TIME}.txt"
    AUDIO_LINKS_PATH = f"{PATH_PREFIX}_audio_links_{START_TIME}.json"

    # Считывание файла со словами
    with open(WORD_JSON_PATH, "r", encoding="UTF-8") as read_file:
        WORDS = json.load(read_file)

    # Куча. skip - 0, add - 1, delete - 2
    CARDS_STATUSES = []
    SKIPPED_COUNTER = 0
    DEL_COUNTER = 0
    ADD_COUNTER = 0

    # Создание файла для пропускаемых карт
    SKIPPED_FILE_PATH = Path(f"{PATH_PREFIX}_skipped_cards_{START_TIME}.json")
    if SKIPPED_FILE_PATH.is_file():
        with open(SKIPPED_FILE_PATH, "r", encoding="UTF-8") as f:
            SKIPPED_FILE = json.load(f)
    else:
        SKIPPED_FILE = []

    # Получение места, где в последний раз остановился
    if JSON_HISTORY_FILE.get(WORD_JSON_PATH) is None:
        JSON_HISTORY_FILE[WORD_JSON_PATH] = start_item = 0
    else:
        start_item = min(len(WORDS), JSON_HISTORY_FILE[WORD_JSON_PATH])

    SIZE = len(WORDS) - start_item + 1

    return WORDS, FILE_NAME, WORD_JSON_PATH, SAVE_DIR, CARDS_PATH, MEDIA_DIR, AUDIO_LINKS, AUDIO_LINKS_PATH, SKIPPED_FILE, \
           SKIPPED_FILE_PATH, start_item, SIZE, CARDS_STATUSES, ADD_COUNTER, DEL_COUNTER, SKIPPED_COUNTER, START_TIME


@error_handler(callback=show_errors)
def get_word_block(index):
    index = max(0, index)
    if index >= len(WORDS):
        raise StopIteration
    return WORDS[index]


@error_handler(callback=show_errors)
def replace_sentences(dict_sentence_list):
    word = word_text.get(1.0, "end").strip()
    for start_index in range(0, max(len(dict_sentence_list), 1), 4):
        add_sentences_button["text"] = f"Добавить предложения {start_index//4+1}/{len(dict_sentence_list)//4+1}"
        for current_sentence_index in range(start_index, start_index+4):
            under_focus = not bool(sent_text_list[current_sentence_index % 4].get(1.0, "end").strip())
            sent_text_list[current_sentence_index % 4].delete(1.0, END)
            if len(dict_sentence_list) > current_sentence_index:
                sent_text_list[current_sentence_index % 4]["foreground"] = sent_text_list[current_sentence_index % 4].default_fg_color
                sent_text_list[current_sentence_index % 4].insert(1.0, dict_sentence_list[current_sentence_index])
            elif not under_focus:
                sent_text_list[current_sentence_index % 4].fill_placeholder()
        yield
        new_word = word_text.get(1.0, "end").strip()
        if word != new_word:
            word = new_word
            break

    sent_gen = sentence_parser(word, step=4)
    add_sentences_button["text"] = "Добавить предложения +"
    try:
        for batch in sent_gen:
            if word != word_text.get(1.0, "end").strip():
                break
            if len(batch) == 0:
                raise AttributeError
            for current_sentence_index in range(4):
                sent_text_list[current_sentence_index].delete(1.0, END)
                if len(batch) > current_sentence_index:
                    sent_text_list[current_sentence_index]["foreground"] = sent_text_list[current_sentence_index].default_fg_color
                    sent_text_list[current_sentence_index].insert(1.0, batch[current_sentence_index])
            yield
    except requests.ConnectionError:
        messagebox.showerror("Ошибка", "Ошибка получения web-страницы!\nПроверьте подключение к интернету.")
    except AttributeError:
        messagebox.showerror("Ошибка", "Ошибка получения предложений!\nПроверьте написание слова.")
    finally:
        new_gen = replace_sentences(dict_sentence_list)
        add_sentences_button["command"] = lambda x=new_gen: next(x)
        next(new_gen)
        yield


@error_handler(callback=show_errors)
def refresh():
    """
    Переход от старого блока слов к новому после выбора предложения
    """
    global LAST_ITEM, SIZE, DICT_TAGS, IMAGES, CURRENT_AUDIO_LINK, DICT_IMAGE_LINK

    def fill_additional_dict_data(widget, text):
        """
        Заполняет тэги и альтернативные названия слов
        :param widget: виджет куда заполнять
        :param text: что заполлнять
        :return:
        """
        widget["state"] = NORMAL
        widget.delete(1.0, END)
        widget.insert(1.0, text)
        widget["state"] = DISABLED

    word_text.focus()
    # нужно для избжания двойного заполнения виджета загушкой
    IMAGES = []
    DICT_IMAGE_LINK = ""

    if LAST_ITEM == start_item:
        prev_button["state"] = DISABLED
    else:
        prev_button["state"] = NORMAL

    # Получение и обработка нового блока слов
    try:
        next_word = get_word_block(LAST_ITEM)
    except StopIteration:
        LAST_ITEM = len(WORDS) + 1
        SIZE = 0

        root.title(f"Поиск предложений для Anki. Осталось: {SIZE} слов.")

        word_text.delete(1.0, END)
        meaning_text.delete(1.0, END)
        meaning_text.fill_placeholder()

        for j in range(4):
            sent_text_list[j].delete(1.0, END)
            sent_text_list[j].fill_placeholder()

        DICT_TAGS["domain"][0] = [""]
        DICT_TAGS["level"][0] = [""]
        DICT_TAGS["region"][0] = [""]
        DICT_TAGS["usage"][0] = [""]
        DICT_TAGS["pos"][0] = ""
        fill_additional_dict_data(dict_tags_field, "")
        fill_additional_dict_data(alt_terms_field, "")

        delete_button["state"] = DISABLED
        skip_button["state"] = DISABLED

        CURRENT_AUDIO_LINK = ""
        sound_button["state"] = DISABLED

        sentence_generator = replace_sentences([])
        next(sentence_generator)
        add_sentences_button["command"] = lambda x=sentence_generator: next(x)
        return

    DICT_TAGS["domain"][0] = next_word.get("domain", [""])
    DICT_TAGS["level"][0] = next_word.get("level", [""])
    DICT_TAGS["region"][0] = next_word.get("region", [""])
    DICT_TAGS["usage"][0] = next_word.get("usage", [""])
    DICT_TAGS["pos"][0] = next_word.get("pos", "")
    fill_additional_dict_data(dict_tags_field, get_dict_tags(include_prefix=False))

    LAST_ITEM += 1
    SIZE -= 1

    # Обновление поля для слова
    word_text.delete(1.0, END)
    if next_word["word"]:
        word_text["foreground"] = word_text.default_fg_color
        word_text.insert(1.0, next_word["word"])

    # Обновление поля для значения
    meaning_text.delete(1.0, END)
    if next_word["meaning"]:
        meaning_text["foreground"] = meaning_text.default_fg_color
        meaning_text.insert(1.0, next_word["meaning"])
    else:
        meaning_text.fill_placeholder()

    alt_terms = " ".join(next_word.get("alt_terms", []))
    fill_additional_dict_data(alt_terms_field, alt_terms)

    DICT_IMAGE_LINK = next_word.get("image_link", "")
    if DICT_IMAGE_LINK:
        find_image_button["text"] = "Добавить изображение ★"
    else:
        find_image_button["text"] = "Добавить изображение"
    CURRENT_AUDIO_LINK = next_word.get("audio_link", "")

    if CURRENT_AUDIO_LINK:
        sound_button["state"] = NORMAL
    else:
        sound_button["state"] = DISABLED

    delete_button["state"] = NORMAL
    add_sentences_button["state"] = NORMAL
    skip_button["state"] = NORMAL
    # Обновление полей для примеров предложений
    sentence_generator = replace_sentences(next_word["Sen_Ex"]) if next_word.get("Sen_Ex") is not None else replace_sentences([])
    next(sentence_generator)
    add_sentences_button["command"] = lambda x=sentence_generator: next(x)

    root.title(f"Поиск предложений для Anki. Осталось: {SIZE} слов.")


@error_handler(callback=show_errors)
def get_dict_tags(include_prefix=True):
    str_dict_tags = ""
    for tag_tame in DICT_TAGS:
        tag, add_tag_flag = DICT_TAGS[tag_tame]
        if add_tag_flag.get():
            if tag_tame == "pos":
                str_dict_tags += prepare_tags(tag_tame, tag, list_tag=False, include_prefix=include_prefix)
            else:
                str_dict_tags += prepare_tags(tag_tame, tag, include_prefix=include_prefix)
    return str_dict_tags.strip()


@error_handler(callback=show_errors)
def choose_sentence(button_index):
    """
    Выбор предложения на выбор
    :param button_index: номер кнопки (0..4)
    """
    global ADD_COUNTER, DICT_TAGS, IMAGES

    word = word_text.get(1.0, "end").strip()
    if not word:
        return

    meaning = meaning_text.get(1.0, "end").strip()
    sentence_example = sent_text_list[button_index].get(1.0, "end").rstrip()

    pos = DICT_TAGS["pos"][0]
    tags = user_tags_field.get().strip()
    # Если есть кастомные теги, то добавим пробел
    if tags:
        tags += " "
    tags += get_dict_tags()

    CARDS_STATUSES.append(1)
    ADD_COUNTER += 1
    AUDIO_LINKS.append((word, pos, word_parser_name, CURRENT_AUDIO_LINK))

    audio_name = get_audio_file_name(word, pos, word_parser_name, sep="-")
    save_audio_path = f"[sound:{audio_name}]" if CURRENT_AUDIO_LINK else ""

    if not sentence_example:
        sentence_example = word
    with open(CARDS_PATH, 'a', encoding="UTF-8", newline='') as f:
        images_path_str = "".join(IMAGES)
        cards_writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        cards_writer.writerow([sentence_example, word, meaning, images_path_str, save_audio_path, tags])
    if SIZE == 0:
        user_created_word_block = {
                                   "word": word,
                                   "meaning": meaning,
                                   "Sen_Ex": sent_text_list,
                                   }
        WORDS.append(user_created_word_block)
    refresh()


@error_handler(callback=show_errors)
def skip_command():
    """
    Откладывает карточку в файл
    """
    global CARDS_STATUSES, SKIPPED_COUNTER
    # Исправляет проблему срабатывания функции при выключенных кнопках
    if skip_button["state"] == NORMAL:
        word = word_text.get(1.0, "end").strip()
        meaning = meaning_text.get(1.0, "end").strip()
        sentences = []
        for sentence in sent_text_list:
            sentences.append(sentence.get(1.0, "end").rstrip())
        SKIPPED_FILE.append({"word": word, "meaning": meaning, "Sen_Ex": sentences})
        CARDS_STATUSES.append(0)
        SKIPPED_COUNTER += 1
        refresh()


@error_handler(callback=show_errors)
def open_new_file(is_start=False):
    """
    Открывает новый файл слов
    """
    global WORDS, FILE_NAME, WORD_JSON_PATH, SAVE_DIR, CARDS_PATH, MEDIA_DIR, AUDIO_LINKS, AUDIO_LINKS_PATH, SKIPPED_FILE
    global SKIPPED_FILE_PATH, start_item, SIZE, CARDS_STATUSES, ADD_COUNTER, DEL_COUNTER, SKIPPED_COUNTER, START_TIME
    global LAST_ITEM
    save_files()
    try:
        WORDS, FILE_NAME, WORD_JSON_PATH, SAVE_DIR, CARDS_PATH, MEDIA_DIR, AUDIO_LINKS, AUDIO_LINKS_PATH, SKIPPED_FILE, \
            SKIPPED_FILE_PATH, start_item, SIZE, CARDS_STATUSES, ADD_COUNTER, DEL_COUNTER, SKIPPED_COUNTER, \
            START_TIME = get_needed(is_start)
        LAST_ITEM = start_item
        refresh()
    except TypeError:
        pass


@error_handler(callback=show_errors)
def create_new_file():
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
            copy_encounter = Toplevel(create_file_win)
            copy_encounter.withdraw()
            message = f"Файл уже существует.\nВыберите нужную опцию:"
            encounter_label = Label(copy_encounter, width=BOTTOM_TEXT_FIELDS_WIDTH,
                                    text=message, relief="ridge")
            skip_encounter_button = Button(copy_encounter, text="Пропустить", command=lambda: foo())
            rewrite_encounter_button = Button(copy_encounter, text="Заменить", command=lambda: copy_encounter.destroy())

            encounter_label.grid(row=0, column=0, padx=text_padx, pady=text_pady)
            skip_encounter_button.grid(row=1, column=0, padx=text_padx, pady=text_pady, sticky="news")
            rewrite_encounter_button.grid(row=2, column=0, padx=text_padx, pady=text_pady, sticky="news")
            spawn_toplevel(copy_encounter)
            copy_encounter.deiconify()
            create_file_win.wait_window(copy_encounter)

        create_file_win.destroy()

        if not skip_var.get():
            with open(new_file_path, "w", encoding="UTF8") as new_file:
                json.dump([], new_file)

        new_save_dir = askdirectory(title="Выберете директорию сохранения", initialdir="./")
        if len(new_save_dir) == 0:
            return

        JSON_CONF_FILE["last_save_dir"] = new_save_dir
        JSON_CONF_FILE["last_open_file"] = new_file_path
        open_new_file(True)

    new_file_dir = askdirectory(title="Выберете директорию для файла со словами", initialdir="./")
    if len(new_file_dir) == 0:
        return
    create_file_win = Toplevel()
    create_file_win.withdraw()
    name_entry = Entry(create_file_win, placeholder="Имя файла", justify="center")
    name_button = Button(create_file_win, text="Создать", command=create_file)
    name_entry.grid(row=0, column=0, padx=5, pady=3, sticky="news")
    name_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
    spawn_toplevel(create_file_win)
    name_entry.focus()
    create_file_win.deiconify()
    create_file_win.bind("<Escape>", lambda event: create_file_win.destroy())
    create_file_win.bind("<Return>", lambda event: create_file())


@error_handler(callback=show_errors)
def save_button():
    messagebox.showinfo(message="Файлы сохранены")
    save_files()


@error_handler(callback=show_errors)
def delete_command():
    global DEL_COUNTER, LAST_ITEM
    # Исправляет проблему срабатывания функции при выключенных кнопках
    # ГАНДОН НА РАЗРАБЕ В АНДРОИДЕ СДЕЛАЛ ВМЕСТО "STATE:NORMAL" "STATE:ACTIVE"
    if delete_button["state"] == "ACTIVE":
        CARDS_STATUSES.append(2)
        DEL_COUNTER += 1
        refresh()
    else:
        LAST_ITEM -= 1
        refresh()


@error_handler(callback=show_errors)
def delete_last_line():
    """
    Удаление последних двух строк файла
    """
    with open(CARDS_PATH, "rb+") as file:
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


@error_handler(callback=show_errors)
def prev_command():
    global LAST_ITEM, SIZE, start_item, SKIPPED_COUNTER, ADD_COUNTER, DEL_COUNTER
    # -2 т. к. при refresh прибавляется 1
    if LAST_ITEM - 2 >= start_item:
        SIZE += 2
        LAST_ITEM -= 2

        # Получение статуса текущей карточки для отмены изменений файлов.
        decision = CARDS_STATUSES.pop()

        # Если карточка была пропущена, то она удаляется из файла с пропусками
        if decision == 0:
            SKIPPED_COUNTER -= 1
            SKIPPED_FILE.pop()
        # Если карточка была добавлена, то она удаляется из файла с карточками
        elif decision == 1:
            ADD_COUNTER -= 1
            delete_last_line()
            AUDIO_LINKS.pop()
        else:
            DEL_COUNTER -= 1
        refresh()


@error_handler(callback=show_errors)
def help_command():
    mes = "Программа для Sentence mining'a\n\n * Каждое поле полностью редактируемо!" + \
          "\n * Для выбора подходящего примера с предложением просто нажмите на кнопку, стоящую рядом с ним\n\n" + \
          "Назначения кнопок и полей:\n * Кнопки 1-4: кнопки выбора\nсоответствующих предложений\n" + \
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
          " Ctrl + 1..4: быстрый выбор предложения\n" + \
          " Ctrl + 0: возврат прилодения на середину экрана\n(если оно застряло)"

    messagebox.showinfo("Справка", message=mes)


@error_handler(callback=show_errors)
def match_strings(source, query):
    c = 0
    if source == query:
        return True
    if source.endswith(" " + query) or source.startswith(query + " "):
        return True
    while c < len(source) - len(query):
        done_without_break = True
        for i in range(len(query)):
            current_query_l = query[i]
            current_source_l = source[c + i]
            if current_source_l != current_query_l:
                c += i + 1
                done_without_break = False
                break
        if done_without_break:
            is_prev_space = source[c-1] == " " if c > 0 else True
            c += len(query)
            is_next_space = source[c] == " "
            if is_prev_space and is_next_space:
                break
    else:
        return False
    return True


@error_handler(callback=show_errors)
def get_local_wrapper(local_parser_name):
    def get_local(word):
        def fuzzy_word_search():
            result = []
            for found_word, word_dict in LOCAL_DICT:
                if match_strings(source=found_word, query=word):
                    result.append((found_word, word_dict))
            if not result:
                raise KeyError
            result.sort(key=lambda x: len(x[0]))
            return result

        nonlocal local_parser_name
        try:
            raw_result = fuzzy_word_search()
        except KeyError:
            return []
        transformed = discovered_local_parsers[local_parser_name].translate(raw_result)
        return transformed
    return get_local


@error_handler(callback=show_errors)
def call_second_window(window_type):
    """
    :param window_type: call_parser, stat, find
    :return:
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT

    second_window = Toplevel(root)
    second_window.withdraw()
    custom_height = 0
    custom_width = 0

    if window_type == "call_parser":
        custom_height = 170
        custom_width = 555

        def define_word_button():
            clean_word = second_window_entry.get().strip()
            parse_word(clean_word)
            second_window.destroy()

        second_window.title("Добавить")
        second_window_entry = Entry(second_window, justify="center")
        second_window_entry.focus()

        second_window_entry.grid(row=0, column=0, padx=5, pady=3, sticky="news")
        start_parsing_button = Button(second_window, text="Добавить", command=define_word_button)
        start_parsing_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
    elif window_type == "find":
        def go_to():
            global LAST_ITEM, SIZE, CARDS_STATUSES, DEL_COUNTER
            custom_height = 250
            custom_width = 555

            word = second_window_entry.get().strip().lower()
            pattern = re.compile(word)
            for iterating_index in range(1, len(WORDS) - LAST_ITEM + 1):
                block = WORDS[LAST_ITEM + iterating_index - 1]
                prepared_word_in_block = block["word"].rstrip().lower()
                if re_search.get():
                    search_condition = re.search(pattern, prepared_word_in_block)
                else:
                    search_condition = prepared_word_in_block == word
                if search_condition:
                    LAST_ITEM = LAST_ITEM + iterating_index - 1
                    SIZE = SIZE - iterating_index + 1
                    CARDS_STATUSES += [2 for _ in range(iterating_index)]
                    DEL_COUNTER += iterating_index
                    second_window.destroy()
                    refresh()
                    return
            messagebox.showerror("Ошибка", "Слово не найдено!")
            second_window.destroy()
            return

        second_window.title("Перейти")
        second_window_entry = Entry(second_window, justify="center")
        second_window_entry.focus()

        start_parsing_button = Button(second_window, text="Перейти", command=go_to)

        re_search = BooleanVar()
        re_search.set(False)
        second_window_re = Checkbutton(second_window, variable=re_search, text="RegEx search")

        second_window_entry.grid(row=0, column=0, padx=5, pady=3, sticky="news")
        start_parsing_button.grid(row=1, column=0, padx=5, pady=3, sticky="ns")
        second_window_re.grid(row=2, column=0, sticky="news")

    elif window_type == "stat":
        second_window.title("Статистика")
        text_list = (('Добавлено', 'Пропущено', 'Удалено', 'Осталось', "Файл", "Директория сохранения"),
                     (ADD_COUNTER, SKIPPED_COUNTER, DEL_COUNTER, SIZE, WORD_JSON_PATH, SAVE_DIR))

        scroll_frame = ScrolledFrame(second_window, scrollbars="horizontal")
        scroll_frame.pack()
        scroll_frame.bind_scroll_wheel(second_window)
        inner_frame = scroll_frame.display_widget(partial(Frame, bg=main_bg))
        # //TODO обойти 19 (размер слайдера)
        custom_height += 50
        for row_index in range(len(text_list[0])):
            max_current_row_height = 0
            current_row_width = 0
            for column_index in range(2):
                info = Label(inner_frame, text=text_list[column_index][row_index], anchor="center", relief="ridge")
                info.grid(column=column_index, row=row_index, sticky="news")
                info.update()
                max_current_row_height = max(max_current_row_height, info.winfo_height())
                current_row_width += info.winfo_width()
            custom_width = min(max(current_row_width, custom_width), WIDTH)
            scroll_frame["width"] = custom_width
            custom_height += max_current_row_height
    spawn_toplevel(second_window, custom_width, custom_height)
    second_window.deiconify()


root = Tk()
root.withdraw()
CURRENT_AUDIO_LINK = ""
DICT_IMAGE_LINK = ""
SCREEN_WIDTH = root.winfo_screenwidth()
SCREEN_HEIGHT = root.winfo_screenheight()
user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
headers = {'User-Agent': user_agent}

MEANING_TEXT_HEIGHT = 6
SENTENCE_TEXT_HEIGHT = 5
TOP_TEXT_FIELDS_WIDTH = 44  # ширина Text widget для слова и его значения
BOTTOM_TEXT_FIELDS_WIDTH = 26  # ширина Text widget для предложений

word_parser_name = JSON_CONF_FILE["base_word_parser"]
sentence_parser_name = JSON_CONF_FILE["base_sentence_parser"]
image_parser_name = JSON_CONF_FILE["base_image_parser"]

if word_parser_name.startswith("local"):
    with open(f"./parsers/word_parsers/{word_parser_name}/{word_parser_name}.json", "r", encoding="utf-8") as local_dictionary:
        LOCAL_DICT = json.load(local_dictionary)
    parse = get_local_wrapper(word_parser_name)
else:
    parse = discovered_web_parsers[word_parser_name].define
sentence_parser = discovered_web_sent_parsers[sentence_parser_name].get_sentence_batch
image_parser = discovered_image_parsers[image_parser_name].get_image_links

WORDS, FILE_NAME, WORD_JSON_PATH, SAVE_DIR, CARDS_PATH, MEDIA_DIR, AUDIO_LINKS, AUDIO_LINKS_PATH, SKIPPED_FILE, \
    SKIPPED_FILE_PATH, start_item, SIZE, CARDS_STATUSES, ADD_COUNTER, DEL_COUNTER, SKIPPED_COUNTER, START_TIME = \
    get_needed(True)

LAST_ITEM = start_item
IMAGES = []

# Создание меню
main_menu = Menu(root)
filemenu = Menu(main_menu, tearoff=0)
filemenu.add_command(label="Создать", command=create_new_file)
filemenu.add_command(label="Открыть", command=open_new_file)
filemenu.add_command(label="Сохранить", command=save_button)
filemenu.add_separator()
filemenu.add_command(label="Справка", command=help_command)
filemenu.add_separator()
filemenu.add_command(label="Скачать аудио", command=lambda: download_audio(choose_file=True))
main_menu.add_cascade(label="Файл", menu=filemenu)

domain_var = BooleanVar(name="domain")
level_var = BooleanVar(name="level")
region_var = BooleanVar(name="region")
usage_var = BooleanVar(name="usage")
pos_var = BooleanVar(name="pos")

DICT_TAGS = {"domain": [[""], domain_var],
             "level": [[""], level_var],
             "region": [[""], region_var],
             "usage": [[""], usage_var],
             "pos": ["", pos_var]}

domain_var.set(JSON_CONF_FILE["include_domain"])
level_var.set(JSON_CONF_FILE["include_level"])
region_var.set(JSON_CONF_FILE["include_region"])
usage_var.set(JSON_CONF_FILE["include_usage"])
pos_var.set(JSON_CONF_FILE["include_pos"])


tag_menu = Menu(main_menu, tearoff=0)
tag_menu.add_checkbutton(label='domain', variable=domain_var)
tag_menu.add_checkbutton(label='level', variable=level_var)
tag_menu.add_checkbutton(label='region', variable=region_var)
tag_menu.add_checkbutton(label='usage', variable=usage_var)
tag_menu.add_checkbutton(label='pos', variable=pos_var)
main_menu.add_cascade(label='Тэги', menu=tag_menu)

main_menu.add_command(label="Добавить", command=lambda: call_second_window("call_parser"))
main_menu.add_command(label="Найти", command=lambda: call_second_window("find"))
main_menu.add_command(label="Инфо", command=lambda: call_second_window("stat"))


@error_handler(callback=show_errors)
def change_theme():
    JSON_CONF_FILE["theme"] = index2theme_map[theme_index_var.get()]
    messagebox.showinfo(message="Изменения вступят в силу\nтолько после перезапуска программы")


theme_menu = Menu(main_menu, tearoff=0)
index2theme_map = {0: "white",
                   1: "dark"}
theme2index_map = {value: key for key, value in index2theme_map.items()}

theme_index_var = IntVar(value=theme2index_map[JSON_CONF_FILE["theme"]])
theme_menu.add_radiobutton(label="Светлая", variable=theme_index_var, value=0, command=change_theme)
theme_menu.add_radiobutton(label="Тёмная", variable=theme_index_var, value=1, command=change_theme)
main_menu.add_cascade(label="Тема", menu=theme_menu)

main_menu.add_command(label="Выход", command=on_closing)

root.config(menu=main_menu)


def change_to_start_geometry():
    JSON_CONF_FILE["image_search_position"] = "+0+0"
    root.geometry(f"{WIDTH}x{HEIGHT}+{SCREEN_WIDTH // 2 - WIDTH // 2}+{0}")


# Создание виджетов
@error_handler(callback=show_errors)
def change_word_parser(given_word_parser_name):
    global parse, LOCAL_DICT, word_parser_name
    given_word_parser_name = given_word_parser_name.strip()
    if given_word_parser_name.startswith("web"):
        parse = discovered_web_parsers[given_word_parser_name].define
        LOCAL_DICT = {}

    elif given_word_parser_name.startswith("local"):
        with open(f"./parsers/word_parsers/{given_word_parser_name}/{given_word_parser_name}.json", "r", encoding="utf-8") as dict_loader:
            LOCAL_DICT = json.load(dict_loader)
        parse = get_local_wrapper(given_word_parser_name)

    JSON_CONF_FILE["base_word_parser"] = given_word_parser_name
    word_parser_name = given_word_parser_name
    parsers_var.set(given_word_parser_name)


@error_handler(callback=show_errors)
def change_sentence_parser(given_sentence_parser_name):
    global sentence_parser, sentence_parsers_var
    given_sentence_parser_name = given_sentence_parser_name.strip()
    if given_sentence_parser_name.startswith("web"):
        JSON_CONF_FILE["base_sentence_parser"] = given_sentence_parser_name
        sentence_parser = discovered_web_sent_parsers[JSON_CONF_FILE["base_sentence_parser"]].get_sentence_batch
        sentence_parsers_var.set(given_sentence_parser_name)


@error_handler(callback=show_errors)
def change_image_parser(given_image_parser_name):
    global image_parser, image_parser_var
    given_image_parser_name = given_image_parser_name.strip()
    JSON_CONF_FILE["base_image_parser"] = given_image_parser_name
    image_parser = discovered_image_parsers[JSON_CONF_FILE["base_image_parser"]].get_image_links
    image_parser_var.set(given_image_parser_name)


@error_handler(callback=show_errors)
def get_option_menu(start_variable_name, given_parser_names, command):
    def prepare_option_menu(single_option):
        # /TODO сделать оптимальный размер меню
        return single_option

    var = StringVar()
    var.set(start_variable_name)
    optimal_parsers_names = [prepare_option_menu(item) for item in given_parser_names]
    option_menu = OptionMenu(root, var, *optimal_parsers_names, command=command)
    option_menu.configure(background=button_bg, foreground=widget_fg,
                          activebackground=button_bg, activeforeground=text_selectbackground,
                          highlightthickness=0, relief="ridge")
    option_menu["menu"].configure(background=button_bg, foreground=widget_fg)

    for i in range(len(discovered_web_sent_parsers) + len(discovered_local_parsers)):
        option_menu["menu"].entryconfig(i, activebackground=text_selectbackground,
                                        activeforeground=text_selectforeground)
    return option_menu, var


parsers_names = []
for key in discovered_web_parsers:
    parsers_names.append(key)
for key in discovered_local_parsers:
    parsers_names.append(key)
word_parser_option_menu, parsers_var = get_option_menu(start_variable_name=word_parser_name,
                                                       given_parser_names=parsers_names,
                                                       command=lambda word_name:
                                                       change_word_parser(word_name))


def start_image_search(word=None, master=root):
    global MEDIA_DIR

    def connect_images_to_card(instance):
        global IMAGES, JSON_CONF_FILE
        nonlocal word

        card_pattern = "<img src='{}.png'/>"
        saving_images_names = getattr(instance, "saving_images_names", [])
        saving_images_indices = getattr(instance, "saving_indices", [])

        for img_index in saving_images_indices:
            IMAGES.append(card_pattern.format(saving_images_names[img_index]))

        # получение координат на экране через instance.winfo_rootx(), instance.winfo_rooty() даёт некоторое смещение
        image_search_pos = instance.winfo_geometry().split(sep="+")[1:]
        JSON_CONF_FILE['image_search_position'] = f"+{image_search_pos[0]}+{image_search_pos[1]}"

    if word is None:
        if word_text["foreground"] != word_text.placeholder_fg_color:
            word = word_text.get(1.0, "end").strip()
        else:
            word = ""

    clean_word = remove_special_chars(word, sep='-')

    show_image_width = SCREEN_WIDTH // 6
    name_pattern = f"mined-{clean_word}" + "-{}"

    button_pady = button_padx = 10
    height_lim = SCREEN_HEIGHT * 2 // 3
    image_finder = ImageSearch(master=master, search_term=word, saving_dir=MEDIA_DIR,
                               url_scrapper=image_parser, init_urls=[DICT_IMAGE_LINK], headers=headers,
                               show_image_width=show_image_width,
                               saving_image_width=300, image_saving_name_pattern=name_pattern,
                               button_padx=button_padx, button_pady=button_pady,
                               window_height_limit=height_lim, window_bg=main_bg,
                               on_close_action=connect_images_to_card,
                               command_button_params=button_params,
                               entry_params=entry_params)
    image_finder.grab_set()
    root.after(500, image_finder.geometry(JSON_CONF_FILE["image_search_position"]))
    image_finder.start()


find_image_button = Button(text="Добавить изображение", command=lambda: start_image_search())
image_parsers_names = list(discovered_image_parsers)
image_parser_option_menu, image_parser_var = get_option_menu(start_variable_name=image_parser_name,
                                                             given_parser_names=image_parsers_names,
                                                             command=lambda parser_name:
                                                             change_image_parser(parser_name))


add_sentences_button = Button(text="Добавить предложения", width=BOTTOM_TEXT_FIELDS_WIDTH//2)
sentence_parsers_names = list(discovered_web_sent_parsers)
sentence_parser_option_menu, sentence_parsers_var = get_option_menu(start_variable_name=sentence_parser_name,
                                                                    given_parser_names=sentence_parsers_names,
                                                                    command=lambda parser_name:
                                                                    change_sentence_parser(parser_name))

word_text = Text(root, placeholder="Слово", height=1, width=TOP_TEXT_FIELDS_WIDTH)
alt_terms_field = Text(root, height=2, width=TOP_TEXT_FIELDS_WIDTH, relief="ridge", bg=button_bg)
meaning_text = Text(root, placeholder="Значение", height=MEANING_TEXT_HEIGHT, width=TOP_TEXT_FIELDS_WIDTH)

sent_text_list = []
buttons_list = []

for i in range(4):
    sent_text_list.append(Text(root, placeholder=f"Предложение {i + 1}",
                                     height=SENTENCE_TEXT_HEIGHT,
                                     width=BOTTOM_TEXT_FIELDS_WIDTH))
    sent_text_list[-1].fill_placeholder()
    buttons_list.append(Button(text=f"{i+1}", command=lambda x=i: choose_sentence(x), width=3))

delete_button = Button(text="Del", command=delete_command, width=3)
prev_button = Button(text="Prev", command=prev_command, width=3)
sound_button = Button(text="Play", command=play_sound, width=3)
skip_button = Button(text="Skip", command=skip_command, width=3)


tags_field_placeholder = "Тэги"
user_tags_field = Entry(root, placeholder=tags_field_placeholder)
user_tags_field.fill_placeholder()

tag_prefix_field = Entry(root, width=1, justify="center")
tag_prefix_field.insert(0, JSON_CONF_FILE["hierarchical_pref"])
dict_tags_field = Text(root, height=3, width=TOP_TEXT_FIELDS_WIDTH, relief="ridge", bg=button_bg)

text_padx = 0
text_pady = 6

# Расстановка виджетов
word_parser_option_menu.grid(row=0, column=0, padx=text_padx, columnspan=5, sticky="we")

word_text.grid(row=1, column=0, padx=text_padx, pady=text_pady, columnspan=5, sticky="w")

alt_terms_field.grid(row=2, column=0, padx=text_padx, columnspan=5, sticky="w")
alt_terms_field["state"] = DISABLED

find_image_button.grid(row=3, column=0, padx=text_padx, pady=text_pady, sticky="we")
image_parser_option_menu.grid(row=3, column=1, padx=text_padx, pady=text_pady, columnspan=4, sticky="we")

meaning_text.grid(row=4, column=0, padx=text_padx, columnspan=5, sticky="w")

sentence_parser_option_menu.grid(row=5, column=1, padx=text_padx, pady=text_pady, columnspan=4, sticky="we")
add_sentences_button.grid(row=5, column=0, padx=text_padx, pady=text_pady, sticky="we")

for i in range(4):
    if i % 2:
        c_pady = text_pady
    else:
        c_pady = 0
    sent_text_list[i].grid(row=5 + i + 1, column=0, columnspan=3, padx=text_padx, pady=c_pady, sticky="w")
    buttons_list[i].grid(row=5 + i + 1, column=3, padx=0, pady=c_pady, sticky="ns")

delete_button.grid(row=6, column=4, padx=text_padx, pady=0, sticky="ns")
prev_button.grid(row=7, column=4, padx=text_padx, pady=text_pady, sticky="ns")
sound_button.grid(row=8, column=4, padx=text_padx, pady=0, sticky="ns")

skip_button.grid(row=9, column=4, padx=text_padx, pady=0, sticky="ns")

user_tags_field.grid(row=10, column=0, padx=text_padx, pady=text_pady, columnspan=3, sticky="news")
tag_prefix_field.grid(row=10, column=3, padx=(0, text_padx), pady=text_pady, columnspan=2, sticky="news")
dict_tags_field.grid(row=11, column=0, padx=text_padx, pady=(0, text_pady), columnspan=5, sticky="w")
dict_tags_field["state"] = DISABLED

root.configure(bg=main_bg)
root.title(f"Поиск предложений для Anki. Осталось: {SIZE} слов.")
root.protocol("WM_DELETE_WINDOW", on_closing)
# Заставляет приложение вызваться поверх остальных окон
# root.call('wm', 'attributes', '.', '-topmost', True)
root.update()
WIDTH = root.winfo_width()
HEIGHT = root.winfo_height()
root.resizable(0, 0)


root.after(300_000, autosave)
refresh()
root.deiconify()
root.mainloop()
