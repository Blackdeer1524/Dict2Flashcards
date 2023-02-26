import importlib
import os.path
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Callable, ClassVar, Generic, Type, TypeVar

from .. import plugins
from .wrappers import (BatchGeneratorWrapper, CardGeneratorProtocol,
                                         LocalCardGenerator, WebCardGenerator)
from ..consts import TypedParserName
from ..consts.parser_types import ParserType, TypedParserName
from ..consts.paths import (LOCAL_DICTIONARIES_DIR, 
                            CHAIN_AUDIO_GETTERS_DATA_DIR, 
                            CHAIN_IMAGE_PARSERS_DATA_DIR, 
                            CHAIN_SENTENCE_PARSERS_DATA_DIR)
from .chaining import (CHAIN_INFO_T, AudioGettersChain, CardGeneratorsChain,
                       ImageParsersChain, SentenceParsersChain,
                       WrappedBatchGeneratorProtocol)
from .containers import (CardProcessorContainer, DeckSavingFormatContainer,
                         ImageParserContainer, LanguagePackageContainer,
                         LocalAudioGetterContainer, LocalWordParserContainer,
                         ThemeContainer, WebAudioGetterContainer,
                         WebSentenceParserContainer, WebWordParserContainer)
from .exceptions import LoaderError, UnknownPluginName


def parse_namespace(namespace, postfix: str = "") -> dict[str, ModuleType]:
    def iter_namespace(ns_pkg):
        # Specifying the second argument (prefix) to iter_modules makes the
        # returned name an absolute name instead of a relative one. This allows
        # import_module to work without having to do additional modification to
        # the name.
        return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

    res: dict[str, ModuleType] = {}
    for finder, name, ispkg in iter_namespace(namespace):
        parser_trunc_name = name.split(sep=".")[-1]
        res[parser_trunc_name] = importlib.import_module(name + postfix)
    return res


PluginContainer = TypeVar("PluginContainer")

