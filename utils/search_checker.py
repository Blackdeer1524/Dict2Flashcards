import copy

from consts.card_fields import FIELDS
from typing import Optional, Any, Union
from enum import Enum, auto
from dataclasses import dataclass, field
from utils.cards import Card
from typing import Callable, Iterable


class ParsingException(Exception):
    pass


class LogicOperatorError(ParsingException):
    pass


class WrongMethodError(ParsingException):
    pass
    

class WrongTokenError(ParsingException):
    pass


class QuerySyntaxError(ParsingException):
    pass


LOGIC_HIGH = frozenset(("<", "<=", ">", ">=", "==", "!="))
LOGIC_MID = frozenset(("and", "not"))
LOGIC_LOW  = frozenset(("or"))
LOGIC_SET  = LOGIC_HIGH | LOGIC_LOW


def logic_factory(operator: str) -> Union[Callable[[bool], bool],
                                          Callable[[bool, bool], bool]]:
    if operator == "and":
        return lambda x, y: x and y
    elif operator == "or":
        return lambda x, y: x or y
    elif operator == "not":
        return lambda x: not x
    elif operator == "<":
        return lambda x, y: x < y
    elif operator == "<=":
        return lambda x, y: x <= y
    elif operator == ">":
        return lambda x, y: x > y
    elif operator == ">=":
        return lambda x, y: x >= y
    elif operator == "==":
        return lambda x, y: x == y
    elif operator == "!=":
        return lambda x, y: x != y
    raise LogicOperatorError(f"Unknown operator: {operator}")
    

def method_factory(method_name: str) -> Callable[[Iterable], int]:
    if method_name == "len":
        return lambda x: len(x)
    raise WrongMethodError(f"Unknown method name: {method_name}")
    

FIELD_VAL_SEP = ":"
FIELD_NAMES_SET = frozenset(FIELDS)


class Token_T(Enum):
    START = auto()
    END = auto()
    SEP = auto()
    LOGIC = auto()
    LP = auto()
    RP = auto()
    STRING = auto()
    WRONG_VALUE = auto()


@dataclass(frozen=True)
class Token:
    value: str
    type: Optional[Token_T] = None

    def __post_init__(self):
        if self.type is not None:
            return

        if not self.value:
            super().__setattr__("type", Token_T.END)
        elif self.value == FIELD_VAL_SEP:
            super().__setattr__("type", Token_T.SEP)
        elif self.value == "(":
            super().__setattr__("type", Token_T.LP)
        elif self.value == ")":
            super().__setattr__("type", Token_T.RP)
        elif self.value in LOGIC_SET:
            super().__setattr__("type", Token_T.LOGIC)
        else:
            super().__setattr__("type", Token_T.STRING)


class Tokenizer:
    def __init__(self, exp: str):
        self.exp = exp

    def _get_next_token(self, start_ind: int) -> tuple[Token, int]:
        while start_ind < len(self.exp) and self.exp[start_ind].isspace():
            start_ind += 1

        if start_ind == len(self.exp):
            return Token("", Token_T.END), start_ind

        if self.exp[start_ind] in f"(){FIELD_VAL_SEP}":
            return Token(self.exp[start_ind]), start_ind + 1


        if self.exp[start_ind] == "\"":
            start_ind += 1
            i = start_ind
            while i < len(self.exp) and (self.exp[i] != "\"" or self.exp[i-1] == "\\"):
                i += 1
            if i == len(self.exp):
                return Token("Error", Token_T.WRONG_VALUE), i
            return Token(self.exp[start_ind:i], Token_T.STRING), i + 1

        i = start_ind
        while i < len(self.exp):
            if self.exp[i].isspace():
                return Token(self.exp[start_ind:i]), i + 1
            elif self.exp[i] in f"(){FIELD_VAL_SEP}":
                break
            i += 1

        return Token(self.exp[start_ind:i]), i

    def get_tokens(self):
        cur_token: Token = Token("", Token_T.START)
        search_index = 0
        res: list[Token] = []
        while cur_token.type != Token_T.END :
            cur_token, search_index = self._get_next_token(search_index)
            res.append(cur_token)
            if cur_token.type == Token_T.WRONG_VALUE:
                raise WrongTokenError("Wrong search query!")
        return res


