import os.path

from utils.string_utils import remove_special_chars


def get_saving_image_name(word: str,
                          image_source: str,
                          dict_tags: dict,
                          image_parser_name: str) -> str:
    return f"mined-{remove_special_chars(word, sep='-')}-{hash(image_source)}.png"


def get_card_image_name(saved_image_path: str) -> str:
    return f"<img src='{os.path.split(saved_image_path)[-1]}.png'/>"


def get_save_audio_name(word: str, dict_tags: dict, word_parser_name: str) -> str:
    word = word.strip().lower()
    pos = dict_tags.get("pos")

    raw_audio_name = f"{remove_special_chars(word, sep='-')}-{remove_special_chars(pos, sep='-')}" \
        if pos is not None else remove_special_chars(word, sep='-')

    prepared_word_parser_name = remove_special_chars(word_parser_name, sep='-')
    audio_name = f"mined-{raw_audio_name}-{prepared_word_parser_name}.mp3"
    return audio_name


def get_card_audio_name(saved_audio_path: str) -> str:
    return f"[sound:{os.path.split(saved_audio_path)[-1]}]"


def process_dict_tags(tags: dict) -> dict:
    return tags
