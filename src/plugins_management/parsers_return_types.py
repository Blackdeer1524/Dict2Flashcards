from typing import Generator

from ..consts import CardFormat  # <---  import for plugins!!!

IMAGE_DATA_T = tuple[list[str], str]
IMAGE_SCRAPPER_RETURN_T = Generator[IMAGE_DATA_T, int, IMAGE_DATA_T]
SENTENCE_DATA_T = tuple[list[str], str]
SENTENCE_SCRAPPER_RETURN_T = Generator[SENTENCE_DATA_T, int, SENTENCE_DATA_T]
AUDIO_DATA_T = tuple[tuple[list[str], list[str]], str]
AUDIO_SCRAPPER_RETURN_T = Generator[AUDIO_DATA_T, int, AUDIO_DATA_T]
