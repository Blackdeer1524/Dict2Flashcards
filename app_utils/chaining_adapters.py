import copy
from collections import Counter
from typing import Iterable
from typing import Optional, Callable

from app_utils.cards import Card, CardGenerator
from consts import parser_types
from consts.paths import *
from plugins_loading.factory import loaded_plugins
from plugins_management.config_management import LoadableConfig
from plugins_management.parsers_return_types import ImageGenerator, SentenceGenerator, AudioData, AudioGenerator
from typing import Generator


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
                 additional_val_scheme: Optional[dict] = None,
                 additional_docs: str = ""
                 ):
        if additional_val_scheme is None:
            validation_scheme = {}
            docs_list = []
        else:
            validation_scheme = copy.deepcopy(additional_val_scheme)
            docs_list = [additional_docs]

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


class CardGeneratorsChain:
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name
        self.enum_name2generator: dict[str, CardGenerator] = {}

        parser_configs = []
        scheme_docs_list = []
        for parser_name, enum_parser_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
            if parser_name.startswith(f"[{parser_types.WEB}]"):
                generator = loaded_plugins.get_web_card_generator(parser_name[3 + len(parser_types.WEB):])
            elif parser_name.startswith(f"[{parser_types.LOCAL}]"):
                generator = loaded_plugins.get_local_card_generator(parser_name[3 + len(parser_types.LOCAL):])
            else:
                raise NotImplementedError(f"Word parser of unknown type: {parser_name}")

            self.enum_name2generator[enum_parser_name] = generator
            parser_configs.append(generator.config)
            scheme_docs_list.append("{}\n{}".format(parser_name, generator.scheme_docs.replace("\n", "\n |\t")))
        self.config = ChainConfig(config_dir=CHAIN_WORD_PARSERS_DATA_DIR,
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config in
                                                     zip(chain_data["chain"], parser_configs)])
        self.scheme_docs = "\n".join(scheme_docs_list)

    def get(self,
            query: str,
            word_filter: Callable[[str], bool],
            additional_filter: Callable[[Card], bool] = None) -> list[Card]:
        current_result = []
        for enum_name, generator in self.enum_name2generator.items():
            self.config.update_config(enum_name)
            if current_result := generator.get(query, word_filter, additional_filter):
                break
        return current_result


class SentenceParsersChain:
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name
        self.enum_name2get_sentences_functions: dict[str, Callable[[str, dict], SentenceGenerator]] = {}
        parser_configs = []
        for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
            plugin_container = loaded_plugins.get_sentence_parser(parser_name)
            self.enum_name2get_sentences_functions[enum_name] = plugin_container.get
            parser_configs.append(plugin_container.config)
        self.config = ChainConfig(config_dir=CHAIN_SENTENCE_PARSERS_DATA_DIR,
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config in
                                                     zip(chain_data["chain"], parser_configs)])

    def get(self, word: str, card_data: dict) -> SentenceGenerator:
        batch_size = yield
        for enum_name, get_sentences_f in self.enum_name2get_sentences_functions.items():
            self.config.update_config(enum_name)
            sent_generator = get_sentences_f(word, card_data)
            try:
                next(sent_generator)
            except StopIteration as e:
                sentence_list, error_message = e.value
                if sentence_list or error_message:
                    yield sentence_list, error_message
                continue

            while True:
                try:
                    sentence_list, error_message = sent_generator.send(batch_size)
                    if not sentence_list:
                        break
                    batch_size = yield sentence_list, error_message
                except StopIteration:
                    break
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
            self.enum_name2url_getting_functions[enum_name] = parser.get
            parser_configs.append(parser.config)

        self.config = ChainConfig(config_dir=CHAIN_IMAGE_PARSERS_DATA_DIR,
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config in
                                                     zip(chain_data["chain"], parser_configs)])

    def get(self, word: str) -> ImageGenerator:
        batch_size = yield
        for enum_name, url_getting_function in self.enum_name2url_getting_functions.items():
            self.config.update_config(enum_name)
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
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name
        self.enum_name2parsers_data: dict[str, tuple[str, Callable[[str, dict], AudioGenerator] | None]] = {}
        names = []
        parser_configs = []
        for parser_name, enum_name in zip(chain_data["chain"], get_enumerated_names(chain_data["chain"])):
            names.append(parser_name)
            if parser_name.startswith(f"[{parser_types.WEB}]"):
                parser_type = parser_types.WEB
                getter = loaded_plugins.get_web_audio_getter(parser_name[3 + len(parser_types.WEB):])
            elif parser_name.startswith(f"[{parser_types.LOCAL}]"):
                parser_type = parser_types.LOCAL
                getter = loaded_plugins.get_local_audio_getter(parser_name[3 + len(parser_types.LOCAL):])
            else:
                raise NotImplementedError(f"Audio getter of unknown type: {parser_name}")
            self.enum_name2parsers_data[enum_name] = (parser_type, getter.get)
            parser_configs.append(getter.config)

        get_all_configuration = {"error_verbosity": ("silent", [str], ["silent", "if_found_audio", "all"])}
        get_all_docs = """
error_verbosity:
    silent - doesn't save any errors
    if_found_audio - saves errors ONLY IF found audios
    all - saves all errors
"""
        self.config = ChainConfig(config_dir=CHAIN_AUDIO_GETTERS_DATA_DIR,
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(parser_name, config) for parser_name, config
                                                     in zip(names, parser_configs)],
                                  additional_val_scheme=get_all_configuration,
                                  additional_docs=get_all_docs)
                
    def get(self, word: str, card_data: dict) -> \
            Generator[list[tuple[tuple[str, str], AudioData]], int, list[tuple[tuple[str, str], AudioData]]]:

        results = []
        batch_size = yield
        for enum_name, (parser_type, get_audio_generator) in self.enum_name2parsers_data.items():
            self.config.update_config(enum_name)

            audio_data_generator = get_audio_generator(word, card_data)
            try:
                next(audio_data_generator)
            except StopIteration as e:
                _, error_message = e.value
                if self.config["error_verbosity"] == "silent":
                    error_message = ""

                if error_message and self.config["error_verbosity"] == "all":
                    results.append(((enum_name, parser_type), (([], []), error_message)))
                continue

            while True:
                try:
                    ((audios, additional_info), error_message) = audio_data_generator.send(batch_size)
                    if self.config["error_verbosity"] == "silent":
                        error_message = ""

                    if audios or self.config["error_verbosity"] == "all" and error_message:
                        results.append(((enum_name, parser_type),
                                        ((audios, additional_info), error_message)))
                        batch_size -= len(audios)
                        if batch_size <= 0:
                            batch_size = yield results
                            results = []

                except StopIteration as e:
                    ((audios, additional_info), error_message) = e.value
                    if self.config["error_verbosity"] == "silent":
                        error_message = ""

                    if audios or self.config["error_verbosity"] == "all" and error_message:
                        results.append(((enum_name, parser_type),
                                        ((audios, additional_info), error_message)))
                        batch_size -= len(audios)
                        if batch_size <= 0:
                            batch_size = yield results
                            results = []
                    break
        return results
