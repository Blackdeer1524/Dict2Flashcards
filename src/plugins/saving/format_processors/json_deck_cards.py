import json
from typing import Callable

from .. import app_utils


def save(deck: app_utils.cards.SavedDataDeck,
         saving_card_status: app_utils.cards.CardStatus,
         saving_path: str,
         image_names_wrapper: Callable[[str], str],
         audio_names_wrapper: Callable[[str], str]):
    saving_object = deck.get_card_data(saving_card_status)

    if saving_object:
        with open(saving_path + ".json", "w", encoding="utf-8") as deck_file:
            json.dump(saving_object, deck_file, cls=app_utils.cards.FrozenDictJSONEncoder)
