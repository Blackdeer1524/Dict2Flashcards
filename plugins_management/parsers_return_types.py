from typing import NewType, Generator, Iterator


AudioData = tuple[tuple[list[str], list[str]], str]
ImageGenerator = NewType("ImageGenerator", Generator[tuple[list[str], str], int, tuple[list[str], str]])
SentenceGenerator = NewType("SentenceGenerator", Generator[tuple[list[str], str], int, tuple[list[str], str]])
