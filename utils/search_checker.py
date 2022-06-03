from consts.card_fields import FIELDS
from typing import Optional, Any
from enum import Enum, auto
from dataclasses import dataclass, field
from utils.cards import Card


FIELD_NAMES_SET = frozenset(FIELDS)
LOGIC_SET = frozenset(("and", "or", "not", "<", "<=", ">", ">=", "==", "!="))
FIELD_VAL_SEP = ":"


class ParsingException(Exception):
    pass


class WrongTokenException(ParsingException):
    pass


class QuerySyntaxError(ParsingException):
    pass


class TokenType(Enum):
    START = auto()
    END = auto()
    SEP = auto()
    LOGIC = auto()
    PARENTHESIS = auto()
    VALUE = auto()
    WRONG_VALUE = auto()

@dataclass(frozen=True)
class Token:
    value: str
    type: Optional[TokenType] = None

    def __post_init__(self):
        if self.type is not None:
            return

        if not self.value:
            super().__setattr__("type", TokenType.END)
        elif self.value == FIELD_VAL_SEP:
            super().__setattr__("type", TokenType.SEP)
        elif self.value in LOGIC_SET:
            super().__setattr__("type", TokenType.LOGIC)
        elif self.value in "()":
            super().__setattr__("type", TokenType.PARENTHESIS)
        else:
            super().__setattr__("type", TokenType.VALUE)


class Tokenizer:
    def __init__(self, exp: str):
        self.exp = exp

    def _get_next_token(self, start_ind: int) -> tuple[Token, int]:
        while start_ind < len(self.exp) and self.exp[start_ind].isspace():
            start_ind += 1

        if start_ind == len(self.exp):
            return Token("", TokenType.END), start_ind

        if self.exp[start_ind] in f"(){FIELD_VAL_SEP}":
            return Token(self.exp[start_ind]), start_ind + 1

        if self.exp[start_ind] == "\"":
            start_ind += 1
            i = start_ind
            while i < len(self.exp) and (self.exp[i] != "\"" or self.exp[i-1] == "\\"):
                i += 1
            if i == len(self.exp):
                return Token("Error", TokenType.WRONG_VALUE), i
            return Token(self.exp[start_ind:i], TokenType.VALUE), i + 1

        i = start_ind
        while i < len(self.exp):
            if self.exp[i].isspace():
                return Token(self.exp[start_ind:i]), i + 1
            elif self.exp[i] in f"(){FIELD_VAL_SEP}":
                break
            i += 1

        return Token(self.exp[start_ind:i]), i

    def tokenize(self):
        cur_token: Token = Token("", TokenType.START)
        search_index = 0
        res: list[Token] = []
        while cur_token.type != TokenType.END :
            cur_token, search_index = self._get_next_token(search_index)
            res.append(cur_token)
            if cur_token.type == TokenType.WRONG_VALUE:
                raise WrongTokenException("Wrong search query!")
        return res


def get_field_data(field_path: list[str], card: Card) -> Any:
    """field_path: chain of keys"""
    current_entry = card
    for key in field_path:
        current_entry = current_entry.get(key)
        if current_entry is None:
            return None
    return current_entry


@dataclass(frozen=True)
class FieldQuery:
    path: str
    query: str
    field_path: list[str] = field(init=False)

    def __post_init__(self):
        split_path = self.path.split(sep="[")
        FieldQuery.__setattr__(self, "field_path")

    def check_nested_path(self):
        bracket_stack = 0
        for char in self.path:
            if char == "[":
                bracket_stack += 1
            elif char == "]":
                bracket_stack -= 1
                if bracket_stack < 0:
                    raise QuerySyntaxError("Wrong order of brackets in search query!")


@dataclass(frozen=True)
class Method:
    method_name: str
    target: str


# class Parser:
#     def __init__(self, tokens: list[Token]):
#         self._tokens: list[Token] = tokens
#         self._expressions = []
#
#     def token2expression(self):
#         i = 0
#         while i < len(self._tokens):
#             if self._tokens[i].type == TokenType.VALUE:
#                 if self._tokens[i + 1].type == TokenType.SEP and self._tokens[i + 2].type == TokenType.VALUE:
#                     self._expressions.append(FieldQuery(self._tokens[i].value, self._tokens[i + 2].value))
#                 elif
#
#
#
#
# def calculate_field_length(field_token: Token) -> int:
#     if field_token.type != TokenType.VALUE:
#         raise WrongTokenException(f"VALUE token expected. {field_token.type} was given!")
#
#     tags[pos][test]
#     seq = field_token.value.split(sep="[")




# class Parser:
#     methods = {"len": }
#
#
#     def __init__(self, tokens: list[Token]):
#         self.tokens = tokens
#
#     def parse(self):
#         i = 1
#         while i < len(self.tokens):





def main():
    from pprint import pprint

    tokenizer = Tokenizer("word: test and meaning:\"some meaning\" "
                          "or alt_terms:alt and (sentences : \"some sentences\" or tags : some_tags) "
                          "and len(sentences) < 5")
    res = tokenizer.tokenize()

    pprint(res)


if __name__ == "__main__":
    main()
