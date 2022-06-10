import os
from utils.string_utils import remove_special_chars
from consts.paths import LOCAL_MEDIA_DIR


LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")
AUDIO_NAME_SPEC_CHARS = '/\\:*?\"<>| '
AUDIO_FOLDER = "us_audios"


def get_local_audio_path(word: str, dict_tags: dict):
    word = word.strip().lower()
    pos = dict_tags.get("pos", "")
    if not word or not pos:
        return ""

    letter_group = word[0] if word[0] in LETTERS else "0-9"
    name = f"{remove_special_chars(word.lower(), '-', AUDIO_NAME_SPEC_CHARS)}.mp3"
    search_root = os.path.join(LOCAL_MEDIA_DIR, AUDIO_FOLDER, letter_group)
    pos = remove_special_chars(pos.lower(), '-', AUDIO_NAME_SPEC_CHARS)
    res = os.path.join(search_root, pos, name)
    return res if os.path.exists(res) else ""
