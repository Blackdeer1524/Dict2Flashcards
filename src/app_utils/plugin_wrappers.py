from dataclasses import dataclass, field
from typing import Generator, Generic, Optional, Protocol, TypeVar

from ..plugins_management.config_management import Config

GeneratorYieldType = TypeVar("GeneratorYieldType")
ExternalDataGenerator = Generator[GeneratorYieldType, int, GeneratorYieldType]


@dataclass(slots=True)
class ExternalDataGeneratorWrapper(Generic[GeneratorYieldType]):
    class DataGeneratorProtocol(Protocol):
        name: str
        config: Config

        def get(self, word: str, card_data: dict) -> ExternalDataGenerator:
            ...

    data_generator: DataGeneratorProtocol

    _word: str = field(init=False, default="")
    _card_data: dict = field(init=False, default_factory=dict)
    _update_status: bool = field(init=False, default=False)
    _data_generator: ExternalDataGenerator = field(init=False)

    def __post_init__(self):
        self._start()

    def _start(self):
        self._data_generator = self._get_data_generator()
        next(self._data_generator)

    def force_update(self, word: str, card_data: dict):
        self._word = word
        self._card_data = card_data
        self._update_status = True
        self._start()

    def _get_data_generator(self) -> ExternalDataGenerator:
        """
        Yields: Sentence_batch, error_message
        """
        batch_size = yield

        data_generator = self.data_generator.get(self._word, self._card_data)
        try:
            next(data_generator)
        except StopIteration as e:
            yield e.value
            return

        self._update_status = False
        while True:
            try:
                batch_size = yield data_generator.send(batch_size)
                if self._update_status :
                    break
            except StopIteration as e:
                yield e.value
                return

    def get(self, word: str, card_data:dict, batch_size: int) -> Optional[GeneratorYieldType]:
        if self._word != word or self._card_data != card_data:
            self.force_update(word, card_data)

        try:
            return self._data_generator.send(batch_size)
        except StopIteration:
            return None
