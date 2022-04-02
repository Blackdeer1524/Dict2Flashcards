from tkinter import messagebox
from pathlib import Path
import json
from tkinter.filedialog import askopenfilename, askdirectory
import time
import importlib
import pkgutil
import os
import requests
from tkinter import *
import re
from functools import partial
from tkinter import Entry as Original_Entry
import copy
from parsers import image_parsers, word_parsers, sentence_parsers


def save_history_file():
    with open("./history.json", "w") as saving_f:
        json.dump(JSON_HISTORY_FILE, saving_f, indent=3)


def save_conf_file():
    with open(CONF_FILE, "w") as f:
        json.dump(JSON_CONF_FILE, f, indent=3)

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
                      "base_sentence_parser": "web_sentencedict",
                      "base_word_parser": "web_cambridge[UK]",
                      "base_image_parser": "google",
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

Label = partial(Label, background=main_bg, foreground=widget_fg)
Button = partial(Button, background=button_bg, foreground=widget_fg,
                 activebackground=button_bg, activeforeground=text_selectbackground)
Text = partial(Text, background=text_bg, foreground=widget_fg, selectbackground=text_selectbackground,
               selectforeground=text_selectforeground, insertbackground=text_selectbackground)
Entry = partial(Original_Entry, background=text_bg, foreground=widget_fg, selectbackground=text_selectbackground,
               selectforeground=text_selectforeground, insertbackground=text_selectbackground)
Checkbutton = partial(Checkbutton, background=main_bg, foreground=widget_fg,
                      activebackground=main_bg, activeforeground=widget_fg, selectcolor=main_bg)
Toplevel = partial(Toplevel, bg=main_bg)


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


def save_files():
    """
    Сохраняет файлы если они не пустые или есть изменения
    """
    JSON_CONF_FILE["hierarchical_pref"] = tag_prefix_field.get()
    JSON_CONF_FILE["include_domain"] = domain_var.get()
    JSON_CONF_FILE["include_level"] = level_var.get()
    JSON_CONF_FILE["include_region"] = region_var.get()
    JSON_CONF_FILE["include_usage"] = usage_var.get()
    JSON_CONF_FILE["include_pos"] = pos_var.get()
    JSON_CONF_FILE["is_hierarchical"] = is_hierarchical.get()
    save_conf_file()

    JSON_HISTORY_FILE[WORD_JSON_PATH] = LAST_ITEM - 1

    save_words()

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
        root.destroy()


def prepare_tags(tag_name, tag, list_tag=True, include_prefix=True):
    JSON_CONF_FILE['hierarchical_pref'] = get_clean_text(tag_prefix_field)
    start_tag_pattern = f"{JSON_CONF_FILE['hierarchical_pref']}::" if include_prefix else ""
    if list_tag:
        if tag[0] == "":
            return ""
        result = ""
        for item in tag:
            item = item.replace(' ', '_')
            if is_hierarchical.get():
                result += f"{start_tag_pattern}{tag_name}::{item} "
            else:
                result += item + " "
        return result
    else:
        if tag == "":
            return ""
        tag = tag.replace(' ', '_')
        if is_hierarchical.get():
            return f"{start_tag_pattern}{tag_name}::{tag} "
        return tag + " "


def save_words():
    global WORDS
    with open(WORD_JSON_PATH, "w", encoding="utf-8") as new_write_file:
        json.dump(WORDS, new_write_file, indent=4)


def parse_word(_word=None):
    """
    Парсит слово из словаря
    """
    global WORDS, SIZE, LAST_ITEM
    if _word is None:
        word = get_clean_text(second_window_entry)
    else:
        word = _word

    parsed_word = None
    try:
        parsed_word = parse(word)
    except ValueError:
        pass
    except requests.ConnectionError:
        messagebox.showerror("Ошибка", "Ошибка получения web-страницы!\nПроверьте подключение к интернету.")
        if _word is None:
            second_window.destroy()
        return

    word_blocks_list = parsed_word if parsed_word is not None else []
    # Добавляет только если блок не пуст
    if len(word_blocks_list) > 0:
        SIZE += len(word_blocks_list) + 1
        LAST_ITEM -= 1
        # Ставит Полученный блок слов на место предыдущего слова
        WORDS = WORDS[:LAST_ITEM] + word_blocks_list + WORDS[LAST_ITEM:]
        # Закрыть окно в случае испоьзования меню
        if _word is None:
            second_window.destroy()
        refresh()
    else:
        messagebox.showerror("Ошибка", "Слово не найдено!")

    # Закрыть окно в случае испоьзования меню
    if _word is None:
        second_window.destroy()


