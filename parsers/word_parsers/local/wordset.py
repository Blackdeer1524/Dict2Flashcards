DICTIONARY_PATH = "wordset"


def translate(word_dict):
    """
    Adapt new parser to legacy code
    """
    word_list = []
    for word, data in word_dict:
        for pos in data:
            # uk_ipa = word_dict[word][pos]["UK IPA"]
            # us_ipa = word_dict[word][pos]["US IPA"]
            for name in ("examples", "domain", "labels_and_codes", "level", "region", "usage"):
                if data[pos].get(name) is None:
                    data[pos][name] = []
                while len(data[pos]["definitions"]) > len(data[pos][name]):
                    data[pos][name].append([""])

            for definition, examples, domain, labels_and_codes, level, \
                region, usage in zip(data[pos]["definitions"],
                                     data[pos]["examples"],
                                     data[pos]["domain"],
                                     data[pos]["labels_and_codes"],
                                     data[pos]["level"],
                                     data[pos]["region"],
                                     data[pos]["usage"]):

                # {"word": слово_n, "meaning": значение_n, "Sen_Ex": [пример_1, ..., пример_n]}
                word_list.append({"word": word, "meaning": definition,
                                  "Sen_Ex": examples, "domain": domain, "level": level, "region": region,
                                  "usage": usage, "pos": pos})
    return word_list
