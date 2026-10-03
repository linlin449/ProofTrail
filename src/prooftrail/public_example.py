"""Public synthetic bytes and receipt, never a cached verification verdict."""

import json
from importlib.resources import files

from .models import ReceiptBundle


def public_example(registry):
    if registry.mode != "monad":
        return None
    example = json.loads(files("prooftrail").joinpath("data/public-example.json").read_text("utf-8"))
    bundle = ReceiptBundle.model_validate(example["bundle"])
    if bundle.domain != registry.domain:
        return None
    return example
