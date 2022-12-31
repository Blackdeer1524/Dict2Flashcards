from typing import Any, Callable, Mapping

from .processing_pipeline import EvaluationTree, Token_T, Tokenizer


def get_card_filter(expression: str) -> Callable[[Mapping], Any]:
    _tokenizer = Tokenizer(expression)
    tokens = _tokenizer.get_tokens()
    if tokens[0].t_type == Token_T.END:
        return lambda x: True

    _logic_tree = EvaluationTree(tokens)
    _logic_tree.construct()
    return _logic_tree.get_master_node().compute
