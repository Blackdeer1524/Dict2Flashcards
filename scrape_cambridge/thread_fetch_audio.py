import requests
import time
import json
import concurrent.futures
import os
import re


def fetch_audio(audio_url, audio_save_path):
    try:
        r = requests.get(audio_url, timeout=5, headers=headers)
        if r.status_code == 200:
            audio_bin = r.content
            with open(audio_save_path, "wb") as audio_file:
                audio_file.write(audio_bin)
        if r.status_code != 404:
            r.raise_for_status()
    except Exception as e:
        print("======\n", e, audio_url, "\n======\n")
        time.sleep(10)
        fetch_audio(audio_url, audio_save_path)


def remove_forbidden_chars(text, sep=" ", spec_exceptions=None):
    """
    :param text: to to clean
    :param sep: replacement for special chars
    :param spec_exceptions: skip chars

    chars: (!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ )

    :return:
    """
    remove_chars = '/\\:*?\"<>| '
    if spec_exceptions is None:
        spec_exceptions = []

    for char in remove_chars:
        if char not in spec_exceptions:
            text = text.replace(char, sep)
    text = re.sub(f"({sep})+", text, sep)
    return text.strip(sep)


user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
headers = {'User-Agent': user_agent}

with open("./uk_audio.json", encoding="utf-8") as f:
    uk_audio_file = json.load(f)

with open("./us_audio.json", encoding="utf-8") as f:
    us_audio_file = json.load(f)

futures_list = []

audio_path = "./Audios"
if not os.path.exists(audio_path):
    os.mkdir(audio_path)

uk_path = f"{audio_path}/uk_audios"
if not os.path.exists(uk_path):
    os.mkdir(uk_path)

us_path = f"{audio_path}/us_audios"
if not os.path.exists(us_path):
    os.mkdir(us_path)

length = len(uk_audio_file) + len(us_audio_file)
i = 0
prefs = ("\\\\", "//")
last_flag = False
last_string_length = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    for item in uk_audio_file:
        if not (i % 50):
            prefix = prefs[last_flag]
            log_string = f"\r{prefix}{i / length * 100: .2f}%"
            print("\r" + " " * last_string_length, end="")
            print(log_string, end="")
            last_string_length = len(log_string)
            last_flag = not last_flag
        i += 1

        word, pos, _, url = item
        save_path = uk_path + f"/{remove_forbidden_chars(word.lower(), '-')}${remove_forbidden_chars(pos)}.mp3"
        if not os.path.exists(save_path):
            futures_list.append(executor.submit(fetch_audio, url, save_path))

    for item in us_audio_file:
        if not (i % 50):
            prefix = prefs[last_flag]
            log_string = f"\r{prefix}{i / length * 100: .2f}%"
            print("\r" + " " * last_string_length, end="")
            print(log_string, end="")
            last_string_length = len(log_string)
            last_flag = not last_flag
        i += 1

        word, pos, _, url = item
        save_path = us_path + f"/{remove_forbidden_chars(word.lower(), '-')}${remove_forbidden_chars(pos)}.mp3"
        if not os.path.exists(save_path):
            futures_list.append(executor.submit(fetch_audio, url, save_path))

concurrent.futures.wait(futures_list)
