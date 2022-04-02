import os
import json
from cambridge_scrapper_vars.local_cambridge_parser import define
import concurrent.futures


def get_file_content(path: str) -> str:
    with open(path, "r", encoding="utf-8") as html_f:
        return html_f.read()

DICT_LOCATION = r"C:\Users\Danila\Desktop\sentence_mining\dictionaries\cambridge"
HTMLS_LOCATION = os.path.join(DICT_LOCATION, "html")
SAVING_LOCATION = os.path.join(DICT_LOCATION, "json")
if not os.path.exists(SAVING_LOCATION):
    os.makedirs(SAVING_LOCATION)

executor = concurrent.futures.ThreadPoolExecutor()

s = False
section_logs = ("Done % \\\\", "Done % //")
last_log_length = 0
for folder_name in os.listdir(HTMLS_LOCATION):
    print("\n\n", folder_name)

    res = []
    folder_path = os.path.join(HTMLS_LOCATION, folder_name)
    folder_containments = os.listdir(folder_path)
    json_saving_loc = os.path.join(SAVING_LOCATION, folder_name) + ".json"

    if os.path.exists(json_saving_loc):
        continue

    step = 50
    for batch_start in range(0, len(folder_containments), step):
        log_string = f"\r{section_logs[s]}{batch_start / len(folder_containments) * 100: .2f}%"
        print("\r" + " " * last_log_length, end="")
        print(log_string, end="")
        s = not s
        last_log_length = len(log_string)
        
        files = [os.path.join(folder_path, file_path) for file_path in folder_containments[batch_start:batch_start+step]]
        get_file_content_results = executor.map(get_file_content, files)

        intermediate_res = []
        for content in get_file_content_results:
            intermediate_res.append(define(content))
        res.extend([[word, definitions] for block in intermediate_res for word, definitions in block.items()])

    with open(json_saving_loc, "w", encoding="utf-8") as json_f:
        json.dump(sorted(res, key=lambda x: x[0]), json_f, indent=2)
