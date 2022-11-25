"""
Unary operators:
* logic operators:
    not

Binary operators:
* logic operators
    and, or
* arithmetics operators:
    <, <=, >, >=, ==, !=

Keywords:
    in
        Checks whether <thing> is in <field>[<subfield_1>][...][<subfield_n>]
        Example:
            {
                "field": [val_1, .., val_n]}
            }

        thing in field
        Returns True if thing is in [val_1, .., val_n]


Special queries & commands
    $ANY
        Gets result from the whole hierarchy level
        Example:
            {
                "pos": {
                    "noun": {
                        "data": value_1
                    },
                    "verb" : {
                        "data": value_2
                    }
                }
            }
        $ANY will return ["noun", "verb"]
        pos[$ANY][data] will return [value_1, value_2]
        $ANY[$ANY][data] will also will return [value_1, value_2]

    $SELF
        Gets current hierarchy level keys
        Example:
            {
                "field_1": 1,
                "field_2": 2,
            }
        $SELF will return ["field_1", "field_2"]

    d_$
        Will convert string expression to a digit.
        By default, every key inside query strings
        (for example, in field[subfield] the keys are field and subfield)
        are treated as strings. If you have an integer/float key or an array
        with specific index, then you would need to use this prefix

        Example:
            {
                "array_field": [1, 2, 3],
                "int_field": {
                    1: [4, 5, 6]
                }
            }

        array_field[d_$1] will return 2
        int_field[d_$1] will return [4, 5, 6]

    f_$
        Will convert a numeric expression to a field
        By default, every stranded decimal-like strings
        are treated as decimals. So if your scheme contains decimal as a
        key you would need this prefix

        Example:
            {
                1: [1, 2, 3],
                2: {
                    "data": [4, 5, 6]
                }
            }

        f_$d_$1 will return [1, 2, 3]
        You would need to also use d_$ prefix, because as 1 would be converted to
        a <field> type, it would also be treated as a string
        Note:
            to get [4, 5, 6] from this scheme you would only need d_$ prefix:
            d_$2[data]

Methods:
    len
        Measures length of iterable object
        Example:
            {
                "field": [1, 2, 3]
            }
        len(field) will return 3
        Example:
            {
                "field": {
                    "subfield_1": {
                        "data": [1, 2, 3]
                    },
                    "subfield_2": {
                        "data": [4, 5]
                    }
                }
            }
        len(field[$ANY][data]) = len([[1, 2, 3], [4, 5]]) = 2

    split
        Splits given string or list of strings
        Example:
            {
                "field": "text with spaces",
                "list_field": ["text with spaces 1", "text with spaces 2"]
            }
        split(field) = ["text", "with", "spaces"]
        split(list_field) = [["text", "with", "spaces", "1"],
                             ["text", "with", "spaces", "2"]]

    any
        Returns True if one of items is True
        Example:
            {
                "field": {
                    "subfield_1": {
                        "data": 1
                    },
                    "subfield_2": {
                        "data": 2
                    }
                }
            }
       any(field[$ANY][data] > 1) will return True

    all
        Returns True if all items are True
        Example:
            {
                "field": {
                    "subfield_1": {
                        "data": 1
                    },
                    "subfield_2": {
                        "data": 2
                    }
                }
            }
        all($ANY[$ANY][data] > 0) will return True
        all($ANY[$ANY][data] > 1) will return False

    lower
        Makes all strings lowercase
        Example:
            {
                "field_1": ["ABC", "abc", "AbC"],
                "field_2": "ABC"
            }
        lower(field_1) will return ["abc", "abc", "abc"]
        lower(field_2) will return "abc"

    upper
        Makes all strings uppercase
        Example:
            {
                "field_1": ["ABC", "abc", "AbC"],
                "field_2": "abc"
            }
        upper(field_1) will return ["ABC", "ABC", "ABC", ""]
        upper(field_2) will return "ABC"

    reduce
        Flattens one layer of nested list result:
        Example:
            {
                "field_1": ["a", "b", "c"],
                "field_2": ["d", "e", "f"]
            }
        $ANY will return [["a", "b", "c"], ["d", "e", "f"]]
        reduce($ANY) will return ["a", "b", "c", "d", "e", "f"]
        Note:
            {
                "field_1": [["a"], ["b"], ["c"]],
                "field_2": [[["d"], ["e"], ["f"]]]
            }
        $ANY will return [[["a"], ["b"], ["c"]], [[["d"], ["e"], ["f"]]]]
        reduce($ANY) will return [["a"], ["b"], ["c"], [["d"], ["e"], ["f"]]]

    Note:
        You can also combine methods:
        Example:
            {
                "field_1": ["ABC", "abc", "AbC"],
                "field_2": ["Def", "dEF", "def"]
            }
        lower(reduce($ANY)) will return ["abc", "abc", "abc", "def", "def", "def"]

Evaluation precedence:
1) expressions in parentheses
2) keywords, methods
3) unary operators
4) binary operators
"""


