import json


def translate_word_uk(word_dict):
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



def translate_word_us(word_dict):
    """
    Adapt new parser to legacy code
    """
    word_list = []
    for def_block in word_dict:
        word, data = def_block[0], def_block[1]
        for pos in data:
            audio = data[pos].get("US_audio_link", "")
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

DICTIONARY_DIR = r"C:\Users\Danila\Desktop\sentence_mining\dictionaries\cambridge/"
with open(f"{DICTIONARY_DIR}local_cambridge_dict.json", encoding="utf-8") as f:
    data = json.load(f)

uk_data = translate_word_uk(data)
audio_list = []
image_list = []
parser_name = "cambridge_UK"
for word_block in uk_data:
    word, pos, audio_link, image_link = word_block.get("word", "").lower().strip(),\
                                        word_block.get("pos", ""), word_block.get("audio_link", ""), \
                                        word_block.get("image_link", "")
    if audio_link:
        audio_list.append([word, pos, parser_name, audio_link])
    if image_link:
        image_list.append([word, pos, parser_name, image_link])

with open(f"{DICTIONARY_DIR}/media_info/uk_audios.json", "w", encoding="utf-8") as audio_file, \
     open(f"{DICTIONARY_DIR}/media_info/images.json", "w", encoding="utf-8") as image_file:
    json.dump(audio_list, audio_file, indent=1)
    json.dump(image_list, image_file, indent=1)

audio_list = []
us_data = translate_word_us(data)
parser_name = "cambridge_US"
for word_block in us_data:
    word, pos, audio_link = word_block.get("word", "").lower().strip(), \
                            word_block.get("pos", ""), word_block.get("audio_link", "")
    if audio_link:
        audio_list.append([word, pos, parser_name, audio_link])

with open(f"{DICTIONARY_DIR}/media_info/us_audios.json", "w", encoding="utf-8") as audio_file:
    json.dump(audio_list, audio_file, indent=1)
