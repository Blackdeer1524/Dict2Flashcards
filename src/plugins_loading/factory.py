import importlib
import os.path
import pkgutil
from collections import Counter
from dataclasses import dataclass
from types import ModuleType
from typing import (Callable, ClassVar, Generator, Generic, Iterable, Optional,
                    Type, TypeVar, Union, TypedDict)

from .. import plugins
from ..consts.parser_types import ParserType, TypedParserName
from ..consts.paths import *
from ..consts import CardFormat, TypedParserName

from ..plugins_management.config_management import LoadableConfig
from .containers import (CardProcessorContainer, DeckSavingFormatContainer,
                         ImageParserContainer, LanguagePackageContainer,
                         LocalAudioGetterContainer, LocalWordParserContainer,
                         ThemeContainer, WebAudioGetterContainer,
                         WebSentenceParserContainer, WebWordParserContainer)
from .exceptions import LoaderError, UnknownPluginName
from .chaining import CHAIN_INFO_T, CardGeneratorsChain, ChainOfGenerators, SentenceParsersChain, WrappedBatchGeneratorProtocol
from ..app_utils.parser_interfaces import CardGeneratorProtocol, AudioGeneratorProtocol, ImageGeneratorProtocol, SentenceGeneratorProtocol
from ..app_utils.plugin_wrappers import WebCardGenerator, LocalCardGenerator, BatchGeneratorWrapper

def parse_namespace(namespace, postfix: str = "") -> dict:
    def iter_namespace(ns_pkg):
        # Specifying the second argument (prefix) to iter_modules makes the
        # returned name an absolute name instead of a relative one. This allows
        # import_module to work without having to do additional modification to
        # the name.
        return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

    res = {}
    for finder, name, ispkg in iter_namespace(namespace):
        parser_trunc_name = name.split(sep=".")[-1]
        res[parser_trunc_name] = importlib.import_module(name + postfix)
    return res


PluginContainer = TypeVar("PluginContainer")

@dataclass(slots=True, init=False, frozen=True)
class PluginLoader(Generic[PluginContainer]):
    plugin_type: str
    _loaded_plugin_data: dict[str, PluginContainer]
    not_loaded: tuple[str]

    _already_initialized: ClassVar[set[str]] = set()

    def __init__(self,
                 plugin_type: str,
                 module: ModuleType,
                 configurable: bool,
                 container_type: Type[PluginContainer],
                 error_callback: Callable[[Exception, str, str], None] = lambda *_: None):
        if (module_name := module.__name__) in PluginLoader._already_initialized:
            raise LoaderError(f"{module_name} loader was created earlier!")
        PluginLoader._already_initialized.add(module_name)
        object.__setattr__(self, "plugin_type", plugin_type)

        _loaded_plugin_data = {}
        not_loaded = []
        namespace_parsed_results = parse_namespace(module, postfix=".main") if configurable else parse_namespace(module)
        for name, module in namespace_parsed_results.items():
            try:
                _loaded_plugin_data[name] = container_type(name, module)  # type: ignore [call-arg]
            except Exception as e:
                error_callback(e, plugin_type, name)
                not_loaded.append(name)
        object.__setattr__(self, "_loaded_plugin_data", _loaded_plugin_data)
        object.__setattr__(self, "not_loaded", tuple(not_loaded))

    @property
    def loaded(self):
        return tuple(self._loaded_plugin_data)

    def get(self, name: str) -> PluginContainer:
        if (value := self._loaded_plugin_data.get(name)) is not None:
            return value
        raise UnknownPluginName(f"Unknown {self.plugin_type}: {name}")


