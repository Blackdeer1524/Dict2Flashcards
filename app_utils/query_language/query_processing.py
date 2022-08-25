from app_utils.query_language.processing_pipeline import Tokenizer, Token_T, EvaluationTree
from typing import Callable, Mapping, Any


def get_card_filter(expression: str) -> Callable[[Mapping], Any]:
    _tokenizer = Tokenizer(expression)
    tokens = _tokenizer.get_tokens()
    if tokens[0].t_type == Token_T.END:
        return lambda x: True

    _logic_tree = EvaluationTree(tokens)
    _logic_tree.construct()
    return _logic_tree.get_master_node().compute
