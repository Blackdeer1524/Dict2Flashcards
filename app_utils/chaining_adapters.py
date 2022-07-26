from typing import Optional, Callable

from app_utils.cards import Card, CardGenerator
from app_utils.cards import DataSourceType
from consts.paths import *
from plugins_loading.factory import loaded_plugins
from plugins_management.config_management import LoadableConfig
from plugins_management.parsers_return_types import ImageGenerator, SentenceGenerator, AudioData
from consts.card_fields import FIELDS
from collections import Counter
import re
from typing import Iterable


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
    _MULTIPLE_NAMES_POSTFIX_REGEX = re.compile(r".*\[\d+]$")

    def __init__(self,
                 config_dir: str,
                 config_name: str,
                 name_config_pairs: list[tuple[str, LoadableConfig]]):
        seen_config_ids = set()
        docs_list = []
        validation_scheme = {}
        self.enum_name2config = {}
        for enum_name, (name, config) in zip(get_enumerated_names([item[0] for item in name_config_pairs]),
                                             name_config_pairs):
            self.enum_name2config[enum_name] = config
            validation_scheme[enum_name] = config.validation_scheme
            if id(config) not in seen_config_ids:
                docs_list.append("{}:\n{}".format(name, config.docs.replace('\n', '\n |\t')))
                seen_config_ids.add(id(config))
            config.save()

        docs = "\n".join(docs_list)
        super(ChainConfig, self).__init__(validation_scheme=validation_scheme,  # type: ignore
                                          docs=docs,
                                          config_location=config_dir,
                                          _config_file_name=config_name)
        self.load()

    def update_children_configs(self):
        for enum_name, config in self.enum_name2config.items():
            config.data = self[enum_name]

    def update_config(self, enum_name: str):
        if re.match(self._MULTIPLE_NAMES_POSTFIX_REGEX, enum_name):
            self.enum_name2config[enum_name].data = self[enum_name]

    def load(self) -> Optional[LoadableConfig.SchemeCheckResults]:
        errors = super(ChainConfig, self).load()
        self.update_children_configs()
        return errors

    def save(self):
        self.update_children_configs()
        super(ChainConfig, self).save()


class CardGeneratorsChain:
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name

        self.enum_name2generator: dict[str, CardGenerator] = {}
        self.card_generators: list[CardGenerator] = []

        parser_configs = []
        scheme_docs_list = []
        for parser_name, enum_parser_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
            if parser_name.startswith(f"[{DataSourceType.WEB}]"):
                generator = loaded_plugins.get_web_card_generator(parser_name[3 + len(DataSourceType.WEB):])
            elif parser_name.startswith(f"[{DataSourceType.LOCAL}]"):
                generator = loaded_plugins.get_local_card_generator(parser_name[3 + len(DataSourceType.LOCAL):])
            else:
                raise NotImplementedError(f"Word parser of unknown type: {parser_name}")

            self.enum_name2generator[enum_parser_name] = generator
            parser_configs.append(generator.config)
            scheme_docs_list.append("{}\n{}".format(parser_name,
                                                    self.card_generators[-1].scheme_docs.replace("\n", "\n |\t")))
        self.config = ChainConfig(config_dir=CHAIN_DATA_DIR / "configs" / "word_parsers",
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config in
                                                     zip(chain_data["chain"], parser_configs)])
        self.scheme_docs = "\n".join(scheme_docs_list)

    def get(self,
            query: str,
            word_filter: Callable[[str], bool],
            additional_filter: Callable[[Card], bool] = None) -> list[Card]:
        current_result = []
        for generator in self.card_generators:
            if (current_result := generator.get(query, word_filter, additional_filter)):
                break
        return current_result


class SentenceParsersChain:
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name
        self.enum_name2get_sentence_batch_functions: dict[str, Callable[[str, int], SentenceGenerator]] = {}
        parser_configs = []
        for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
            plugin_container = loaded_plugins.get_sentence_parser(parser_name)
            self.enum_name2get_sentence_batch_functions[enum_name] = plugin_container.get_sentence_batch
            parser_configs.append(plugin_container.config)
        self.config = ChainConfig(config_dir=CHAIN_DATA_DIR / "configs" / "sentence_parsers",
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config in
                                                     zip(chain_data["chain"], parser_configs)])

    def get_sentence_batch(self, word: str, size: int) -> SentenceGenerator:
        yielded_once = False
        for enum_name, get_sentence_batch_f in self.enum_name2get_sentence_batch_functions.items():
            self.config.update_config(enum_name)
            sent_generator = get_sentence_batch_f(word, size)
            for sentence_list, error_message in sent_generator:
                if not sentence_list:
                    yielded_once = False
                    break
                yield sentence_list, error_message
                yielded_once = True
        if not yielded_once:
            return [], ""


class ImageParsersChain:
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name
        self.enum_name2url_getting_functions: dict[str, Callable[[str], ImageGenerator]] = {}
        parser_configs = []
        for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
            parser = loaded_plugins.get_image_parser(parser_name)
            self.enum_name2url_getting_functions[enum_name] = parser.get_image_links
            parser_configs.append(parser.config)

        self.config = ChainConfig(config_dir=CHAIN_DATA_DIR / "configs" / "image_parsers",
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config in
                                                     zip(chain_data["chain"], parser_configs)])

    def get_image_links(self, word: str) -> ImageGenerator:
        batch_size = yield
        for enum_name, url_getting_function in self.enum_name2url_getting_functions.items():
            self.config.update_config(enum_name)
            url_generator = url_getting_function(word)
            try:
                next(url_generator)
            except StopIteration:
                continue
            while True:
                try:
                    batch_size = yield url_generator.send(batch_size)
                except StopIteration:
                    break
        return [], ""


class AudioGettersChain:
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name
        self.enum_name2parsers_data: dict[str, tuple[str, Callable[[str, dict], AudioData] | None]] = {}
        names = []
        parser_configs = []
        for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
            if parser_name == "default":
                parser_type = "default"
                self.enum_name2parsers_data[enum_name] = (parser_type, None)
                continue

            names.append(parser_name)
            if parser_name.startswith(f"[{DataSourceType.WEB}]"):
                parser_type = DataSourceType.WEB
                getter = loaded_plugins.get_web_audio_getter(parser_name[3 + len(DataSourceType.WEB):])
            elif parser_name.startswith(f"[{DataSourceType.LOCAL}]"):
                parser_type = DataSourceType.LOCAL
                getter = loaded_plugins.get_local_audio_getter(parser_name[3 + len(DataSourceType.LOCAL):])
            else:
                raise NotImplementedError(f"Audio getter of unknown type: {parser_name}")
            self.enum_name2parsers_data[enum_name] = (parser_type, getter.get_audios)
            parser_configs.append(getter.config)

        self.config = ChainConfig(config_dir=CHAIN_DATA_DIR / "configs" / "image_parsers",
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config
                                                     in zip(names, parser_configs)])

    def get_audios(self, word: str, card_data: dict) -> tuple[str, AudioData]:
        source = []
        additional_info = []
        error_message = ""
        parser_type = DataSourceType.WEB  # arbitrary type
        for enum_name, (parser_type, audio_getting_function) in self.enum_name2parsers_data.items():
            if parser_type == "default":
                source = additional_info = card_data.get(FIELDS.audio_links, [])
                error_message = ""
            else:
                self.config.update_config(enum_name)
                (source, additional_info), error_message = audio_getting_function(word, card_data)
            if source:
                break
        return parser_type, ((source, additional_info), error_message)