import copy
import itertools
import re
import sys
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import partial
from functools import reduce
from typing import Callable, Sized, ClassVar
from typing import Iterable, Iterator, Generator
from typing import Optional, Any
from typing import Type

from app_utils.query_language.exceptions import *
from app_utils.storages import FrozenDict
from consts import CardFields


class Computable(ABC):
    value: str

    @abstractmethod
    def compute(self, mapping: Mapping):
        pass


KEYWORDS = frozenset(("in", ))
UNARY_LOGIC = frozenset(("not", ))
BIN_LOGIC_HIGH = frozenset(("<", "<=", ">", ">=", "==", "!="))
BIN_LOGIC_MID = frozenset(("and", ))
BIN_LOGIC_LOW = frozenset(("or", ))
BIN_LOGIC_PRECEDENCE = (BIN_LOGIC_HIGH, BIN_LOGIC_MID, BIN_LOGIC_LOW)
BIN_LOGIC_SET = reduce(lambda x, y: x | y, BIN_LOGIC_PRECEDENCE)

T_unary_op =  Callable[[Iterable[Computable] | Computable, 
                        Mapping], Iterator[bool] | bool]
T_binary_op = Callable[[Iterable[Computable] | Computable,
                        Iterable[Computable] | Computable,
                        Mapping], Iterator[bool] | bool]
LIST_LIKE_TYPES = (list, tuple, Generator, itertools.chain)

def logic_factory(operator: str) -> T_unary_op | T_binary_op:
    def operator_not(x: Iterable[Computable] | Computable,
                      mapping: Mapping):
        x_computed = x.compute(mapping)
        if isinstance(x_computed, LIST_LIKE_TYPES):
            return (not item for item in x)
        return not x_computed

    def operator_and(x: Iterable[Computable] | Computable,
                     y: Iterable[Computable] | Computable,
                     mapping: Mapping):
        x_computed = x.compute(mapping)
        y_computed = y.compute(mapping)

        if isinstance(x_computed, LIST_LIKE_TYPES):
            if isinstance(y_computed, LIST_LIKE_TYPES):
                return (item_x and item_y for item_x in x_computed for item_y in y_computed)
            if not y_computed:
                return (False for _ in x_computed)
            return (item_x for item_x in x_computed)

        if isinstance(y_computed, LIST_LIKE_TYPES):
            if not x_computed:
                return (False for _ in y_computed)
            return (item_y for item_y in y_computed)

        if not x_computed:
            return False
        return y_computed

    def operator_or(x: Iterable[Computable] | Computable,
                    y: Iterable[Computable] | Computable,
                    mapping: Mapping):
        x_computed = x.compute(mapping)
        y_computed = y.compute(mapping)

        if isinstance(x_computed, LIST_LIKE_TYPES):
            if isinstance(y_computed, LIST_LIKE_TYPES):
                return (item_x or item_y for item_x in x_computed for item_y in y_computed)
            if y_computed:
                return (True for _ in x_computed)
            return (item_x for item_x in x_computed)

        if isinstance(y_computed, LIST_LIKE_TYPES):
            if x_computed:
                return (True for _ in y_computed)
            return (item_y for item_y in y_computed)

        if x_computed:
            return True

        return y_computed


    def bin_op_template(x: Iterable[Computable] | Computable,
                        y: Iterable[Computable] | Computable,
                        mapping: Mapping,
                        _op: Callable[[Any, Any], bool]):
        x_computed = x.compute(mapping)
        y_computed = y.compute(mapping)

        if isinstance(x_computed, LIST_LIKE_TYPES):
            if isinstance(y_computed, LIST_LIKE_TYPES):
                return (_op(item_x, item_y) for item_x in x_computed for item_y in y_computed)
            return (_op(item_x, y_computed) for item_x in x_computed)

        if isinstance(y_computed, LIST_LIKE_TYPES):
            return (_op(x_computed, item_y) for item_y in y_computed)

        return _op(x_computed, y_computed)

    if operator == "not":
        return operator_not
    elif operator == "and":
        return operator_and
    elif operator == "or":
        return operator_or
    elif operator == "<":
        return partial(bin_op_template, _op=lambda x, y: x < y)  # type: ignore
    elif operator == "<=":
        return partial(bin_op_template, _op=lambda x, y: x <= y) # type: ignore
    elif operator == ">":
        return partial(bin_op_template, _op=lambda x, y: x > y)  # type: ignore
    elif operator == ">=":
        return partial(bin_op_template, _op=lambda x, y: x >= y)  # type: ignore
    elif operator == "==":
        return partial(bin_op_template, _op=lambda x, y: x == y)  # type: ignore
    elif operator == "!=":
        return partial(bin_op_template, _op=lambda x, y: x != y)  # type: ignore
    raise LogicOperatorError(f"Unknown operator: {operator}")
    

