from typing import Generator, TypeVar


AudioData = tuple[tuple[list[str], list[str]], str]
T = TypeVar("T")
DictionaryFormat = list[tuple[str, T]]
ImageGenerator = Generator[tuple[list[str], str], int, tuple[list[str], str]]
SentenceData = tuple[list[str], str]
SentenceGenerator = Generator[SentenceData, int, SentenceData]
AudioGenerator = Generator[AudioData, int, AudioData]
