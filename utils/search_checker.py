import copy
from consts.card_fields import FIELDS
from typing import Optional, Any, Union
from enum import Enum, auto
from dataclasses import dataclass, field
from utils.cards import Card
from typing import Callable, Iterable, ClassVar
from functools import reduce
from utils.storages import FrozenDict


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
LOGIC_MID = frozenset(("and", ))
LOGIC_LOW  = frozenset(("or", ))
LOGIC_PRECEDENCE = (LOGIC_HIGH, LOGIC_MID, LOGIC_LOW)
LOGIC_SET  = reduce(lambda x, y: x | y, LOGIC_PRECEDENCE)


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
    STRING = auto()
    SEP = auto()
    QUERY_STRING = auto()
    LOGIC = auto()
    METHOD_LP = auto()
    METHOD_STRING = auto()
    METHOD_RP = auto()
    LOGIC_LP = auto()
    LOGIC_RP = auto()
    END = auto()

STRING_PLACEHOLDER = "*"
END_PLACEHOLDER = "END"

@dataclass(frozen=True)
class Token:
    logic_deduction: ClassVar[FrozenDict] = FrozenDict({logic_statement: Token_T.LOGIC for logic_statement in LOGIC_SET})
    next_expected: ClassVar[FrozenDict] = FrozenDict(
        {Token_T.START:         {"(": Token_T.LOGIC_LP,
                                 STRING_PLACEHOLDER: Token_T.STRING,
                                 END_PLACEHOLDER: Token_T.END},

         Token_T.STRING:        {FIELD_VAL_SEP: Token_T.SEP,
                                 "(": Token_T.METHOD_LP,
                                 ")": Token_T.LOGIC_RP,
                                 END_PLACEHOLDER: Token_T.END} | logic_deduction.to_dict(),

         Token_T.SEP:           {STRING_PLACEHOLDER: Token_T.QUERY_STRING},

         Token_T.QUERY_STRING:  {")": Token_T.LOGIC_RP,
                                 END_PLACEHOLDER: Token_T.END} | logic_deduction.to_dict(),

         Token_T.LOGIC:         {STRING_PLACEHOLDER: Token_T.STRING,
                                 "(": Token_T.LOGIC_LP},

         Token_T.METHOD_LP:     {STRING_PLACEHOLDER: Token_T.METHOD_STRING},

         Token_T.METHOD_STRING: {")": Token_T.METHOD_RP},

         Token_T.METHOD_RP:     {")": Token_T.LOGIC_RP,
                                 END_PLACEHOLDER: Token_T.END} | logic_deduction.to_dict(),

         Token_T.LOGIC_LP:      {STRING_PLACEHOLDER: Token_T.STRING},

         Token_T.LOGIC_RP:      {END_PLACEHOLDER: Token_T.END,
                                 ")": Token_T.LOGIC_RP} | logic_deduction.to_dict(),

         Token_T.END:           {}
         })
    
    value: str
    prev_token_type: Token_T = field(repr=False)
    type: Token_T = field(init=False)
    
    def __post_init__(self):
        expected_types = Token.next_expected[self.prev_token_type]
        if (deduced_type := expected_types.get(self.value)) is None:
            if (str_type := expected_types.get(STRING_PLACEHOLDER)) is None:
                raise WrongTokenError(f"Unexpected token! {self.value} was given when "
                                      f"[{' '.join(expected_types.keys())}] were expected!")
            super().__setattr__("type", str_type)
            return
        super().__setattr__("type", deduced_type)


class Tokenizer:
    all_token_types = frozenset((t_type for t_type in Token_T))
    
    next_expected = FrozenDict({Token_T.START: all_token_types,
                                Token_T.END: frozenset(),
                                Token_T.SEP: frozenset((Token_T.QUERY_STRING, )),
                                Token_T.QUERY_STRING: frozenset((Token_T.LOGIC, Token_T.LOGIC_RP, Token_T.END)),
                                Token_T.STRING: frozenset((Token_T.METHOD_LP, Token_T.METHOD_RP, Token_T.LOGIC, Token_T.SEP, Token_T.END)),
                                })
    
    def __init__(self, exp: str):
        self.exp = exp

    def _get_next_token(self, start_ind: int, prev_token_type: Token_T) -> tuple[Token, int]:
        while start_ind < len(self.exp) and self.exp[start_ind].isspace():
            start_ind += 1

        if start_ind == len(self.exp):
            return Token(END_PLACEHOLDER, prev_token_type), start_ind

        if self.exp[start_ind] in f"(){FIELD_VAL_SEP}":
            return Token(self.exp[start_ind], prev_token_type), start_ind + 1

        if self.exp[start_ind] == "\"":
            start_ind += 1
            i = start_ind
            while i < len(self.exp) and (self.exp[i] != "\"" or self.exp[i-1] == "\\"):
                i += 1
            if i == len(self.exp):
                raise WrongTokenError("Wrong <\"> usage!")
            return Token(self.exp[start_ind:i], prev_token_type), i + 1

        i = start_ind
        while i < len(self.exp):
            if self.exp[i].isspace():
                return Token(self.exp[start_ind:i], prev_token_type), i + 1
            elif self.exp[i] in f"(){FIELD_VAL_SEP}":
                break
            i += 1

        return Token(self.exp[start_ind:i], prev_token_type), i

    def get_tokens(self):
        search_index = 0
        res: list[Token] = []

        current_token_type = Token_T.START

        parenthesis_counter = 0
        while current_token_type != Token_T.END:
            cur_token, search_index = self._get_next_token(search_index, current_token_type)
            res.append(cur_token)
            if cur_token.value == "(":
                parenthesis_counter += 1
            elif cur_token.value == ")":
                parenthesis_counter -= 1
                if parenthesis_counter < 0:
                    raise QuerySyntaxError("Too many closing parentheses!")
            current_token_type = cur_token.type
        if parenthesis_counter:
            raise QuerySyntaxError("Too many opening parentheses!")
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
                    raise QuerySyntaxError(f"Wrong bracket sequence! Query: {path}")

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
        raise NotImplementedError(f"<compute> method was not implemented for {self.__class__.__name__}!")


