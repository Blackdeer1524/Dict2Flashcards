from cambridge_parser import define
from tkinter.filedialog import askopenfilename
from tkinter import Tk
import json
import os
import time


root = Tk()
root.withdraw()
filename = askopenfilename(title="Выберете файл со словами", initialdir="./")
root.destroy()

TEST_DIR = "./tests/"
if not os.path.exists(TEST_DIR):
    os.mkdir(TEST_DIR)
os.chdir(TEST_DIR)

with open(filename, encoding="UTF-8") as f:
    terms = f.readlines()

    word_index = 0
    last_log_length = 0
    word_logs = ("Words % \\\\", "Words % //")
    for search_term in terms:
        search_term = search_term.strip()

        log_string = f"\r{word_logs[word_index % 2]}{word_index / len(terms) * 100: .2f}%"
        print("\r" + " " * last_log_length, end="")
        print(log_string, end="")
        last_log_length = len(log_string)

        search_test_path = f"./original_{search_term}.json"
        if not os.path.exists(search_test_path):
            time.sleep(5)
            res = define(search_term)

            with open(search_test_path, "w", encoding="UTF-8") as j_f:
                json.dump(res, j_f, indent=4)

        word_index += 1
