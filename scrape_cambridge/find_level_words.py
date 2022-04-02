import json
import os

os.chdir("./LEVELS")
levels = ("A1", "A2", "B1", "B2", "C1", "C2")
level_dicts = {}
level_files = {}
for level in levels:
    level_dicts[level] = []
    level_files[level] = set()  # open(f"./{level}.txt", "w", encoding="UTF8")


with open("/parsers/word_parsers/local_cambridge/parsed_local_cambridge.json") as f:
    data = json.load(f)


for word_block in data:
    word_level = word_block["level"][0]
    if word_level in levels:
        level_dicts[word_level].append(word_block)
        saving_meaning = word_block["meaning"].strip()
        if saving_meaning.endswith(":"):
            saving_meaning = saving_meaning[:-1]
        level_files[word_level].add(word_block["word"].strip() + "|" + saving_meaning)

for level in levels:
    with open(f"./{level}.json", "w", encoding="UTF8") as json_write_file:
        level_dicts[level] = list(level_dicts[level])
        level_dicts[level].sort(key=lambda x: x["word"].lower())
        json.dump(level_dicts[level], json_write_file)
    with open(f"./{level}.txt", "w", encoding="UTF8") as txt_write_file:
        listed_files = list(level_files[level])
        listed_files.sort(key=str.lower)
        str_repr = "\n".join(level_files[level]) + "\n"
        txt_write_file.write(str_repr)
