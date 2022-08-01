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

pos_search:
    Whether to search audio by Part Of Speach (pos) or not
    valid values: (true, false) 
"""


_CONF_VALIDATION_SCHEME = \
    {
        "audio_region": ("us", [str], ["us", "uk"]),
    }

config = LoadableConfig(config_location=os.path.dirname(__file__),
                validation_scheme=_CONF_VALIDATION_SCHEME,
                docs=_CONFIG_DOCS)

_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")
_AUDIO_NAME_SPEC_CHARS = '/\\:*?\"<>| '


def get_audios(word, card_data: dict) -> AudioData:
    word = word.strip()
    if not word:
        return ([], []), ""

    audio_folder = f"{config['audio_region']}_audios"

    letter_group = word[0] if word[0].lower() in _LETTERS else "0-9"
    name = f"{remove_special_chars(word, '-', _AUDIO_NAME_SPEC_CHARS)}.mp3"
    search_root = os.path.join(LOCAL_MEDIA_DIR, audio_folder, letter_group)

    pos = card_data.get(FIELDS.dict_tags, {}).get("pos", "")
    clear_pos = remove_special_chars(pos.lower(), '-', _AUDIO_NAME_SPEC_CHARS)
    res = os.path.join(search_root, clear_pos, name)
    if not os.path.exists(res):
        return ([], []), ""
    if os.path.isfile(res):
        return ([res], [f"[{pos}] {os.path.splitext(name)[0]}"]), ""
    if os.path.isdir(res):
        file_paths = []
        additional_info = []
        for item in os.listdir(res):
            if os.path.isfile((file_path := os.path.join(res, item))):
                file_paths.append(file_path)
                additional_info.append(f"[{pos}] {os.path.splitext(item)[0]}")
        return (file_paths, additional_info), ""

    no_pos_location = os.path.join(search_root, name)
    if os.path.exists(no_pos_location):
        if os.path.isfile(no_pos_location):
            return ([no_pos_location], [name]), ""
        if os.path.isdir(no_pos_location):
            file_paths = []
            additional_info = []
            for item in os.listdir(no_pos_location):
                if os.path.isfile((file_path := os.path.join(no_pos_location, item))):
                    file_paths.append(file_path)
                    additional_info.append(os.path.splitext(item)[0])
            return (file_paths, additional_info), ""
    
    pos_dirs = [directory_path for directory in os.listdir(search_root)
                if os.path.isdir(directory_path := os.path.join(search_root, directory))]
    for dir_root in pos_dirs:
        for current_dir_path, dirs, files in os.walk(dir_root):
            if name in files:
                return ([os.path.join(str(current_dir_path), name)],
                        [f"[{os.path.split(current_dir_path)[-1]}] {os.path.splitext(name)[0]}"]), ""
            elif name in dirs:
                directory = os.path.join(str(current_dir_path), name)
                file_paths = []
                additional_info = []
                for item in os.listdir(directory):
                    if os.path.isfile((file_path := os.path.join(directory, item))):
                        file_paths.append(file_path)
                        additional_info.append(f"[{name}] {os.path.splitext(item)[0]}")
                return (file_paths, additional_info), ""
    return ([], []), ""

