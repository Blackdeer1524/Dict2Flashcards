import os
from typing import Callable
import genanki

from .. import app_utils
from .. import consts


RESULTING_MODEL = genanki.Model(
  1869993568,  # just a random number
  'Mined Sentence Vocab',
  fields=[
    {'name': 'Sentence'},
    {'name': 'Word'},
    {'name': 'Definition'},
    {'name': 'Image'},
    {'name': 'Word Audio'},
  ],
  templates=[
    {
      'name': 'Recognition',
      'qfmt': '{{Sentence}}',
      'afmt': """\
{{FrontSide}}
<hr id="answer">
{{Word}}<br>
{{Definition}}<br>
{{Image}}<br>
{{Word Audio}}<br>

Tags{{#Tags}}｜{{/Tags}}{{Tags}}
"""},],
    css="""\
.card { 
    font-size: 23px; 
    text-align: left; 
    color: black; 
    background-color: #FFFAF0; 
    margin: 20px auto 20px auto; 
    padding: 0 20px 0 20px; 
    max-width: 600px; 
}

.accent {
    font-size: 40px;
}
""")


def save(deck: app_utils.cards.SavedDataDeck,
         saving_card_status: app_utils.cards.CardStatus,
         saving_path: str,
         image_names_wrapper: Callable[[str], str],
         audio_names_wrapper: Callable[[str], str]):
    if not deck.get_card_status_stats(saving_card_status):
        return

    anki_deck_name = os.path.basename(saving_path).split(".", 1)[0]
    anki_deck_id = int(str(abs(hash(anki_deck_name)))[:10])
    anki_deck = genanki.Deck(anki_deck_id, anki_deck_name)

    for card_page in deck:
        if card_page[app_utils.cards.SavedDataDeck.CARD_STATUS] != saving_card_status:
            continue
        card_data = card_page[app_utils.cards.SavedDataDeck.CARD_DATA]

        images = ""
        audios = ""
        hierarchical_prefix = ""
        if (additional := card_page.get(app_utils.cards.SavedDataDeck.ADDITIONAL_DATA)):
            image_paths = additional.get(app_utils.cards.SavedDataDeck.SAVED_IMAGES_PATHS, [])
            images = " ".join([image_names_wrapper(name) for name in image_paths])

            if (audio_data := additional.get(app_utils.cards.SavedDataDeck.AUDIO_DATA)) is not None:
                audio_paths = audio_data[app_utils.cards.SavedDataDeck.AUDIO_SAVING_PATHS]
                audios = " ".join([audio_names_wrapper(name) for name in audio_paths])

            hierarchical_prefix = additional.get(app_utils.cards.SavedDataDeck.HIERARCHICAL_PREFIX, "")

        sentence_example = card_data.get(consts.CardFields.sentences, [""])[0]
        saving_word = card_data.get(consts.CardFields.word, "")
        definition = card_data.get(consts.CardFields.definition, "")
        dict_tags = card_data.get_str_dict_tags(card_data=card_data,
                                                prefix=hierarchical_prefix,
                                                sep="::",
                                                tag_processor=lambda tag: app_utils.string_utils.remove_special_chars(tag, sep="_")).split()

        user_tags = card_data.get(app_utils.cards.SavedDataDeck.USER_TAGS, "").split()
        if hierarchical_prefix:
            user_tags = [f"{hierarchical_prefix}::{tag}" for tag in user_tags]
        tags = dict_tags + user_tags

        note = genanki.Note(
            model=RESULTING_MODEL,
            fields=[sentence_example, 
                    saving_word, 
                    definition, 
                    images, 
                    audios],
            tags=tags)  
        anki_deck.add_note(note)

    my_package = genanki.Package(anki_deck)
    my_package.write_to_file(f'{saving_path}.apkg')
