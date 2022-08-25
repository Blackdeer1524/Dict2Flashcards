from app_utils.query_language.query_processing import get_card_filter
from app_utils.query_language.exceptions import ResultPrint
from typing import Any, Generator, Iterable
from itertools import chain


def assert_result(query: str,
                  scheme: dict,
                  assertion: Any,
                  print_if_failed: str | list[str] | None = None):
    def open_generators(item: Any):
        if isinstance(item, str) or not isinstance(item, Iterable):
            return

        for i in range(len(item)):
            if isinstance(item[i], (Generator, chain)):
                new_item_i = []
                for k in item[i]:
                    open_generators(k)
                    new_item_i.append(k)
                item[i] = new_item_i

    res = get_card_filter(query)(scheme)
    if isinstance(res, (Generator, chain)):
        res = [i for i in res]
    open_generators(res)
    if assertion == res:
        return
    if print_if_failed is None:
        try:
            get_card_filter(f"print({query})")(scheme)
        except ResultPrint as e:
            print(f"Query:{query}\nResult:{str(e)}\nExpected:\n{assertion}\n\n")
        exit(1)

    if isinstance(print_if_failed, list):
        for i in print_if_failed:
            try:
                get_card_filter(f"print({i})")(scheme)
            except ResultPrint as e:
                print(f"Query:{query}\nResult:{str(e)}\nExpected:\n{assertion}\n\n")
        exit(1)

    try:
        get_card_filter(f"print({print_if_failed})")(scheme)
    except ResultPrint as e:
        print(f"Query:{query}\nResult:{str(e)}\nExpected:\n{assertion}\n\n")
    exit(1)


def test_keywords():
    def test_in():
        scheme = {
            "field": ["1", "2", "3"]
        }
        assert_result(query="1 in field",
                      scheme=scheme, 
                      assertion=True, 
                      print_if_failed="field")
        assert_result(query="not 2 in field",
                      scheme=scheme,
                      assertion=False,
                      print_if_failed="field")
    test_in()


def test_special_queries():
    def test_any():
        scheme = {
            "pos": {
                "noun": {
                    "data": 1
                },
                "verb": {
                    "data": 2
                }
            }
        }
        assert_result(query="$ANY",
                      scheme=scheme,
                      assertion=["noun", "verb"])
        assert_result(query="pos[$ANY][data]",
                      scheme=scheme,
                      assertion=[1, 2])
        assert_result(query="$ANY[$ANY][data]",
                      scheme=scheme,
                      assertion=[1, 2])
    test_any()
    
    def test_self():
        scheme = {
            "field_1": 1,
            "field_2": 2
        }
        assert_result(query="$SELF",
                      scheme=scheme,
                      assertion=["field_1", "field_2"])
    test_self()
    
    def test_digit_cast():
        scheme = {
            "array_field": [1, 2, 3],
            "int_field": {
                1: [4, 5, 6]
            }
        }
        assert_result(query="array_field[d_$1]",
                      scheme=scheme,
                      assertion=2)
        assert_result(query="int_field[d_$1]",
                      scheme=scheme,
                      assertion=[4, 5, 6])
    test_digit_cast()
    
    def test_field_cast():
        scheme = {
            1: [1, 2, 3],
            2: {
                "data": [4, 5, 6]
            }
        }
        assert_result(query="f_$d_$1",
                      scheme=scheme,
                      assertion=[1, 2, 3])
        assert_result(query="d_$2[data]",
                      scheme=scheme,
                      assertion=[4, 5, 6])
    test_field_cast()
    
    
def test_methods():
    def test_len():
        scheme_1 = {
            "field": [1, 2, 3]
        }
        assert_result(query="len(field)",
                      scheme=scheme_1,
                      assertion=3,
                      print_if_failed=["len(field)", "field"])

        scheme_2 = \
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
        assert_result(query="len(field[$ANY][data])",
                      scheme=scheme_2,
                      assertion=2,
                      print_if_failed=["len(field[$ANY][data])",
                                       "field[$ANY][data]"])
    test_len()

    def test_split():
        scheme = \
        {
            "field": "text with spaces",
             "list_field": ["text with spaces 1", "text with spaces 2"]
        }
        assert_result(query="split(field)",
                      scheme=scheme,
                      assertion=["text", "with", "spaces"],
                      print_if_failed=["split(field)",
                                       "field"])
        assert_result(query="split(list_field)",
                      scheme=scheme,
                      assertion=[["text", "with", "spaces", "1"],
                                 ["text", "with", "spaces", "2"]],
                      print_if_failed=["split(list_field)",
                                       "list_field"])
    test_split()

    def test_any():
        scheme = \
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
        assert_result(query="any(field[$ANY][data] > 1)",
                      scheme=scheme,
                      assertion=True,
                      print_if_failed=["field[$ANY][data]",
                                       "field[$ANY][data] > 1"])
    test_any()

    def test_all():
        scheme = \
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
        assert_result(query="all($ANY[$ANY][data] > 0)",
                      scheme=scheme,
                      assertion=True,
                      print_if_failed=["$ANY[$ANY][data]",
                                       "$ANY[$ANY][data] > 0"])
        assert_result(query="all($ANY[$ANY][data] > 1)",
                      scheme=scheme,
                      assertion=False,
                      print_if_failed=["$ANY[$ANY][data]",
                                       "$ANY[$ANY][data] > 1"])
    test_all()

    def test_lower():
        scheme = \
        {
            "field_1": ["ABC", "abc", "AbC"],
            "field_2": "ABC"
        }
        assert_result(query="lower(field_1)",
                      scheme=scheme,
                      assertion=["abc", "abc", "abc"],
                      print_if_failed=["lower(field_1)",
                                       "field_1"])
        assert_result(query="lower(field_2)",
                      scheme=scheme,
                      assertion="abc",
                      print_if_failed=["lower(field_2)",
                                       "field_2"])
    test_lower()

    def test_upper():
        scheme = \
        {
            "field_1": ["ABC", "abc", "AbC"],
            "field_2": "ABC"
        }
        assert_result(query="upper(field_1)",
                      scheme=scheme,
                      assertion=["ABC", "ABC", "ABC"],
                      print_if_failed=["upper(field_1)",
                                       "field_1"])
        assert_result(query="upper(field_2)",
                      scheme=scheme,
                      assertion="ABC",
                      print_if_failed=["upper(field_2)",
                                       "field_2"])
    test_upper()

    def test_reduce():
        scheme = \
        {
            "field_1": ["a", "b", "c"],
            "field_2": ["d", "e", "f"]
        }
        assert_result(query="reduce($ANY)",
                      scheme=scheme,
                      assertion=["a", "b", "c", "d", "e", "f"],
                      print_if_failed=["reduce($ANY)",
                                       "$ANY"])

        scheme_2 = \
        {
            "field_1": [["a"], ["b"], ["c"]],
            "field_2": [[["d"], ["e"], ["f"]]]
        }
        assert_result(query="reduce($ANY)",
                      scheme=scheme_2,
                      assertion=[["a"], ["b"], ["c"], [["d"], ["e"], ["f"]]],
                      print_if_failed=["reduce($ANY)",
                                       "$ANY"])
    test_reduce()


if __name__ == "__main__":
    test_keywords()
    test_special_queries()
    test_methods()
