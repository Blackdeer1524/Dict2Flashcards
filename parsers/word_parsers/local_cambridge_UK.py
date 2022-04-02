DICTIONARY_PATH = "cambridge"


def translate(word_dict):
    """
    Adapt new parser to legacy code
    """
    word_list = []
    for def_block in word_dict:
        word, data = def_block[0], def_block[1]
        for pos in data:
            audio = data[pos].get("UK_audio_link", "")
            for definition, examples, domain, labels_and_codes, level, \
                region, usage, image, alt_terms in zip(data[pos]["definitions"],
                                                       data[pos]["examples"],
                                                       data[pos]["domain"],
                                                       data[pos]["labels_and_codes"],
                                                       data[pos]["level"],
                                                       data[pos]["region"],
                                                       data[pos]["usage"],
                                                       data[pos]["image_links"],
                                                       data[pos]["alt_terms"]):
                # {"word": слово_n, "meaning": значение_n, "Sen_Ex": [пример_1, ..., пример_n]}
                current_word_dict = {"word": word.strip(), "meaning": definition,
                                     "Sen_Ex": examples, "domain": domain, "level": level, "region": region,
                                     "usage": usage, "pos": pos, "audio_link": audio, "image_link": image,
                                     "alt_terms": alt_terms}
                current_word_dict = {key: value for key, value in current_word_dict.items() if
                                     value not in ("", [])}
                word_list.append(current_word_dict)
    return word_list
