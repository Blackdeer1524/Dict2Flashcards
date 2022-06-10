from dataclasses import dataclass
from typing import Callable

from utils.cards import SavedDeck
from parsers.return_types import SentenceGenerator, ImageGenerator
from plugins.interfaces import ImageParserInterface
from plugins.interfaces import LocalWordParserInterface
from plugins.interfaces import WebSentenceParserInterface
from plugins.interfaces import WebWordParserInterface
from plugins.interfaces import CardProcessorInterface
from plugins.interfaces import LocalAudioGetterInterface
from plugins.interfaces import DeckSavingFormatInterface


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False)
class PluginContainer:
    pass


class WebWordParserContainer(PluginContainer):
    define: Callable[[str], list[(str, dict)]]
    translate: Callable[[str, dict], dict]

    def __init__(self, source_module: WebWordParserInterface):
        super().__setattr__("define", source_module.define)
        super().__setattr__("translate", source_module.translate)


class LocalWordParserContainer(PluginContainer):
    local_dict_name: str
    translate: Callable[[str], dict]

    def __init__(self, source_module: LocalWordParserInterface):
        super().__setattr__("local_dict_name", source_module.DICTIONARY_PATH)
        super().__setattr__("translate", source_module.translate)


class WebSentenceParserContainer(PluginContainer):
    get_sentence_batch: Callable[[str, int], SentenceGenerator]

    def __init__(self, source_module: WebSentenceParserInterface):
        super().__setattr__("get_sentence_batch", source_module.get_sentence_batch)


class ImageParserContainer(PluginContainer):
    get_image_links: Callable[[str], ImageGenerator]

    def __init__(self, source_module: ImageParserInterface):
        super().__setattr__("get_image_links", source_module.get_image_links)


class CardProcessorContainer(PluginContainer):
    get_saving_image_name: Callable[[str, str, dict], str]
    get_card_image_name:   Callable[[str], str]
    get_save_audio_name:   Callable[[str, str, dict], str]
    get_card_audio_name:   Callable[[str], str]
    process_card:          Callable[[dict], None]

    def __init__(self, source_module: CardProcessorInterface):
        super().__setattr__("get_saving_image_name", source_module.get_saving_image_name)
        super().__setattr__("get_card_image_name",   source_module.get_card_image_name)
        super().__setattr__("get_save_audio_name",   source_module.get_save_audio_name)
        super().__setattr__("get_card_audio_name",   source_module.get_card_audio_name)
        super().__setattr__("process_card",          source_module.process_card)


class DeckSavingFormatContainer(PluginContainer):
    save: Callable[[SavedDeck], None]

    def __init__(self, source_module: DeckSavingFormatInterface):
        super().__setattr__("save", source_module.save)


class LocalAudioGetterContainer(PluginContainer):
    get_local_audio_path: Callable[[str, dict], str]

    def __init__(self, source_module: LocalAudioGetterInterface):
        super().__setattr__("get_local_audio_path", source_module.get_local_audio_path)
