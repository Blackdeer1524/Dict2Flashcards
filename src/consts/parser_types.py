from .. import StrEnum
from enum import auto
from dataclasses import dataclass, field


class ParserType(StrEnum):
    web = auto()
    local = auto()
    chain = auto()
    custom = auto()

    def prefix(self):
        return f"[{self}]"

    @staticmethod
    def merge_into_full_name(parser_type: "ParserType", parser_name: str) -> str:
        return f"{parser_type.prefix()} {parser_name}"


_WEB_PREFIX = ParserType.web.prefix()
_LOCAL_PREFIX = ParserType.local.prefix()
_CHAIN_PREFIX = ParserType.chain.prefix()
_CUSTOM_PREFIX = ParserType.custom.prefix()


@dataclass(frozen=True, slots=True)
class TypedParserName():
    parser_t: ParserType
    name: str

    @property
    def full_name(self) -> str:
        return ParserType.merge_into_full_name(self.parser_t, self.name)

    @staticmethod
    def split_full_name(full_name: str) -> "TypedParserName":
        """splits full name <[ParserType] parser_name>. Raises Value error if unknown ParserType was given"""
        if full_name.startswith(_WEB_PREFIX):
            return TypedParserName(parser_t=ParserType.web, name=full_name[len(_WEB_PREFIX) + 1:])
        elif full_name.startswith(_LOCAL_PREFIX):
            return TypedParserName(parser_t=ParserType.local, name=full_name[len(_LOCAL_PREFIX) + 1:])
        elif full_name.startswith(_CHAIN_PREFIX):
            return TypedParserName(parser_t=ParserType.chain, name=full_name[len(_CHAIN_PREFIX) + 1:])
        elif full_name.startswith(_CUSTOM_PREFIX):
            return TypedParserName(parser_t=ParserType.custom, name=full_name[len(_CUSTOM_PREFIX) + 1:])
        raise ValueError(f"Failed to split full name {full_name}: unknown parser type")
