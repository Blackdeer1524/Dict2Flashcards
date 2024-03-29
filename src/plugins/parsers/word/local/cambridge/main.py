import os
import re
from typing import TypedDict

from .. import config_management, consts

DICTIONARY_NAME = "cambridge"

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
"""

_CONF_VALIDATION_SCHEME = \
    {
        "audio_region": ("us", [str], ["us", "uk"]),
    }

config = config_management.LoadableConfig(
    config_location=os.path.dirname(__file__),
    validation_scheme=_CONF_VALIDATION_SCHEME,
    docs=_CONFIG_DOCS)


DEFINITION_T       = str
IMAGE_LINK_T       = str
LEVEL_T            = str
UK_IPA_T           = list[str]
UK_AUDIO_LINKS_T   = list[str]
US_IPA_T           = list[str]
US_AUDIO_LINKS_T   = list[str]
ALT_TERMS_T        = list[str]
DOMAINS_T          = list[str]
EXAMPLES_T         = list[str]
IRREGULAR_FORMS_T  = list[str]
LABELS_AND_CODES_T = list[str] 
REGIONS_T          = list[str]
USAGES_T           = list[str]              

WORD_T = str
POS_T = list[str]

class POSFields(TypedDict):
    UK_IPA:           list[UK_IPA_T]
    UK_audio_links:   list[UK_AUDIO_LINKS_T]
    US_IPA:           list[US_IPA_T]
    US_audio_links:   list[US_AUDIO_LINKS_T]
    alt_terms:        list[ALT_TERMS_T]
    definitions:      list[DEFINITION_T]
    domains:          list[DOMAINS_T]
    examples:         list[EXAMPLES_T]
    image_links:      list[IMAGE_LINK_T]
    irregular_forms:  list[IRREGULAR_FORMS_T]
    labels_and_codes: list[LABELS_AND_CODES_T]
    levels:           list[LEVEL_T]
    regions:          list[REGIONS_T]
    usages:           list[USAGES_T]


class POSData(TypedDict):
    POS:  POS_T
    data: POSFields


def translate(word: str, word_data: list[POSData]) -> list[consts.CardFormat]:
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
            current_word_dict:consts.CardFormat = {
                "word": word.strip(),
                "special": irreg_forms + alt_terms,
                "definition": definition,
                "examples": examples,
                "image_links": [image] if image else [],
                "audio_links": region_audio_links,
                "tags": {
                    "domain": domain,
                    "region": region,
                    "usage":  usage,
                    "pos":    pos
                    },
                }
            if level:
                current_word_dict["tags"]["level"] = level

            word_list.append(current_word_dict)
    return word_list


def define(query: str, dictionary: list[tuple[WORD_T, list[POSData]]]) -> tuple[list[consts.CardFormat], str]:
    word_query = re.compile(query)
    results: list[consts.CardFormat] = []
    for word, word_data in dictionary:
        if not word_query.fullmatch(word):
            continue
        results.extend(translate(word=word, word_data=word_data))
    return results, ""