def method_factory(method_name: str):
    if method_name == "len":
        def field_length(x):
            if isinstance(x, Sized):
                return len(x)
            elif isinstance(x, Iterable):
                n = 0
                for n, _ in enumerate(x, 1):
                    pass
                return n
            return 0
        return field_length
    elif method_name == "print":
        def print_results(x):
            if isinstance(x, (Generator, itertools.chain)):
                raise ResultPrint(f"{[i for i in x]}")
            raise ResultPrint(x)
        return print_results
    elif method_name == "split":
        def string_split(x):
            if not isinstance(x, Iterable):
                raise ArgumentTypeError(f"{type(x)} type was given. Iterable[String] or String types ware expected")

            if isinstance(x, str):
                return x.split(sep=" ")
            
            def raise_if_not_str(item):
                raise ArgumentTypeError(f"Wrong collection item type. Got {type(item)}. String type was expected")

            return (i.split(sep=" ") if isinstance(i, str) else raise_if_not_str(i) for i in x)
        return string_split
    elif method_name == "any":
        def any_aggregation_method(x):
            if not isinstance(x, Iterable):
                raise ArgumentTypeError(f"{type(x)} type was given. Iterable type was expected")
            return any(x)
        return any_aggregation_method
    elif method_name == "all":
        def all_aggregation_method(x):
            if not isinstance(x, Iterable):
                raise ArgumentTypeError(f"{type(x)} type was given. Iterable type was expected")
            return all(x)
        return all_aggregation_method
    elif method_name == "lower":
        def lower(x):
            def raise_if_not_str(item):
                raise ArgumentTypeError(f"Wrong collection item type. Got {type(item)}. String type was expected")
            if isinstance(x, str):
                return x.lower()
            elif isinstance(x, Iterable):
                return (item_x.lower() if isinstance(item_x, str) else raise_if_not_str(item_x) for item_x in x)
            raise ArgumentTypeError(f"{type(x)} type was given. Iterable[String] or String types were expected")
        return lower
    elif method_name == "upper":
        def upper(x):
            def raise_if_not_str(item):
                raise ArgumentTypeError(f"Wrong collection item type. Got {type(item)}. String type was expected")
            if isinstance(x, str):
                return x.upper()
            elif isinstance(x, Iterable):
                return (item_x.upper() if isinstance(item_x, str) else raise_if_not_str(item_x) for item_x in x)
            raise ArgumentTypeError(f"{type(x)} type was given. Iterable or String types were expected")
        return upper
    elif method_name == "reduce":
        def reduce(x):
            computed_x = []
            for i in x:
                if not isinstance(i, LIST_LIKE_TYPES):
                    raise ArgumentTypeError(f"Can concatenate only Iterable (not String) objects. Got {type(i)}")
                computed_x.append(i)
            return itertools.chain(*computed_x)
        return reduce
    raise WrongMethodError(f"Unknown method name: {method_name}")


def keyword_factory(keyword_name: str) -> Callable[[Any], int]:
    if keyword_name == "in":
        def field_contains(collection: Iterable, search_pattern: re.Pattern):
            if not isinstance(collection, Iterable):
                raise ArgumentTypeError(f"{type(collection)} type was given. Iterable[String] or String types were expected")

            if isinstance(collection, str):
                return re.search(search_pattern, collection) is not None

            for i in collection:
                if not isinstance(i, str):
                    raise ArgumentTypeError(f"Wrong collection item type: {type(i)}. String type wes expected")

            return any((re.search(search_pattern, str(item)) is not None for item in collection))
        return field_contains
    raise WrongKeywordError(f"Unknown keyword: {keyword_name}")