@dataclass(slots=True, init=False, frozen=True)
class PluginLoader(Generic[PluginContainer]):
    plugin_type: str
    _loaded_plugin_data: dict[str, PluginContainer]
    not_loaded: list[str]

    _already_initialized: ClassVar[set[str]] = set()

    def __init__(self,
                 plugin_type: str,
                 module: ModuleType,
                 HasConfigFile: bool,
                 container_type: Type[PluginContainer],
                 error_callback: Callable[[Exception, str, str], None] = lambda *_: None):
        if (module_name := module.__name__) in PluginLoader._already_initialized:
            raise LoaderError(f"{module_name} loader was created earlier!")
        PluginLoader._already_initialized.add(module_name)
        object.__setattr__(self, "plugin_type", plugin_type)

        _loaded_plugin_data = {}
        not_loaded: list[str] = []
        namespace_parsed_results = parse_namespace(module, postfix=".main") if HasConfigFile else parse_namespace(module)
        for name, module in namespace_parsed_results.items():
            try:
                _loaded_plugin_data[name] = container_type(name, module)  # type: ignore [call-arg]
            except Exception as e:
                error_callback(e, plugin_type, name)
                not_loaded.append(name)
        object.__setattr__(self, "_loaded_plugin_data", _loaded_plugin_data)
        object.__setattr__(self, "not_loaded", tuple(not_loaded))

    @property
    def loaded(self) -> list[str]:
        return list(self._loaded_plugin_data.keys())

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
                                                                     HasConfigFile=False,
                                                                     container_type=LanguagePackageContainer))
        object.__setattr__(self, "themes",              PluginLoader(plugin_type="theme",
                                                                     module=plugins.themes,
                                                                     HasConfigFile=False,
                                                                     container_type=ThemeContainer))
        object.__setattr__(self, "web_word_parsers",    PluginLoader(plugin_type="web word parser",
                                                                     module=plugins.parsers.word.web,
                                                                     HasConfigFile=True,
                                                                     container_type=WebWordParserContainer))
        object.__setattr__(self, "local_word_parsers",  PluginLoader(plugin_type="local word parser",
                                                                     module=plugins.parsers.word.local,
                                                                     HasConfigFile=True,
                                                                     container_type=LocalWordParserContainer))
        object.__setattr__(self, "web_sent_parsers",    PluginLoader(plugin_type="web sentence parser",
                                                                     module=plugins.parsers.sentence,
                                                                     HasConfigFile=True,
                                                                     container_type=WebSentenceParserContainer))
        object.__setattr__(self, "web_image_parsers",   PluginLoader(plugin_type="web image parser",
                                                                     module=plugins.parsers.image,
                                                                     HasConfigFile=True,
                                                                     container_type=ImageParserContainer))
        object.__setattr__(self, "card_processors",     PluginLoader(plugin_type="card processor",
                                                                     module=plugins.saving.card_processors,
                                                                     HasConfigFile=False,
                                                                     container_type=CardProcessorContainer))
        object.__setattr__(self, "deck_saving_formats", PluginLoader(plugin_type="deck saving format",
                                                                     module=plugins.saving.format_processors,
                                                                     HasConfigFile=True,
                                                                     container_type=DeckSavingFormatContainer))
        object.__setattr__(self, "local_audio_getters", PluginLoader(plugin_type="local audio getter",
                                                                     module=plugins.parsers.audio.local,
                                                                     HasConfigFile=True,
                                                                     container_type=LocalAudioGetterContainer))
        object.__setattr__(self, "web_audio_getters",   PluginLoader(plugin_type="web audio getter",
                                                                     module=plugins.parsers.audio.web,
                                                                     HasConfigFile=True,
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
            parser_info: TypedParserName,
            chain_data: CHAIN_INFO_T) -> CardGeneratorProtocol:
        if parser_info.parser_t == ParserType.web:
            if (web_parser := self.web_word_parsers.get(parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown web word parser: {parser_info.name}")
            return WebCardGenerator(name=web_parser.name,
                                    word_definition_function=web_parser.define,
                                    config=web_parser.config,
                                    scheme_docs=web_parser.scheme_docs)
        elif parser_info.parser_t == ParserType.local:
            if (local_parser := self.local_word_parsers.get(parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown local word parser: {parser_info.name}")
            return LocalCardGenerator(name=local_parser.name,
                                      local_dict_path=os.path.join(LOCAL_DICTIONARIES_DIR, 
                                                                   f"{local_parser.local_dict_name}.json"),
                                      word_definition_function=local_parser.define,
                                      config=local_parser.config,
                                      scheme_docs=local_parser.scheme_docs)
        elif parser_info.parser_t == ParserType.chain:
            return CardGeneratorsChain(card_generator_getter=self.get_card_generator,
                                       chain_name=parser_info.name,
                                       chain_data=chain_data)
        raise ValueError(f"Unknown card generator type: {parser_info.parser_t}")

    def get_sentence_parser(
            self,
            parser_info: TypedParserName,
            chain_data: CHAIN_INFO_T) -> WrappedBatchGeneratorProtocol[list[str]]:
        if parser_info.parser_t == ParserType.web:
            if (gen := self.web_sent_parsers.get(parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown sentence parser: {parser_info.name}")
            return BatchGeneratorWrapper(config=gen.config,
                                         generator_initializer=gen.get,
                                         parser_name=parser_info.name,
                                         parser_type=ParserType.web)
        elif parser_info.parser_t == ParserType.local:
            raise NotImplementedError("Local sentence parsers are not implemented")
        elif parser_info.parser_t == ParserType.chain:
            return SentenceParsersChain(generator_getter=self.get_sentence_parser,
                                        config_dir=str(CHAIN_SENTENCE_PARSERS_DATA_DIR),
                                        chain_name=parser_info.name,
                                        chain_data=chain_data)
        raise ValueError(f"Unknown sentence parser type: {parser_info.parser_t}")

    def get_image_parser(
            self,
            parser_info: TypedParserName,
            chain_data: CHAIN_INFO_T) -> WrappedBatchGeneratorProtocol[list[str]]:
        if parser_info.parser_t == ParserType.web:
            if (gen := self.web_image_parsers.get(parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown image parser: {parser_info.name}")
            return BatchGeneratorWrapper(config=gen.config,
                                         generator_initializer=gen.get,
                                         parser_name=parser_info.name,
                                         parser_type=ParserType.web)
        elif parser_info.parser_t == ParserType.local:
            raise NotImplementedError("Local image parsers are not implemented")
        elif parser_info.parser_t == ParserType.chain:
            return ImageParsersChain(generator_getter=self.get_image_parser,
                                     config_dir=str(CHAIN_IMAGE_PARSERS_DATA_DIR),
                                     chain_name=parser_info.name,
                                     chain_data=chain_data)
        raise ValueError(f"Unknown image parser type: {parser_info.parser_t}")

    def get_audio_getter(
            self,
            parser_info: TypedParserName,
            chain_data: CHAIN_INFO_T) -> WrappedBatchGeneratorProtocol[list[tuple[str, str]]]:
        if parser_info.parser_t == ParserType.web:
            if (web_gen := self.web_audio_getters.get(parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown web audio getter: {parser_info.name}")
            return BatchGeneratorWrapper(config=web_gen.config,
                                         generator_initializer=web_gen.get,
                                         parser_name=parser_info.name,
                                         parser_type=ParserType.web)
        elif parser_info.parser_t == ParserType.local:
            if (local_gen := self.local_audio_getters.get(parser_info.name)) is None:
                raise UnknownPluginName(f"Unknown local audio getter: {parser_info.name}")
            return BatchGeneratorWrapper(config=local_gen.config,
                                         generator_initializer=local_gen.get,
                                         parser_name=parser_info.name,
                                         parser_type=ParserType.local)
        elif parser_info.parser_t == ParserType.chain:
            return AudioGettersChain(generator_getter=self.get_audio_getter,
                                     config_dir=str(CHAIN_AUDIO_GETTERS_DATA_DIR),
                                     chain_name=parser_info.name,
                                     chain_data=chain_data)
        raise ValueError(f"Unknown audio getter type: {parser_info.parser_t}")

    def get_card_processor(self, name: str) -> CardProcessorContainer:
        if (proc := self.card_processors.get(name)) is None:
            raise UnknownPluginName(f"Unknown card processor: {name}")
        return proc
    
    def get_deck_saving_formats(self, name: str) -> DeckSavingFormatContainer:
        if (saving_format := self.deck_saving_formats.get(name)) is None:
            raise UnknownPluginName(f"Unknown deck plugins.saving format: {name}")
        return saving_format


loaded_plugins = PluginFactory()