def get_needed(is_start=False):
    # Получение JSON файла со словами
    START_TIME = int(time.time())  # Получение времени начала работы программы. Нужно для имени файла с карточками
    last_open_file_path = Path(JSON_CONF_FILE["last_open_file"])
    last_save_dir_path = Path(JSON_CONF_FILE["last_save_dir"])

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
        SAVE_DIR = askdirectory(title="Выберете директорию для сохранения", initialdir="./")
        if len(SAVE_DIR) == 0:
            if is_start:
                quit()
            return None

        JSON_CONF_FILE["last_open_file"] = WORD_JSON_PATH
        JSON_CONF_FILE["last_save_dir"] = SAVE_DIR

    FILE_NAME = os.path.split(WORD_JSON_PATH)[-1][:-5]

    # Считывание файла со словами
    with open(WORD_JSON_PATH, "r", encoding="UTF-8") as read_file:
        WORDS = json.load(read_file)

    # Куча. skip - 0, add - 1, delete - 2
    CARDS_STATUSES = []
    SKIPPED_COUNTER = 0
    DEL_COUNTER = 0
    ADD_COUNTER = 0

    # Создание файла для пропускаемых карт
    SKIPPED_FILE_PATH = Path(f'{SAVE_DIR}/{FILE_NAME}_skipped_cards_{START_TIME}.json')
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

    return START_TIME, WORD_JSON_PATH, SAVE_DIR, FILE_NAME, WORDS, CARDS_STATUSES, SIZE, \
           SKIPPED_FILE_PATH, SKIPPED_FILE, start_item, SKIPPED_COUNTER, DEL_COUNTER, ADD_COUNTER


def get_word_block(index):
    index = max(0, index)
    if index >= len(WORDS):
        raise StopIteration
    return WORDS[index]


def get_clean_text(widget, clear_placeholder=False):
    if isinstance(widget, getattr(Text, "func", Text)):
        clear_text = widget.get(1.0, END).replace("\n", " ").strip()
        if clear_placeholder and clear_text == getattr(widget, "placeholder", None):
            clear_text = ""
    elif isinstance(widget, getattr(Entry, "func", Entry)):
        clear_text = widget.get().replace("\n", " ").strip()
        if clear_placeholder and clear_text == getattr(widget, "placeholder", None):
            clear_text = ""
    else:
        raise Exception("Widget has to be either Text or Entry!")
    return clear_text


def prepare_for_text_field(text, is_top=True):
    """
    Добавляет правильные переносы строк для данного текста
    :param text: текста
    :param is_top: пойдел ли предложение в строку значения (True) или в строки для предложений (False)
    :return: исправленное предложение
    """
    width = TOP_TEXT_FIELDS_WIDTH if is_top else BOTTOM_TEXT_FIELDS_WIDTH
    text = text.replace("\n", " ")
    listed_text = text.split(sep=" ")
    if len(listed_text) == 0:
        return text
    a = listed_text[0]
    new_str_text = ""
    for k in range(1, len(listed_text)):
        if len(a + ' ' + listed_text[k]) > width:
            new_str_text = new_str_text + a + "\n"
            a = listed_text[k]
        else:
            a += ' ' + listed_text[k]
    return new_str_text + a


