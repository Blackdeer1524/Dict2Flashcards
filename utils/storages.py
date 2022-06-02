import abc
from typing import Any, TypeVar


_T = TypeVar("_T")
class PointerList:
    def __init__(self, data: list[_T] = None,
                 starting_position: int = 0,
                 default_return_value: Any = None):
        self._data: list[_T] = data if data is not None else []
        self._starting_position = min(max(len(self._data) - 1, 0),
                                      max(0, starting_position))
        self._starting_position: int = self._starting_position
        self._pointer_position: int = self._starting_position
        self._default_return_value: Any = default_return_value

    def __len__(self):
        return len(self._data)

    def __bool__(self):
        return bool(self._data)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._data[item] if self._starting_position <= item < len(self) \
                                    else self._default_return_value
        elif isinstance(item, slice):
            return self._data[item]

    def __repr__(self):
        res = f"Name: {self.__class__.__name__}\n" \
              f"Length: {len(self)}\n" \
              f"Starting pointer position: {self._starting_position}\n" \
              f"Current pointer position: {self._pointer_position}\n"
        for index, item in enumerate(self, 0):
            if index == self._pointer_position or index == self._starting_position:
                res += "C" if index == self._pointer_position else " "
                res += "S" if index == self._starting_position else " "
                res += " --> "
            else:
                res += " " * 7
            res += f"{index}: {item}\n"
            if index == len(self):
                break
        return res

    def get_starting_position(self) -> int:
        return self._starting_position

    def get_pointer_position(self) -> int:
        return self._pointer_position

    def get_pointed_item(self) -> Any:
        return self[self._pointer_position]

    def move(self, n: int):
        self._pointer_position = min(max(self._pointer_position + n, 0), len(self))

    def save(self, *args, **kwargs):
        raise NotImplementedError


def validate_json(checking_scheme: dict[Any, Any], default_scheme: dict[Any, Any]) -> None:
    check_queue: list[tuple[dict[Any, Any], dict[Any, Any]], ...] = [(checking_scheme, default_scheme)]

    for (checking_part, default_part) in check_queue:
        default_keys = set(default_part)

        checking_keys = list(checking_part)
        for c_key in checking_keys:
            if c_key in default_keys:
                if type(checking_part[c_key]) != type(default_part[c_key]):
                    checking_part[c_key] = default_part[c_key]
                elif isinstance(checking_part[c_key], dict):
                    check_queue.append((checking_part[c_key], default_part[c_key]))
                default_keys.remove(c_key)
            else:
                checking_part.pop(c_key)
        del checking_keys

        for d_key in default_keys:
            c_value = checking_part.get(d_key)
            d_value = default_part[d_key]
            if isinstance(d_value, dict) and isinstance(c_value, dict):
                check_queue.append((c_value, d_value))
            elif type(c_value) != type(default_part[d_key]):
                checking_part[d_key] = default_part[d_key]


def main():
    from pprint import pprint

    standard_conf_file = {"app": {"theme": "dark",
                                  "main_window_geometry": "500x800+0+0",
                                  "image_search_position": "+0+0"},
                          "scrappers": {"base_sentence_parser": "web_sentencedict",
                                        "word_parser_type": "web",
                                        "word_parser_name": "cambridge_US",
                                        "base_image_parser": "google",
                                        "local_search_type": 0,
                                        "local_audio": "",
                                        "non_pos_specific_search": False},
                          "directories": {"media_dir": "",
                                          "last_open_file": "",
                                          "last_save_dir": ""},
                          "anki": {"anki_deck": "",
                                   "anki_field": ""}
                          }
    checking = {"app": {1: 2,
                         "theme": "dark",
                                  "main_window_geometry": "500x800+0+0",
                                  "image_search_position": "+0+0"},
                         "scrappers": {"base_sentence_parser": "web_sentencedict",
                                        "word_parser_type": "web",
                                        "word_parser_name": "cambridge_US",
                                        "base_image_parser": "google",
                                        "local_search_type": 0,
                                        "local_audio": "",
                                        "non_pos_specific_search": False},
                         "directories": {"media_dir": "",
                                          "last_open_file": "",
                                          "last_save_dir": ""},
                         "anki": {1: {3: 2},
                                   "anki_deck": "",
                                   "anki_field": {1: 2}}
                         }
    validate_json(checking, standard_conf_file)
    pprint(checking)
    assert checking == standard_conf_file


if __name__ == "__main__":
    main()

