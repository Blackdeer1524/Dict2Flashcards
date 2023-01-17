from typing import Generator

from ..consts import CardFormat  # <---  import for plugins!!!

ImageGeneratorProtocol = Generator[tuple[list[str], str], int, tuple[list[str], str]]
SentenceData = tuple[list[str], str]
SENTENCE_SCRAPPER_RETURN_T = Generator[SentenceData, int, SentenceData]
AudioData = tuple[tuple[list[str], list[str]], str]
AUDIO_SCRAPPER_RETURN_T = Generator[AudioData, int, AudioData]