FIELD_NAMES_SET = frozenset(CardFields)
DIGIT_FORCE_PREFIX = "d_$"
FIELD_FORCE_PREFIX = "f_$"


class Token_T(Enum):
    START = auto()  # type: ignore
    KEYWORD = auto()  # type: ignore
    STRING = auto()  # type: ignore
    UN_LOGIC_OP = auto()  # type: ignore
    BIN_LOGIC_OP = auto()  # type: ignore
    L_PARENTHESIS = auto()  # type: ignore
    R_PARENTHESIS = auto()  # type: ignore
    COMMA = auto()  # type: ignore
    END = auto()  # type: ignore

STRING_PLACEHOLDER = "*"
END_PLACEHOLDER = "END"


@dataclass(slots=True, frozen=True, init=False)
class FieldDataGetter(Computable):
    value: str
    ANY_FIELD: ClassVar[str] = "$ANY"
    SELF_FIELD: ClassVar[str] = "$SELF"

    query_chain: list[str] = field(init=False, repr=True)

    def __init__(self, path: str):
        object.__setattr__(self, "value", path)
        self._check_nested_path(path)
        path_chain = []

        start = current_index = 0
        while current_index < len(path) and path[current_index] != "[":
            current_index += 1
        last_closed_bracket = current_index

        while current_index < len(path):
            if path[current_index] == "[":
                path_chain.append(path[start:last_closed_bracket])
                start = current_index + 1
            elif path[current_index] == "]":
                last_closed_bracket = current_index
            current_index += 1

        if start != current_index:
            path_chain.append(path[start:last_closed_bracket])

        object.__setattr__(self, "query_chain", path_chain)

    def _check_nested_path(self, path) -> None:
        bracket_stack = 0
        brace_sequence_start = 0
        brace_sequence_end = 0
        for i in range(len(path)):
            char = path[i]
            if char == "[":
                if bracket_stack == 0:
                    brace_sequence_start = i
                bracket_stack += 1
            elif char == "]":
                brace_sequence_end = i
                bracket_stack -= 1
                if bracket_stack < 0:
                    format_exception(
                        exc=QuerySyntaxError,
                        exception_message="Too much closing braces!",
                        token_string=self.value[brace_sequence_start:max(brace_sequence_start, brace_sequence_end) + 1])

        if bracket_stack > 0:
            raise QuerySyntaxError("Too much opening braces!")

        if brace_sequence_end > 0:
            for i in range(brace_sequence_end + 1, len(path)):
                if not path[i].isspace():
                    raise QuerySyntaxError("Wrong bracket sequence in field query!")

    def compute(self, mapping: Mapping) -> list[Any]:
        """query_chain: chain of keys"""
        result = None
        seen = False

        def traverse_recursively(entry: Mapping | Any, chain_index: int = 0) -> None:
            nonlocal result, seen
            if chain_index == len(self.query_chain):
                end = list(entry.keys()) if isinstance(entry, Mapping) else entry
                if result is None:
                    result = end
                else:
                    if not seen:
                        result = [result]
                        seen = True
                    result.append(end)
                return

            current_key = self.query_chain[chain_index]
            if current_key.startswith(DIGIT_FORCE_PREFIX):
                current_key = current_key[len(DIGIT_FORCE_PREFIX):]
                if current_key.lstrip("-").isdigit() and isinstance(entry, (list, tuple)):
                    current_key = int(current_key)
                    if len(entry) > current_key:
                        traverse_recursively(entry[current_key], chain_index + 1)
                    return
                elif current_key.lstrip("-").isdecimal():
                    current_key = float(current_key)

            if not isinstance(entry, Mapping):
                return None

            if current_key == FieldDataGetter.ANY_FIELD:
                for key in entry:
                    if (val := entry.get(key)) is not None:
                        traverse_recursively(val, chain_index + 1)
                return

            elif current_key == FieldDataGetter.SELF_FIELD:
                return traverse_recursively(entry, chain_index + 1)

            if (val := entry.get(current_key)) is not None:
                traverse_recursively(val, chain_index + 1)

        traverse_recursively(mapping)
        return result


