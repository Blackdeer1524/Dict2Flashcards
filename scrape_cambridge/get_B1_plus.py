import json
import os
from parsers.word_parsers.local_cambridge_UK.translate import translate
from tkinter import Tk
from tkinter.filedialog import askopenfilename


PATH = "./LEVELS/"
if not os.path.exists(PATH):
    os.mkdir(PATH)
os.chdir(PATH)

root = Tk()
root.withdraw()
dict_path = askopenfilename(title="Выберете словарь", filetypes=(("JSON", ".json"),), initialdir="./")
root.destroy()
dict_name = dict_path.split(sep="/")[-1]


with open(dict_path, encoding="UTF-8") as f:
    result_dict = json.load(f)


b1_up = ("B1", "B2", "C1", "C2")
result = []
for word, word_data in result_dict:
    for pos in word_data:
        word_levels = word_data[pos]["level"]
        for level in word_levels:
            if level and level[0] in b1_up:
                result.append([word, word_data])
                break
        else:
            continue
        break


translated_result = translate(result)
translated_result.sort(key=lambda x: x["word"].strip().lower())
with open(f"./B1_plus_{dict_name}.json", "w", encoding="UTF8") as write_f:
    json.dump(translated_result, write_f)
