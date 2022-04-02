from tkinter import Tk
from tkinter.filedialog import askopenfilename
import re
import time
from cambridge_parser import parse
import json
import random
from functools import reduce


PARSE_CASH = {}
MAX_LENGTH = 100
# DEQUE
LAST_ADDED_KEYS = []


def cashed_parse(word: str, dictionary_index: int = 0) -> (bool, dict):
    """
    :param word: word to be parsed
        :param dictionary_index:
        * 0 - English dictionary (Also used to search Idioms);
        * 1 - American dictionary;
        * 2 - Business dictionary
    :return: is_cashed, parsed_word
    """
    key = f"{word}_{dictionary_index}"
    if PARSE_CASH.get(key) is None:
        result = parse(word, dictionary_index)

        if len(LAST_ADDED_KEYS) == MAX_LENGTH:
            first_added_key = LAST_ADDED_KEYS.pop(0)
            PARSE_CASH.pop(first_added_key, None)
        LAST_ADDED_KEYS.append(key)
        PARSE_CASH[key] = result
        return False, result
    else:
        return True, PARSE_CASH[key]


def prepare_tags(tag_name, tag, list_tag=True, is_hierarchical=True):
    if list_tag:
        if tag[0] == "":
            return ""
        result = ""
        for item in tag:
            item = item.replace(' ', '_')
            if is_hierarchical:
                result += f"eng::{tag_name}::{item} "
            else:
                result += item + " "
        return result
    else:
        if tag == "":
            return ""
        tag = tag.replace(' ', '_')
        if is_hierarchical:
            return f"eng::{tag_name}::{tag} "
        return tag + " "


def translate_word(word_dict):
    """
    Adapt new parser to legacy code
    """
    word_list = []
    for word in word_dict:
        for pos in word_dict[word]:
            # uk_ipa = word_dict[word][pos]["UK IPA"]
            # us_ipa = word_dict[word][pos]["US IPA"]
            for definition, examples, domain, labels_and_codes, level, \
                region, usage in zip(word_dict[word][pos]["definitions"], word_dict[word][pos]["examples"],
                                     word_dict[word][pos]["domain"], word_dict[word][pos]["labels_and_codes"],
                                     word_dict[word][pos]["level"], word_dict[word][pos]["region"],
                                     word_dict[word][pos]["usage"]):
                # {"word": слово_n, "meaning": значение_n, "Sen_Ex": [пример_1, ..., пример_n]}
                word_list.append({"word": word, "meaning": definition,
                                  "Sen_Ex": examples, "domain": domain, "level": level, "region": region,
                                  "usage": usage, "pos": pos})
    return word_list


CURRENT_TIME = int(time.time())

file_open_window = Tk()
file_open_window.withdraw()
WORDS_PATH = askopenfilename(title="Выберете файл со словами", filetypes=(("JSON", ".json"),))
if len(WORDS_PATH) == 0:
    quit()

SAVE_DIR = WORDS_PATH.replace(".json", "[tagged].json")
file_open_window.destroy()

with open(WORDS_PATH, encoding="utf-8") as f:
    loaded_deck = json.load(f)

total_vol = len(loaded_deck["notes"])
print(total_vol)
last_string_length = 0

loaded_deck["notes"].sort(key=lambda x: x["fields"][1].lower())

exceptions = open(SAVE_DIR.replace(".json", "[exceptions].txt"), "w")


def clean_word(word, additional_cleaning=False):
    # https://stackoverflow.com/questions/9662346/python-code-to-remove-html-tags-from-a-string
    # old_pattern : '((<.*?>)|([^A-Za-z0-9\)\( ]+))' .replace("&nbsp", "")
    cleaner = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});')
    word = re.sub(cleaner, '', word)
    if additional_cleaning:
        word = re.sub("\(.*?\)", "", word)
    word = re.sub(" +", " ", word.replace("\n", " ").replace(":", " ").replace(";", " | ").strip())
    return word


def get_tag_list(word_block: dict, dictionary_index : int = 0) -> list:
    """
    :param word_block: loaded_deck["notes"][index]
    :param dictionary_index:
        * 0 - English dictionary (Also used to search Idioms);
        * 1 - American dictionary;
        * 2 - Business dictionary
    :return: exception_flag, tag_list
    """
    global last_string_length

    current_word = word_block["fields"][1]
    if not current_word:
        current_word = word_block["fields"][0]

    original_meaning = clean_word(word_block["fields"][2])
    prepared_word = clean_word(current_word)

    # logs
    prefix = "\\\\" if index % 2 == 0 else "//"
    log_string = f"\r{prefix}{index / total_vol * 100: .2f}% {prepared_word}"
    print("\r" + " " * last_string_length, end="")
    print(log_string, end="")
    last_string_length = len(log_string)

    try:
        is_cashed, parsed_word = cashed_parse(prepared_word, dictionary_index=dictionary_index)
        parsed_word = translate_word(parsed_word)
    except:
        # If NOT english dictionary
        if not dictionary_index:
            exceptions.write(prepared_word + "\n")
        parsed_word = None
        is_cashed = False

    tag_list = []
    # if word was parsed and current card has non-empty meaning field
    if parsed_word is not None and original_meaning:
        for item in parsed_word:
            item["meaning"] = clean_word(item["meaning"])

            if original_meaning in item["meaning"] or clean_word(original_meaning, True) in item["meaning"]:
                domain = prepare_tags("domain", item["domain"])
                level = prepare_tags("level", item["level"])
                region = prepare_tags("region", item["region"])
                usage = prepare_tags("usage", item["usage"])
                pos = prepare_tags("pos", item["pos"], False)
                tag_list = [domain, level, region, usage, pos]
                tag_list = reduce(lambda x, y: x + y, tag_list).strip().split()
                break
    if not is_cashed:
        time.sleep(round(random.randint(3, 4) / 10 + random.randint(0, 9) / 100, 2))
    return tag_list


try:
    for index in range(total_vol):
        # parsing eng dict
        tags = get_tag_list(loaded_deck["notes"][index])
        if tags:
            loaded_deck["notes"][index]["tags"] = tags
        # if nothing found in eng dict then parse american dict
        else:
            tags = get_tag_list(loaded_deck["notes"][index], 1)
            loaded_deck["notes"][index]["tags"] = tags
except:
    pass
finally:
    exceptions.close()
    with open(SAVE_DIR, "w", encoding="utf-8") as f:
        json.dump(loaded_deck, f)