@dataclass(slots=True, init=False, frozen=True, repr=False)
class PluginFactory:
    _is_initialized:     ClassVar[bool] = False

    language_packages:   PluginLoader[LanguagePackageContainer]
    themes:              PluginLoader[ThemeContainer]
    web_word_parsers:    PluginLoader[WebWordParserContainer]
    local_word_parsers:  PluginLoader[LocalWordParserContainer]
    web_sent_parsers:    PluginLoader[WebSentenceParserContainer]
    web_image_parsers:   PluginLoader[ImageParserContainer]
    local_audio_getters: PluginLoader[LocalAudioGetterContainer]
    web_audio_getters:   PluginLoader[WebAudioGetterContainer]
    card_processors:     PluginLoader[CardProcessorContainer]
    deck_saving_formats: PluginLoader[DeckSavingFormatContainer]

    def __init__(self):
        if PluginFactory._is_initialized:
            raise LoaderError(f"{self.__class__.__name__} already exists!")
        PluginFactory._is_initialized = True

        object.__setattr__(self, "language_packages",   PluginLoader(plugin_type="language package",
                                                                     module=plugins.language_packages,
                                                                     configurable=False,
                                                                     container_type=LanguagePackageContainer))
        object.__setattr__(self, "themes",              PluginLoader(plugin_type="theme",
                                                                     module=plugins.themes,
                                                                     configurable=False,
                                                                     container_type=ThemeContainer))
        object.__setattr__(self, "web_word_parsers",    PluginLoader(plugin_type="web word parser",
                                                                     module=plugins.parsers.word.web,
                                                                     configurable=True,
                                                                     container_type=WebWordParserContainer))
        object.__setattr__(self, "local_word_parsers",  PluginLoader(plugin_type="local word parser",
                                                                     module=plugins.parsers.word.local,
                                                                     configurable=True,
                                                                     container_type=LocalWordParserContainer))
        object.__setattr__(self, "web_sent_parsers",    PluginLoader(plugin_type="web sentence parser",
                                                                     module=plugins.parsers.sentence,
                                                                     configurable=True,
                                                                     container_type=WebSentenceParserContainer))
        object.__setattr__(self, "web_image_parsers",   PluginLoader(plugin_type="web image parser",
                                                                     module=plugins.parsers.image,
                                                                     configurable=True,
                                                                     container_type=ImageParserContainer))
        object.__setattr__(self, "card_processors",     PluginLoader(plugin_type="card processor",
                                                                     module=plugins.saving.card_processors,
                                                                     configurable=False,
                                                                     container_type=CardProcessorContainer))
        object.__setattr__(self, "deck_saving_formats", PluginLoader(plugin_type="deck plugins.saving format",
                                                                     module=plugins.saving.format_processors,
                                                                     configurable=False,
                                                                     container_type=DeckSavingFormatContainer))
        object.__setattr__(self, "local_audio_getters", PluginLoader(plugin_type="local audio getter",
                                                                     module=plugins.parsers.audio.local,
                                                                     configurable=True,
                                                                     container_type=LocalAudioGetterContainer))
        object.__setattr__(self, "web_audio_getters",   PluginLoader(plugin_type="web audio getter",
                                                                     module=plugins.parsers.audio.web,
                                                                     configurable=True,
                                                                     container_type=WebAudioGetterContainer))

    def get_language_package(self, name: str) -> LanguagePackageContainer:
        if (lang_pack := self.language_packages.get(name)) is None:
            raise UnknownPluginName(f"Unknown language package: {name}")
        return lang_pack

    def get_theme(self, name: str) -> ThemeContainer:
        if (theme := self.themes.get(name)) is None:
            raise UnknownPluginName(f"Unknown theme: {name}")
        return theme

    def get_card_generator(
            self,
            card_generator_info: TypedParserName,
            chain_data: CHAIN_INFO_T) -> CardGeneratorProtocol:
        if card_generator_info.parser_t == ParserType.web:
            if (web_parser := self.web_word_parsers.get(card_generator_info.name)) is None:
                raise UnknownPluginName(f"Unknown web word parser: {card_generator_info.name}")
            return WebCardGenerator(name=web_parser.name,
                                    word_definition_function=web_parser.define,
                                    config=web_parser.config,
                                    scheme_docs=web_parser.scheme_docs)
        elif card_generator_info.parser_t == ParserType.local:
            if (local_parser := self.local_word_parsers.get(card_generator_info.name)) is None:
                raise UnknownPluginName(f"Unknown local word parser: {card_generator_info.name}")
            return LocalCardGenerator(name=local_parser.name,
                                    local_dict_path=os.path.join(LOCAL_DICTIONARIES_DIR,
                                                                f"{local_parser.local_dict_name}.json"),
                                    word_definition_function=local_parser.define,
                                    config=local_parser.config,
                                    scheme_docs=local_parser.scheme_docs)
        elif card_generator_info.parser_t == ParserType.chain:
            return CardGeneratorsChain(card_generator_getter=self.get_card_generator,
                                       chain_name=card_generator_info.name,
                                       chain_data=chain_data)
        raise ValueError(f"Unknown card generator type: {card_generator_info.parser_t}")

    def get_sentence_parser(
            self,
            sentence_parser_info: TypedParserName,
            chain_data: CHAIN_INFO_T) -> WrappedBatchGeneratorProtocol:
        if sentence_parser_info.parser_t == ParserType.web:
            if (gen := self.web_sent_parsers.get(sentence_parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown sentence parser: {sentence_parser_info.name}")
            return BatchGeneratorWrapper(config=gen.config,
                                         generator_initializer=gen.get,
                                         parser_info=sentence_parser_info)
        elif sentence_parser_info.parser_t == ParserType.local:
            raise NotImplementedError("Local sentence parsers are not implemented")
        elif sentence_parser_info.parser_t == ParserType.chain:
            return SentenceParsersChain(generator_getter=self.get_sentence_parser,
                                        chain_name=sentence_parser_info.name,
                                        chain_data=chain_data)
        raise ValueError(f"Unknown sentence parser type: {sentence_parser_info.parser_t}")

    def get_image_parser(
            self,
            image_parser_info: TypedParserName,
            chain_data: CHAIN_INFO_T) -> ImageGeneratorProtocol:
        if image_parser_info.parser_t == ParserType.web:
            if (gen := self.web_image_parsers.get(image_parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown image parser: {image_parser_info.name}")
            return BatchGeneratorWrapper(parser_info=image_parser_info,
                                         config=gen.config,
                                         generator_initializer=gen.get)
        elif image_parser_info.parser_t == ParserType.local:
            raise NotImplementedError("Local image parsers are not implemented")
        elif image_parser_info.parser_t == ParserType.chain:
            return ChainOfGenerators(generator_getter=self.get_image_parser,
                                     chain_name=image_parser_info.name,
                                     chain_data=chain_data)
        raise ValueError(f"Unknown sentence parser type: {image_parser_info.parser_t}")

    def get_audio_getter(
            self,
            audio_getter_info: TypedParserName,
            chain_data: dict[str, str | list[str]] | None = None) -> Union[LocalAudioGetterContainer,
                                                                           WebAudioGetterContainer,
                                                                           "AudioGettersChain"]:
        if getter_type == ParserType.web:
            if (web_getter := self.web_audio_getters.get(name)) is None:
                raise UnknownPluginName(f"Unknown web audio getter: {name}")
            return web_getter
        elif getter_type == ParserType.local:
            if (local_getter := self.local_audio_getters.get(name)) is None:
                raise UnknownPluginName(f"Unknown local audio getter: {name}")
            return local_getter
        elif getter_type == ParserType.chain:
            if chain_data is None:
                raise ValueError("Chain audio getter was requested but no chain data was given")
            return self.AudioGettersChain(
                loaded_plugins=self,
                name=name,
                chain_data=chain_data)
        raise ValueError(f"Unknown card generator type: {getter_type}")

    def get_card_processor(self, name: str) -> CardProcessorContainer:
        if (proc := self.card_processors.get(name)) is None:
            raise UnknownPluginName(f"Unknown card processor: {name}")
        return proc
    
    def get_deck_saving_formats(self, name: str) -> DeckSavingFormatContainer:
        if (saving_format := self.deck_saving_formats.get(name)) is None:
            raise UnknownPluginName(f"Unknown deck plugins.saving format: {name}")
        return saving_format


loaded_plugins = PluginFactory()
