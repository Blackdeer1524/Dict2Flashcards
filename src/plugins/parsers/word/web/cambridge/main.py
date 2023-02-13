import os

from .. import config_management  # import LoadableConfig
from .. import consts  # .card_fields import CardFields
from .utils import RESULT_FORMAT
from .utils import define as _define
from .. import app_utils

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
audio region
    Audio region 
    type: string
    valid values: either of ["uk", "us"] 

bilingual variation
    Type of bilingual dictionary. "" specifies monolingual dictionary
    type: string
    valid values: either of [
        "",
        "dutch",
        "french",
        "german",
        "indonesian",
        "italian",
        "japanese",
        "norwegian",
        "polish",
        "portuguese",
        "spanish",
        "arabic",
        "catalan",
        "chinese-simplified",
        "chinese-traditional",
        "czech",
        "danish",
        "korean",
        "malay",
        "russian",
        "thai",
        "turkish",
        "ukrainian",
        "vietnamese",
    ] 

timeout
    Request timeout in seconds
    type: integer | float
    default value: 1
"""

_CONF_VALIDATION_SCHEME = \
    {   
        "bilingual variation": ("", [str], [
                "",
                "dutch",
                "french",
                "german",
                "indonesian",
                "italian",
                "japanese",
                "norwegian",
                "polish",
                "portuguese",
                "spanish",
                "arabic",
                "catalan",
                "chinese-simplified",
                "chinese-traditional",
                "czech",
                "danish",
                "korean",
                "malay",
                "russian",
                "thai",
                "turkish",
                "ukrainian",
                "vietnamese",
        ]),
        "audio region": ("us", [str], ["us", "uk"]),
        "timeout": (1, [int, float], [])
    }

config = config_management.LoadableConfig(
    config_location=os.path.dirname(__file__),
    validation_scheme=_CONF_VALIDATION_SCHEME,
    docs=_CONFIG_DOCS)


def translate(definitons_data: RESULT_FORMAT) -> list[consts.CardFormat]:
    audio_region_field = f"{config['audio region'].upper()}_audio_links"
    word_list = []

    for word, pos_lists in definitons_data.items():
        for pos_data in pos_lists: 
            pos = pos_data["POS"]
            pos_fields = pos_data["data"]

            for definition, definition_translation, examples, domain, level, \
                region, usage, image, alt_terms, irreg_forms, region_audio_links \
                    in zip(pos_fields["definitions"],
                        pos_fields["definitions_translations"],
                        pos_fields["examples"],
                        pos_fields["domains"],
                        pos_fields["levels"],
                        pos_fields["regions"],
                        pos_fields["usages"],
                        pos_fields["image_links"],
                        pos_fields["alt_terms"],
                        pos_fields["irregular_forms"],
                        pos_fields[audio_region_field]):  # type: ignore

                current_word_dict: consts.CardFormat = {
                    "word": word.strip(),
                    "special": irreg_forms + alt_terms,
                    "definition": f"{definition_translation}\n{definition}" if definition_translation else definition,
                    "examples": examples,
                    "audio_links": region_audio_links,
                    "image_links": [image] if image else [],
                    "tags": {
                        "domain": domain,
                        "region": region,
                        "usage": usage,
                        "pos": pos
                    }
                }
                if level:
                    current_word_dict["tags"]["level"] = level

                word_list.append(current_word_dict)
    return word_list


def define(word: str) -> tuple[list[consts.CardFormat], str]:
    definitions, error = _define(word=app_utils.string_utils.remove_special_chars(word, 
                                                                                  " ", 
                                                                                  '№!"#%\'()*,./:;<>?@[\\]^_`{|}~'),  # $ & + - =
                                 bilingual_vairation=config["bilingual variation"],
                                 timeout=config["timeout"])
    return translate(definitions), error
