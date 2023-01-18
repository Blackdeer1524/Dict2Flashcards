import os.path
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from ..app_utils.decks import CardStatus, SavedDataDeck
from ..consts import CardFormat
from ..consts.paths import LOCAL_AUDIO_DIR, LOCAL_DICTIONARIES_DIR
from ..plugins_management.config_management import (HasConfigFile,
                                                    LoadableConfig)
from ..plugins_management.parsers_return_types import (
    AUDIO_SCRAPPER_RETURN_T, IMAGE_SCRAPPER_RETURN_T,
    SENTENCE_SCRAPPER_RETURN_T)
from .exceptions import LoaderError, WrongPluginProtocol
from .interfaces import (CardProcessorInterface, DeckSavingFormatInterface,
                         ImageParserInterface, LanguagePackageInterface,
                         LocalAudioGetterInterface, LocalWordParserInterface,
                         ThemeInterface, WebAudioGetterInterface,
                         WebSentenceParserInterface, WebWordParserInterface)
from .wrappers import Named


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class WebWordParserContainer(Named, HasConfigFile):
    name: str
    scheme_docs: str
    config: LoadableConfig
    define: Callable[[str], tuple[list[CardFormat], str]]

    def __init__(self, name: str, source_module: WebWordParserInterface):
        if not isinstance(source_module, WebWordParserInterface):
            raise WrongPluginProtocol(f"{source_module} should have WebWordParserInterface protocol!")

        object.__setattr__(self, "name",        name)
        object.__setattr__(self, "scheme_docs", source_module.SCHEME_DOCS)
        object.__setattr__(self, "config",      source_module.config)
        object.__setattr__(self, "define",      source_module.define)


DICTIONARY_T = TypeVar("DICTIONARY_T")

