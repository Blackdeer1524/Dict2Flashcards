# errors
error_title = "Error"

# main window
main_window_cards_left = "Cards left"

# main menu
create_file_menu_label = "Create"
open_file_menu_label = "Open"
save_files_menu_label = "Save"
hotkeys_and_buttons_help_menu_label = "Buttons/Hotkeys"
query_settings_language_label_text = "Query language"
help_master_menu_label = "Help"
download_audio_menu_label = "Download audio"
change_media_folder_menu_label = "Change downloaded media storage"
file_master_menu_label = "File"

add_card_menu_label = "Add"
search_inside_deck_menu_label = "Find"
added_cards_browser_menu_label = "Browse added"
statistics_menu_label = "Statistics"
settings_themes_label_text = "Theme"
settings_language_label_text = "Language"
settings_configure_anki_button_text = "Anki"
settings_menu_label = "Settings"
settings_image_search_configuration_label_text = "Image search"
setting_web_audio_downloader_configuration_label_text = "web audio downloader"
settings_extern_audio_placer_configuration_label_text = "External audios supply"
settings_extern_sentence_placer_configuration_label = "Enternal sentences supply"
settings_format_processor_configuration_label = "Format processor"
settings_card_processor_label_text = "Card format"
settings_format_processor_label_text = "Saving format"
settings_audio_autopick_label_text = "Audio autochoose"
settings_audio_autopick_off = "Off"
settings_audio_autopick_first_default_audio = "First dictionary audio"
settings_audio_autopick_all_default_audios = "All dictionary audios"
settings_audio_autopick_first_available_audio = "First available audio"
settings_audio_autopick_first_available_audio_source = "First available audio source"
settings_audio_autopick_all = "All"

chain_management_menu_label = "Chains"
chain_management_word_parsers_option = "Word parsers"
chain_management_sentence_parsers_option = "Sentence parsers"
chain_management_image_parsers_option = "Image parsers"
chain_management_audio_getters_option = "Audio getters"
chain_management_chain_type_label_text = "Chain type"
chain_management_existing_chains_treeview_name_column = "Name"
chain_management_existing_chains_treeview_chain_column = "Chain"
chain_management_pop_up_menu_edit_label = "Edit"
chain_management_pop_up_menu_remove_label = "Remove"
chain_management_chain_name_entry_placeholder = "Chain name"
chain_management_empty_chain_name_entry_message = "Empty chain name!"
chain_management_chain_already_exists_message = "Chain with this name already exists!"
chain_management_save_chain_button_text = "Save"
chain_management_close_chain_building_button_text = "Close"
chain_management_call_chain_building_button_text = "Build"
chain_management_close_chain_type_selection_button = "Close"

exit_menu_label = "Exit"

# widgets
anki_button_text = "Anki"
browse_button_text = "Find in browser"
word_text_placeholder = "Word"
definition_text_placeholder = "Definition"
bury_button_text = "Bury"
fetch_images_button_normal_text = "Add image"
fetch_images_button_image_link_encountered_postfix = "★"
fetch_audio_data_button_text = "Load audio"
audio_search_entry_text = "Audio query"
fetch_ext_sentences_button = "Add sentences"
sentence_search_entry_text = "Sentence query"
sentence_text_placeholder_prefix = "Sentence"
user_tags_field_placeholder = "Tags"

# display_audio_on_frame
display_audio_getter_results_audio_not_found_message = "Audio not found"

# choose files
choose_media_dir_message = "Choose downloaded media storage"
choose_deck_file_message = "Choose deck"
choose_save_dir_message = "Choose saving directory"

# create new deck file
create_file_choose_dir_message = "Choose directory for new deck"
create_file_name_entry_placeholder = "File name"
create_file_name_button_placeholder = "Create"
create_file_no_file_name_was_given_message = "No file name was given!"
create_file_file_already_exists_message = "File already exists.\nChoose:"
create_file_skip_encounter_button_text = "Skip"
create_file_rewrite_encounter_button_text = "Replace"

# save files
save_files_message = "Files were saved"

# word definition
card_insertion_limit_exceed_title = "Found too many cards"
card_insertion_limit_exceed_message = "Found too many cards. Are you sure you want to add {} cards?"

