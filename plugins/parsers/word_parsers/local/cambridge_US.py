from consts.card_fields import FIELDS
from utils.preprocessing import remove_empty_keys


DICTIONARY_PATH = "cambridge"


def translate(word: str, word_dict: dict):
    word_list = []
    for pos in word_dict:
        audio = word_dict[pos].get("US_audio_link", "")
        for definition, examples, domain, labels_and_codes, level, \
            region, usage, image, alt_terms in zip(word_dict[pos]["definitions"],
                                                   word_dict[pos]["examples"],
                                                   word_dict[pos]["domain"],
                                                   word_dict[pos]["labels_and_codes"],
                                                   word_dict[pos]["level"],
                                                   word_dict[pos]["region"],
                                                   word_dict[pos]["usage"],
                                                   word_dict[pos]["image_links"],
                                                   word_dict[pos]["alt_terms"]):
            current_word_dict = {FIELDS.word: word.strip(),
                                 FIELDS.alt_terms: alt_terms,
                                 FIELDS.definition: definition,
                                 FIELDS.sentences: examples,
                                 FIELDS.audio_links: [audio] if audio else [],
                                 FIELDS.img_links: [image] if image else [],
                                 FIELDS.dict_tags: {"domain": domain,
                                                    "level": level,
                                                    "region": region,
                                                    "usage": usage,
                                                    "pos": pos
                                                    }
                                 }
            remove_empty_keys(current_word_dict)
            word_list.append(current_word_dict)
    return word_list