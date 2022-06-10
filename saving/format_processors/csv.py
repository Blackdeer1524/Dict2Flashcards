import csv
from typing import Callable

from utils.cards import SavedDeck
from utils.cards import CardStatus
from consts.card_fields import FIELDS


def save(deck: SavedDeck,
         saving_card_status: CardStatus,
         saving_path: str,
         image_names_wrapper: Callable[[str], str]):
    csv_file = open(saving_path + ".csv", 'w', encoding="UTF-8")
    cards_writer = csv.writer(csv_file, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    for card_page in deck:
        if card_page[SavedDeck.CARD_STATUS] != saving_card_status:
            continue
        card_data = card_page[SavedDeck.CARD_DATA]

        sentence_example = card_data.get(FIELDS.sentences, [""])[0]
        saving_word = card_data.get(FIELDS.word, "")
        definition = card_data.get(FIELDS.definition, "")
        dict_tags = card_data.get_str_dict_tags(card_data)

        user_tags = card_data.get(SavedDeck.USER_TAGS, "")
        tags = f"{dict_tags} {user_tags}"

        images = ""
        audios = ""
        if (additional := card_page.get(SavedDeck.ADDITIONAL_DATA)) is not None:
            images = " ".join([image_names_wrapper(name) for name in additional.get(SavedDeck.IMAGES_DATA, [])])
            audios = " ".join([name for name in additional.get(SavedDeck.AUDIO_DATA, [])])

        cards_writer.writerow([sentence_example, saving_word, definition, images, audios, tags])
    csv_file.close()
