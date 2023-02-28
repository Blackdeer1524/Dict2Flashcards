import os
from typing import Callable
import genanki

from .. import app_utils, config_management, consts, parsers_return_types


_CONF_VALIDATION_SCHEME = {
    "merge picked sentences in one card": (False, [bool], []), 
    "merge separator": (" |<br><br>", [str], [])
}


_CONFIG_DOCS = """
merge picked sentences in one card:
    whether to merge picked sentences in one card or create different card for each sentence
    type: str
    
merge separator:
    Separator used in sentence merging
    default: " |<br><br>"
    type: str
"""

config = config_management.LoadableConfig(
    config_location=os.path.dirname(__file__),
    validation_scheme=_CONF_VALIDATION_SCHEME,
    docs=_CONFIG_DOCS)


MODEL_FIELDS = [
    {'name': 'Sentence'},
    {'name': 'Word'},
    {'name': 'Definition'},
    {'name': 'Image'},
    {'name': 'Word Audio'},
]


MODEL_CSS = """\
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
"""


ONE_SENTENCE_RESULTING_MODEL = genanki.Model(
  1869993568,  # just a random number
  'Mined Sentence Vocab',
  fields=MODEL_FIELDS,
  templates=[
    {
      'name': 'Recognition',
      'qfmt': '{{Sentence}}',
      'afmt': """\
{{FrontSide}}
<hr id="answer">
<div class="accent">
    {{Word}}
</div>
{{Definition}}<br>
{{Image}}<br>
{{Word Audio}}<br>

Tags{{#Tags}}|{{/Tags}}{{Tags}}
"""},],
    css=MODEL_CSS)


# https://ankiweb.net/shared/info/1639213385
MERGING_RESULTING_MODEL = genanki.Model(
  1607392319,  # just a random number
  '[Random] Mined Sentence Vocab',
  fields=MODEL_FIELDS,
  templates=[
    {
      'name': 'Recognition',
      'qfmt': '{{rand-alg:Sentence}}',
      'afmt': """\
{{Sentence}}
<hr id="answer">
<div class="accent">
    {{Word}}
</div>
{{Definition}}<br>
{{Image}}<br>
{{Word Audio}}<br>

Tags{{#Tags}}|{{/Tags}}{{Tags}}
"""},],
    css=MODEL_CSS)


def save(deck: app_utils.decks.SavedDataDeck,
         saving_card_status: app_utils.decks.CardStatus,
         saving_path: str,
         image_names_wrapper: Callable[[str], str],
         audio_names_wrapper: Callable[[str], str]):
    if not deck.get_card_status_stats(saving_card_status):
        return

    anki_deck_name = os.path.basename(saving_path).split(".", 1)[0]
    anki_deck_id = int(str(abs(hash(anki_deck_name)))[:10])
    anki_deck = genanki.Deck(anki_deck_id, anki_deck_name)

    for card_page in deck:
        if card_page[app_utils.decks.SavedDataDeck.CARD_STATUS] != saving_card_status:
            continue
        card_data = card_page[app_utils.decks.SavedDataDeck.CARD_DATA]

        images = ""
        audios = ""
        hierarchical_prefix = ""
        tags = []
        if (additional := card_page.get(app_utils.decks.SavedDataDeck.ADDITIONAL_DATA)):
            image_paths = additional.get(app_utils.decks.SavedDataDeck.SAVED_IMAGES_PATHS, [])
            images = " ".join([image_names_wrapper(name) for name in image_paths])

            if (audio_data := additional.get(app_utils.decks.SavedDataDeck.AUDIO_DATA)) is not None:
                audio_paths = audio_data[app_utils.decks.SavedDataDeck.AUDIO_SAVING_PATHS]
                audios = " ".join([audio_names_wrapper(name) for name in audio_paths])

            hierarchical_prefix = additional.get(app_utils.decks.SavedDataDeck.HIERARCHICAL_PREFIX, "")
            
            user_tags = additional.get(app_utils.decks.SavedDataDeck.USER_TAGS, "").split()
            if hierarchical_prefix:
                user_tags = [f"{hierarchical_prefix}::{tag}" for tag in user_tags]
            tags.extend(user_tags)

        saving_word = card_data.get(consts.CardFields.word, "")
        definition = card_data.get(consts.CardFields.definition, "")
        dict_tags = card_data.get_str_dict_tags(card_data=card_data,
                                                prefix=hierarchical_prefix,
                                                sep="::",
                                                tag_processor=lambda tag: app_utils.string_utils.remove_special_chars(tag, sep="_")).split()

        tags.extend(dict_tags)

        if config["merge picked sentences in one card"]:
            sentence_example = config["merge separator"].join(card_data.get(consts.CardFields.sentences, [""]))
            note = genanki.Note(
                model=MERGING_RESULTING_MODEL,
                # I have no idea why, but if any of the fields is empty, then card won't be added, 
                fields=[sentence_example if sentence_example else " ",  
                        saving_word      if saving_word      else " ",  
                        definition       if definition       else " ",  
                        images           if images           else " ",  
                        audios           if audios           else " ",  
                        ],
                tags=tags
                )  
            anki_deck.add_note(note)
        else:
            for sentence_example in card_data.get(consts.CardFields.sentences, [""]):
                note = genanki.Note(
                    model=ONE_SENTENCE_RESULTING_MODEL,
                    fields=[sentence_example, 
                            saving_word, 
                            definition, 
                            images, 
                            audios],
                    tags=tags)  
                anki_deck.add_note(note)

    my_package = genanki.Package(anki_deck)
    my_package.write_to_file(f'{saving_path}.apkg')


if __name__ == "__main__":
    import genanki

    my_model = genanki.Model(
    1607392319,
    'Simple Model',
    fields=[
        {'name': 'Question'},
        {'name': 'Answer'},
    ],
    templates=[
        {
        'name': 'Card 1',
        'qfmt': '{{rand-alg:Question}}',
        'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
        },
    ])

    my_note = genanki.Note(
            model=my_model,
            fields=['Capital of Argentina', 'Buenos Aires'])
    
    my_deck = genanki.Deck(
    2059400110,
    'Country Capitals')

    my_deck.add_note(my_note)
    genanki.Package(my_deck).write_to_file('output.apkg')
    