@dataclass(frozen=True, init=False)
class _CardFieldData:
    query_chain: list[str] = field(init=False, repr=True)
    
    def __init__(self, path: str):
        self._check_nested_path(path)
        chain = []

        start = current_index = 0
        while current_index < len(path) and path[current_index] != "[":
            current_index += 1
        last_closed_bracket = current_index

        while current_index < len(path):
            if path[current_index] == "[":
                chain.append(path[start:last_closed_bracket])
                start = current_index + 1
            elif path[current_index] == "]":
                last_closed_bracket = current_index
            current_index += 1

        if start != current_index:
            chain.append(path[start:last_closed_bracket])

        super().__setattr__("query_chain", chain)
    
    @staticmethod
    def _check_nested_path(path) -> None:
        bracket_stack = 0
        last_closing_bracket = -1
        for i in range(len(path)):
            char = path[i]
            if char == "[":
                bracket_stack += 1
            elif char == "]":
                last_closing_bracket = i
                bracket_stack -= 1
                if bracket_stack < 0:
                    raise QuerySyntaxError(f"Wrong order of brackets in search query! Query: {path}")

        if last_closing_bracket > 0:
            for i in range(last_closing_bracket + 1, len(path)):
                if not path[i].isspace():
                    raise QuerySyntaxError(f"Wrong bracket sequence! Query: {path}")
    
    def get_field_data(self, card: Card) -> Any:
        """query_chain: chain of keys"""
        current_entry = card
        for key in self.query_chain:
            current_entry = current_entry.get(key)
            if current_entry is None:
                return None
        return current_entry


@dataclass(frozen=True)
class Expression:
    def compute(self, card: Card):
        raise NotImplementedError(f"compute method was not implemented for {self.__class__.__name__}!")


@dataclass(frozen=True)
class FieldExpression(Expression):
    card_field_data: _CardFieldData


@dataclass(frozen=True)
class FieldCheck(FieldExpression):
    query: str

    def compute(self, card: Card) -> bool:
        return self.query in self.card_field_data.get_field_data(card)


@dataclass(frozen=True)
class Method(FieldExpression):
    method: Callable[[Any], int]
    
    def compute(self, card: Card) -> int:
        return self.method(self.card_field_data.get_field_data(card))
    

class TokenParses:
    def __init__(self, tokens: list[Token]):
        self._tokens: list[Token] = tokens
        self._expressions: list[Union[Expression, Token]] = []

    def get_field_check(self, index: int) -> tuple[Union[FieldCheck, None], int]:
        """index: Value token index"""
        if self._tokens[index + 1].type == Token_T.SEP and \
           self._tokens[index + 2].type == Token_T.STRING:
            return FieldCheck(_CardFieldData(self._tokens[index].value), self._tokens[index + 2].value), 2
        return None, 0

    def get_method(self, index: int) -> tuple[Union[Method, None], int]:
        """index: Value token index"""
        if self._tokens[index + 1].type == Token_T.LP and \
           self._tokens[index + 2].type == Token_T.STRING and \
           self._tokens[index + 3].type == Token_T.RP:
            return Method(_CardFieldData(self._tokens[index + 2].value), method_factory(self._tokens[index].value)), 3
        return None, 0

    def _promote_to_expressions(self):
        i = 0
        while i < len(self._tokens):
            if self._tokens[i].type == Token_T.STRING:

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

    def _check_grammar(self):
        if len(self._expressions) == 1:
            return

        parenthesis_stack = 0
        for i in range(len(self._expressions) - 1):
            current = self._expressions[i]
            right = self._expressions[i + 1]

            if isinstance(current, Expression) and \
                not ((isinstance(right, Token) and
                      (right.type == Token_T.LP or
                       right.type == Token_T.RP or
                       right.type == Token_T.LOGIC or
                       right.type == Token_T.END))):
                raise QuerySyntaxError("Stranded EXPRESSION")
            elif isinstance(current, Token):
                if current.type == Token_T.LOGIC and not (isinstance(right, Expression) or
                                                            isinstance(right, Token) and
                                                            (right.type == Token_T.LP or
                                                             right.type == Token_T.RP or
                                                             right.type == Token_T.STRING)):
                    raise QuerySyntaxError("Wrong logic operator usage!")
                elif current.type == Token_T.STRING and (not current.value.isdecimal() or not
                (isinstance(right, Token) and (right.type == Token_T.LOGIC or right.type == Token_T.END))):
                    raise QuerySyntaxError("Stranded STRING token!")
                elif current.type == Token_T.SEP:
                    raise QuerySyntaxError("Stranded SEP token!")
                elif current.type == Token_T.LP:
                    parenthesis_stack += 1
                elif current.type == Token_T.RP:
                    parenthesis_stack -= 1
                    if parenthesis_stack < 0:
                        raise QuerySyntaxError("Too many closing parentheses!")
        if parenthesis_stack:
            raise QuerySyntaxError("Too many opening parentheses!")

    def tokens2expressions(self) -> list[Union[Expression, Token]]:
        self._promote_to_expressions()
        self._check_grammar()
        return self._expressions


