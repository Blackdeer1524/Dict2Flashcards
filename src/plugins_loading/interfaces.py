from typing import Callable, Protocol, TypeVar, runtime_checkable

from ..app_utils.decks import CardStatus, SavedDataDeck
from ..plugins_management.config_management import LoadableConfig
from ..consts import CardFormat
from ..plugins_management.parsers_return_types import AUDIO_SCRAPPER_RETURN_T, IMAGE_SCRAPPER_RETURN_T, SENTENCE_SCRAPPER_RETURN_T

@runtime_checkable
class LanguagePackageInterface(Protocol):
    # errors
    error_title: str

    # main window
    main_window_cards_left: str

    # main menu
    create_file_menu_label: str
    open_file_menu_label: str
    save_files_menu_label: str
    hotkeys_and_buttons_help_menu_label: str
    query_settings_language_label_text: str
    help_master_menu_label: str
    download_audio_menu_label: str
    change_media_folder_menu_label: str
    file_master_menu_label: str

    add_card_menu_label: str
    search_inside_deck_menu_label: str
    added_cards_browser_menu_label: str
    statistics_menu_label: str

    settings_menu_label: str
    settings_themes_label_text: str
    settings_language_label_text: str
    settings_image_search_configuration_label_text: str
    setting_web_audio_downloader_configuration_label_text: str
    settings_extern_audio_placer_configuration_label_text: str
    settings_extern_sentence_placer_configuration_label: str
    settings_format_processor_configuration_label: str
    settings_card_processor_label_text: str
    settings_format_processor_label_text: str
    settings_audio_autopick_label_text: str
    settings_audio_autopick_off: str
    settings_audio_autopick_first_default_audio: str
    settings_audio_autopick_all_default_audios: str
    settings_audio_autopick_first_available_audio: str
    settings_audio_autopick_first_available_audio_source: str
    settings_audio_autopick_all: str
    settings_configure_anki_button_text: str

    chain_management_menu_label: str
    chain_management_word_parsers_option: str
    chain_management_sentence_parsers_option: str
    chain_management_image_parsers_option: str
    chain_management_audio_getters_option: str
    chain_management_chain_type_label_text: str
    chain_management_existing_chains_treeview_name_column: str
    chain_management_existing_chains_treeview_chain_column: str
    chain_management_pop_up_menu_edit_label: str
    chain_management_pop_up_menu_remove_label: str
    chain_management_chain_name_entry_placeholder: str
    chain_management_empty_chain_name_entry_message: str
    chain_management_chain_already_exists_message: str
    chain_management_save_chain_button_text: str
    chain_management_close_chain_building_button_text: str
    chain_management_call_chain_building_button_text: str
    chain_management_close_chain_type_selection_button: str

    exit_menu_label: str

    # widgets
    anki_button_text: str
    browse_button_text: str
    word_text_placeholder: str
    definition_text_placeholder: str
    bury_button_text: str
    fetch_images_button_normal_text: str
    fetch_images_button_image_link_encountered_postfix: str
    fetch_audio_data_button_text: str
    audio_search_entry_text: str
    fetch_ext_sentences_button: str
    sentence_search_entry_text: str
    sentence_text_placeholder_prefix: str
    user_tags_field_placeholder: str

    # display_audio_on_frame
    display_audio_getter_results_audio_not_found_message: str

    # choose files
    choose_media_dir_message: str
    choose_deck_file_message: str
    choose_save_dir_message: str

    # create new deck file
    create_file_choose_dir_message: str
    create_file_name_entry_placeholder: str
    create_file_name_button_placeholder: str
    create_file_no_file_name_was_given_message: str
    create_file_file_already_exists_message: str
    create_file_skip_encounter_button_text: str
    create_file_rewrite_encounter_button_text: str

    # save files
    save_files_message: str

    # word definition
    card_insertion_limit_exceed_title: str
    card_insertion_limit_exceed_message: str

    # help
    buttons_hotkeys_help_message: str
    buttons_hotkeys_help_window_title: str
    word_field_help: str
    special_field_help: str
    definition_field_help: str
    sentences_field_help: str
    img_links_field_help: str
    audio_links_field_help: str
    dict_tags_field_help: str
    query_language_docs: str
    query_language_window_title: str
    general_scheme_label: str
    current_scheme_label: str
    query_language_label: str

    # download audio
    download_audio_choose_audio_file_title: str

    # define word
    define_word_wrong_regex_message: str
    define_word_word_not_found_message: str
    define_word_query_language_error_message_title: str

    # add_word_dialog
    add_word_window_title: str
    add_word_entry_placeholder: str
    add_word_additional_filter_entry_placeholder: str
    add_word_start_parsing_button_text: str

    # find dialog
    find_dialog_empty_query_message: str
    find_dialog_wrong_move_message: str
    find_dialog_end_rotation_button_text: str
    find_dialog_nothing_found_message: str
    find_dialog_find_window_title: str
    find_dialog_find_button_text: str

    # statistics dialog
    statistics_dialog_copied_text: str
    statistics_dialog_statistics_window_title: str
    statistics_dialog_added_label: str
    statistics_dialog_buried_label: str
    statistics_dialog_skipped_label: str
    statistics_dialog_cards_left_label: str
    statistics_dialog_current_file_label: str
    statistics_dialog_saving_dir_label: str
    statistics_dialog_media_dir_label: str

    # anki dialog
    anki_dialog_anki_window_title: str
    anki_dialog_anki_deck_entry_placeholder: str
    anki_dialog_anki_field_entry_placeholder: str
    anki_dialog_save_anki_settings_button_text: str

    # theme change
    restart_app_text: str

    # program exit
    on_closing_message_title: str
    on_closing_message: str

    # call_configuration_window
    configuration_window_conf_window_title: str
    configuration_window_restore_defaults_done_message: str
    configuration_window_restore_defaults_button_text: str
    configuration_window_cancel_button_text: str
    configuration_window_bad_json_scheme_message: str
    configuration_window_saved_message: str
    configuration_window_wrong_type_field: str
    configuration_window_wrong_value_field: str
    configuration_window_missing_keys_field: str
    configuration_window_unknown_keys_field: str
    configuration_window_expected_prefix: str
    configuration_window_save_button_text: str

    # play_sound
    play_audio_playaudio_window_title: str
    play_audio_local_audio_not_found_message: str
    play_audio_no_audio_source_found_message: str

    # request anki
    request_anki_connection_error_message: str
    request_anki_general_request_error_message_prefix: str

    # audio downloader
    audio_downloader_title: str
    audio_downloader_file_exists_message: str
    audio_downloader_skip_encounter_button_text: str
    audio_downloader_rewrite_encounter_button_text: str
    audio_downloader_apply_to_all_button_text: str
    audio_downloader_n_errors_message_prefix: str

    # image downloader
    image_search_title: str
    image_search_start_search_button_text: str
    image_search_show_more_button_text: str
    image_search_save_button_text: str
    image_search_empty_search_query_message: str