@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class LocalWordParserContainer(Named, HasConfigFile, Generic[DICTIONARY_T]):
    name: str
    scheme_docs: str
    config: LoadableConfig
    local_dict_name: str
    define: Callable[[str, DICTIONARY_T], tuple[list[CardFormat], str]]
    
    def __init__(self, name: str, source_module: LocalWordParserInterface):
        if not isinstance(source_module, LocalWordParserInterface):
            raise WrongPluginProtocol(f"{source_module} should have LocalWordParserInterface protocol!")

        if not os.path.exists(os.path.join(LOCAL_DICTIONARIES_DIR, source_module.DICTIONARY_NAME + ".json")):
            raise LoaderError(f"Local dictionary doesn't exists!")

        object.__setattr__(self, "name",        name)
        object.__setattr__(self, "local_dict_name", source_module.DICTIONARY_NAME)
        object.__setattr__(self, "scheme_docs", source_module.SCHEME_DOCS)
        object.__setattr__(self, "config", source_module.config)
        object.__setattr__(self, "define", source_module.define)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class WebAudioGetterContainer(Named, HasConfigFile):
    name: str
    config: LoadableConfig
    get: Callable[[str, CardFormat], AUDIO_SCRAPPER_RETURN_T]

    def __init__(self, name: str, source_module: WebAudioGetterInterface):
        if not isinstance(source_module, WebAudioGetterInterface):
            raise WrongPluginProtocol(f"{source_module} should have WebAudioGetterInterface protocol!")

        object.__setattr__(self, "name",        name)
        object.__setattr__(self, "config", source_module.config)
        object.__setattr__(self, "get", source_module.get)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class LocalAudioGetterContainer(Named, HasConfigFile):
    name: str
    config: LoadableConfig
    get: Callable[[str, CardFormat], AUDIO_SCRAPPER_RETURN_T]

    def __init__(self, name: str, source_module: LocalAudioGetterInterface):
        if not isinstance(source_module, LocalAudioGetterInterface):
            raise WrongPluginProtocol(f"{source_module} should have LocalAudioGetterInterface protocol!")

        if not os.path.exists(os.path.join(LOCAL_AUDIO_DIR, source_module.AUDIO_FOLDER)):
            raise LoaderError(f"Local dictionary doesn't exists!")

        object.__setattr__(self, "name",        name)
        object.__setattr__(self, "config", source_module.config)
        object.__setattr__(self, "get", source_module.get)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class WebSentenceParserContainer(Named, HasConfigFile):
    name: str
    config: LoadableConfig
    get: Callable[[str, CardFormat], SENTENCE_SCRAPPER_RETURN_T]

    def __init__(self, name: str, source_module: WebSentenceParserInterface):
        if not isinstance(source_module, WebSentenceParserInterface):
            raise WrongPluginProtocol(f"{source_module} should have WebSentenceParserInterface protocol!")

        object.__setattr__(self, "name",        name)
        object.__setattr__(self, "config", source_module.config)
        object.__setattr__(self, "get", source_module.get)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class ImageParserContainer(Named, HasConfigFile):
    name: str
    config: LoadableConfig
    get: Callable[[str, CardFormat], IMAGE_SCRAPPER_RETURN_T]

    def __init__(self, name: str, source_module: ImageParserInterface):
        if not isinstance(source_module, ImageParserInterface):
            raise WrongPluginProtocol(f"{source_module} should have ImageParserInterface protocol!")

        object.__setattr__(self, "name",        name)
        object.__setattr__(self, "config", source_module.config)
        object.__setattr__(self, "get", source_module.get)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class CardProcessorContainer(Named):
    name: str
    get_save_image_name: Callable[[str, str, dict], str]
    get_card_image_name: Callable[[str], str]
    get_save_audio_name: Callable[[str, str, str, dict], str]
    get_card_audio_name: Callable[[str], str]
    process_card:        Callable[[dict], None]

    def __init__(self, name: str, source_module: CardProcessorInterface):
        if not isinstance(source_module, CardProcessorInterface):
            raise WrongPluginProtocol(f"{source_module} should have CardProcessorInterface protocol!")

        object.__setattr__(self, "name",        name)
        object.__setattr__(self, "get_save_image_name", source_module.get_save_image_name)
        object.__setattr__(self, "get_card_image_name", source_module.get_card_image_name)
        object.__setattr__(self, "get_save_audio_name", source_module.get_save_audio_name)
        object.__setattr__(self, "get_card_audio_name", source_module.get_card_audio_name)
        object.__setattr__(self, "process_card",        source_module.process_card)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class DeckSavingFormatContainer(Named):
    name: str
    save: Callable[[SavedDataDeck, CardStatus, str, Callable[[str], str], Callable[[str], str]], None]

    def __init__(self, name: str, source_module: DeckSavingFormatInterface):
        if not isinstance(source_module, DeckSavingFormatInterface):
            raise WrongPluginProtocol(f"{source_module} should have DeckSavingFormatInterface protocol!")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "save", source_module.save)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class ThemeContainer(Named, ThemeInterface):
    name: str
    
    def __init__(self, name: str, source_module: ThemeInterface):
        if not isinstance(source_module, ThemeInterface):
            raise WrongPluginProtocol(f"{source_module} should have ThemeInterface protocol!")

        object.__setattr__(self, "name",                name)
        object.__setattr__(self, "label_cfg",           source_module.label_cfg)
        object.__setattr__(self, "button_cfg",          source_module.button_cfg)
        object.__setattr__(self, "text_cfg",            source_module.text_cfg)
        object.__setattr__(self, "entry_cfg",           source_module.entry_cfg)
        object.__setattr__(self, "checkbutton_cfg",     source_module.checkbutton_cfg)
        object.__setattr__(self, "toplevel_cfg",        source_module.toplevel_cfg)
        object.__setattr__(self, "root_cfg",            source_module.root_cfg)
        object.__setattr__(self, "frame_cfg",           source_module.frame_cfg)
        object.__setattr__(self, "option_menu_cfg",     source_module.option_menu_cfg)
        object.__setattr__(self, "option_submenus_cfg", source_module.option_submenus_cfg)


