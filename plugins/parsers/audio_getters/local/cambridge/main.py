import os

from app_utils.string_utils import remove_special_chars
from consts.card_fields import FIELDS
from consts.paths import LOCAL_MEDIA_DIR
from plugins_management.config_management import LoadableConfig
from plugins_management.parsers_return_types import AudioData

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

config = LoadableConfig(config_location=os.path.dirname(__file__),
                validation_scheme=_CONF_VALIDATION_SCHEME,
                docs=_CONFIG_DOCS)

_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")
_AUDIO_NAME_SPEC_CHARS = '/\\:*?\"<>| '


def get(word, card_data: dict) -> AudioData:
    word = word.strip()
    if not word:
        return ([], []), ""

    audio_folder = f"{config['audio_region']}_audios"
    letter_group = lower_first_letter if (lower_first_letter := word[0].lower()) in _LETTERS else "0-9"
    search_root = os.path.join(LOCAL_MEDIA_DIR, audio_folder, letter_group)

    filename_without_extension = f"{remove_special_chars(word, '-', _AUDIO_NAME_SPEC_CHARS)}"
    extension = ".mp3"
    filename_with_extension = filename_without_extension + extension

    pos = card_data.get(FIELDS.dict_tags, {}).get("pos", "")
    clear_pos = remove_special_chars(pos.lower(), '-', _AUDIO_NAME_SPEC_CHARS)

    batch_size = yield
    if clear_pos:
        given_pos_dir = os.path.join(search_root, clear_pos)
        pos_audio_file_path = os.path.join(given_pos_dir, filename_with_extension)
        if os.path.isfile(pos_audio_file_path):
            return ([pos_audio_file_path], [f"[{pos}] {filename_without_extension}"]), ""

        pos_named_dir = os.path.join(given_pos_dir, filename_without_extension)
        if os.path.isdir(pos_named_dir):
            file_paths = []
            additional_info = []
            for item in os.listdir(pos_named_dir):
                if os.path.isfile(file_path := os.path.join(pos_named_dir, item)):
                    file_paths.append(file_path)
                    additional_info.append(f"[{pos}] {os.path.splitext(item)[0]}")

                    if len(file_paths) == batch_size:
                        batch_size = yield (file_paths, additional_info), ""
                        file_paths = []
                        additional_info = []
            return (file_paths, additional_info), ""
    
    if config["pos_only"]:
        return ([], []), ""

    no_pos_audio_file_path = os.path.join(search_root, filename_with_extension)
    if os.path.isfile(no_pos_audio_file_path):
        return ([no_pos_audio_file_path], [filename_without_extension]), ""
    
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
            return ([os.path.join(pos_dir_abspath, filename_with_extension)],
                    [f"[{pos}] {filename_without_extension}"]), ""

        if filename_without_extension in dirs:
            directory = os.path.join(pos_dir_abspath, filename_without_extension)
            file_paths = []
            additional_info = []
            for item in os.listdir(directory):
                if os.path.isfile((file_path := os.path.join(directory, item))):
                    file_paths.append(file_path)
                    additional_info.append(f"[{pos}/{filename_without_extension}] {os.path.splitext(item)[0]}")

                    if len(file_paths) == batch_size:
                        batch_size = yield (file_paths, additional_info), ""
                        file_paths = []
                        additional_info = []

            return (file_paths, additional_info), ""
    return ([], []), ""

