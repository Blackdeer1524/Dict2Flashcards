from typing import NamedTuple


__all__ = ["FIELDS"]


class _CardFields(NamedTuple):
    word: str = "word"
    alt_terms: str = "alt_terms"
    definition: str = "definition"
    sentences: str = "examples"
    img_links: str = "image_links"
    audio_links: str = "audio_links"
    dict_tags: str = "tags"


FIELDS = _CardFields()
