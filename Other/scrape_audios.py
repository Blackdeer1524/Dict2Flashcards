import os
import json
from str_utils import remove_special_chars
from string import ascii_lowercase
import concurrent.futures
import requests
import time


LETTERS = set(ascii_lowercase)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'}
remove_chars = '/\\:*?\"<>| '


def get_local_audio_path(word, pos="", local_audio_folder="./", with_pos=True):
    word = word.strip().lower()
    if not word:
        return ""


    letter_group = word[0] if word[0] in LETTERS else "0-9"
    name = f"{remove_special_chars(word.lower(), '-', remove_chars)}.mp3"
    search_root = f"{local_audio_folder}/{letter_group}"
    if with_pos:
        pos = remove_special_chars(pos.lower(), '-', remove_chars)
        res = f"{search_root}/{pos}/{name}"
    else:
        res = ""
        for root, dirs, files in os.walk(search_root):
            if name in files:
                res = os.path.join(root, name)
                break
    return res if os.path.exists(res) else ""


def get_web_content(url, saving_path):
    try:
        r = requests.get(url, timeout=5, headers=headers)
        return r.content, saving_path
    except:
        print("sleep")
        time.sleep(30)
        return get_web_content(url, saving_path)


def download(audio_bin, result_path):
    with open(result_path, "wb") as audio_file:
        audio_file.write(audio_bin)


audio_data_dir = "C:/Users/Danila/Desktop/sentence_mining/dictionaries/cambridge/media_info/"

os.chdir("C:/Users/Danila/Desktop/sentence_mining/parsers/media")
# n = 0
# total = 0
# for data_name in ("uk_audios", "us_audios"):
#     needs_to_be_downloaded = []
#
#     with open(os.path.join(audio_data_dir, data_name + ".json"), encoding="utf-8") as data_f:
#         data = json.load(data_f)
#
#     for word, pos, scrapper, url in data:
#         search = get_local_audio_path(word, pos, local_audio_folder=f"./{data_name}", with_pos=True)
#         if not search:
#             needs_to_be_downloaded.append([word, pos, scrapper, url])
#
#     with open(os.path.join(audio_data_dir, data_name + "_addiotional.json"), "w", encoding="utf-8") as data_f:
#         json.dump(needs_to_be_downloaded, data_f, indent=2)

executor = concurrent.futures.ThreadPoolExecutor()

step = 50
for data_name in ("uk_audios", "us_audios"):
    with open(os.path.join(audio_data_dir, data_name + "_addiotional.json"), encoding="utf-8") as data_f:
        data = json.load(data_f)

    last_log_length = 0
    total_len = len(data)
    out = 0
    section_logs = ("Done % \\\\", "Done % //")
    while data:
        batch = data[:step]
        submitting_data = []
        for word, pos, _, url in batch:
            word = remove_special_chars(word, "-", remove_chars)
            pos = remove_special_chars(pos, "-", remove_chars)
            letter_group = word[0] if word[0] in LETTERS else "0-9"
            if pos:
                pos_dir = os.path.join(data_name, letter_group, pos)
                if not os.path.exists(pos_dir):
                    os.mkdir(pos_dir)
                result_path = os.path.join(pos_dir, word + ".mp3")
            else:
                result_path = os.path.join(data_name, letter_group, word + ".mp3")
            if not os.path.exists(result_path):
                submitting_data.append((url, result_path))

        content_res = []
        for url, result_path in submitting_data:
            content_res.append(executor.submit(get_web_content, url, result_path))

        for result in concurrent.futures.as_completed(content_res):
            content, result_path = result.result()
            if word is not None:
                executor.submit(download, content, result_path)

        del data[:step]

        log_string = f"\r{section_logs[out]}{(1 - len(data) / total_len) * 100: .2f}% | {len(data)}"
        print("\r" + " " * last_log_length, end="")
        print(log_string, end="")
        out = not out
        last_log_length = len(log_string)
