import os

from .. import app_utils  # .preprocessing import remove_empty_keys
from .. import config_management  # import LoadableConfig
from .. import consts  # .card_fields import CardFields
from .. import parsers_return_types  # import DictionaryFormat
from .utils import POSData
from .utils import define as _define

SCHEME_DOCS = """
tags: {
    pos: part of speach (list[str])
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

config = config_management.LoadableConfig(config_location=os.path.dirname(__file__),
                        validation_scheme=_CONF_VALIDATION_SCHEME,
                        docs=_CONFIG_DOCS)


def translate(word: str, word_data: list[POSData]) -> list[dict]:
    audio_region_field = f"{config['audio_region'].upper()}_audio_links"
    word_list = []

    for pos_data in word_data:
        pos = pos_data["POS"]
        pos_fields = pos_data["data"]

        for definition, examples, domain, level, \
            region, usage, image, alt_terms, irreg_forms, region_audio_links \
                in zip(pos_fields["definitions"],
                       pos_fields["examples"],
                       pos_fields["domains"],
                       pos_fields["levels"],
                       pos_fields["regions"],
                       pos_fields["usages"],
                       pos_fields["image_links"],
                       pos_fields["alt_terms"],
                       pos_fields["irregular_forms"],
                       pos_fields[audio_region_field]):  # type: ignore
            current_word_dict = {consts.CardFields.word: word.strip(),
                                 consts.CardFields.special: irreg_forms + alt_terms,
                                 consts.CardFields.definition: definition,
                                 consts.CardFields.sentences: examples,
                                 consts.CardFields.audio_links: region_audio_links,
                                 consts.CardFields.img_links: [image] if image else [],
                                 consts.CardFields.dict_tags: {"domain": domain,
                                                        "level": level,
                                                        "region": region,
                                                        "usage": usage,
                                                        "pos": pos
                                                        }
                                 }
            app_utils.preprocessing.remove_empty_keys(current_word_dict)
            word_list.append(current_word_dict)
    return word_list


def define(word: str) -> tuple[parsers_return_types.DictionaryFormat, str]:
    return list(_define(word=word, timeout=config["timeout"]).items()), ""
