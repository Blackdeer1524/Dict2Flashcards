import json
from typing import Callable
import os

from .. import app_utils, config_management


config = config_management.LoadableConfig(
    config_location=os.path.dirname(__file__),
    validation_scheme={},
    docs="")


def save(deck: app_utils.decks.SavedDataDeck,
         saving_card_status: app_utils.decks.CardStatus,
         saving_path: str,
         image_names_wrapper: Callable[[str], str],
         audio_names_wrapper: Callable[[str], str]):
    saving_object = deck.get_audio_data(saving_card_status)

    if saving_object:
        with open(saving_path + ".json", "w", encoding="utf-8") as deck_file:
            json.dump(saving_object, deck_file, cls=app_utils.storages.FrozenDictJSONEncoder, indent=2)
