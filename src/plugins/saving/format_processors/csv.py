import csv
from typing import Callable

from .. import app_utils, consts


def save(deck: app_utils.decks.SavedDataDeck,
         saving_card_status: app_utils.decks.CardStatus,
         saving_path: str,
         image_names_wrapper: Callable[[str], str],
         audio_names_wrapper: Callable[[str], str]):
    if not deck.get_card_status_stats(saving_card_status):
        return

    csv_file = open(saving_path + ".csv", 'w', encoding="UTF-8")
    cards_writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    for card_page in deck:
        if card_page[app_utils.decks.SavedDataDeck.CARD_STATUS] != saving_card_status:
            continue
        card_data = card_page[app_utils.decks.SavedDataDeck.CARD_DATA]

        images = ""
        audios = ""
        hierarchical_prefix = ""
        if (additional := card_page.get(app_utils.decks.SavedDataDeck.ADDITIONAL_DATA)):
            images = " ".join([image_names_wrapper(name) for name in additional.get(app_utils.decks.SavedDataDeck.SAVED_IMAGES_PATHS, [])])
            if (audio_data := additional.get(app_utils.decks.SavedDataDeck.AUDIO_DATA)) is not None:
                audios = " ".join([audio_names_wrapper(name) for name in audio_data[app_utils.decks.SavedDataDeck.AUDIO_SAVING_PATHS]])
            hierarchical_prefix = additional.get(app_utils.decks.SavedDataDeck.HIERARCHICAL_PREFIX, "")

        sentence_example = card_data.get(consts.CardFields.sentences, [""])[0]
        saving_word = card_data.get(consts.CardFields.word, "")
        definition = card_data.get(consts.CardFields.definition, "")
        dict_tags = card_data.get_str_dict_tags(card_data=card_data,
                                                prefix=hierarchical_prefix,
                                                sep="::",
                                                tag_processor=lambda tag: app_utils.string_utils.remove_special_chars(tag, sep="_"))

        user_tags = card_data.get(app_utils.decks.SavedDataDeck.USER_TAGS, "")
        if hierarchical_prefix:
            user_tags = " ".join((f"{hierarchical_prefix}::{tag}" for tag in user_tags.split()))
        tags = f"{dict_tags} {user_tags}"

        cards_writer.writerow([sentence_example, saving_word, definition, images, audios, tags])
    csv_file.close()
