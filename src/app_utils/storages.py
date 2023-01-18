import copy
from json import JSONEncoder
from typing import Any, Generic, Mapping, TypeVar, Sequence
from functools import singledispatchmethod


class _FrozenDictNode(Mapping):
    __slots__ = "_data"

    def __init__(self, data: dict[Any, Any]):
        self._data = data

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):
        return self._data[item]

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return str(self._data)

    def __bool__(self):
        return bool(self._data)

    def to_dict(self):
        return self._data


class FrozenDict(_FrozenDictNode):
    __slots__ = ()

    def __init__(self, data: dict[Any, Any]):
        def _convert_to_frozen_node(master: dict, master_key: Any, proc_unit: Any):
            if isinstance(proc_unit, dict):
                for proc_key in proc_unit:
                    if isinstance((proc_val := proc_unit[proc_key]), dict):
                        _convert_to_frozen_node(proc_unit, proc_key, proc_val)
                master[master_key] = _FrozenDictNode(proc_unit)
            else:
                master[master_key] = proc_unit

        master_dict = copy.deepcopy(data)
        for key in master_dict:
            _convert_to_frozen_node(master_dict, key, master_dict[key])

        super(FrozenDict, self).__init__(data=master_dict)

    def to_dict(self):
        def convert(data: _FrozenDictNode):
            # you make a deepcopy so that you wouldn't overwrite original _data
            a = copy.deepcopy(data._data)
            for key in a:
                if isinstance((value:=a[key]), _FrozenDictNode):
                    value = convert(value)
                    a[key] = value
            return a
        return convert(self)


class FrozenDictJSONEncoder(JSONEncoder):
    def default(self, o):
        return o.to_dict()


T = TypeVar("T")
DEFAULT_T = TypeVar("DEFAULT_T")
class PointerList(Generic[T, DEFAULT_T]):
    __slots__ = "_data", "_starting_position", "_pointer_position", "_default_return_value"

    def __init__(self, 
                 data: list[T] | None = None,
                 starting_position: int = 0,
                 default_return_value: DEFAULT_T | None = None):
        self._data: list[T] = data if data is not None else []
        self._starting_position = min(len(self._data), starting_position)
        self._pointer_position: int = self._starting_position
        self._default_return_value: Any = default_return_value

    def __len__(self):
        return len(self._data)

    def __bool__(self):
        return bool(self._data)

    @singledispatchmethod
    def __getitem__(self, item):
        raise NotImplementedError("__getitem__ not implemented")
    
    @__getitem__.register
    def _(self, item: int) -> T | DEFAULT_T:
        return self._data[item] if self._starting_position <= item < len(self) \
                                else self._default_return_value

    @__getitem__.register
    def _(self, item: slice) -> Sequence[T | DEFAULT_T]:
        return self._data[item]

    def __iter__(self):
        return (self._data[i] for i in range(self._starting_position, len(self._data)))

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

    def get_pointed_item(self) -> T | DEFAULT_T:
        return self[self._pointer_position]

    def move(self, n: int) -> None:
        self._pointer_position = min(max(self._pointer_position + n, self.get_starting_position()), len(self))


def main():
    a = PointerList(data=[(1, 2), (2, 3), (3, 4), (4, 5)],
                default_return_value=(0, 0))

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

    frozen_check = FrozenDict(data=checking)
    checking_queue = [(checking, frozen_check)]
    while checking_queue:
        src, frozen_src = checking_queue.pop()
        assert len(src) == len(frozen_src)
        for src_key, frozen_src_key in zip(sorted(list(src.keys()),        key=lambda x: str(x)),
                                           sorted(list(frozen_src.keys()), key=lambda x: str(x))):
            assert src_key == frozen_src_key
            src_val        = src[src_key]
            frozen_src_val = frozen_src[frozen_src_key]
            if isinstance(src_val, dict):
                checking_queue.append((src_val, frozen_src_val))
            else:
                assert src_val == frozen_src_val

    # validate_json(checking, standard_conf_file)
    # assert checking == standard_conf_file


if __name__ == "__main__":
    main()

