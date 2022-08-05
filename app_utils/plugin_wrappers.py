from typing import Callable, Any, Generator, TypeVar, Generic, Optional


GeneratorYieldType = TypeVar("GeneratorYieldType")
ExternalDataGenerator = Generator[GeneratorYieldType, int, GeneratorYieldType]


class ExternalDataFetcherWrapper(Generic[GeneratorYieldType]):
    def __init__(self,
                 data_fetcher: Callable[[str, dict], ExternalDataGenerator]):
        self._word: str = ""
        self._card_data: dict = {}
        self._sentences: list[str] = []
        self._data_fetcher: Callable[[str, dict], Any] = data_fetcher
        self._update_status: bool = False
        self._start()

    def _start(self):
        self._data_generator: ExternalDataGenerator = self._get_data_generator()
        next(self._data_generator)

    def _update(self, word: str, card_data: dict):
        if self._word != word or self._card_data != card_data:
            self._word = word
            self._card_data = card_data
            self._start()
            self._update_status = True

    def _get_data_generator(self) -> ExternalDataGenerator:
        """
        Yields: Sentence_batch, error_message
        """
        batch_size = yield

        data_generator = self._data_fetcher(self._word, self._card_data)
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
        self._update(word=word, card_data=card_data)
        try:
            return self._data_generator.send(batch_size)
        except StopIteration:
            return None
