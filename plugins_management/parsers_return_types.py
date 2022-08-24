from typing import NewType, Generator


AudioData = NewType("AudioData", tuple[tuple[list[str], list[str]], str])
DictionaryFormat = NewType("DictionaryFormat", list[tuple[str, dict]])
ImageGenerator = NewType("ImageGenerator", Generator[tuple[list[str], str], int, tuple[list[str], str]])
SentenceData = tuple[list[str], str]
SentenceGenerator = NewType("SentenceGenerator", Generator[SentenceData, int, SentenceData])
AudioGenerator = NewType("AudioGenerator", Generator[AudioData, int, AudioData])
