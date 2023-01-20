import os

from .. import app_utils, config_management, consts, parsers_return_types

AUDIO_FOLDER = "cambridge"

_CONFIG_DOCS = \
"""
type: 
    Audio region 
    valid values: either of ["uk", "us"] 

pos_only:
    Whether to search audio by Part Of Speach (pos) or not
    valid values: (true, false) 
"""


_CONF_VALIDATION_SCHEME = \
    {
        "audio_region": ("us", [str], ["us", "uk"]),
        "pos_only": (False, [bool], [False, True])
    }

config = config_management.LoadableConfig(config_location=os.path.dirname(__file__),
                                          validation_scheme=_CONF_VALIDATION_SCHEME,
                                          docs=_CONFIG_DOCS)

_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")
_AUDIO_NAME_SPEC_CHARS = '/\\:*?\"<>| '


def get(word, card_data: dict) -> parsers_return_types.AUDIO_SCRAPPER_RETURN_T:
    word = word.strip()
    if not word:
        return [], ""

    letter_group = lower_first_letter if (lower_first_letter := word[0].lower()) in _LETTERS else "0-9"
    search_root = os.path.join(consts.paths.LOCAL_AUDIO_DIR, AUDIO_FOLDER, config["audio_region"], letter_group)

    filename_without_extension = f"{app_utils.string_utils.remove_special_chars(word, '-', _AUDIO_NAME_SPEC_CHARS)}"
    extension = ".mp3"
    filename_with_extension = filename_without_extension + extension

    pos = card_data.get(consts.CardFields.dict_tags, {}).get("pos", "")
    clear_pos = app_utils.string_utils.remove_special_chars(pos.lower(), '-', _AUDIO_NAME_SPEC_CHARS)

    batch_size = yield
    if clear_pos:
        given_pos_dir = os.path.join(search_root, clear_pos)
        pos_audio_file_path = os.path.join(given_pos_dir, filename_with_extension)
        if os.path.isfile(pos_audio_file_path):
            return [(pos_audio_file_path, f"[{pos}] {filename_without_extension}")], ""

        pos_named_dir = os.path.join(given_pos_dir, filename_without_extension)
        if os.path.isdir(pos_named_dir):
            audio_batch: list[tuple[str, str]] = []
            for item in os.listdir(pos_named_dir):
                if os.path.isfile(file_path := os.path.join(pos_named_dir, item)):
                    audio_batch.append((file_path, f"[{pos}] {os.path.splitext(item)[0]}"))
                    if len(audio_batch) == batch_size:
                        batch_size = yield audio_batch, ""
                        audio_batch = []
            return audio_batch, ""
    
    if config["pos_only"]:
        return [], ""

    no_pos_audio_file_path = os.path.join(search_root, filename_with_extension)
    if os.path.isfile(no_pos_audio_file_path):
        return [(no_pos_audio_file_path, filename_without_extension)], ""
    
    pos_dirs = [(directory_path, directory) for directory in os.listdir(search_root)
                if os.path.isdir(directory_path := os.path.join(search_root, directory))]
    
    for pos_dir_abspath, pos in pos_dirs:
        files = []
        dirs = []

        for item in os.listdir(pos_dir_abspath):
            joined_name = os.path.join(pos_dir_abspath, item)
            if os.path.isfile(joined_name):
                files.append(item)
            elif os.path.isdir(joined_name):
                dirs.append(item)

        if filename_with_extension in files:
            return [(os.path.join(pos_dir_abspath, filename_with_extension), f"[{pos}] {filename_without_extension}")], ""

        if filename_without_extension in dirs:
            directory = os.path.join(pos_dir_abspath, filename_without_extension)
            audio_batch = []
            for item in os.listdir(directory):
                if os.path.isfile((file_path := os.path.join(directory, item))):
                    audio_batch.append((file_path, f"[{pos}/{filename_without_extension}] {os.path.splitext(item)[0]}"))
                    if len(audio_batch) == batch_size:
                        batch_size = yield audio_batch, ""
                        audio_batch = []

            return audio_batch, ""
    return [], ""

