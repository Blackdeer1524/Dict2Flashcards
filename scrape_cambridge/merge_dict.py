import json
import os


DICT_PATH = r"C:\Users\Danila\Desktop\sentence_mining\dictionaries\cambridge"
JSON_PARTS_PATH = os.path.join(DICT_PATH, "json")

res = []
for filename in os.listdir(JSON_PARTS_PATH):
    path = os.path.join(JSON_PARTS_PATH, filename)
    with open(path, "r", encoding="utf-8") as f:
        res.extend(json.load(f))

res.sort(key=lambda x: x[0])
for i in range(len(res) - 1, 0, -1):
    if res[i][0] == res[i - 1][0]:
        for pos in res[i][1]:
            if res[i - 1][1].get(pos) is None:
                res[i - 1][1][pos] = res[i][1][pos]
            else:
                for definition_ind in range(len(res[i][1][pos]["definitions"])):
                    if res[i][1][pos]["definitions"][definition_ind] not in res[i - 1][1][pos]["definitions"]:
                        res[i - 1][1][pos]["definitions"].append(res[i][1][pos]["definitions"][definition_ind])
                        res[i - 1][1][pos]["alt_terms"].append(res[i][1][pos]["alt_terms"][definition_ind])
                        res[i - 1][1][pos]["examples"].append(res[i][1][pos]["examples"][definition_ind])
                        res[i - 1][1][pos]["level"].append(res[i][1][pos]["level"][definition_ind])
                        res[i - 1][1][pos]["labels_and_codes"].append(res[i][1][pos]["labels_and_codes"][definition_ind])
                        res[i - 1][1][pos]["region"].append(res[i][1][pos]["region"][definition_ind])
                        res[i - 1][1][pos]["usage"].append(res[i][1][pos]["usage"][definition_ind])
                        res[i - 1][1][pos]["domain"].append(res[i][1][pos]["domain"][definition_ind])
                        res[i - 1][1][pos]["image_links"].append(res[i][1][pos]["image_links"][definition_ind])
        res.pop(i)

with open(os.path.join(DICT_PATH, "trimmed_local_cambridge_dict.json"), "w", encoding="utf-8") as f:
    json.dump(res, f)
