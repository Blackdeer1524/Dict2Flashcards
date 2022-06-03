from consts.card_fields import FIELDS
from typing import Optional, Any, Union
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


class Expression:
    pass


@dataclass(frozen=True)
class Token(Expression):
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


def get_field_data(query_chain: list[str], card: Card) -> Any:
    """query_chain: chain of keys"""
    current_entry = card
    for key in query_chain:
        current_entry = current_entry.get(key)
        if current_entry is None:
            return None
    return current_entry


@dataclass(frozen=True)
class _Field:
    path: str = field(repr=False)
    query_chain: list[str] = field(init=False, repr=True)

    def __post_init__(self):
        self._check_nested_path()
        split_path = []

        start = current_index = 0

        while current_index < len(self.path) and self.path[current_index] != "[":
            current_index += 1
        last_closed_bracket = current_index

        while current_index < len(self.path):
            if self.path[current_index] == "[":
                split_path.append(self.path[start:last_closed_bracket])
                start = current_index + 1
            elif self.path[current_index] == "]":
                last_closed_bracket = current_index
            current_index += 1
        
        if start != current_index:
            split_path.append(self.path[start:last_closed_bracket])
            
        super().__setattr__("query_chain", split_path)

    def _check_nested_path(self) -> None:
        bracket_stack = 0
        last_closing_bracket = -1
        for i in range(len(self.path)):
            char = self.path[i]
            if char == "[":
                bracket_stack += 1
            elif char == "]":
                last_closing_bracket = i
                bracket_stack -= 1
                if bracket_stack < 0:
                    raise QuerySyntaxError("Wrong order of brackets in search query!")

        if last_closing_bracket > 0:
            for i in range(last_closing_bracket + 1, len(self.path)):
                if not self.path[i].isspace():
                    raise QuerySyntaxError("Wrong bracket sequence")


@dataclass(frozen=True)
class FieldCheck(Expression):
    field: _Field
    query: str


@dataclass(frozen=True)
class Method(Expression):
    method_name: str
    target: str


class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens: list[Token] = tokens
        self._expressions: list[Expression] = []

    def get_field_check(self, index: int) -> tuple[Union[FieldCheck, None], int]:
        """index: Value token index"""
        if self._tokens[index + 1].type == TokenType.SEP and \
           self._tokens[index + 2].type == TokenType.VALUE:
            return FieldCheck(_Field(self._tokens[index].value), self._tokens[index + 2].value), 2
        return None, 0

    def get_method(self, index: int) -> tuple[Union[Method, None], int]:
        """index: Value token index"""
        if self._tokens[index + 1].type == TokenType.PARENTHESIS and \
           self._tokens[index + 2].type == TokenType.VALUE and \
           self._tokens[index + 3].type == TokenType.PARENTHESIS:
            return Method(self._tokens[index].value, self._tokens[index + 2].value), 3
        return None, 0

    def token2expression(self):
        i = 0
        while i < len(self._tokens):
            if self._tokens[i].type == TokenType.VALUE:
                res, offset = self.get_field_check(i)
                if res is None:
                    res, offset = self.get_method(i)
                if res is None:
                    self._expressions.append(self._tokens[i])
                else:
                    self._expressions.append(res)
                i += offset
            else:
                self._expressions.append(self._tokens[i])

            i += 1

    def get_expressions(self):
        return self._expressions


# def calculate_field_length(field_token: Token) -> int:
#     if field_token.type != TokenType.VALUE:
#         raise WrongTokenException(f"VALUE token expected. {field_token.type} was given!")
#
#     tags[pos][test]
#     seq = field_token.value.split(sep="[")


def main():
    from pprint import pprint

    tokenizer = Tokenizer("word: test and meaning:\"some meaning\" "
                          "or alt_terms:alt and (sentences : \"some sentences\" or tags : some_tags) "
                          "and len(sentences) < 5")
    tokens = tokenizer.tokenize()

    parser = Parser(tokens=tokens)
    parser.token2expression()
    pprint(parser.get_expressions())


if __name__ == "__main__":
    main()
