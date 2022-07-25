from typing import Optional, Callable

from app_utils.cards import Card, CardGenerator
from app_utils.cards import DataSourceType
from consts.paths import *
from plugins_loading.factory import loaded_plugins
from plugins_management.config_management import LoadableConfig
from plugins_management.parsers_return_types import ImageGenerator


class ChainConfig(LoadableConfig):
    def __init__(self,
                 config_dir: str,
                 config_name: str,
                 name_config_pairs: list[tuple[str, LoadableConfig]]):
        self.name_config_pairs = name_config_pairs
        validation_scheme = {}
        data = {}
        docs_list = []
        for name, config in self.name_config_pairs:
            data[name] = config.data
            validation_scheme[name] = config.validation_scheme
            docs_list.append("{}:\n{}".format(name, config.docs.replace('\n', '\n |\t')))
            config.save()
        docs = "\n".join(docs_list)
        super(ChainConfig, self).__init__(validation_scheme=validation_scheme,  # type: ignore
                                          docs=docs,
                                          config_location=config_dir,
                                          _config_file_name=config_name)
        self.load()

    def update_children_configs(self):
        for name, config in self.name_config_pairs:
            config.data = self[name]

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
        self.card_generators: list[CardGenerator] = []
        parser_configs = []
        scheme_docs_list = []
        for parser_name in chain_data["chain"]:
            if parser_name.startswith(f"[{DataSourceType.WEB}]"):
                self.card_generators.append(
                    loaded_plugins.get_web_card_generator(parser_name[3 + len(DataSourceType.WEB):]))
            elif parser_name.startswith(f"[{DataSourceType.LOCAL}]"):
                self.card_generators.append(
                    loaded_plugins.get_local_card_generator(parser_name[3 + len(DataSourceType.LOCAL):]))
            else:
                raise NotImplementedError(f"Parser with unknown type: {parser_name}")
            parser_configs.append(self.card_generators[-1].config)
            scheme_docs_list.append("{}\n{}".format(parser_name,
                                                    self.card_generators[-1].scheme_docs.replace("\n", "\n |\t")))
        self.config = ChainConfig(config_dir=CHAIN_DATA_DIR / "configs" / "word_parsers",
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(name, config) for name, config in
                                                     zip(chain_data["chain"], parser_configs)])


        self.scheme_docs = "\n".join(scheme_docs_list)

    @property
    def type(self):
        return "chain"

    def get(self,
            query: str,
            word_filter: Callable[[str], bool],
            additional_filter: Callable[[Card], bool] = None) -> list[Card]:
        current_result = []
        for generator in self.card_generators:
            if (current_result := generator.get(query, word_filter, additional_filter)):
                break
        return current_result


class ImageParsersChain:
    def __init__(self,
                 name: str,
                 chain_data: dict[str, str | list[str]]):
        self.name = name
        self.url_getting_functions = []
        parser_configs = []
        for parser_name in chain_data["chain"]:
            parser = loaded_plugins.get_image_parser(parser_name)
            self.url_getting_functions.append(parser.get_image_links)
            parser_configs.append(parser.config)

        self.config = ChainConfig(config_dir=CHAIN_DATA_DIR / "configs" / "image_parsers",
                                  config_name=chain_data["config_name"],
                                  name_config_pairs=[(name, config) for name, config in
                                                     zip(chain_data["chain"], parser_configs)])

    def get_image_links(self, word: str) -> ImageGenerator:
        batch_size = yield
        for url_getting_function in self.url_getting_functions:
            url_generator = url_getting_function(word)
            next(url_generator)
            while True:
                try:
                    batch_size = yield url_generator.send(batch_size)
                except StopIteration:
                    break