@dataclass(init=False, repr=False, frozen=True, eq=False, order=False, slots=True)
class LanguagePackageContainer(Named, LanguagePackageInterface):
    name: str

    def __init__(self, name: str, source_module: LanguagePackageInterface):
        if not isinstance(source_module, LanguagePackageInterface):
            raise WrongPluginProtocol(f"{source_module} should have LanguagePackageInterface protocol!")

        object.__setattr__(self, "name",        name)
        # errors
        object.__setattr__(self, "error_title", source_module.error_title)

        # main window
        object.__setattr__(self, "main_window_title_prefix", source_module.main_window_title_prefix)

        # main menu
        object.__setattr__(self, "create_file_menu_label", source_module.create_file_menu_label)
        object.__setattr__(self, "open_file_menu_label", source_module.open_file_menu_label)
        object.__setattr__(self, "save_files_menu_label", source_module.save_files_menu_label)
        object.__setattr__(self, "hotkeys_and_buttons_help_menu_label",
                           source_module.hotkeys_and_buttons_help_menu_label)
        object.__setattr__(self, "query_settings_language_label_text", source_module.query_settings_language_label_text)
        object.__setattr__(self, "help_master_menu_label", source_module.help_master_menu_label)
        object.__setattr__(self, "download_audio_menu_label", source_module.download_audio_menu_label)
        object.__setattr__(self, "change_media_folder_menu_label", source_module.change_media_folder_menu_label)
        object.__setattr__(self, "file_master_menu_label", source_module.file_master_menu_label)

        object.__setattr__(self, "add_card_menu_label", source_module.add_card_menu_label)
        object.__setattr__(self, "search_inside_deck_menu_label", source_module.search_inside_deck_menu_label)
        object.__setattr__(self, "added_cards_browser_menu_label", source_module.added_cards_browser_menu_label)
        object.__setattr__(self, "statistics_menu_label", source_module.statistics_menu_label)
        object.__setattr__(self, "settings_themes_label_text", source_module.settings_themes_label_text)
        object.__setattr__(self, "settings_language_label_text", source_module.settings_language_label_text)
        object.__setattr__(self, "settings_configure_anki_button_text", source_module.settings_configure_anki_button_text)
        object.__setattr__(self, "settings_menu_label", source_module.settings_menu_label)
        object.__setattr__(self, "settings_image_search_configuration_label_text", source_module.settings_image_search_configuration_label_text)
        object.__setattr__(self, "setting_web_audio_downloader_configuration_label_text",
                           source_module.setting_web_audio_downloader_configuration_label_text)
        object.__setattr__(self, "settings_extern_audio_placer_configuration_label_text",
                           source_module.settings_extern_audio_placer_configuration_label_text)
        object.__setattr__(self, "settings_extern_sentence_placer_configuration_label",
                           source_module.settings_extern_sentence_placer_configuration_label)
        object.__setattr__(self, "settings_card_processor_label_text",
                           source_module.settings_card_processor_label_text)
        object.__setattr__(self, "settings_format_processor_label_text",
                           source_module.settings_format_processor_label_text)
        object.__setattr__(self, "settings_audio_autopick_label_text",
                           source_module.settings_audio_autopick_label_text)
        object.__setattr__(self, "settings_audio_autopick_off",
                           source_module.settings_audio_autopick_off)
        object.__setattr__(self, "settings_audio_autopick_first_default_audio",
                           source_module.settings_audio_autopick_first_default_audio)
        object.__setattr__(self, "settings_audio_autopick_all_default_audios",
                           source_module.settings_audio_autopick_all_default_audios)
        object.__setattr__(self, "settings_audio_autopick_first_available_audio",
                           source_module.settings_audio_autopick_first_available_audio)
        object.__setattr__(self, "settings_audio_autopick_first_available_audio_source",
                           source_module.settings_audio_autopick_first_available_audio_source)
        object.__setattr__(self, "settings_audio_autopick_all",
                           source_module.settings_audio_autopick_all)


        object.__setattr__(self, "chain_management_menu_label", source_module.chain_management_menu_label)
        object.__setattr__(self, "chain_management_word_parsers_option",
                           source_module.chain_management_word_parsers_option)
        object.__setattr__(self, "chain_management_sentence_parsers_option",
                           source_module.chain_management_sentence_parsers_option)
        object.__setattr__(self, "chain_management_image_parsers_option",
                           source_module.chain_management_image_parsers_option)
        object.__setattr__(self, "chain_management_audio_getters_option",
                           source_module.chain_management_audio_getters_option)
        object.__setattr__(self, "chain_management_chain_type_label_text",
                           source_module.chain_management_chain_type_label_text)
        object.__setattr__(self, "chain_management_existing_chains_treeview_name_column",
                           source_module.chain_management_existing_chains_treeview_name_column)
        object.__setattr__(self, "chain_management_existing_chains_treeview_chain_column",
                           source_module.chain_management_existing_chains_treeview_chain_column)
        object.__setattr__(self, "chain_management_pop_up_menu_edit_label",
                           source_module.chain_management_pop_up_menu_edit_label)
        object.__setattr__(self, "chain_management_pop_up_menu_remove_label",
                           source_module.chain_management_pop_up_menu_remove_label)
        object.__setattr__(self, "chain_management_chain_name_entry_placeholder",
                           source_module.chain_management_chain_name_entry_placeholder)
        object.__setattr__(self, "chain_management_empty_chain_name_entry_message",
                           source_module.chain_management_empty_chain_name_entry_message)
        object.__setattr__(self, "chain_management_chain_already_exists_message",
                           source_module.chain_management_chain_already_exists_message)
        object.__setattr__(self, "chain_management_save_chain_button_text",
                           source_module.chain_management_save_chain_button_text)
        object.__setattr__(self, "chain_management_close_chain_building_button_text",
                           source_module.chain_management_close_chain_building_button_text)
        object.__setattr__(self, "chain_management_call_chain_building_button_text",
                           source_module.chain_management_call_chain_building_button_text)
        object.__setattr__(self, "chain_management_close_chain_type_selection_button",
                           source_module.chain_management_close_chain_type_selection_button)

        object.__setattr__(self, "exit_menu_label", source_module.exit_menu_label)

        # widgets
        object.__setattr__(self, "anki_button_text", source_module.anki_button_text)
        object.__setattr__(self, "browse_button_text", source_module.browse_button_text)
        object.__setattr__(self, "word_text_placeholder", source_module.word_text_placeholder)
        object.__setattr__(self, "definition_text_placeholder", source_module.definition_text_placeholder)
        object.__setattr__(self, "bury_button_text", source_module.bury_button_text)
        object.__setattr__(self, "fetch_images_button_normal_text", source_module.fetch_images_button_normal_text)
        object.__setattr__(self, "fetch_images_button_image_link_encountered_postfix",
                           source_module.fetch_images_button_image_link_encountered_postfix)
        object.__setattr__(self, "fetch_audio_data_button_text", source_module.fetch_audio_data_button_text)
        object.__setattr__(self, "audio_search_entry_text", source_module.audio_search_entry_text)
        object.__setattr__(self, "fetch_ext_sentences_button", source_module.fetch_ext_sentences_button)
        object.__setattr__(self, "sentence_search_entry_text", source_module.sentence_search_entry_text)
        object.__setattr__(self, "sentence_text_placeholder_prefix", source_module.sentence_text_placeholder_prefix)
        object.__setattr__(self, "user_tags_field_placeholder", source_module.user_tags_field_placeholder)

        # display_audio_on_frame
        object.__setattr__(self, "display_audio_getter_results_audio_not_found_message",
                           source_module.display_audio_getter_results_audio_not_found_message)

        # choose files
        object.__setattr__(self, "choose_media_dir_message", source_module.choose_media_dir_message)
        object.__setattr__(self, "choose_deck_file_message", source_module.choose_deck_file_message)
        object.__setattr__(self, "choose_save_dir_message", source_module.choose_save_dir_message)

        # create new deck file
        object.__setattr__(self, "create_file_choose_dir_message", source_module.create_file_choose_dir_message)
        object.__setattr__(self, "create_file_name_entry_placeholder", source_module.create_file_name_entry_placeholder)
        object.__setattr__(self, "create_file_name_button_placeholder",
                           source_module.create_file_name_button_placeholder)
        object.__setattr__(self, "create_file_no_file_name_was_given_message",
                           source_module.create_file_no_file_name_was_given_message)
        object.__setattr__(self, "create_file_file_already_exists_message",
                           source_module.create_file_file_already_exists_message)
        object.__setattr__(self, "create_file_skip_encounter_button_text",
                           source_module.create_file_skip_encounter_button_text)
        object.__setattr__(self, "create_file_rewrite_encounter_button_text",
                           source_module.create_file_rewrite_encounter_button_text)

        # save files
        object.__setattr__(self, "save_files_message", source_module.save_files_message)

        # word definition
        object.__setattr__(self, "card_insertion_limit_exceed_title", source_module.card_insertion_limit_exceed_title)
        object.__setattr__(self, "card_insertion_limit_exceed_message", source_module.card_insertion_limit_exceed_message)

        # help
        object.__setattr__(self, "buttons_hotkeys_help_message", source_module.buttons_hotkeys_help_message)
        object.__setattr__(self, "buttons_hotkeys_help_window_title",
                           source_module.buttons_hotkeys_help_window_title)
        object.__setattr__(self, "word_field_help", source_module.word_field_help)
        object.__setattr__(self, "special_field_help", source_module.special_field_help)
        object.__setattr__(self, "definition_field_help", source_module.definition_field_help)
        object.__setattr__(self, "sentences_field_help", source_module.sentences_field_help)
        object.__setattr__(self, "img_links_field_help", source_module.img_links_field_help)
        object.__setattr__(self, "audio_links_field_help", source_module.audio_links_field_help)
        object.__setattr__(self, "dict_tags_field_help", source_module.dict_tags_field_help)
        object.__setattr__(self, "query_language_docs", source_module.query_language_docs)
        object.__setattr__(self, "query_language_window_title", source_module.query_language_window_title)
        object.__setattr__(self, "general_scheme_label", source_module.general_scheme_label)
        object.__setattr__(self, "current_scheme_label", source_module.current_scheme_label)
        object.__setattr__(self, "query_language_label", source_module.query_language_label)

        # download audio
        object.__setattr__(self, "download_audio_choose_audio_file_title",
                           source_module.download_audio_choose_audio_file_title)

        # define word
        object.__setattr__(self, "define_word_wrong_regex_message", source_module.define_word_wrong_regex_message)
        object.__setattr__(self, "define_word_word_not_found_message", source_module.define_word_word_not_found_message)
        object.__setattr__(self, "define_word_query_language_error_message_title",
                           source_module.define_word_query_language_error_message_title)

        # add_word_dialog
        object.__setattr__(self, "add_word_window_title", source_module.add_word_window_title)
        object.__setattr__(self, "add_word_entry_placeholder", source_module.add_word_entry_placeholder)
        object.__setattr__(self, "add_word_additional_filter_entry_placeholder",
                           source_module.add_word_additional_filter_entry_placeholder)
        object.__setattr__(self, "add_word_start_parsing_button_text", source_module.add_word_start_parsing_button_text)

        # find dialog
        object.__setattr__(self, "find_dialog_empty_query_message", source_module.find_dialog_empty_query_message)
        object.__setattr__(self, "find_dialog_wrong_move_message", source_module.find_dialog_wrong_move_message)
        object.__setattr__(self, "find_dialog_end_rotation_button_text", source_module.find_dialog_end_rotation_button_text)
        object.__setattr__(self, "find_dialog_nothing_found_message", source_module.find_dialog_nothing_found_message)
        object.__setattr__(self, "find_dialog_find_window_title", source_module.find_dialog_find_window_title)
        object.__setattr__(self, "find_dialog_find_button_text", source_module.find_dialog_find_button_text)

        # statistics dialog
        object.__setattr__(self, "statistics_dialog_statistics_window_title",
                           source_module.statistics_dialog_statistics_window_title)
        object.__setattr__(self, "statistics_dialog_added_label", source_module.statistics_dialog_added_label)
        object.__setattr__(self, "statistics_dialog_buried_label", source_module.statistics_dialog_buried_label)
        object.__setattr__(self, "statistics_dialog_skipped_label", source_module.statistics_dialog_skipped_label)
        object.__setattr__(self, "statistics_dialog_cards_left_label", source_module.statistics_dialog_cards_left_label)
        object.__setattr__(self, "statistics_dialog_current_file_label",
                           source_module.statistics_dialog_current_file_label)
        object.__setattr__(self, "statistics_dialog_saving_dir_label", source_module.statistics_dialog_saving_dir_label)
        object.__setattr__(self, "statistics_dialog_media_dir_label", source_module.statistics_dialog_media_dir_label)

        # anki dialog
        object.__setattr__(self, "anki_dialog_anki_window_title", source_module.anki_dialog_anki_window_title)
        object.__setattr__(self, "anki_dialog_anki_deck_entry_placeholder",
                           source_module.anki_dialog_anki_deck_entry_placeholder)
        object.__setattr__(self, "anki_dialog_anki_field_entry_placeholder",
                           source_module.anki_dialog_anki_field_entry_placeholder)
        object.__setattr__(self, "anki_dialog_save_anki_settings_button_text",
                           source_module.anki_dialog_save_anki_settings_button_text)

        # theme change
        object.__setattr__(self, "restart_app_text", source_module.restart_app_text)

        # program exit
        object.__setattr__(self, "on_closing_message_title", source_module.on_closing_message_title)
        object.__setattr__(self, "on_closing_message", source_module.on_closing_message)

        object.__setattr__(self, "configuration_window_conf_window_title",
                           source_module.configuration_window_conf_window_title)
        object.__setattr__(self, "configuration_window_restore_defaults_done_message",
                           source_module.configuration_window_restore_defaults_done_message)
        object.__setattr__(self, "configuration_window_restore_defaults_button_text",
                           source_module.configuration_window_restore_defaults_button_text)
        object.__setattr__(self, "configuration_window_cancel_button_text",
                           source_module.configuration_window_cancel_button_text)
        object.__setattr__(self, "configuration_window_bad_json_scheme_message",
                           source_module.configuration_window_bad_json_scheme_message)
        object.__setattr__(self, "configuration_window_saved_message",
                           source_module.configuration_window_saved_message)
        object.__setattr__(self, "configuration_window_wrong_type_field",
                           source_module.configuration_window_wrong_type_field)
        object.__setattr__(self, "configuration_window_wrong_value_field",
                           source_module.configuration_window_wrong_value_field)
        object.__setattr__(self, "configuration_window_missing_keys_field",
                           source_module.configuration_window_missing_keys_field)
        object.__setattr__(self, "configuration_window_unknown_keys_field",
                           source_module.configuration_window_unknown_keys_field)
        object.__setattr__(self, "configuration_window_expected_prefix",
                           source_module.configuration_window_expected_prefix)
        object.__setattr__(self, "configuration_window_save_button_text",
                           source_module.configuration_window_save_button_text)

        # play_audio
        object.__setattr__(self, "play_audio_playaudio_window_title",
                           source_module.play_audio_playaudio_window_title)
        object.__setattr__(self, "play_audio_local_audio_not_found_message",
                           source_module.play_audio_local_audio_not_found_message)
        object.__setattr__(self, "play_audio_no_audio_source_found_message",
                           source_module.play_audio_no_audio_source_found_message)

        # request anki
        object.__setattr__(self, "request_anki_connection_error_message",
                           source_module.request_anki_connection_error_message)
        object.__setattr__(self, "request_anki_general_request_error_message_prefix",
                           source_module.request_anki_general_request_error_message_prefix)

        # audio downloader
        object.__setattr__(self, "audio_downloader_title",
                           source_module.audio_downloader_title)
        object.__setattr__(self, "audio_downloader_file_exists_message",
                           source_module.audio_downloader_file_exists_message)
        object.__setattr__(self, "audio_downloader_skip_encounter_button_text",
                           source_module.audio_downloader_skip_encounter_button_text)
        object.__setattr__(self, "audio_downloader_rewrite_encounter_button_text",
                           source_module.audio_downloader_rewrite_encounter_button_text)
        object.__setattr__(self, "audio_downloader_apply_to_all_button_text",
                           source_module.audio_downloader_apply_to_all_button_text)
        object.__setattr__(self, "audio_downloader_n_errors_message_prefix",
                           source_module.audio_downloader_n_errors_message_prefix)

        # image downloader
        object.__setattr__(self, "image_search_title",
                           source_module.image_search_title)
        object.__setattr__(self, "image_search_start_search_button_text",
                           source_module.image_search_start_search_button_text)
        object.__setattr__(self, "image_search_show_more_button_text",
                           source_module.image_search_show_more_button_text)
        object.__setattr__(self, "image_search_save_button_text",
                           source_module.image_search_save_button_text)
        object.__setattr__(self, "image_search_empty_search_query_message",
                           source_module.image_search_empty_search_query_message)
