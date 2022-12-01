import os.path

from app_utils.string_utils import remove_special_chars
from consts import CardFields

SCHEME_PREFIX = os.path.basename(__file__).rstrip(".py")


def get_save_image_name(word: str,
                        image_source: str,
                        image_parser_name: str,
                        card_data: dict) -> str:
    return f"mined-{SCHEME_PREFIX}-{image_parser_name}-{remove_special_chars(word, sep='-')}-{hash(image_source)}.png"


def get_card_image_name(saved_image_path: str) -> str:
    return f"<img src='{os.path.split(saved_image_path)[-1]}'/>"


def get_save_audio_name(word: str, 
                        audio_provider: str,
                        uniqueness_postfix: str, 
                        card_data: dict) -> str:
    word = word.strip().lower()
    pos = card_data.get(CardFields.dict_tags, {}).get("pos")

    raw_audio_name = f"{remove_special_chars(pos, sep='-')}-{remove_special_chars(word, sep='-')}" \
        if pos is not None else remove_special_chars(word, sep='-')

    prepared_word_parser_name = remove_special_chars(audio_provider, sep='-')
    audio_name = f"mined-{SCHEME_PREFIX}-{prepared_word_parser_name}-{raw_audio_name}-{uniqueness_postfix}.mp3"
    return audio_name


def get_card_audio_name(saved_audio_path: str) -> str:
    return f"[sound:{os.path.split(saved_audio_path)[-1]}]"


def process_card(card: dict) -> None:
    return
