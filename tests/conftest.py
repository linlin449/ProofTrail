import pytest

from prooftrail import Metadata, build_batch, create_receipt
from prooftrail.chain import Registry


@pytest.fixture
def registry():
    return Registry.local()


@pytest.fixture
def issued(registry):
    content = "一份可移植的研究笔记。\n".encode()
    signed = create_receipt(
        content, Metadata(title="研究笔记"), registry.domain, registry.local_key
    )
    bundle = build_batch([signed])[0]
    registry.anchor(bundle.root, 1, registry.local_key)
    return content, bundle
