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
            # {"word": слово_n, "meaning": значение_n, "Sen_Ex": [пример_1, ..., пример_n]}
            current_word_dict = {"word": word.strip(), "meaning": definition,
                                 "Sen_Ex": examples, "domain": domain, "level": level, "region": region,
                                 "usage": usage, "pos": pos, "audio_link": audio, "image_link": image,
                                 "alt_terms": alt_terms}
            current_word_dict = {key: value for key, value in current_word_dict.items() if
                                 value not in ("", [])}
            word_list.append(current_word_dict)
    return word_list
