from local_cambridge_parser import define
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
os.chdir(TEST_DIR)


with open(filename, encoding="UTF-8") as f:
    terms = f.readlines()

    for html_path in terms:
        html_path = html_path.strip()

        search_term = os.path.split(html_path)[-1][:-18].strip()
        search_test_path = f"./original_{search_term}.json"

        if not os.path.exists(search_test_path):
            print(search_test_path, 'doesn\'t exist')
            continue

        with open(html_path, "r", encoding="utf-8") as f:
            current_res = define(f.read())
        with open(search_test_path, "r", encoding="UTF-8") as right_j_f:
            right_res = json.load(right_j_f)

        print(search_term, ": ", sep="", end="")
        if current_res == right_res:
            print("Pass")
        else:
            with open(f"./wrong_{search_term}.json", "w", encoding="UTF-8") as wrong_j_f:
                json.dump(current_res, wrong_j_f, indent=4)
            print("Failed")
