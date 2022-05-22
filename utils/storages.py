from typing import Any, TypeVar


_T = TypeVar("_T")
class PointerList:
    def __init__(self, data: list[_T] = None,
                 starting_position: int = 0,
                 default_return_value: Any = None):
        self._data: list[Any] = data if data is not None else []
        self._starting_position = min(max(len(self._data) - 1, 0),
                                      max(0, starting_position))
        self._starting_position: int = self._starting_position
        self._pointer_position: int = self._starting_position
        self._default_return_value: Any = default_return_value

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._data[item] if self._starting_position <= item < len(self) \
                                    else self._default_return_value
        elif isinstance(item, slice):
            return self._data[item]

    def __repr__(self):
        res = f"Length: {len(self)}\n" \
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