def format_exception(exc: Type[QueryLangException],exception_message: str,token_string: str):
    raise exc(message=f"\n{token_string}\n" +
                      "~" * max(1, len(token_string)) + "\n" +
                      str(exception_message),
              caught=True)


@dataclass(slots=True, frozen=True)
class Token(Computable):
    un_logic_deduction: ClassVar[FrozenDict] =  FrozenDict({logic_operator: Token_T.UN_LOGIC_OP for 
                                                            logic_operator in UNARY_LOGIC})
    bin_logic_deduction: ClassVar[FrozenDict] = FrozenDict({logic_operator: Token_T.BIN_LOGIC_OP for 
                                                            logic_operator in BIN_LOGIC_SET})
    keyword_deduction: ClassVar[FrozenDict] =   FrozenDict({keyword_name: Token_T.KEYWORD for 
                                                            keyword_name in KEYWORDS})
    
    next_expected: ClassVar[FrozenDict] = FrozenDict(
        {Token_T.START:         {"(": Token_T.L_PARENTHESIS,
                                 STRING_PLACEHOLDER: Token_T.STRING,
                                 END_PLACEHOLDER: Token_T.END} 
                                | un_logic_deduction.to_dict(),

         Token_T.STRING:        {"(": Token_T.L_PARENTHESIS,
                                 ")": Token_T.R_PARENTHESIS,
                                 END_PLACEHOLDER: Token_T.END} 
                                | bin_logic_deduction.to_dict() 
                                | keyword_deduction.to_dict(),
         
         Token_T.KEYWORD:       {STRING_PLACEHOLDER: Token_T.STRING,
                                 "(": Token_T.L_PARENTHESIS},

         Token_T.UN_LOGIC_OP:   {STRING_PLACEHOLDER: Token_T.STRING,
                                 "(": Token_T.L_PARENTHESIS},

         Token_T.BIN_LOGIC_OP:  {STRING_PLACEHOLDER: Token_T.STRING,
                                 "(": Token_T.L_PARENTHESIS} 
                                | un_logic_deduction.to_dict(),

         Token_T.L_PARENTHESIS: {STRING_PLACEHOLDER: Token_T.STRING,
                                 "(": Token_T.L_PARENTHESIS} 
                                | un_logic_deduction.to_dict(),

         Token_T.R_PARENTHESIS: {END_PLACEHOLDER: Token_T.END,
                                 ")": Token_T.R_PARENTHESIS} 
                                | bin_logic_deduction.to_dict(),

         Token_T.END:           {}
         })
    
    value: str
    start_position: int
    length: int
    prev_token_type: Token_T = field(repr=False)
    t_type: Optional[Token_T] = None

    def __post_init__(self):
        def get_expected_keys() -> str:
            nonlocal expected_types
            return f"[{' '.join(expected_types.keys())}] were expected!"

        def get_expected_values() -> str:
            nonlocal expected_types
            return f"[{' '.join([token.name for token in expected_types.values()])}] were expected!"

        expected_types: FrozenDict[str, Token_T] = Token.next_expected[self.prev_token_type]
        if self.t_type is not None:
            if (self.t_type == Token_T.STRING and expected_types.get(STRING_PLACEHOLDER)) is None or \
                expected_types.get(self.value) is None:

                format_exception(exc=WrongTokenError,
                                 exception_message=f"Unexpected forced token! \"{self.t_type}\" was forced when "
                                                    f"{get_expected_values()}",
                                 token_string=self.value)
            return

        if (deduced_type := expected_types.get(self.value)) is None:
            if (str_type := expected_types.get(STRING_PLACEHOLDER)) is None:
                format_exception(exc=WrongTokenError,
                                 exception_message=f"Unexpected token! \"{self.value}\" was given when "
                                                    f"{get_expected_keys()}",
                                 token_string=self.value)
            object.__setattr__(self, "t_type", str_type)
            return
        object.__setattr__(self, "t_type", deduced_type)

    def compute(self, mapping: Mapping):
        if self.t_type != Token_T.STRING:
            format_exception(exc=WrongTokenError,
                             exception_message="Can't compute non-STRING token!",
                             token_string=self.value)

        if self.value.lstrip("-").isdecimal():
            return float(self.value)

        try:
            if self.value.startswith(FIELD_FORCE_PREFIX):
                return FieldDataGetter(self.value[len(FIELD_FORCE_PREFIX):]).compute(mapping)

            return FieldDataGetter(self.value).compute(mapping)
        except QueryLangException as e:
            if e.caught:
                raise
            exc_type, *_ = sys.exc_info()
            format_exception(exc=exc_type,
                             exception_message=str(e),
                             token_string=self.value)


