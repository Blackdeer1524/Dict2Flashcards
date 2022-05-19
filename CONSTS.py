from pathlib import Path
import os
from platform import system

HISTORY_FILE_PATH = Path("./history.json")
CONFIG_FILE_PATH = Path("./config.json")
USER_FOLDER = Path(os.path.expanduser("~"))
CURRENT_SYSTEM = system()
if CURRENT_SYSTEM == "Linux":
    STANDARD_ANKI_MEDIA = USER_FOLDER / ".local/share/Anki2/"
elif CURRENT_SYSTEM == "Windows":
    STANDARD_ANKI_MEDIA = USER_FOLDER / "AppData/Roaming/Anki2/"
else:
    STANDARD_ANKI_MEDIA = "./"
STANDARD_ANKI_MEDIA = Path(STANDARD_ANKI_MEDIA)
if not STANDARD_ANKI_MEDIA.exists():
    STANDARD_ANKI_MEDIA = Path("./")