@dataclass(frozen=True)
class EvalNode:
    operator: str
    left: Optional[Union[Expression, Token]] = None
    right: Optional[Union[Expression, Token]] = None
    operation: Union[Callable[[Any],       bool],
                     Callable[[Any, Any], bool]] = field(init=False, repr=False)

    def __post_init__(self):
        if isinstance(self.left, Token) and isinstance(self.right, Token):
            raise QuerySyntaxError("Two STRING's in one node!")
        super().__setattr__("operation", logic_factory(self.operator))

    def compute(self, card: Card) -> bool:
        if self.left is not None and self.right is not None:
            if isinstance(self.left, Token):
                return self.operation(float(self.left.value), self.right.compute(card))
            elif isinstance(self.right, Token):
                return self.operation(self.left.compute(card), float(self.right.value))
            return self.operation(self.left.compute(card), self.right.compute(card))
        elif self.left is not None:
            return self.operation(self.left.compute(card))
        raise LogicOperatorError("Empty node!")


class LogicTree:
    def __init__(self, expressions):
        self._expressions = copy.deepcopy(expressions)

    def construct(self, start: int = 0) -> EvalNode:
        current_index = start
        while current_index < len(self._expressions) - 1:
            left_operand = self._expressions[current_index]
            if isinstance(left_operand, Token):
                if (left_operand.type == Token_T.RP or left_operand.type == Token_T.END):
                    break
                elif left_operand.type == Token_T.LP:
                    self._expressions.pop(current_index)
                    self.construct(current_index)

            operator = self._expressions[current_index + 1]
            assert isinstance(operator, Token)
            if operator.type == Token_T.RP or operator.type == Token_T.END:
                break

            right_operand = self._expressions[current_index + 2]
            if isinstance(right_operand, Token) and right_operand.type == Token_T.LP:
                self._expressions.pop(current_index + 2)
                self.construct(current_index + 2)

            if operator.value in LOGIC_HIGH:
                left_operand = self._expressions.pop(current_index)
                self._expressions.pop(current_index)
                right_operand = self._expressions.pop(current_index)
                self._expressions.insert(current_index, EvalNode(left=left_operand, right=right_operand,
                                                                 operator=operator.value))
            else:
                current_index += 2

        current_index = start
        while current_index < len(self._expressions) - 1:
            left_operand = self._expressions[current_index]

            operator = self._expressions.pop(current_index + 1)
            assert isinstance(operator, Token)
            if operator.type == Token_T.RP or operator.type == Token_T.END:
                break

            self._expressions.pop(current_index)
            right_operand = self._expressions.pop(current_index)
            self._expressions.insert(current_index, EvalNode(left=left_operand, right=right_operand,
                                                             operator=operator.value))

        return self._expressions[start]



def main():
    from pprint import pprint

    tokenizer = Tokenizer("word: test and meaning:\"some meaning\" "
                          "or alt_terms:alt and (sentences : \"some sentences\" or tags : some_tags) "
                          "and len(sentences) < 5")
    tokens = tokenizer.get_tokens()

    parser = TokenParses(tokens=tokens)
    expressions = parser.tokens2expressions()
    tree = LogicTree(expressions)
    master_node = tree.construct()
    pprint()


if __name__ == "__main__":
    main()