# help
buttons_hotkeys_help_message = """
Buttons:
* <:    returns to a previous card
* Bury: moves current card to a separate file which is located in the saving directory. Name of this file would be the same as the saved cards file name + "_buried" postfix 
* >:   skips current card
* >>>: skips all remaining cards

Hotkeys (local):
* Ctrl + ` | Ctrl + Enter: skips current card if no sentences were chosen or creates card(s) with chosen sentences 
* Ctrl + 0:                moves app to upper left corner of the screen
* Ctrl + 1..9:             chooses n-th sentence
* Ctrl + d:                skips current card
* Ctrl + Shift + d:        skips all remaining cards
* Ctrl + z:                returns to a previous card
* Ctrl + q:                moves current card to a separate file
* Ctrl + Shift + a:        calls <add word> window
* Ctrl + e:                calls <statistics> window
* Ctrl + b:                invoke added cards browser
* Ctrl + f:                calls <find> window
* Ctrl + v:                pastes image in image browser

Hotkeys (global):
* Ctrl + c + Space: adds currently highlighted word to deck
* Ctrl + c + Alt: adds currently highlighted text to the app as a sentence
"""
buttons_hotkeys_help_window_title = "Help"
word_field_help = "word (str)"
special_field_help = "special term (list[str])"
definition_field_help = "definition (str)"
sentences_field_help = "sentences (list[str])"
img_links_field_help = "image links (list[str])"
audio_links_field_help = "audio links (list[str])"
dict_tags_field_help = "tags (dict)"
query_language_docs = \
"""
Field queries:
    field_1[subfield_1][subfield_2]...[subfield_n]
    returns None if filed(subfield) wasn't found

Logic operators:
    if one of the arguments is None then it is automatically converted to False

    Unary operators:
    * logic operators:
        not

    Binary operators:
    * logic operators
        and, or
    * arithmetics operators:
        <, <=, >, >=, ==, !=

Keywords:
    in
        Checks whether <thing> is in <field>[<subfield_1>][...][<subfield_n>]
        returns False if argument is None

        Example:
            {
                "field": [val_1, .., val_n]}
            }

        thing in field
        Returns True if thing is in [val_1, .., val_n]


Special queries & commands
    $ANY
        Gets result from the whole hierarchy level

        Example:
            {
                "pos": {
                    "noun": {
                        "data": value_1
                    },
                    "verb" : {
                        "data": value_2
                    }
                }
            }

        $ANY returns ["noun", "verb"]
        pos[$ANY][data] returns [value_1, value_2]
        $ANY[$ANY][data] will also returns [value_1, value_2]

    $SELF
        Gets current hierarchy level keys

        Example:
            {
                "field_1": 1,
                "field_2": 2,
            }
        
        $SELF returns ["field_1", "field_2"]

    d_$
        Will convert string expression to a digit.

        By default, every key inside query strings
        (for example, in field[subfield] the keys are field and subfield)
        are treated as strings. If you have an integer/float key or an array
        with specific index, then you would need to use this prefix

        Example:
            {
                "array_field": [1, 2, 3],
                "int_field": {
                    1: [4, 5, 6]
                }
            }

        array_field[d_$1] returns 2
        int_field[d_$1] returns [4, 5, 6]

    f_$
        Will convert a numeric expression to a field

        By default, every stranded decimal-like strings
        are treated as decimals. So if your scheme contains decimal as a
        key you would need this prefix

        Example:
            {
                1: [1, 2, 3],
                2: {
                    "data": [4, 5, 6]
                }
            }

        f_$d_$1 returns [1, 2, 3]
        You would need to also use d_$ prefix, because as 1 would be converted to
        a <field> type, it would also be treated as a string
        Note:
            to get [4, 5, 6] from this scheme you would only need d_$ prefix:
            d_$2[data]

Methods:
    len
        Measures length of iterable object
        returns 0 if argument is None

        Example:
            {
                "field": [1, 2, 3]
            }

        len(field) returns 3

        Example:
            {
                "field": {
                    "subfield_1": {
                        "data": [1, 2, 3]
                    },
                    "subfield_2": {
                        "data": [4, 5]
                    }
                }
            }

        len(field[$ANY][data]) = len([[1, 2, 3], [4, 5]]) = 2

    split
        Splits given string or list of strings
        returns empty list if argument is None

        Example:
            {
                "field": "text with spaces",
                "list_field": ["text with spaces 1", "text with spaces 2"]
            }

        split(field) = ["text", "with", "spaces"]
        split(list_field) = [["text", "with", "spaces", "1"],
                             ["text", "with", "spaces", "2"]]

    any
        Returns True if one of items is True
        returns False if argument is None

        Example:
            {
                "field": {
                    "subfield_1": {
                        "data": 1
                    },
                    "subfield_2": {
                        "data": 2
                    }
                }
            }

       any(field[$ANY][data] > 1) returns True

    all
        Returns True if all items are True
        returns False if argument is None

        Example:
            {
                "field": {
                    "subfield_1": {
                        "data": 1
                    },
                    "subfield_2": {
                        "data": 2
                    }
                }
            }

        all($ANY[$ANY][data] > 0) returns True
        all($ANY[$ANY][data] > 1) returns False

    lower
        Makes all strings lowercase
        returns empty string ("") if argument is None

        Example:
            {
                "field_1": ["ABC", "abc", "AbC"],
                "field_2": "ABC"
            }
        
        lower(field_1) returns ["abc", "abc", "abc"]
        lower(field_2) returns "abc"

    upper
        Makes all strings uppercase
        returns empty string ("") if argument is None

        Example:
            {
                "field_1": ["ABC", "abc", "AbC"],
                "field_2": "abc"
            }
        
        upper(field_1) returns ["ABC", "ABC", "ABC", ""]
        upper(field_2) returns "ABC"

    reduce
        Flattens one layer of nested list result:
        returns empty list if argument is None

        Example:
            {
                "field_1": ["a", "b", "c"],
                "field_2": ["d", "e", "f"]
            }
        $ANY returns [["a", "b", "c"], ["d", "e", "f"]]
        reduce($ANY) returns ["a", "b", "c", "d", "e", "f"]
        Note:
            {
                "field_1": [["a"], ["b"], ["c"]],
                "field_2": [[["d"], ["e"], ["f"]]]
            }
        $ANY returns [[["a"], ["b"], ["c"]], [[["d"], ["e"], ["f"]]]]
        reduce($ANY) returns [["a"], ["b"], ["c"], [["d"], ["e"], ["f"]]]

    Note:
        You can also combine methods:
        Example:
            {
                "field_1": ["ABC", "abc", "AbC"],
                "field_2": ["Def", "dEF", "def"]
            }
        lower(reduce($ANY)) returns ["abc", "abc", "abc", "def", "def", "def"]

Evaluation precedence:
1) expressions in parentheses
2) keywords, methods
3) unary operators
4) binary operators
"""
query_language_window_title = "Help"
general_scheme_label = "Standard scheme"
current_scheme_label = "Current dictionary scheme"
query_language_label = "Query language syntax"