class Tokenizer:
    def __init__(self, exp: str):
        self.exp = exp

    def _get_next_token(self, start_ind: int, prev_token_type: Token_T) -> tuple[Token, int]:
        while start_ind < len(self.exp) and self.exp[start_ind].isspace():
            start_ind += 1

        if start_ind == len(self.exp):
            return Token(value=END_PLACEHOLDER,
                         start_position=start_ind,
                         length=0,
                         prev_token_type=prev_token_type), start_ind

        if self.exp[start_ind] in "()":
            return Token(value=self.exp[start_ind],
                         start_position=start_ind,
                         length=1,
                         prev_token_type=prev_token_type), start_ind + 1

        if self.exp[start_ind] == "\"":
            start_ind += 1
            i = start_ind
            while i < len(self.exp) and (self.exp[i] != "\"" or self.exp[i-1] == "\\"):
                i += 1
            if i == len(self.exp):
                format_exception(exc=QuerySyntaxError,
                                 exception_message="Wrong <\"> usage! No closing quote found!",
                                 token_string=self.exp[max(0, start_ind - 5):start_ind + 5])
            return Token(value=self.exp[start_ind:i],
                         start_position=start_ind,
                         length=i - start_ind + 1,
                         prev_token_type=prev_token_type), i + 1

        i = start_ind
        while i < len(self.exp):
            if self.exp[i].isspace():
                return Token(value=self.exp[start_ind:i],
                             start_position=start_ind,
                             length=i - start_ind + 1,
                             prev_token_type=prev_token_type), i + 1
            elif self.exp[i] in f"()":
                break
            i += 1

        return Token(value=self.exp[start_ind:i],
                     start_position=start_ind,
                     length=i - start_ind + 1,
                     prev_token_type=prev_token_type), i

    def get_tokens(self):
        search_index = 0
        res: list[Token] = []

        current_token_type = Token_T.START

        parenthesis_counter = 0
        first_opening_parenthesis_pos = -1
        last_closing_parenthesis_pos = -1

        while current_token_type != Token_T.END:
            cur_token, search_index = self._get_next_token(search_index, current_token_type)
            res.append(cur_token)
            if cur_token.value == "(":
                if parenthesis_counter == 0:
                    first_opening_parenthesis_pos = cur_token.start_position
                parenthesis_counter += 1
            elif cur_token.value == ")":
                parenthesis_counter -= 1
                if parenthesis_counter == 0:
                    last_closing_parenthesis_pos = cur_token.start_position
                elif parenthesis_counter < 0:
                    format_exception(exc=QuerySyntaxError,
                                     exception_message="Too many closing parentheses!",
                                     token_string=self.exp[max(0, first_opening_parenthesis_pos - 5):
                                                            last_closing_parenthesis_pos + 1 + 5])
            current_token_type = cur_token.t_type
        if parenthesis_counter:
            format_exception(exc=QuerySyntaxError,
                             exception_message="Too many opening parentheses!",
                             token_string=self.exp[max(0, first_opening_parenthesis_pos - 5):
                                                    max(first_opening_parenthesis_pos, last_closing_parenthesis_pos) + 1 + 5])
        return res


@dataclass(slots=True, frozen=True)
class Method(Computable):
    operand: Computable
    method_name: str
    method: Callable[[Any], int]
    value: str = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "value", f"{self.method_name}({self.operand.value})")

    def compute(self, mapping: Mapping) -> Iterator[int] | int:
        try:
            computed_operand = self.operand.compute(mapping)
            return self.method(computed_operand)
        except QueryLangException as e:
            if e.caught:
                raise
            exc_type, *_ = sys.exc_info()
            format_exception(exc=exc_type,
                             exception_message=str(e),
                             token_string=self.value)

