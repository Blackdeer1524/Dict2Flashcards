from .. import StrEnum
from enum import auto
from dataclasses import dataclass, field


class ParserType(StrEnum):
    web = auto()
    local = auto()
    chain = auto()

    def prefix(self):
        return f"[{self}]"


@dataclass(frozen=True, slots=True)
class TypedParserName():
    parser_t: ParserType
    name: str

    full_name: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "full_name", f"{self.parser_t.prefix()} {self.name}")
