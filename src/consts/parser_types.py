from enum import StrEnum, auto


class ParserTypes(StrEnum):
    web = auto()
    local = auto()
    chain = auto()

    def prefix(self):
        return f"[{self}]"