@dataclass(frozen=True)
class FieldExpression(Expression):
    card_field_data: _CardFieldData


@dataclass(frozen=True)
class FieldCheck(FieldExpression):
    query: str

    def compute(self, card: Card) -> bool:
        field_data = self.card_field_data.get_field_data(card)
        return self.query in field_data if field_data is not None else False


@dataclass(frozen=True)
class Method(FieldExpression):
    method: Callable[[Any], int]
    
    def compute(self, card: Card) -> int:
        field_data = self.card_field_data.get_field_data(card)
        return self.method(self.card_field_data.get_field_data(card)) if field_data is not None else 0
    

class TokenParser:
    def __init__(self, tokens: list[Token]):
        self._tokens: list[Token] = tokens
        self._expressions: list[Union[Expression, Token]] = []

    def get_field_check(self, index: int) -> tuple[Union[FieldCheck, None], int]:
        """index: STRING token index"""
        if self._tokens[index + 1].type == Token_T.SEP and \
           self._tokens[index + 2].type == Token_T.QUERY_STRING:
            return FieldCheck(_CardFieldData(self._tokens[index].value), self._tokens[index + 2].value), 2
        return None, 0

    def get_method(self, index: int) -> tuple[Union[Method, None], int]:
        """index: STRING token index"""
        if self._tokens[index + 1].type == Token_T.METHOD_LP and \
           self._tokens[index + 2].type == Token_T.METHOD_STRING and \
           self._tokens[index + 3].type == Token_T.METHOD_RP:
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

    def tokens2expressions(self) -> list[Union[Expression, Token]]:
        self._promote_to_expressions()
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

    def construct(self, start: int = 0):
        highest = LOGIC_PRECEDENCE[0]
        current_index = start
        while current_index < len(self._expressions) - 1:
            left_operand = self._expressions[current_index]
            if isinstance(left_operand, Token):
                if (left_operand.type == Token_T.LOGIC_RP or left_operand.type == Token_T.END):
                    break
                elif left_operand.type == Token_T.LOGIC_LP:
                    self._expressions.pop(current_index)
                    self.construct(current_index)

            operator = self._expressions[current_index + 1]
            if operator.type == Token_T.LOGIC_RP or operator.type == Token_T.END:
                break

            right_operand = self._expressions[current_index + 2]
            if isinstance(right_operand, Token) and right_operand.type == Token_T.LOGIC_LP:
                self._expressions.pop(current_index + 2)
                self.construct(current_index + 2)

            if operator.value in highest:
                left_operand = self._expressions.pop(current_index)
                self._expressions.pop(current_index)
                right_operand = self._expressions.pop(current_index)
                self._expressions.insert(current_index, EvalNode(left=left_operand, right=right_operand,
                                                                 operator=operator.value))
            else:
                current_index += 2

        done_once = False
        for cur_logic_precedence in LOGIC_PRECEDENCE[1:]:
            current_index = start
            while current_index < len(self._expressions) - 1:

                operator = self._expressions[current_index + 1]
                assert isinstance(operator, Token)

                if operator.type == Token_T.LOGIC_RP or operator.type == Token_T.END:
                    break

                if operator.value in cur_logic_precedence:
                    left_operand = self._expressions.pop(current_index)
                    self._expressions.pop(current_index)
                    right_operand = self._expressions.pop(current_index)
                    self._expressions.insert(current_index, EvalNode(left=left_operand, right=right_operand,
                                                                     operator=operator.value))
                else:
                    current_index += 2
            else:
                continue
            done_once = True

        if done_once:
            self._expressions.pop(current_index + 1)

    def get_master_node(self):
        if len(self._expressions) != 1:
            raise ParsingException("Error creating syntax tree! ")
        return self._expressions[0]


def parse_language(expression: str) -> EvalNode:
    _tokenizer = Tokenizer(expression)
    tokens = _tokenizer.get_tokens()
    _token_parser = TokenParser(tokens=tokens)
    expressions = _token_parser.tokens2expressions()
    _logic_tree = LogicTree(expressions)
    _logic_tree.construct()
    return _logic_tree.get_master_node()


def main():
    from pprint import pprint

    queries = ("word: test and meaning:\"some meaning\" "
                          "or alt_terms:alt and (sentences : \"some sentences\" or tags : some_tags and (tags[pos] : noun)) "
                          "and (len(sentences) < 5)",
                "\"test tag\": \"test value\" and len(user_tags[image_links]) == 5",
               "len(\"meaning [  test  ][tag]\") == 2 or len(meaning[test][tag]) != 2")


    for query in queries:
        root = parse_language(query)

    query = "word: test and pos: verb and len(Sen_Ex)"
    syntax_tree = parse_language(query)
    print(syntax_tree)

    test_card = {
        "word": "test",
        "meaning": "to do something in order to discover if something is safe, works correctly, etc., or if something is present",
        "Sen_Ex": [
            "The manufacturers are currently testing the new engine.",
            "They tested her blood for signs of the infection."
        ],
        "level": [
            "B2"
        ],
        "pos": "verb",
        "audio_link": "https://dictionary.cambridge.org//media/english/us_pron/t/tes/test_/test.mp3"
    }
    result = syntax_tree.compute(card=test_card)
    print(result)


if __name__ == "__main__":
    main()
