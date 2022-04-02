import random
import json
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
import os
import time
from parsers.word_parsers.web_cambridge import define


"""
Fix parser name
"""

CURRENT_TIME = int(time.time())

file_open_window = Tk()
file_open_window.withdraw()
WORDS_PATH = askopenfilename(title="Выберете файл со словами", filetypes=(("TXT", ".txt"),))
if len(WORDS_PATH) == 0:
    quit()

FILE_NAME = os.path.split(WORDS_PATH)[-1][:-4]

SAVE_DIR = askdirectory(title="Выберете директорию для сохранения")
if len(SAVE_DIR) == 0:
    quit()

file_open_window.destroy()


def get_word(word, d=0):
    try:
        if d == 6:
            raise ValueError
        return define(word)
    except ValueError:
        exceptions.write(word + '\n')
    except AttributeError:
        exceptions.write(word + '\n')
    except:
        time.sleep(10)
        return get_word(word, d=d+1)
    return []


# words accounting
word_counter = 0
with open(WORDS_PATH, 'r') as f:
    for line in f:
        word_counter += 1


WORDS = []
with open(WORDS_PATH, 'r') as word_list, \
        open(f"{SAVE_DIR}/[EXCEPTIONS]{FILE_NAME}_{CURRENT_TIME}.txt", "w") as exceptions:
    print("Слов обработано (%): ")
    last_string_length = 0
    for i, word in enumerate(word_list, 1):
        word = word.rstrip()
        prefix = "\\\\" if i % 2 == 0 else "//"
        log_string = f"\r{prefix}{i / word_counter * 100: .2f}% {word}"
        print("\r" + " " * last_string_length, end="")
        print(log_string, end="")
        last_string_length = len(log_string)
        result = get_word(word)
        if result is not None:
            WORDS.extend(result)
            # time.sleep(round(random.randint(4, 6) / 10 + random.randint(0, 9) / 100, 2))
        if i % 500 == 0:
            with open(f"{SAVE_DIR}/[WORDS]{FILE_NAME}_{CURRENT_TIME}.json", "w", encoding="utf-8") as write_file:
                json.dump(WORDS, write_file)
            with open(f"{SAVE_DIR}/local_dict_history.txt", "w") as f:
                f.write(str(i))