def sentence_sort(sentences):
    if len(sentences) <= 1:
        return sentences
    mid_item = sentences[len(sentences) // 2]
    left = []
    middle = []
    right = []
    zero_length = []
    for sentence in sentences:
        if len(sentence) == 0:
            zero_length.append(sentence)
        elif len(sentence) < len(mid_item):
            left.append(sentence)
        elif len(sentence) > len(mid_item):
            right.append(sentence)
        else:
            middle.append(sentence)

    left_result = sentence_sort(left)
    right_result = sentence_sort(right)
    left_result.extend(middle)
    left_result.extend(right_result)
    left_result.extend(zero_length)
    return left_result


def prepare_word_block(word_block):
    """
    приводит блок слов под формат приложения
    :param word_block: Блок слов: {"word": слово_n, "meaning": значение_n, "Sen_Ex": [пример_1, ..., пример_n]}
    :return: отредактированный блок
    """
    # Добавление подходящих переносов
    new_word_block = {}
    new_word_block["word"] = prepare_for_text_field(word_block["word"])
    new_word_block["meaning"] = prepare_for_text_field(word_block["meaning"])

    # Добавляем/урезаем количество предложений до 5
    if word_block.get('Sen_Ex') is None:
        new_word_block['Sen_Ex'] = ["" for _ in range(5)]
    else:
        new_word_block['Sen_Ex'] = copy.copy(word_block["Sen_Ex"])
        if len(new_word_block['Sen_Ex']) > 5:
            new_word_block['Sen_Ex'] = new_word_block['Sen_Ex'][:5]

    # Добавление подходящих переносов
    new_word_block['Sen_Ex'] = sentence_sort(new_word_block['Sen_Ex'])
    for q in range(len(new_word_block['Sen_Ex'])):
        new_word_block['Sen_Ex'][q] = prepare_for_text_field(new_word_block['Sen_Ex'][q], is_top=False)

    audio_link = word_block.get("audio_link", "")
    if audio_link:
        new_word_block["audio_link"] = audio_link
    return new_word_block


def refresh():
    """
    Переход от старого блока слов к новому после выбора предложения
    """
    global LAST_ITEM, SIZE, add_tag_data, IMAGES, CURRENT_AUDIO_LINK
    IMAGES = []
    word_text.focus()
    # Получение и обработка нового блока слов
    try:
        if LAST_ITEM == start_item:
            prev_button["state"] = DISABLED
        else:
            prev_button["state"] = ACTIVE

        next_word = get_word_block(LAST_ITEM)

        add_tag_data["domain"][0] = next_word.get("domain", [""])
        add_tag_data["level"][0] = next_word.get("level", [""])
        add_tag_data["region"][0] = next_word.get("region", [""])
        add_tag_data["usage"][0] = next_word.get("usage", [""])
        add_tag_data["pos"][0] = next_word.get("pos", "")

        LAST_ITEM += 1
        SIZE -= 1

        delete_button["state"] = ACTIVE
        add_sentences_button["state"] = ACTIVE
        add_sentences_button["command"] = lambda x=replace_sentences(): next(x)
        skip_button["state"] = ACTIVE

    except StopIteration:
        LAST_ITEM = len(WORDS) + 1
        SIZE = 0
        root.title(f"Поиск предложений для Anki. Осталось: {SIZE} слов.")
        word_text.delete(1.0, END)

        meaning_text.delete(1.0, END)
        fill_placeholder(meaning_text)

        for j in range(5):
            sent_text_list[j].delete(1.0, END)
            fill_placeholder(sent_text_list[j])

        add_tag_data["domain"][0] = [""]
        add_tag_data["level"][0] = [""]
        add_tag_data["region"][0] = [""]
        add_tag_data["usage"][0] = [""]
        add_tag_data["pos"][0] = ""

        delete_button["state"] = DISABLED
        skip_button["state"] = DISABLED
        # messagebox.showinfo(message="Колода закончилась.")
        return

    next_word = prepare_word_block(next_word)

    # Обновление поля для слова
    word_text.delete(1.0, END)

    if not next_word["word"]:
        fill_placeholder(word_text)
    else:
        word_text["fg"] = widget_fg
        word_text.insert(1.0, next_word["word"])

    # Обновление поля для значения
    meaning_text.delete(1.0, END)
    if not next_word["meaning"]:
        fill_placeholder(meaning_text)
    else:
        meaning_text["fg"] = widget_fg
        meaning_text.insert(1.0, next_word["meaning"])

    # Обновление полей для примеров предложений
    for i in range(5):
        sent_text_list[i].delete(1.0, END)
        if len(next_word["Sen_Ex"]) < i + 1:
            fill_placeholder(sent_text_list[i])
        else:
            sent_text_list[i]["fg"] = widget_fg
            sent_text_list[i].insert(1.0, next_word["Sen_Ex"][i])
    root.title(f"Поиск предложений для Anki. Осталось: {SIZE} слов.")


def get_dict_tags(include_prefix=True):
    dict_tags = ""
    for tag_tame in add_tag_data:
        value, variable = add_tag_data[tag_tame]
        if variable.get():
            if tag_tame == "pos":
                dict_tags += prepare_tags(tag_tame, value, list_tag=False, include_prefix=include_prefix)
            else:
                dict_tags += prepare_tags(tag_tame, value, include_prefix=include_prefix)
    return dict_tags.strip()


def choose_sentence(button_index):
    """
    Выбор предложения на выбор
    :param button_index: номер кнопки (0..4)
    """
    global ADD_COUNTER, add_tag_data
    # Получение сведений о слове
    word = get_clean_text(word_text)
    if word == word_text.placeholder:
        word = ""
    # Исправляет проблему срабатывания функции при выключенных кнопках
    if len(word) == 0:
        return
    meaning = get_clean_text(meaning_text)
    if meaning == meaning_text.placeholder:
        meaning = ""
    tags = get_clean_text(user_tags_field, True)
    # Если есть кастомные теги, то добавим пробел
    if tags:
        tags += " "

    pos = add_tag_data["pos"][0]
    tags += get_dict_tags()

    # Получение предложения
    sentence_example = get_clean_text(sent_text_list[button_index])
    if sentence_example == sent_text_list[button_index].placeholder:
        sentence_example = ""

    if len(word) + len(meaning) + len(sentence_example) != 0:
        CARDS_STATUSES.append(1)
        ADD_COUNTER += 1

        if len(sentence_example) == 0:
            sentence_example = word
        with open(f'{SAVE_DIR}/{FILE_NAME}_cards_{START_TIME}.txt', 'a', encoding="UTF-8") as f:
            f.write(f"{sentence_example};{word};{meaning};{tags}\n")
        if SIZE == 0:
            user_created_word_block = {
                                       "word": word,
                                       "meaning": meaning,
                                       "Sen_Ex": [sentence_example],
                                       }
            WORDS.append(user_created_word_block)
    refresh()


def replace_sentences():
    word = get_clean_text(word_text, True)
    sent_gen = sentence_parser(word)
    try:
        for batch in sent_gen:
            if word != get_clean_text(word_text, True):
                break
            if len(batch) == 0:
                raise AttributeError
            for sentence_ind in range(len(batch)):
                batch[sentence_ind] = prepare_for_text_field(batch[sentence_ind], is_top=False)
            while len(batch) < 5:
                batch.append("")
            for j in range(5):
                sent_text_list[j].delete(1.0, END)
                if not batch[j]:
                    fill_placeholder(sent_text_list[j])
                else:
                    sent_text_list[j]["fg"] = widget_fg
                    sent_text_list[j].insert(1.0, batch[j])
            yield
        new_gen = replace_sentences()
        next(new_gen)
        add_sentences_button["command"] = lambda x=new_gen: next(x)
        yield
    except requests.ConnectionError:
        messagebox.showerror("Ошибка", "Ошибка получения web-страницы!\nПроверьте подключение к интернету.")
        add_sentences_button["command"] = lambda x=replace_sentences(): next(x)
        yield
    except AttributeError:
        messagebox.showerror("Ошибка", "Ошибка получения предложений!\nПроверьте написание слова.")
        add_sentences_button["command"] = lambda x=replace_sentences(): next(x)
        yield


def skip_command():
    """
    Откладывает карточку в файл
    """
    global CARDS_STATUSES, SKIPPED_COUNTER
    # Исправляет проблему срабатывания функции при выключенных кнопках
    if skip_button["state"] == ACTIVE:
        word = get_clean_text(word_text)
        meaning = get_clean_text(meaning_text)
        sentences = []
        for item in sent_text_list:
            sentences.append(get_clean_text(item))
        SKIPPED_FILE.append({"word": word, "meaning": meaning, "Sen_Ex": sentences})
        CARDS_STATUSES.append(0)
        SKIPPED_COUNTER += 1
        refresh()


def open_new_file():
    """
    Открывает новый файл слов
    """
    global START_TIME, WORD_JSON_PATH, SAVE_DIR, FILE_NAME, WORDS, CARDS_STATUSES, SIZE
    global SKIPPED_FILE_PATH, SKIPPED_FILE, start_item, LAST_ITEM
    global SKIPPED_COUNTER, DEL_COUNTER, ADD_COUNTER
    save_files()
    try:
        START_TIME, WORD_JSON_PATH, SAVE_DIR, FILE_NAME, WORDS, CARDS_STATUSES, SIZE, \
        SKIPPED_FILE_PATH, SKIPPED_FILE, start_item, SKIPPED_COUNTER, DEL_COUNTER, ADD_COUNTER = get_needed()
        LAST_ITEM = start_item
        refresh()
    except TypeError:
        pass


def save_button():
    messagebox.showinfo(message="Файлы сохранены")
    save_files()


def delete_command():
    global DEL_COUNTER, LAST_ITEM
    # Исправляет проблему срабатывания функции при выключенных кнопках
    # ГАНДОН НА РАЗРАБЕ В АНДРОИДЕ СДЕЛАЛ ВМЕСТО "STATE:NORMAL" "STATE:ACTIVE"
    if delete_button["state"] == ACTIVE:
        CARDS_STATUSES.append(2)
        DEL_COUNTER += 1
        refresh()
    else:
        LAST_ITEM -= 1
        refresh()


def delete_last_line():
    """
    Удаление последних двух строк файла
    """
    with open(f"{SAVE_DIR}/{FILE_NAME}_cards_{START_TIME}.txt", "rb+") as file:
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
        else:
            DEL_COUNTER -= 1
        refresh()


def help_command():
    mes = "Программа для Sentence mining'a\n\n * Каждое поле полностью\nредактируемо!\n" + \
          " * Для выбора подходящего\nпримера с предложением просто\nнажмите на кнопку, стоящую рядом\nс ним\n\n" + \
          "Назначения кнопок и полей:\n * Кнопки 1-5: кнопки выбора\nсоответствующих предложений\n" + \
          " * Кнопка \"Skip\": откладывает\nслово в отдельный файл для\nпросмотра позднее\n" + \
          " * Кнопка \"Del\": удаляет слово\n" + \
          " * Кнопка \"Prev\": возвращается\nк предущему блоку\n" + \
          " * \"IMG TAG\": Добавление тэга \"img\"\n" + \
          " * Самое нижнее окно ввода:\nполе для тэгов"
    messagebox.showinfo("Справка", message=mes)


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
            second_window.destroy()
            return []
        transformed = discovered_local_parsers[local_parser_name].translate(raw_result)
        return transformed
    return get_local


def call_second_window(window_type):
    """
    :param window_type: call_parser, stat, find
    :return:
    """
    global second_window, second_window_entry, SCREEN_WIDTH, SCREEN_HEIGHT

    try:
        second_window.destroy()
    except NameError:
        pass

    second_window = Toplevel(root)
    second_window.withdraw()

    if window_type == "call_parser":
        SECOND_WINDOW_WIDTH = 555
        SECOND_WINDOW_HEIGHT = 170

        second_window_entry = Entry(second_window, justify="center")
        second_window_entry.focus()

        second_window_entry.grid(row=0, column=0, padx=5, pady=3)
        start_parsing_button = Button(second_window, text="Добавить", width=7, height=1, command=parse_word)
        start_parsing_button.grid(row=1, column=0, padx=5, pady=3)
    elif window_type == "find":
        def go_to():
            global LAST_ITEM, SIZE, CARDS_STATUSES, DEL_COUNTER
            word = second_window_entry.get().rstrip().lower()
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
            second_window.destroy()
            messagebox.showerror("Ошибка", "Слово не найдено!")

        SECOND_WINDOW_WIDTH = 555
        SECOND_WINDOW_HEIGHT = 250

        second_window_entry = Entry(second_window, justify="center")
        second_window_entry.focus()

        start_parsing_button = Button(second_window, text="Перейти", width=7, height=1, command=go_to)

        re_search = BooleanVar()
        re_search.set(False)
        second_window_re = Checkbutton(second_window, variable=re_search, text="RegEx search")

        second_window_entry.grid(row=0, column=0, padx=5, pady=3)
        start_parsing_button.grid(row=1, column=0, padx=5, pady=3)
        second_window_re.grid(row=2, column=0)

    elif window_type == "stat":
        text_list = (('Добавлено', 'Пропущено', 'Удалено', 'Осталось'),
                     (ADD_COUNTER, SKIPPED_COUNTER, DEL_COUNTER, SIZE))
        padx = 0
        SECOND_WINDOW_WIDTH = 0
        SECOND_WINDOW_HEIGHT = 0
        anchor = "center"
        for row_index in range(len(text_list[0])):
            row_width_data = []
            for column_index in range(2):
                label = Label(second_window, text=text_list[column_index][row_index], anchor=anchor,
                              relief="ridge")
                label.grid(column=column_index, row=row_index, sticky="we", padx=padx)
                label.update()
                row_width_data.append(label.winfo_width() + 2 * padx)

            SECOND_WINDOW_HEIGHT += label.winfo_height()
            SECOND_WINDOW_WIDTH = max(SECOND_WINDOW_WIDTH, row_width_data[0] + row_width_data[1])

    second_window.resizable(0, 0)
    window_size = f"{SECOND_WINDOW_WIDTH}x{SECOND_WINDOW_HEIGHT}"
    _, X, Y = root.winfo_geometry().split(sep="+")
    center_x = int(X) + WIDTH // 2
    center_y = int(Y) + HEIGHT // 2

    spawn_cords = f"+{center_x - SECOND_WINDOW_WIDTH // 2}+{center_y - SECOND_WINDOW_HEIGHT // 2}"
    second_window.geometry(window_size + spawn_cords)
    second_window.wm_deiconify()
    # second_window.attributes('-topmost',True)
    second_window.grab_set()


root = Tk()
root.withdraw()
CURRENT_AUDIO_LINK = ""
SCREEN_WIDTH = root.winfo_screenwidth()
SCREEN_HEIGHT = root.winfo_screenheight()
user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
headers = {'User-Agent': user_agent}

MEANING_TEXT_HEIGHT = 6
SENTENCE_TEXT_HEIGHT = 5
TOP_TEXT_FIELDS_WIDTH = 42  # ширина Text widget для слова и его значения
BOTTOM_TEXT_FIELDS_WIDTH = 26  # ширина Text widget для предложений
IMG_TAG_NAME = "Добавить тэг изображения"

word_parser_name = JSON_CONF_FILE["base_word_parser"]
sentence_parser_name = JSON_CONF_FILE["base_sentence_parser"]

if word_parser_name.startswith("local"):
    with open(f"./parsers/word_parsers/{word_parser_name}/{word_parser_name}.json", "r", encoding="utf-8") as local_dictionary:
        LOCAL_DICT = json.load(local_dictionary)
    parse = get_local_wrapper(word_parser_name)
else:
    parse = discovered_web_parsers[word_parser_name].define
sentence_parser = discovered_web_sent_parsers[sentence_parser_name].get_sentence_batch

START_TIME, WORD_JSON_PATH, SAVE_DIR, FILE_NAME, WORDS, CARDS_STATUSES, SIZE, \
SKIPPED_FILE_PATH, SKIPPED_FILE, start_item, SKIPPED_COUNTER, DEL_COUNTER, ADD_COUNTER = get_needed(True)

LAST_ITEM = start_item

# Создание меню
main_menu = Menu(root)
filemenu = Menu(main_menu, tearoff=0)
filemenu.add_command(label="Открыть", command=open_new_file)
filemenu.add_command(label="Сохранить", command=save_button)
filemenu.add_separator()
filemenu.add_command(label="Справка", command=help_command)
main_menu.add_cascade(label="Файл", menu=filemenu)

domain_var = BooleanVar(name="domain")
level_var = BooleanVar(name="level")
region_var = BooleanVar(name="region")
usage_var = BooleanVar(name="usage")
pos_var = BooleanVar(name="pos")
is_hierarchical = BooleanVar()

add_tag_data = {"domain": [[""], domain_var],
                "level": [[""], level_var],
                "region": [[""], region_var],
                "usage": [[""], usage_var],
                "pos": ["", pos_var]}

domain_var.set(JSON_CONF_FILE["include_domain"])
level_var.set(JSON_CONF_FILE["include_level"])
region_var.set(JSON_CONF_FILE["include_region"])
usage_var.set(JSON_CONF_FILE["include_usage"])
pos_var.set(JSON_CONF_FILE["include_pos"])
is_hierarchical.set(JSON_CONF_FILE["is_hierarchical"])


def change_pref_entry_state():
    if is_hierarchical.get():
        tag_prefix_field["state"] = ACTIVE
    else:
        tag_prefix_field["state"] = DISABLED


tag_menu = Menu(main_menu, tearoff=0)
tag_menu.add_checkbutton(label='hierarchical', variable=is_hierarchical, command=lambda: change_pref_entry_state())
tag_menu.add_separator()
tag_menu.add_checkbutton(label='domain', variable=domain_var)
tag_menu.add_checkbutton(label='level', variable=level_var)
tag_menu.add_checkbutton(label='region', variable=region_var)
tag_menu.add_checkbutton(label='usage', variable=usage_var)
tag_menu.add_checkbutton(label='pos', variable=pos_var)
main_menu.add_cascade(label='Тэги', menu=tag_menu)

main_menu.add_command(label="Добавить", command=lambda: call_second_window("call_parser"))
main_menu.add_command(label="Найти", command=lambda: call_second_window("find"))
main_menu.add_command(label="Инфо", command=lambda: call_second_window("stat"))


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

# Флажок для тэгов
img_flag_var = BooleanVar()
flag = Checkbutton(text=IMG_TAG_NAME, variable=img_flag_var)


# Создание виджетов
def change_word_parser(given_word_parser_name):
    global parse, LOCAL_DICT
    given_word_parser_name = given_word_parser_name.strip()
    if given_word_parser_name.startswith("web"):
        parse = discovered_web_parsers[given_word_parser_name].define
        LOCAL_DICT = {}

    elif given_word_parser_name.startswith("local"):
        with open(f"./parsers/word_parsers/{given_word_parser_name}/{given_word_parser_name}.json", "r", encoding="utf-8") as dict_loader:
            LOCAL_DICT = json.load(dict_loader)
        parse = get_local_wrapper(given_word_parser_name)

    JSON_CONF_FILE["base_word_parser"] = given_word_parser_name
    parsers_var.set(given_word_parser_name)


def change_sentence_parser(given_sentence_parser_name):
    global sentence_parser, sentence_parsers_var
    given_sentence_parser_name = given_sentence_parser_name.strip()
    if given_sentence_parser_name.startswith("web"):
        JSON_CONF_FILE["base_sentence_parser"] = given_sentence_parser_name
        sentence_parser = discovered_web_sent_parsers[JSON_CONF_FILE["base_sentence_parser"]].get_sentence_batch
        sentence_parsers_var.set(given_sentence_parser_name)


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


add_sentences_button = Button(text="Добавить предложения", command=lambda x=replace_sentences(): next(x), width=5)
sentence_parsers_names = list(discovered_web_sent_parsers)
sentence_parser_option_menu, sentence_parsers_var = get_option_menu(start_variable_name=sentence_parser_name,
                                                                    given_parser_names=sentence_parsers_names,
                                                                    command=lambda parser_name:
                                                                    change_sentence_parser(parser_name))


def text_focusin_action(text_widget):
    """
    :param text_widget:
    :return:
    """
    text = get_clean_text(text_widget)
    if text == text_widget.placeholder:
        text_widget["fg"] = widget_fg
        text_widget.delete(1.0, END)


def fill_placeholder(text_widget):
    """
    :param text_widget:
    :return:
    """
    text_widget["fg"] = "grey"
    text_widget.insert(1.0, text_widget.placeholder)


def text_focusout_action(text_widget, is_top=True):
    """
    :param text_widget:
    :param placeholder:
    :param is_top:
    :return:
    """
    text = get_clean_text(text_widget)
    text_widget.delete(1.0, END)
    if not text:
        fill_placeholder(text_widget)
    else:
        prepared_text = prepare_for_text_field(text, is_top)
        text_widget.insert(1.0, prepared_text)


word_text = Text(height=2, width=TOP_TEXT_FIELDS_WIDTH)
word_text.placeholder = "Слово"
word_text.bind("<FocusIn>",
               lambda event, text_widget=word_text:
               text_focusin_action(text_widget))
word_text.bind("<FocusOut>",
               lambda event, text_widget=word_text, is_top=True:
               text_focusout_action(text_widget, is_top))

meaning_text = Text(height=MEANING_TEXT_HEIGHT, width=TOP_TEXT_FIELDS_WIDTH)
meaning_text.placeholder = "Значение"
meaning_text.bind("<FocusIn>",
               lambda event, text_widget=meaning_text:
               text_focusin_action(text_widget))
meaning_text.bind("<FocusOut>",
                  lambda event, text_widget=meaning_text, is_top=True:
                  text_focusout_action(text_widget, is_top))


sent_text_list = []
buttons_list = []

for i in range(5):
    sent_text_list.append(Text(height=SENTENCE_TEXT_HEIGHT, width=BOTTOM_TEXT_FIELDS_WIDTH))
    sent_text_list[i].placeholder = f"Предложение {i + 1}"
    sent_text_list[i].bind("<FocusIn>", lambda event, text_widget=sent_text_list[i]:
    text_focusin_action(text_widget))

    sent_text_list[i].bind("<FocusOut>", lambda event, text_widget=sent_text_list[i], is_top=False:
    text_focusout_action(text_widget, is_top))

    buttons_list.append(Button(text=f"{i+1}", command=lambda x=i: choose_sentence(x), width=3))

delete_button = Button(text="Del", command=delete_command, width=3)
prev_button = Button(text="Prev", command=prev_command, width=3)
add_sentences_button = Button(text="Sent", command=lambda x=replace_sentences(): next(x), width=3)
skip_button = Button(text="Skip", command=skip_command, width=3)


class EntryWithPlaceholder(Original_Entry):
    def __init__(self, master, width=0, placeholder="", init_text="", color='grey',
                 raise_error_if_empty=False, justify="left", borderwidth=1):
        super().__init__(master)
        self["justify"] = justify
        self.raise_error_if_empty = raise_error_if_empty
        self.placeholder = placeholder
        self.placeholder_color = color
        self["borderwidth"] = borderwidth
        self["bg"] = text_bg
        self["fg"] = widget_fg
        self.default_fg_color = self['fg']

        self["selectbackground"] = text_selectbackground
        self["selectforeground"] = text_selectforeground
        self["insertbackground"] = text_selectbackground
        self["disabledbackground"] = text_bg
        self.bind("<FocusIn>", self.foc_in)
        self.bind("<FocusOut>", self.foc_out)

        self.insert(END, init_text)
        if width:
            self["width"] = width
        self.put_placeholder()

    def put_placeholder(self):
        if not self.get():
            self.insert(1, self.placeholder)
            self['fg'] = self.placeholder_color

    def foc_in(self, *args):
        if self['fg'] == self.placeholder_color:
            self.delete('0', 'end')
            self['fg'] = self.default_fg_color

    def foc_out(self, *args):
        if not self.get():
            if self.raise_error_if_empty and self["state"] == NORMAL:
                messagebox.showerror("Ошибка!", "Пустой префикс! Устанавливаю предыдущий сохраненный префикс.")
                self.delete('0', 'end')
                self.insert(1, JSON_CONF_FILE["hierarchical_pref"])
                self.focus()
            else:
                self.put_placeholder()
        else:
            JSON_CONF_FILE["hierarchical_pref"] = self.get().replace(" ", "-").replace(self.placeholder, "")


tags_field_placeholder = "Тэги"
user_tags_field = EntryWithPlaceholder(root, placeholder=tags_field_placeholder)
tag_prefix_field = EntryWithPlaceholder(root, 14, init_text=JSON_CONF_FILE["hierarchical_pref"],
                                        raise_error_if_empty=True, justify="center")

if is_hierarchical.get():
    tag_prefix_field["state"] = NORMAL
else:
    tag_prefix_field["state"] = DISABLED

text_padx = 10
text_pady = 5

# Расстановка виджетов
word_parser_option_menu.grid(row=0, column=0, padx=text_padx, columnspan=5, sticky="ew")

word_text.grid(row=1, column=0, padx=text_padx, pady=text_pady, columnspan=5)

meaning_text.grid(row=3, column=0, padx=text_padx, pady=text_pady, columnspan=5)

flag.grid(row=2, column=0, padx=15, pady=5)
sentence_parser_option_menu.grid(row=4, column=0, padx=text_padx, columnspan=6, sticky="ew")
add_sentences_button.grid(row=4, column=0, padx=text_padx, sticky="ew")

for i in range(5):
    sent_text_list[i].grid(row=4 + i + 1, column=0, columnspan=3, padx=text_padx, pady=text_pady)
    buttons_list[i].grid(row=4 + i + 1, column=3, padx=0, pady=text_pady, sticky="ns")

delete_button.grid(row=5, column=4, padx=8, pady=text_pady, sticky="ns")
prev_button.grid(row=6, column=4, padx=3, pady=text_pady, sticky="ns")
add_sentences_button.grid(row=7, column=4, padx=3, pady=text_pady, sticky="ns")
skip_button.grid(row=8, column=4, rowspan=2, padx=3, pady=text_pady, sticky="ns")

user_tags_field.grid(row=10, column=0, padx=text_padx, pady=3, columnspan=3, sticky="news")
tag_prefix_field.grid(row=10, column=3, padx=0, pady=3, columnspan=2, sticky="news")

new_order = [word_text, meaning_text, add_sentences_button] + sent_text_list + [user_tags_field] + \
            buttons_list + [delete_button,  prev_button, skip_button, tag_prefix_field]


root.configure(bg=main_bg)
root.title(f"Поиск предложений для Anki. Осталось: {SIZE} слов.")
root.protocol("WM_DELETE_WINDOW", on_closing)
# Заставляет приложение вызваться поверх остальных окон
# root.call('wm', 'attributes', '.', '-topmost', True)
root.update()
WIDTH = root.winfo_width()
HEIGHT = root.winfo_height()
root.resizable(0, 0)


def focus_next_window(event):
    event.widget.tk_focusNext().focus()
    return ("break")


def focus_prev_window(event):
    event.widget.tk_focusPrev().focus()
    return ("break")


root.after(300_000, autosave)
refresh()
root.deiconify()
root.mainloop()
