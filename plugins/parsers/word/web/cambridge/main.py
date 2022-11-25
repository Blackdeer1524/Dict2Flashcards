import os

from app_utils.preprocessing import remove_empty_keys
from consts import CardFields
from plugins_management.config_management import LoadableConfig
from .utils import define as _define
from plugins_management.parsers_return_types import DictionaryFormat


SCHEME_DOCS = """
tags: {
    pos: part of speach (str)
    domain: word domain (list[str])
    level: English proficiency level (str)["A1", "A2", "B1", "B2", "C1", "C2"]
    region: where this word mostly in use (list[str])
    usage: usage context (list[str])
}
"""

_CONFIG_DOCS = """
audio_region
    Audio region 
    valid values: either of ["uk", "us"] 

timeout
    Request timeout in seconds
    type: integer | float
    default value: 1
"""

_CONF_VALIDATION_SCHEME = \
    {
        "audio_region": ("us", [str], ["us", "uk"]),
        "timeout": (1, [int, float], [])
    }

config = LoadableConfig(config_location=os.path.dirname(__file__),
                        validation_scheme=_CONF_VALIDATION_SCHEME,
                        docs=_CONFIG_DOCS)


def translate(word: str, word_dict: dict) -> list[dict]:
    audio_region_field = f"{config['audio_region'].upper()}_audio_links"
    word_list = []
    for pos in word_dict:
        audio = word_dict[pos].get(audio_region_field, [])
        for definition, examples, domain, labels_and_codes, level, \
            region, usage, image, alt_terms, irreg_forms \
                in zip(word_dict[pos]["definitions"],
                       word_dict[pos]["examples"],
                       word_dict[pos]["domain"],
                       word_dict[pos]["labels_and_codes"],
                       word_dict[pos]["level"],
                       word_dict[pos]["region"],
                       word_dict[pos]["usage"],
                       word_dict[pos]["image_links"],
                       word_dict[pos]["alt_terms"],
                       word_dict[pos]["irregular_forms"]):
            current_word_dict = {CardFields.word: word.strip(),
                                 CardFields.special: irreg_forms + alt_terms,
                                 CardFields.definition: definition,
                                 CardFields.sentences: examples,
                                 CardFields.audio_links: audio,
                                 CardFields.img_links: [image] if image else [],
                                 CardFields.dict_tags: {"domain": domain,
                                                    "level": level,
                                                    "region": region,
                                                    "usage": usage,
                                                    "pos": pos
                                                    }
                                 }
            remove_empty_keys(current_word_dict)
            word_list.append(current_word_dict)
    return word_list


def define(word: str) -> tuple[DictionaryFormat, str]:
    return _define(word=word, timeout=config["timeout"])
