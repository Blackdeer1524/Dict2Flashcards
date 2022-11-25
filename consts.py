from enum import StrEnum, auto
import os
from pathlib import Path
from platform import system


class CardFields(StrEnum):
    word: str = "word"
    special: str = "special"
    definition: str = "definition"
    sentences: str = "examples"
    img_links: str = "image_links"
    audio_links: str = "audio_links"
    dict_tags: str = "tags"


class ParserTypes(StrEnum):
    web = auto()
    local = auto()
    chain = auto()


# Project structure
ROOT_DIR = Path(os.path.abspath(__file__)).parent.parent
CARDS_DIR = ROOT_DIR / "Cards"
os.makedirs(CARDS_DIR, exist_ok=True)
WORDS_DIR = ROOT_DIR / "Words"
os.makedirs(WORDS_DIR, exist_ok=True)

# Local media
TEMP_DIR = ROOT_DIR / "temp"
os.makedirs(TEMP_DIR, exist_ok=True)
LOCAL_MEDIA_DIR = ROOT_DIR / "media"
os.makedirs(LOCAL_MEDIA_DIR, exist_ok=True)
LOCAL_AUDIO_DIR = LOCAL_MEDIA_DIR / "Audio"
os.makedirs(LOCAL_AUDIO_DIR, exist_ok=True)
LOCAL_DICTIONARIES_DIR = LOCAL_MEDIA_DIR / "Dictionaries"
os.makedirs(LOCAL_DICTIONARIES_DIR, exist_ok=True)

# Plugins
PLUGINS_DIR = ROOT_DIR / "plugins"
os.makedirs(PLUGINS_DIR, exist_ok=True)
LANGUAGE_PACKAGES_DIR = PLUGINS_DIR / "language_packages"
os.makedirs(LANGUAGE_PACKAGES_DIR, exist_ok=True)

PARSERS_PLUGINS_DIR = PLUGINS_DIR / "parsers"
os.makedirs(PARSERS_PLUGINS_DIR, exist_ok=True)
WORD_PARSERS_PLUGINS_DIR = PARSERS_PLUGINS_DIR / "word"
os.makedirs(WORD_PARSERS_PLUGINS_DIR, exist_ok=True)
AUDIO_PARSERS_PLUGINS_DIR = PARSERS_PLUGINS_DIR / "audio"
os.makedirs(AUDIO_PARSERS_PLUGINS_DIR, exist_ok=True)
SENTENCE_PARSERS_PLUGINS_DIR = PARSERS_PLUGINS_DIR / "sentence"
os.makedirs(SENTENCE_PARSERS_PLUGINS_DIR, exist_ok=True)
IMAGE_PARSERS_PLUGINS_DIR = PARSERS_PLUGINS_DIR / "image"
os.makedirs(IMAGE_PARSERS_PLUGINS_DIR, exist_ok=True)

SAVING_METHODS_DIR = PLUGINS_DIR / "saving"
os.makedirs(SAVING_METHODS_DIR, exist_ok=True)
CARD_PROCESSORS_DIR = SAVING_METHODS_DIR / "card_processors"
os.makedirs(CARD_PROCESSORS_DIR, exist_ok=True)
FORMAT_PROCESSORS_DIR = SAVING_METHODS_DIR / "format_processors"
os.makedirs(FORMAT_PROCESSORS_DIR, exist_ok=True)
THEMES_DIR = PLUGINS_DIR / "themes"
os.makedirs(THEMES_DIR, exist_ok=True)

CONFIGURATIONS_DIR = ROOT_DIR / "configurations"
os.makedirs(CONFIGURATIONS_DIR, exist_ok=True)
HISTORY_FILE_PATH = CONFIGURATIONS_DIR / "history.json"
CONFIG_FILE_PATH = CONFIGURATIONS_DIR / "config.json"
CHAIN_DATA_DIR = CONFIGURATIONS_DIR / "chaining_data"
os.makedirs(CHAIN_DATA_DIR, exist_ok=True)
CHAIN_DATA_FILE_PATH = CHAIN_DATA_DIR / "chains.json"
CHAIN_CONFIGS_DIR = CHAIN_DATA_DIR / "chain_parsers_configurations"
os.makedirs(CHAIN_CONFIGS_DIR, exist_ok=True)
CHAIN_WORD_PARSERS_DATA_DIR = CHAIN_CONFIGS_DIR / "word"
os.makedirs(CHAIN_WORD_PARSERS_DATA_DIR, exist_ok=True)
CHAIN_SENTENCE_PARSERS_DATA_DIR = CHAIN_CONFIGS_DIR / "sentence"
os.makedirs(CHAIN_SENTENCE_PARSERS_DATA_DIR, exist_ok=True)
CHAIN_IMAGE_PARSERS_DATA_DIR = CHAIN_CONFIGS_DIR / "image"
os.makedirs(CHAIN_IMAGE_PARSERS_DATA_DIR, exist_ok=True)
CHAIN_AUDIO_GETTERS_DATA_DIR = CHAIN_CONFIGS_DIR / "audio"
os.makedirs(CHAIN_AUDIO_GETTERS_DATA_DIR, exist_ok=True)

USER_FOLDER = Path(os.path.expanduser("~"))
SYSTEM = system()
if SYSTEM == "Linux":
    MEDIA_DOWNLOADING_LOCATION = USER_FOLDER / ".local/share/Anki2/"
elif SYSTEM == "Windows":
    MEDIA_DOWNLOADING_LOCATION = USER_FOLDER / "AppData/Roaming/Anki2/"
else:
    MEDIA_DOWNLOADING_LOCATION = ROOT_DIR

if not MEDIA_DOWNLOADING_LOCATION.exists():
    MEDIA_DOWNLOADING_LOCATION = ROOT_DIR