@runtime_checkable
class ThemeInterface(Protocol):
    label_cfg: dict
    button_cfg: dict
    text_cfg: dict
    entry_cfg: dict
    checkbutton_cfg: dict
    toplevel_cfg: dict
    root_cfg: dict
    frame_cfg: dict
    option_menu_cfg: dict
    option_submenus_cfg: dict


ERROR_MESSAGE_T = str

@runtime_checkable
class WebWordParserInterface(Protocol):
    SCHEME_DOCS: str
    config: LoadableConfig

    @staticmethod
    def define(query: str) -> tuple[list[CardFormat], ERROR_MESSAGE_T]:
        ...


WORD_T = str
DICTIONARY_T = TypeVar("DICTIONARY_T")

@runtime_checkable
class LocalWordParserInterface(Protocol):
    SCHEME_DOCS: str
    config: LoadableConfig
    DICTIONARY_NAME: str

    @staticmethod
    def define(query: str, dictionary: DICTIONARY_T) -> tuple[list[CardFormat], ERROR_MESSAGE_T]:
        ...


@runtime_checkable
class WebSentenceParserInterface(Protocol):
    config: LoadableConfig

    @staticmethod
    def get(word: str, card_data: dict) -> SENTENCE_SCRAPPER_RETURN_T:
        ...


@runtime_checkable
class ImageParserInterface(Protocol):
    config: LoadableConfig

    @staticmethod
    def get(word: str) -> IMAGE_SCRAPPER_RETURN_T:
        ...


@runtime_checkable
class LocalAudioGetterInterface(Protocol):
    config: LoadableConfig
    AUDIO_FOLDER: str

    @staticmethod
    def get(word: str, card_data: dict) -> AUDIO_SCRAPPER_RETURN_T:
        ...


@runtime_checkable
class WebAudioGetterInterface(Protocol):
    config: LoadableConfig

    @staticmethod
    def get(word: str, card_data: dict) -> AUDIO_SCRAPPER_RETURN_T:
        ...


@runtime_checkable
class CardProcessorInterface(Protocol):
    @staticmethod
    def get_save_image_name(word: str,
                            image_source: str,
                            image_parser_name: str,
                            card_data: dict) -> str:
        ...

    @staticmethod
    def get_card_image_name(saved_image_path: str) -> str:
        ...

    @staticmethod
    def get_save_audio_name(word: str,
                            audio_provider: str,
                            uniqueness_postfix: str,
                            card_data: dict) -> str:
        ...

    @staticmethod
    def get_card_audio_name(saved_audio_path: str) -> str:
        ...

    @staticmethod
    def process_card(card: dict) -> None:
        ...


@runtime_checkable
class DeckSavingFormatInterface(Protocol):
    config: LoadableConfig

    @staticmethod
    def save(deck: SavedDataDeck,
             saving_card_status: CardStatus,
             saving_path: str,
             image_names_wrapper: Callable[[str], str],
             audio_names_wrapper: Callable[[str], str]):
        ...
