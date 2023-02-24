from ..consts.paths import SYSTEM
from typing import Callable
from abc import ABC, abstractmethod


__all__ = "Binder"


class BinderProto(ABC):
    @abstractmethod
    def bind(*key_seq: str, action: Callable[[], None]) -> None:
        ...

    @abstractmethod
    def start(self) -> None:
        ...
    
    @abstractmethod
    def stop(self) -> None:
        ...


if SYSTEM == "Windows":
    from global_hotkeys import (register_hotkeys, start_checking_hotkeys,
                                stop_checking_hotkeys, clear_hotkeys)

    class Binder(BinderProto):
        def __init__(self):
            self.bindings: list[tuple[list[str], None, Callable[[], None]]] = []

        def bind(self, *key_seq, action):
            self.bindings.append(([i.lower() for i in key_seq], None, action))

        def start(self):
            register_hotkeys(self.bindings)
            start_checking_hotkeys()

        def stop(self):
            clear_hotkeys()
            stop_checking_hotkeys()
else:
    from bindglobal import BindGlobal

    class Binder(BinderProto):
        def __init__(self):
            self.binds: list[tuple[str, Callable[[], None]]] = []

        def bind(self, *key_seq, action):
            seq = "<{}>".format("-".join(key_seq))
            self.binds.append((seq, action))

        def start(self):
            self.bg = BindGlobal()
            for seq, action in self.binds:
                self.bg.gbind(seq, lambda _, t=action: t())

        def stop(self):
            self.bg.stop()