# download audio
download_audio_choose_audio_file_title = "Choose JSON file with audio data"

# define word
define_word_wrong_regex_message = "Wrong regular expression for word query!"
define_word_word_not_found_message = "Word not found!"
define_word_query_language_error_message_title = "Query error"

# add_word_dialog
add_word_window_title = "Add"
add_word_entry_placeholder = "Word"
add_word_additional_filter_entry_placeholder = "Additional filter"
add_word_start_parsing_button_text = "Add"

# find dialog
find_dialog_empty_query_message = "Empty query!"
find_dialog_wrong_move_message = "Wrong move expression!"
find_dialog_end_rotation_button_text = "Done"
find_dialog_nothing_found_message = "Nothing found!"
find_dialog_find_window_title = "Move"
find_dialog_find_button_text = "Move"

# statistics dialog
statistics_dialog_statistics_window_title = "Statistics"
statistics_dialog_added_label = "Added"
statistics_dialog_buried_label = "Buried"
statistics_dialog_skipped_label = "Skipped"
statistics_dialog_cards_left_label = "Left"
statistics_dialog_current_file_label = "File"
statistics_dialog_saving_dir_label = "Saving directory"
statistics_dialog_media_dir_label = "downloaded media storage"
statistics_dialog_copied_text = "Copied!"

# anki dialog
anki_dialog_anki_window_title = "Anki settings"
anki_dialog_anki_deck_entry_placeholder = "Deck"
anki_dialog_anki_field_entry_placeholder = "Field"
anki_dialog_save_anki_settings_button_text = "Save"

# theme change
restart_app_text = "Changes will take effect when you restart app!"

# program exit
on_closing_message_title = "Exit"
on_closing_message = "Are you sure?"

# call_configuration_window
configuration_window_conf_window_title = "configuration"
configuration_window_restore_defaults_done_message = "Done"
configuration_window_restore_defaults_button_text = "Restore defaults"
configuration_window_cancel_button_text = "Cancel"
configuration_window_bad_json_scheme_message = "Bad JSON scheme"
configuration_window_saved_message = "Saved"
configuration_window_wrong_type_field = "Wrong field type"
configuration_window_wrong_value_field = "Wrong filed value"
configuration_window_missing_keys_field = "Missing keys"
configuration_window_unknown_keys_field = "Unknown keys"
configuration_window_expected_prefix = "Expected"
configuration_window_save_button_text = "Save"

# play_sound
play_audio_playaudio_window_title = "Audio"
play_audio_local_audio_not_found_message = "Local audio not found"
play_audio_no_audio_source_found_message = "No audio source found"

# request anki
request_anki_connection_error_message = "Make sure Anki is open and AnkiConnect addon is installed"
request_anki_general_request_error_message_prefix = "Error log"

# audio downloader
audio_downloader_title = "Downloading..."
audio_downloader_file_exists_message = "File\n {} \n already exists.\n Choose action:"
audio_downloader_skip_encounter_button_text = "Skip"
audio_downloader_rewrite_encounter_button_text = "Replace"
audio_downloader_apply_to_all_button_text = "Apply to all"
audio_downloader_n_errors_message_prefix = "Number of not processed words:"

# image downloader
image_search_title = "Image search"
image_search_start_search_button_text = "Search"
image_search_show_more_button_text = "Show more"
image_search_save_button_text = "Save"
image_search_empty_search_query_message = "Empty search query"
