import os
import re
from typing import TypedDict

from .. import config_management, consts

DICTIONARY_NAME = "wordset"
SCHEME_DOCS = ""


class POSDataScheme(TypedDict):
    definitions: list[str]
    examples:    list[list[str]]


POS_T = str
WORD_DATA_STRUCTURE = dict[POS_T, POSDataScheme]


_CONF_VALIDATION_SCHEME = {}

config = config_management.LoadableConfig(config_location=os.path.dirname(__file__),
                                          validation_scheme=_CONF_VALIDATION_SCHEME,
                                          docs="")


def translate(word: str, word_data: WORD_DATA_STRUCTURE):
    word_list = []
    for pos in word_data:
        for definition, examples in zip(word_data[pos]["definitions"], word_data[pos]["examples"]):
            current_word_data = {consts.CardFields.word: word.strip(),
                                 consts.CardFields.definition: definition,
                                 consts.CardFields.sentences: examples, 
                                 consts.CardFields.dict_tags: {
                                    "pos": pos,
                                 }}
            word_list.append(current_word_data)
    return word_list


def define(query: str, dictionary: list[tuple[str, WORD_DATA_STRUCTURE]]) -> tuple[list[consts.CardFormat], str]:
    word_query = re.compile(query)
    results: list[consts.CardFormat] = []
    for word, word_data in dictionary:
        if not re.search(word_query, word):
            continue
        results.extend(translate(word=word, word_data=word_data))
    return results, ""
