from typing import Any, Callable, Union

from ..consts.card_fields import CardFields
from .storages import FrozenDict


class Card(FrozenDict):
    __slots__ = ()

    def __init__(self, card_fields: dict[str, Any] | None = None):
        if card_fields is None:
            super(Card, self).__init__(data={})
            return

        super(Card, self).__init__(data=card_fields)

    def __repr__(self):
        return f"Card {self._data}"

    @staticmethod
    def get_str_dict_tags(card_data: Union[dict, "Card"],
                          prefix: str = "",
                          sep: str = "::",
                          tag_processor: Callable[[str], str] = lambda x: x) -> str:
        if (dictionary_tags := card_data.get(CardFields.dict_tags)) is None:
            return ""

        def traverse_tags_dict(res_container: list[str], current_item: dict, cur_stage_prefix: str = ""):
            nonlocal sep

            for key in current_item:
                cur_prefix = f"{cur_stage_prefix}{tag_processor(key)}{sep}"

                if isinstance((value := current_item[key]), dict):
                    traverse_tags_dict(res_container, value, cur_prefix)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            traverse_tags_dict(res_container, item, cur_prefix)
                        else:
                            res_container.append(f"{cur_prefix}{tag_processor(item)}")
                else:
                    res_container.append(f"{cur_prefix}{tag_processor(value)}")

        tags_container = []
        p = f"{prefix}{sep}" if prefix else ""
        traverse_tags_dict(tags_container, dictionary_tags, cur_stage_prefix=p)
        return " ".join(tags_container)

