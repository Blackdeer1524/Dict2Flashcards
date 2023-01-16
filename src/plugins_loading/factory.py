import importlib
import os.path
import pkgutil
from collections import Counter
from dataclasses import dataclass
from types import ModuleType
from typing import (Callable, ClassVar, Generator, Generic, Iterable, Optional,
                    Type, TypeVar, Union)

from .. import plugins
from ..app_utils.cards import (Card, CardGenerator, LocalCardGenerator,
                               WebCardGenerator)
from ..consts.parser_types import ParserTypes
from ..consts.paths import *
from ..consts import CardFormat

from ..plugins_management.config_management import LoadableConfig
from ..plugins_management.parsers_return_types import (AudioData,
                                                       AudioGenerator,
                                                       ImageGenerator,
                                                       SentenceGenerator)
from .containers import (CardProcessorContainer, DeckSavingFormatContainer,
                         ImageParserContainer, LanguagePackageContainer,
                         LocalAudioGetterContainer, LocalWordParserContainer,
                         ThemeContainer, WebAudioGetterContainer,
                         WebSentenceParserContainer, WebWordParserContainer)
from .exceptions import LoaderError, UnknownPluginName



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


def get_enumerated_names(names: Iterable[str]) -> list[str]:
    seen_names_count = Counter(names)
    seen_so_far = {key: value for key, value in seen_names_count.items()}
    enum_names = []
    for name in names:
        if seen_names_count[name] == 1:
            enum_names.append(name)
        else:
            seen_so_far[name] -= 1
            enum_names.append(f"{name} [{seen_names_count[name] - seen_so_far[name]}]")
    return enum_names


