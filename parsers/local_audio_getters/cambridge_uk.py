import os
from utils.string_utils import remove_special_chars
from consts.paths import LOCAL_MEDIA_DIR


LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")
AUDIO_NAME_SPEC_CHARS = '/\\:*?\"<>| '
AUDIO_FOLDER = "uk_audios"


def get_local_audio_path(word, dict_tags: dict):
    word = word.strip()
    if not word:
        return ""

    letter_group = word[0] if word[0].lower() in LETTERS else "0-9"
    name = f"{remove_special_chars(word, '-', AUDIO_NAME_SPEC_CHARS)}.mp3"
    search_root = os.path.join(LOCAL_MEDIA_DIR, AUDIO_FOLDER, letter_group)

    for current_dir_path, dirs, files in os.walk(search_root):
        if name in files:
            return os.path.join(current_dir_path, name)
    return ""
