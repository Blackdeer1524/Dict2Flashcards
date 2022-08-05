from typing import NewType, Generator


AudioData = NewType("AudioData", tuple[tuple[list[str], list[str]], str])
ImageGenerator = NewType("ImageGenerator", Generator[tuple[list[str], str], int, tuple[list[str], str]])
SentenceGenerator = NewType("SentenceGenerator", Generator[tuple[list[str], str], int, tuple[list[str], str]])
AudioGenerator = NewType("AudioGenerator", Generator[AudioData, int, AudioData])
