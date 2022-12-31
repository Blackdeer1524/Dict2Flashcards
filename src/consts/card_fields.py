from enum import StrEnum


class CardFields(StrEnum):
    word: str = "word"
    special: str = "special"
    definition: str = "definition"
    sentences: str = "examples"
    img_links: str = "image_links"
    audio_links: str = "audio_links"
    dict_tags: str = "tags"
