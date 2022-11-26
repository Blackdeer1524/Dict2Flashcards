# Dict2Anki
Sentence-mining app written in Python using Tkinter.

# Structure
* [Demonstration](#demonstration)
* [Installation](#installation)
* [Launch](#launch)
* [Hotkeys](#hotkeys)
* [Resulting file](#resulting-file)
* [Plugins](#plugins)
* [Query language documentation](#query-language-documentation)

# [Demonstration](#structure)
![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/start_to_finish_demo.gif)

### [Drag & Drop](#download-images-from-web) 
#### [Image from browser](#drag--drop) 
![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/drag_image_from_browser.gif)
#### [Local image](#drag--drop) 
![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/drag_local_image.gif)
#### [Image link from any text field](#drag--drop) 
![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/drag_image_link.gif)

### [Paste from clipboard](#download-images-from-web) 
Hotkey: **Ctrl + V**
![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/paste_image_from_clipboard.gif)

## [Bury card to watch them later](#demonstration)
![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/bury_and_reopen.gif)

## [Query language](#demonstration)
![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/add_with_query_lang.gif)

![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/search_in_deck_with_query_lang.gif)

[Query language docs](#query-language-documentation)

# [Installation](#structure)
## [Windows](#installation)
1. Install [Python3.11+](https://www.python.org/downloads/) and add it in PATH.
2. Open downloaded directory with mining.pyw in it.
3. Open command line in this directory
4. Run \<pip install -r win_requirements.txt> to install required libraries

## [Linux](#installation)
1. Install Python3.11+
   * sudo apt install python3.11
2. Install Tkinter
   * sudo apt install python3-tk
3. Install PyGObject
   * sudo apt install python3-gi
4. Install required libraries
   * pip3 install -r linux_requirements.txt

# [Launch](#structure)
To launch this app, open command line in the directory where mining.pyw is located and run
* if you are on Windows: python mining.pyw
* if you are on Linux: python3 mining.pyw

# [Hotkeys](#structure)
## [Local](#hotkeys)
* Ctrl + 0: Moves app to upper left corner of the screen
* Ctrl + 1..9: picks corresponding sentence
* Ctrl + d: skips current card
* Ctrl + z: returns to a previous card
* Ctrl + q: moves current card to a separate file
* Ctrl + Shift + a: calls \<add word> window
* Ctrl + e: calls \<statistics> window
* Ctrl + f: calls \<find> window

## [Global](#hotkeys)
* Ctrl + c + Space: adds currently highlighted word to deck

![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/add_word_global_hotkey.gif)

* Ctrl + c + Alt: adds currently highlighted text to the first sentence field

![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/add_highlighted_sentence_global_hotkey.gif)

# [Resulting file](#structure)
By default, resulting file has CSV extention, is located at saving directory that you choosed, and has the following naming convention:
\<deck_name>\_\<session_start_time>.csv

## CSV fields order
 1. Sentence example
 2. Word
 3. Definition
 4. Image
 5. Word audio 
 6. Tags
 
[How to create custom format processor](#format-processors)

# [Card format](#structure)
A Card is essentially a Python dictionary with the following keys:
  * word: str
  * special: list[str]
  * definition: str
  * examples: list[str]
  * image_links: list[str]
  * audio_links: list[str]
  * tags: dict[str, str | list | dict]

![](https://github.com/Blackdeer1524/Dict2Anki/blob/dev/app_demonstration/card_fields_usage.png)

Cards can have other fields, although they will not be displayed.
But they could be used inside
[format](#format-processors) and [card](#card-processors) processors.

# [Dictionary format](#structure)

\[\[\<word>: str, \<data>: dict], ...]

# [Plugins](#structure)
To view every plugin interface, see **./plugins_loading/interfaces.py**

* [Parsers](#parsers)
    * [Word parsers](#word-parsers)
        * web
        * Local
    * [Sentence parsers](#sentence-parsers)
    * [Image parsers](#image-parsers)
    * [Audio getters](#audio-getters)
        * web
        * Local
* [Saving](#saving)
    * [Card processors](#card-processors)
    * [Format processors](#format-processors)
* [Themes](#themes)
* [Language packages](#language-packages) 
 
Every plugin has to have **config** variable of **LoadableConfig** class 
```
LoadableConfig(config_location: str,
               validation_scheme: dict[Any, tuple[Any, Sequence[Type], Sequence[Any]]],
               docs: str)
```
* config_location has to be os.path.dirname(\__file__)
* validation_scheme:
```
{
   <field>: (<default_value>, [supported_type, ...], [valid_value, ...])
   ...
}
```
suppotred_types and valid values can be empty. **In that case, all types/values are valid**
* docs: config documentation

## [Parsers](#plugins)
### [Word parsers](#parsers) 
#### [web](#word-parsers)  
To create a web parser, create a python file inside **./plugins/parsers/word/web/** with the following protocol:
  * SCHEME_DOCS: str - documentation to the resulting scheme
  * define(word: str) function that returns [dictionary format](#dictionary-format)
  * translate(word: str, word_dict: dict) function that converts [dictionary entry](#dictionary-format) to [card format](#card-format)

#### [Local](#word-parsers)
Parses local JSON dictionary, that is located in **./media** folder

To register a local dictionary, create a python file inside **./plugins/parsers/word/local/** with the following protocol:
  * DICTIONARY_NAME: str - relative path to the JSON dictionary of [dictionary format](#dictionary-format) that is located inside **./media** folder
  * SCHEME_DOCS: str - documentation to the resulting scheme
  * translate(word: str, word_dict: dict) function that converts [dictionary entry](#dictionary-format) to [card format](#card-format)

### [Sentence parsers](#parsers)
To create a sentence parser, create a python file inside **./plugins/parsers/sentence/** with the following protocol:
  * get(word: str) -> Generator\[tuple\[list\[str], str], int, tuple\[list\[str], str]] function that takes word for which
  sentences are needed. This function has to have 2 stages
    * initialization on first next() call
    * current step batch size initialization on \<gen>.send(batch_size) that returns sentence batch of \<batch_size>

### [Image parsers](#parsers)
To create an image parser, create a python file inside **./plugins/parsers/image/** with the following protocol:
  * get(word: str) -> Generator\[tuple\[list\[str], str], int, tuple\[list\[str], str]] function that takes word for which
  images are needed. This function has to have 2 stages
    * initialization on first next() call
    * current step batch size initialization on <gen>.send(batch_size) that returns image links batch of \<batch_size>
 
### [Audio getters](#parsers)
#### [web](#audio-getters)
To register web audio getter, create a python file inside **./plugins/parsers/audio/web/** with the following protocol:
  * get(word: str, card_data: dict) -> tuple\[tuple\[list\[str], list\[str]], str] function that takes 
  word for which audio is needed and current card data for the additional info and returns a list of urls, list of associated to each url information,
  and error message.

#### [Local](#audio-getters)
To register folder with audio files, create a python file inside **./plugins/parsers/audio/local/** with the following protocol:
  * AUDIO_FOLDER: str - relative path to the folder with audio files that is located inside ./media folder
  * get(word: str, card_data: dict) -> tuple\[tuple\[list\[str], list\[str]], str] function that takes 
  word for which audio is needed and current card data for the additional info and returns a list of paths, list of associated to each path information,
  and error message.

## [Saving](#plugins)
### [Card processors](#saving)
You may want to create special card processors to other applications from Anki. These apps may have special requirements for card format. For
Example, to add an audio file to anki, one has to wrap its file name in \[sound:\<filename>].
To create a card processor, create a python file inside **./plugins/saving/card_processors/** with the following protocol:
  * get_save_image_name(word: str, image_source: str, image_parser_name: str, card_data: dict) -> str function that returns saving image file name
  * get_card_image_name(saved_image_path: str) -> str function that returns wrapped saved_image_path (this path is *absolute*)
  * get_save_audio_name(word: str, audio_provider: str, multiple_postfix: str, card_data: dict) -> str function that returns saving audio file name
  * get_card_audio_name(saved_audio_path: str) -> str function that returns wrapped saved_audio_path (this path is *absolute*)
  * process_card(card: dict) -> None function that processes card in-place

### [Format processors](#saving)
Transforms saved card collection to needed file format
To create a format processor, create a python file inside **./plugins/saving/format_processors/** with the following protocol:
  * save(deck: SavedDataDeck,
         saving_card_status: CardStatus,
         saving_path: str,
         image_names_wrapper: Callable\[\[str], str],
         audio_names_wrapper: Callable\[\[str], str]) -> None function that iterates through SavedDataDeck (located in **./app_utils/cards.py**) and 
    pickes cards with saving_card_status from which the format is formed. image_names_wrapper and audio_names_wrapper are wrappers from current 
    card processor

## [Themes](#plugins)
To create a theme, create a python file inside **./plugins/themes/** with the following protocol:
  * label_cfg: dict - Tkinter Label widget config, compatable with Text widget
  * button_cfg: dict - Tkinter Button widget config
  * text_cfg: dict - Tkinter Text widget config
  * entry_cfg: dict - Tkinter Entry widget config
  * checkbutton_cfg: dict - Tkinter Checkbutton widget config
  * toplevel_cfg: dict - Tkinter Toplevel widget config
  * root_cfg: dict - Tkinter Tk config
  * frame_cfg: dict - Tkinter Frame widget config
  * option_menu_cfg: dict - Tkinter OptionMenu widget config
  * option_submenus_cfg: dict - config used to configure submenus of OptionMenu

## [Language packages](#plugins)
To create a language package, create a python file inside **./plugins/language_packages/** with the protocol listed inside 
  **./plugins_loading/interfaces.LanguagePackageInterface** class
 
# [Query language documentation](#structure)
```
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
        $ANY will return ["noun", "verb"]
        pos[$ANY][data] will return [value_1, value_2]
        $ANY[$ANY][data] will also will return [value_1, value_2]

    $SELF
        Gets current hierarchy level keys
        Example:
            {
                "field_1": 1,
                "field_2": 2,
            }
        $SELF will return [["field_1", "field_2"]]

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

        array_field[d_$1] will return 2
        int_field[d_$1] will return [4, 5, 6]

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

        f_$d_$1 will return [1, 2, 3]
        You would need to also use d_$ prefix, because as 1 would be converted to
        a <field> type, it would also be treated as a string
        Note:
            to get [4, 5, 6] from this scheme you would only need d_$ prefix:
            d_$2[data]

Methods:
    len
        Measures length of iterable object
        Example:
            {
                "field": [1, 2, 3]
            }
        len(field) will return 3
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

    any
        Returns True if one of items is True
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
       any(field[$ANY][data] > 1) will return True

    all
        Returns True if all items are True
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
        all($ANY[$ANY][data] > 0) will return True
        all($ANY[$ANY][data] > 1) will return False

    lower
        Makes all strings lowercase, discarding non-string types
        Example:
            {
                "field_1": ["ABC", "abc", "AbC", 1],
                "field_2": [["1", "2", "3"]],
                "field_3": "ABC"
            }
        lower(field_1) will return ["abc", "abc", "abc", ""]
        lower(field_2) will return [""]
        lower(field_3) will return "abc"

    upper
        Makes all strings uppercase, discarding non-string types
        Example:
            {
                "field_1": ["ABC", "abc", "AbC", 1],
                "field_2": [["1", "2", "3"]],
                "field_3": "abc"Linux
            }
        upper(field_1) will return ["ABC", "ABC", "ABC", ""]
        upper(field_2) will return [""]
        upper(field_3) will return "ABC"

    reduce
        Flattens one layer of nested list result:
        Example:
            {
                "field_1": ["a", "b", "c"],
                "field_2": ["d", "e", "f"]
            }
        $ANY will return [["a", "b", "c"], ["d", "e", "f"]]
        reduce($ANY) will return ["a", "b", "c", "d", "e", "f"]
        Note:
            {
                "field_1": [["a"], ["b"], ["c"]],
                "field_2": [[["d"], ["e"], ["f"]]]
            }
        $ANY will return [[["a"], ["b"], ["c"]], [[["d"], ["e"], ["f"]]]]
        reduce($ANY) will return [["a"], ["b"], ["c"], [["d"], ["e"], ["f"]]]

    Note:
        You can also combine methods:
        Example:
            {
                "field_1": ["ABC", "abc", "AbC"],
                "field_2": ["Def", "dEF", "def"]
            }
        lower(reduce($ANY)) will return ["abc", "abc", "abc", "def", "def", "def"]

Evaluation precedence:
1) expressions in parentheses
2) keywords, methods
3) unary operators
4) binary operators
```
