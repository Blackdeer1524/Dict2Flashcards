import json
import os
from utils import get_local_audio_path, get_save_audio_name, AudioDownloader
from tkinter import Tk, Toplevel
import unicodedata
from html import unescape


JSON_DECK_DIR = "/home/blackdeer1524/Desktop/English_language/"
AUDIO_DICT = "us_audios"

with open(os.path.join(JSON_DECK_DIR, "deck.json"), "r", encoding="UTF-8") as f:
    deck = json.load(f)

AUDIO_DATA = []
all_decks = [deck]
while all_decks:
    current_deck = all_decks.pop(0)
    for note in current_deck.get("notes", []):
        word = unicodedata.normalize('NFKD', unescape(note["fields"][1]))
        tags = note.get("tags", [])
        current_pos = ""
        for tag in tags:
            if "pos" in tag:
                current_pos = tag.split(sep="::")[-1]
                break
        local_audio = get_local_audio_path(word, current_pos,
                                           f"./parsers/media/{AUDIO_DICT}", bool(current_pos)
                                           )
        new_audio_path = get_save_audio_name(word, current_pos, AUDIO_DICT)
        if local_audio:
            AUDIO_DATA.append([word, current_pos, AUDIO_DICT, ""])
            note["fields"][5] = f"[sound:{new_audio_path}]"
    all_decks.extend(current_deck["children"])

root = Tk()
root.withdraw()
audio_downloader = AudioDownloader(root, headers={}, timeout=1,
                                   temp_dir="./temp/",
                                   saving_dir="/home/blackdeer1524/.local/share/Anki2/User 1/collection.media",
                                   local_media_dir="./parsers/media/")
audio_downloader.bind("<Destroy>", lambda event: root.destroy() if isinstance(event.widget, Toplevel) else None)

with open(os.path.join(JSON_DECK_DIR, "p_deck.json"), "w", encoding="UTF-8") as f:
    json.dump(deck, f, indent=2)
root.after(0, lambda: audio_downloader.download_audio(AUDIO_DATA))
root.mainloop()
