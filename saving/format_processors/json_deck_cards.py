import json
from typing import Callable

from utils.cards import SavedDeck, CardStatus
from utils.storages import FrozenDictJSONEncoder


def save(deck: SavedDeck,
         saving_card_status: CardStatus,
         saving_path: str,
         image_names_wrapper: Callable[[str], str],
         audio_names_wrapper: Callable[[str], str]):
    saving_object = []
    for card_page in deck:
        if card_page[SavedDeck.CARD_STATUS] != saving_card_status:
            continue
        saving_object.append(card_page[SavedDeck.CARD_DATA])

    if saving_object:
        with open(saving_path + ".json", "w", encoding="utf-8") as deck_file:
            json.dump(saving_object, deck_file, cls=FrozenDictJSONEncoder)