class ChainConfig(LoadableConfig):
    def __init__(self,
                 config_dir: str,
                 config_name: str,
                 name_config_pairs: list[tuple[str, LoadableConfig]],
                 ):
        validation_scheme = {}
        docs_list = []

        validation_scheme["query_type"] = ("all", [str], ["first_found", "all"])
        validation_scheme["error_verbosity"] = ("silent", [str], ["silent", "if_found", "all"])
        docs_list.append("""
query_type:
    How to get data from sources
    first_found: get only first available
    all: get data from all sources

error_verbosity:
    silent: doesn't save any errors
    if_found: saves errors ONLY IF found something
    all: saves all errors
""")

        validation_scheme["parsers"] = {}
        seen_config_ids = set()
        self.enum_name2config = {}
        for enum_name, (name, config) in zip(get_enumerated_names([item[0] for item in name_config_pairs]),
                                             name_config_pairs):
            self.enum_name2config[enum_name] = config
            validation_scheme["parsers"][enum_name] = config.validation_scheme
            if id(config) not in seen_config_ids:
                docs_list.append("{}:\n{}".format(name, config.docs.replace("\n", "\n" + " " * 4)))
                seen_config_ids.add(id(config))
            config.save()

        docs = "\n\n".join(docs_list)
        super(ChainConfig, self).__init__(validation_scheme=validation_scheme,  # type: ignore
                                          docs=docs,
                                          config_location=config_dir,
                                          _config_file_name=config_name)
        self.load()

    def update_children_configs(self):
        for enum_name, config in self.enum_name2config.items():
            config.data = self["parsers"][enum_name]

    def update_config(self, enum_name: str):
        self.enum_name2config[enum_name].data = self["parsers"][enum_name]

    def load(self) -> Optional[LoadableConfig.SchemeCheckResults]:
        errors = super(ChainConfig, self).load()
        self.update_children_configs()
        return errors

    def save(self):
        self.update_children_configs()
        super(ChainConfig, self).save()


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

    class CardGeneratorsChain:
        def __init__(chain_self,
                     loaded_plugins: "PluginFactory",
                     name: str,
                     chain_data: dict[str, str | list[str]]):
            chain_self.loaded_plugins = loaded_plugins
            chain_self.name = name
            chain_self.enum_name2generator: dict[str, CardGenerator] = {}

            parser_configs = []
            scheme_docs_list = []
            for parser_name, enum_parser_name in zip(chain_data["chain"],
                                                     get_enumerated_names(chain_data["chain"])):
                if parser_name.startswith(ParserTypes.web.prefix()):
                    generator = chain_self.loaded_plugins.get_card_generator(
                        name=parser_name[len(ParserTypes.web.prefix()) + 1:],
                        gen_type=ParserTypes.web,
                        chain_data=None)
                elif parser_name.startswith(ParserTypes.local.prefix()):
                    generator = chain_self.loaded_plugins.get_card_generator(
                        name=parser_name[len(ParserTypes.local.prefix()) + 1:],
                        gen_type=ParserTypes.local,
                        chain_data=None)
                else:
                    raise NotImplementedError(f"Word parser of unknown type: {parser_name}")

                chain_self.enum_name2generator[enum_parser_name] = generator
                parser_configs.append(generator.config)
                scheme_docs_list.append("{}\n{}".format(parser_name, generator.scheme_docs.replace("\n", "\n |\t")))

            chain_self.config = ChainConfig(config_dir=CHAIN_WORD_PARSERS_DATA_DIR,
                                            config_name=chain_data["config_name"],
                                            name_config_pairs=[(parser_name, config) for parser_name, config in
                                                               zip(chain_data["chain"], parser_configs)])
            chain_self.scheme_docs = "\n".join(scheme_docs_list)

        def get(chain_self,
                query: str,
                additional_filter: Callable[[CardFormat], bool] | None = None) -> tuple[list[Card], str]:
            current_result = []
            errors = []
            for enum_name, generator in chain_self.enum_name2generator.items():
                chain_self.config.update_config(enum_name)
                cards, error_message = generator.get(query, additional_filter)
                if chain_self.config["error_verbosity"] == "silent":
                    error_message = ""

                if error_message and \
                        (chain_self.config["error_verbosity"] == "all" or cards and chain_self.config[
                            "error_verbosity"] == "if_found"):
                    errors.append("\n  ".join((enum_name, error_message)))

                current_result.extend(cards)
                if chain_self.config["query_type"] == "first_found" and current_result:
                    break
            return current_result, "\n\n".join(errors)

    class SentenceParsersChain:
        def __init__(chain_self,
                     loaded_plugins: "PluginFactory",
                     name: str,
                     chain_data: dict[str, str | list[str]]):
            chain_self.loaded_plugins = loaded_plugins
            chain_self.name = name
            chain_self.enum_name2get_sentences_functions: dict[str, Callable[[str, dict], SentenceGenerator]] = {}
            parser_configs = []
            for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
                plugin_container = chain_self.loaded_plugins.get_sentence_parser(
                    name=parser_name[len(ParserTypes.web.prefix()) + 1:],
                    parser_type=ParserTypes.web,
                    chain_data=None)
                chain_self.enum_name2get_sentences_functions[enum_name] = plugin_container.get
                parser_configs.append(plugin_container.config)
            chain_self.config = ChainConfig(config_dir=CHAIN_SENTENCE_PARSERS_DATA_DIR,
                                            config_name=chain_data["config_name"],
                                            name_config_pairs=[(parser_name, config) for parser_name, config in
                                                               zip(chain_data["chain"], parser_configs)])

        def get(chain_self, word: str, card_data: dict) -> Generator[tuple[str, SentenceGenerator],
                                                                     int,
                                                                     tuple[str, SentenceGenerator]]:
            batch_size = yield
            results = []
            yielded_once = False
            for enum_name, get_sentences_generator in chain_self.enum_name2get_sentences_functions.items():
                chain_self.config.update_config(enum_name)

                sent_generator = get_sentences_generator(word, card_data)
                try:
                    next(sent_generator)
                except StopIteration as e:
                    _, error_message = e.value
                    if chain_self.config["error_verbosity"] == "silent":
                        error_message = ""

                    if error_message and chain_self.config["error_verbosity"] == "all":
                        results.append((enum_name, ([], error_message)))
                    continue

                while True:
                    try:
                        sentences, error_message = sent_generator.send(batch_size)
                        if chain_self.config["error_verbosity"] == "silent":
                            error_message = ""

                        if sentences or chain_self.config["error_verbosity"] == "all" and error_message:
                            results.append((enum_name,
                                            (sentences, error_message)))
                            batch_size -= len(sentences)
                            if batch_size <= 0:
                                batch_size = yield results
                                yielded_once = True
                                results = []

                    except StopIteration as e:
                        sentences, error_message = e.value
                        if chain_self.config["error_verbosity"] == "silent":
                            error_message = ""

                        if sentences or chain_self.config["error_verbosity"] == "all" and error_message:
                            results.append((enum_name,
                                            (sentences, error_message)))
                            batch_size -= len(sentences)
                            if batch_size <= 0:
                                batch_size = yield results
                                yielded_once = True
                                results = []
                        break

                if chain_self.config["query_type"] == "first_found" and yielded_once:
                    break
            return results

    class ImageParsersChain:
        def __init__(chain_self,
                     loaded_plugins: "PluginFactory",
                     name: str,
                     chain_data: dict[str, str | list[str]]):
            chain_self.loaded_plugins = loaded_plugins
            chain_self.name = name
            chain_self.enum_name2url_getting_functions: dict[str, Callable[[str], ImageGenerator]] = {}
            parser_configs = []
            for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
                parser = chain_self.loaded_plugins.get_image_parser(
                    name=parser_name[len(ParserTypes.web.prefix()) + 1:],
                    parser_type=ParserTypes.web,
                    chain_data=None)
                chain_self.enum_name2url_getting_functions[enum_name] = parser.get
                parser_configs.append(parser.config)

            chain_self.config = ChainConfig(config_dir=CHAIN_IMAGE_PARSERS_DATA_DIR,
                                            config_name=chain_data["config_name"],
                                            name_config_pairs=[(parser_name, config) for parser_name, config in
                                                               zip(chain_data["chain"], parser_configs)])

        def get(chain_self, word: str) -> ImageGenerator:
            batch_size = yield
            for enum_name, url_getting_function in chain_self.enum_name2url_getting_functions.items():
                chain_self.config.update_config(enum_name)
                url_generator = url_getting_function(word)
                try:
                    next(url_generator)
                except StopIteration as e:
                    url_batch, error_message = e.value
                    if url_batch or error_message:
                        yield url_batch, error_message
                    continue

                while True:
                    try:
                        batch_size = yield url_generator.send(batch_size)
                    except StopIteration:
                        break
            return [], ""

    class AudioGettersChain:
        def __init__(chain_self,
                     loaded_plugins: "PluginFactory",
                     name: str,
                     chain_data: dict[str, str | list[str]]):
            chain_self.loaded_plugins = loaded_plugins
            chain_self.name = name
            chain_self.enum_name2parsers_data: dict[
                str, tuple[ParserTypes, Callable[[str, dict], AudioGenerator] | None]] = {}
            parser_configs = []
            for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):

                if parser_name.startswith(ParserTypes.web.prefix()):
                    parser_type = ParserTypes.web
                    getter = chain_self.loaded_plugins\
                                       .get_audio_getter(parser_name[len(ParserTypes.web.prefix()) + 1:],
                                                         ParserTypes.web)
                elif parser_name.startswith(ParserTypes.local.prefix()):
                    parser_type = ParserTypes.local
                    getter = chain_self.loaded_plugins\
                                       .get_audio_getter(parser_name[len(ParserTypes.local.prefix()) + 1:],
                                                         ParserTypes.local)
                else:
                    raise NotImplementedError(f"Audio getter of unknown type: {parser_name}")
                chain_self.enum_name2parsers_data[enum_name] = (parser_type, getter.get)
                parser_configs.append(getter.config)

            chain_self.config = ChainConfig(config_dir=CHAIN_AUDIO_GETTERS_DATA_DIR,
                                            config_name=chain_data["config_name"],  # type: ignore
                                            name_config_pairs=[(parser_name, config) for parser_name, config
                                                               in zip(chain_data["chain"], parser_configs)])

        def get(chain_self, word: str, card_data: dict) -> \
                Generator[list[tuple[tuple[str, str], AudioData]], int, list[tuple[tuple[str, str], AudioData]]]:
            batch_size = yield
            results: list[tuple[tuple[str, ParserTypes], AudioData]] = []
            yielded_once = False
            for enum_name, (parser_type, get_audio_generator) in chain_self.enum_name2parsers_data.items():
                chain_self.config.update_config(enum_name)

                audio_data_generator = get_audio_generator(word, card_data)
                try:
                    next(audio_data_generator)
                except StopIteration as e:
                    _, error_message = e.value
                    if chain_self.config["error_verbosity"] == "silent":
                        error_message = ""

                    if error_message and chain_self.config["error_verbosity"] == "all":
                        results.append(((enum_name, parser_type), (([], []), error_message)))
                    continue

                while True:
                    try:
                        ((audios, additional_info), error_message) = audio_data_generator.send(batch_size)
                        if chain_self.config["error_verbosity"] == "silent":
                            error_message = ""

                        if audios or chain_self.config["error_verbosity"] == "all" and error_message:
                            results.append(((enum_name, parser_type),
                                            ((audios, additional_info), error_message)))
                            batch_size -= len(audios)
                            if batch_size <= 0:
                                batch_size = yield results
                                yielded_once = True
                                results = []

                    except StopIteration as e:
                        ((audios, additional_info), error_message) = e.value
                        if chain_self.config["error_verbosity"] == "silent":
                            error_message = ""

                        if audios or chain_self.config["error_verbosity"] == "all" and error_message:
                            results.append(((enum_name, parser_type),
                                            ((audios, additional_info), error_message)))
                            batch_size -= len(audios)
                            if batch_size <= 0:
                                batch_size = yield results
                                yielded_once = True
                                results = []
                        break

                if chain_self.config["query_type"] == "first_found" and yielded_once:
                    break
            return results

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
            name: str, 
            gen_type: ParserTypes, 
            chain_data: dict[str, str | list[str]] | None = None) -> Union[WebCardGenerator, LocalCardGenerator, "CardGeneratorsChain"]:
        if gen_type == ParserTypes.web:
            if (web_parser := self.web_word_parsers.get(name)) is None:
                raise UnknownPluginName(f"Unknown web word parser: {name}")
            return WebCardGenerator(name=web_parser.name,
                                    word_definition_function=web_parser.define,
                                    config=web_parser.config,
                                    scheme_docs=web_parser.scheme_docs)
        elif gen_type == ParserTypes.local:
            if (local_parser := self.local_word_parsers.get(name)) is None:
                raise UnknownPluginName(f"Unknown local word parser: {name}")
            return LocalCardGenerator(name=local_parser.name,
                                    local_dict_path=os.path.join(LOCAL_DICTIONARIES_DIR,
                                                                f"{local_parser.local_dict_name}.json"),
                                    word_definition_function=local_parser.define,
                                    config=local_parser.config,
                                    scheme_docs=local_parser.scheme_docs)
        elif gen_type == ParserTypes.chain:
            if chain_data is None:
                raise ValueError("Chain card generator was requested but no chain data was given")
            return self.CardGeneratorsChain(
                loaded_plugins=self,
                name=name,
                chain_data=chain_data)
        raise ValueError(f"Unknown card generator type: {gen_type}")

    def get_sentence_parser(
            self,
            name: str,
            parser_type: ParserTypes,
            chain_data: dict[str, str | list[str]] | None = None) -> Union[WebSentenceParserContainer,
                                                                           "SentenceParsersChain"]:
        if parser_type == ParserTypes.web:
            if (gen := self.web_sent_parsers.get(name)) is None:
                raise UnknownPluginName(f"Unknown sentence parser: {name}")
            return gen
        elif parser_type == ParserTypes.local:
            raise NotImplementedError("Local sentence parsers are not implemented")
        elif parser_type == ParserTypes.chain:
            if chain_data is None:
                raise ValueError("Chain sentence parser was requested but no chain data was given")
            return self.SentenceParsersChain(
                name=name,
                loaded_plugins=self,
                chain_data=chain_data)
        raise ValueError(f"Unknown sentence parser type: {parser_type}")

    def get_image_parser(
            self,
            name: str,
            parser_type: ParserTypes,
            chain_data: dict[str, str | list[str]] | None = None) -> Union[ImageParserContainer,
                                                                           "ImageParsersChain"]:
        if parser_type == ParserTypes.web:
            if (gen := self.web_image_parsers.get(name)) is None:
                raise UnknownPluginName(f"Unknown image parser: {name}")
            return gen
        elif parser_type == ParserTypes.local:
            raise NotImplementedError("Local image parsers are not implemented")
        elif parser_type == ParserTypes.chain:
            if chain_data is None:
                raise ValueError("Chain image parser was requested but no chain data was given")
            return self.ImageParsersChain(
                loaded_plugins=self,
                name=name,
                chain_data=chain_data)
        raise ValueError(f"Unknown image parser type: {parser_type}")

    def get_audio_getter(
            self,
            name: str,
            getter_type: ParserTypes,
            chain_data: dict[str, str | list[str]] | None = None) -> Union[LocalAudioGetterContainer,
                                                                           WebAudioGetterContainer,
                                                                           "AudioGettersChain"]:
        if getter_type == ParserTypes.web:
            if (web_getter := self.web_audio_getters.get(name)) is None:
                raise UnknownPluginName(f"Unknown web audio getter: {name}")
            return web_getter
        elif getter_type == ParserTypes.local:
            if (local_getter := self.local_audio_getters.get(name)) is None:
                raise UnknownPluginName(f"Unknown local audio getter: {name}")
            return local_getter
        elif getter_type == ParserTypes.chain:
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
