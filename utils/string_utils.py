import re
from enum import IntEnum

LETTERS = set("abcdefghijklmnopqrstuvwxyz")


class SearchType(IntEnum):
    exact = 0
    forward = 1
    backward = 2
    everywhere = 3


def string_search(source, query, search_type=3, case_sencitive=True):
    """
    :param source: where to search
    :param query: what to search
    :param search_type:
        exact = 0
        forward = 1
        backward = 2
        everywhere = 3
    :param case_sencitive:
    :return:
    """
    query = query.strip()
    if search_type == SearchType.exact:
        search_pattern = r"\b{}\b".format(query)
    elif search_type == SearchType.forward:
        search_pattern = r"\b{}".format(query)
    elif search_type == SearchType.backward:
        search_pattern = r"{}\b".format(query)
    else:
        search_pattern = r"{}".format(query)

    if not case_sencitive:
        pattern = re.compile(search_pattern, re.IGNORECASE)
    else:
        pattern = re.compile(search_pattern)

    if re.search(pattern, source):
        return True
    return False


def remove_special_chars(text, sep=" ", special_chars='№!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ '):
    """
    :param text: to to clean
    :param sep: replacement for special chars
    :param special_chars: special characters to remove
    :return:
    """
    new_text = ""
    start_index = 0
    while start_index < len(text) and text[start_index] in special_chars:
        start_index += 1

    while start_index < len(text):
        if text[start_index] in special_chars:
            while text[start_index] in special_chars:
                start_index += 1
                if start_index >= len(text):
                    return new_text
            new_text += sep
        new_text += text[start_index]
        start_index += 1
    return new_text
