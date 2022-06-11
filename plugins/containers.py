from dataclasses import dataclass
from typing import Callable

from parsers.return_types import SentenceGenerator, ImageGenerator
from plugins.interfaces import CardProcessorInterface
from plugins.interfaces import DeckSavingFormatInterface
from plugins.interfaces import ImageParserInterface
from plugins.interfaces import LocalAudioGetterInterface
from plugins.interfaces import LocalWordParserInterface
from plugins.interfaces import WebSentenceParserInterface
from plugins.interfaces import WebWordParserInterface
from utils.cards import CardStatus
from utils.cards import SavedDeck


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False)
class _PluginContainer:
    name: str
    
    def __init__(self, name: str):
        super().__setattr__("name", name)


class WebWordParserContainer(_PluginContainer):
    define: Callable[[str], list[(str, dict)]]
    translate: Callable[[str, dict], dict]

    def __init__(self, name: str, source_module: WebWordParserInterface):
        super(WebWordParserContainer, self).__init__(name)
        super().__setattr__("define", source_module.define)
        super().__setattr__("translate", source_module.translate)


class LocalWordParserContainer(_PluginContainer):
    local_dict_name: str
    translate: Callable[[str], dict]

    def __init__(self, name: str, source_module: LocalWordParserInterface):
        super(LocalWordParserContainer, self).__init__(name)
        super().__setattr__("local_dict_name", source_module.DICTIONARY_PATH)
        super().__setattr__("translate", source_module.translate)


class WebSentenceParserContainer(_PluginContainer):
    get_sentence_batch: Callable[[str, int], SentenceGenerator]

    def __init__(self, name: str, source_module: WebSentenceParserInterface):
        super(WebSentenceParserContainer, self).__init__(name)
        super().__setattr__("get_sentence_batch", source_module.get_sentence_batch)


class ImageParserContainer(_PluginContainer):
    get_image_links: Callable[[str], ImageGenerator]

    def __init__(self, name: str, source_module: ImageParserInterface):
        super(ImageParserContainer, self).__init__(name)
        super().__setattr__("get_image_links", source_module.get_image_links)


class CardProcessorContainer(_PluginContainer):
    get_save_image_name: Callable[[str, str, dict], str]
    get_card_image_name: Callable[[str], str]
    get_save_audio_name: Callable[[str, str, str, dict], str]
    get_card_audio_name: Callable[[str], str]
    process_card:        Callable[[dict], None]

    def __init__(self, name: str, source_module: CardProcessorInterface):
        super(CardProcessorContainer, self).__init__(name)
        super().__setattr__("get_save_image_name", source_module.get_save_image_name)
        super().__setattr__("get_card_image_name", source_module.get_card_image_name)
        super().__setattr__("get_save_audio_name", source_module.get_save_audio_name)
        super().__setattr__("get_card_audio_name", source_module.get_card_audio_name)
        super().__setattr__("process_card",        source_module.process_card)


class DeckSavingFormatContainer(_PluginContainer):
    save: Callable[[SavedDeck, CardStatus, str, Callable[[str], str], Callable[[str], str]], None]

    def __init__(self, name: str, source_module: DeckSavingFormatInterface):
        super(DeckSavingFormatContainer, self).__init__(name)
        super().__setattr__("save", source_module.save)


class LocalAudioGetterContainer(_PluginContainer):
    get_local_audios: Callable[[str, dict], str]

    def __init__(self, name: str, source_module: LocalAudioGetterInterface):
        super(LocalAudioGetterContainer, self).__init__(name)
        super().__setattr__("get_local_audios", source_module.get_local_audios)
