"""Levee seepage-safety evaluation service (Chapter 5 rule chain) with a JSON/HTTP interface.

    from levee_eval import evaluate, evaluate_batch, validate
    response = evaluate(request_dict)
"""

from .engine import API_VERSION, MODEL_INFO, RequestInvalid, evaluate, evaluate_batch, meta
from .schema import validate

__all__ = ["API_VERSION", "MODEL_INFO", "RequestInvalid", "evaluate", "evaluate_batch", "meta", "validate"]
__version__ = API_VERSION
