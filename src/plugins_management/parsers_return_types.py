from typing import Generator, TypeVar

from ..consts import CardFormat  # <---  import for plugins!!!

T = TypeVar("T")
DictionaryFormat = list[tuple[str, T]]
ImageGenerator = Generator[tuple[list[str], str], int, tuple[list[str], str]]
SentenceData = tuple[list[str], str]
SentenceGenerator = Generator[SentenceData, int, SentenceData]
AudioData = tuple[tuple[list[str], list[str]], str]
AudioGenerator = Generator[AudioData, int, AudioData]
