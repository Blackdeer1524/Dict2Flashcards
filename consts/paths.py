import os
from pathlib import Path
from platform import system


ROOT_DIR = Path(os.path.abspath(__file__)).parent.parent
TEMP_DIR = ROOT_DIR / "temp"
CARDS_DIR = ROOT_DIR / "Cards"
WORDS_DIR = ROOT_DIR / "Words"
LOCAL_MEDIA_DIR = ROOT_DIR / "media"
HISTORY_FILE_PATH = ROOT_DIR / "history.json"
CONFIG_FILE_PATH = ROOT_DIR / "config.json"

CHAIN_DATA_DIR = ROOT_DIR / "chaining_data"
CHAIN_DATA_FILE_PATH = CHAIN_DATA_DIR / "chains.json"
CHAIN_CONFIGS_DIR = CHAIN_DATA_DIR / "configs"
CHAIN_WORD_PARSERS_DATA_DIR = CHAIN_CONFIGS_DIR / "word_parsers"
CHAIN_SENTENCE_PARSERS_DATA_DIR = CHAIN_CONFIGS_DIR / "sentence_parsers"
CHAIN_IMAGE_PARSERS_DATA_DIR = CHAIN_CONFIGS_DIR / "image_parsers"
CHAIN_AUDIO_GETTERS_DATA_DIR = CHAIN_CONFIGS_DIR / "audio_getters"

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
