from typing import NamedTuple


__all__ = ["FIELDS"]


class _CardFields(NamedTuple):
    word: str = "word"
    alt_terms: str = "alt_terms"
    definition: str = "meaning"
    sentences: str = "Sen_Ex"
    img_links: str = "image_link"
    audio_links: str = "audio_link"
    dict_tags: str = "dict_tags"
    user_tags: str = "user_tags"


FIELDS = _CardFields()