@dataclass(slots=True, frozen=True)
class EvalNode(Computable):
    value: str = field(init=False)
    operator: str
    left: Optional[Computable | Token] = None
    right: Optional[Computable | Token] = None
    operation: T_unary_op | T_binary_op = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "operation", logic_factory(self.operator))
        if self.left is not None and self.right is not None:
            object.__setattr__(self, "value", f"({self.left.value} {self.operator} {self.right.value})")
        elif self.left is not None:
            object.__setattr__(self, "value", f"({self.operator} {self.left.value})")
        else:
            format_exception(exc=TreeBuildingError,
                             exception_message="Empty node!",
                             token_string="????")

    def compute(self, mapping: Mapping) -> bool:
        if self.left is not None and self.right is not None:
            return self.operation(self.left, self.right, mapping)
        elif self.left is not None:
            return self.operation(self.left, mapping)


class EvaluationTree:
    def __init__(self, tokens):
        if len(tokens) == 1:
            raise TreeBuildingError("Couldn't build from an empty query!")
        self._expressions = copy.deepcopy(tokens)

    def construct(self):
        def build_expression(string_index: int):
            next_item = self._expressions[string_index + 1]

            if next_item.t_type == Token_T.KEYWORD:
                query = self._expressions.pop(string_index).value
                keyword_name = self._expressions.pop(string_index).value

                try:
                    keyword_function = partial(keyword_factory(keyword_name), search_pattern=re.compile(query))
                except QueryLangException as e:
                    format_exception(exc=type(e),
                                     exception_message=str(e),
                                     token_string=keyword_name)

                if self._expressions[string_index].t_type == Token_T.L_PARENTHESIS:
                    self._expressions.pop(string_index)
                    build_expression(string_index)
                    build_logic(string_index)
                else:
                    build_expression(string_index)

                operand = self._expressions.pop(string_index)
                self._expressions.insert(string_index, Method(operand=operand,
                                                              method_name=f"{query} {keyword_name} ",
                                                              method=keyword_function))

            elif next_item.t_type == Token_T.L_PARENTHESIS:
                method_name = self._expressions.pop(string_index).value

                try:
                    method_function = method_factory(method_name)
                except QueryLangException as e:
                    format_exception(exc=type(e),
                                     exception_message=str(e),
                                     token_string=method_name)

                self._expressions.pop(string_index)  # parenthesis
                build_expression(string_index)
                build_logic(string_index)
                operand = self._expressions.pop(string_index)
                self._expressions.insert(string_index, Method(operand=operand,
                                                              method_name=method_name,
                                                              method=method_function))

        def build_logic(start_index: int):
            logic_start = start_index
            while logic_start < len(self._expressions) - 2:
                operator = self._expressions[logic_start]
                if not isinstance(operator, Token):  # Can be of "Method" type
                    logic_start += 1
                    continue

                if operator.t_type == Token_T.L_PARENTHESIS:
                    self._expressions.pop(logic_start)
                    build_logic(logic_start)
                    logic_start += 1
                    continue

                elif operator.t_type == Token_T.R_PARENTHESIS:
                    break

                elif operator.t_type == Token_T.STRING:
                    build_expression(logic_start)
                    logic_start += 1
                    continue

                if operator.value not in UNARY_LOGIC:
                    logic_start += 1
                    continue

                self._expressions.pop(logic_start)
                if self._expressions[logic_start].t_type == Token_T.L_PARENTHESIS:
                    build_logic(logic_start)
                else:
                    build_expression(logic_start)  # guaranteed that STRING

                operand = self._expressions.pop(logic_start)
                self._expressions.insert(logic_start, EvalNode(left=operand, operator=operator.value))

            for current_logic_set in BIN_LOGIC_PRECEDENCE:
                logic_start = start_index
                while logic_start < len(self._expressions) - 2:
                    operator = self._expressions[logic_start + 1]
                    if operator.t_type in (Token_T.R_PARENTHESIS, Token_T.END):
                        break

                    if operator.value in current_logic_set:
                        left_operand = self._expressions.pop(logic_start)
                        self._expressions.pop(logic_start)  # operator
                        right_operand = self._expressions.pop(logic_start)
                        self._expressions.insert(logic_start, EvalNode(left=left_operand, right=right_operand,
                                                                       operator=operator.value))
                    else:
                        logic_start += 2

            if self._expressions[start_index + 1].t_type == Token_T.R_PARENTHESIS:
                self._expressions.pop(start_index + 1)

        build_logic(0)


    def get_master_node(self):
        if len(self._expressions) != 2:
            raise TreeBuildingError("Error creating a syntax tree!")
        return self._expressions[0]


if __name__ == "__main__":
    print(__doc__)
