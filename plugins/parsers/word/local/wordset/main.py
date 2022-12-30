import os

from app_utils.preprocessing import remove_empty_keys
from consts import CardFields
from plugins_management.config_management import LoadableConfig
from typing import TypedDict


DICTIONARY_NAME = "wordset"
SCHEME_DOCS = ""


class POSDataScheme(TypedDict):
    definitions: list[str]
    examples:    list[list[str]]


POS_T = str
WORD_DATA_STRUCTURE = dict[POS_T, POSDataScheme]


_CONF_VALIDATION_SCHEME = {}

config = LoadableConfig(config_location=os.path.dirname(__file__),
                        validation_scheme=_CONF_VALIDATION_SCHEME,
                        docs="")


def translate(word: str, word_data: WORD_DATA_STRUCTURE):
    word_list = []
    for pos in word_data:
        for definition, examples in zip(word_data[pos]["definitions"], word_data[pos]["examples"]):
            current_word_data = {CardFields.word: word.strip(),
                                 CardFields.definition: definition,
                                 CardFields.sentences: examples, 
                                 CardFields.dict_tags: {
                                    "pos": pos,
                                 }}
            word_list.append(current_word_data)
    return word_list
