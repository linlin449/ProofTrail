import copy

import pytest
from eth_utils import keccak

from prooftrail import ReceiptBundle, verify_receipt


@pytest.mark.parametrize("index", range(12))
def test_corrupted_signature_never_crashes(registry, issued, index):
    content, bundle = issued
    data = copy.deepcopy(bundle.model_dump())
    raw = keccak(bytes([index])) + keccak(bytes([index + 20])) + b"\x1b"
    data["signature"] = "0x" + raw.hex()
    assert verify_receipt(content, ReceiptBundle.model_validate(data), registry).status == "invalid"


def test_idle_local_chain_tracks_wall_clock(registry, monkeypatch):
    import time

    from prooftrail import Metadata, build_batch, create_receipt

    later = int(time.time()) + 600
    monkeypatch.setattr("prooftrail.chain.time.time", lambda: later)
    signed = create_receipt(
        b"after idle", Metadata(title="later"), registry.domain, registry.local_key, issued_at=later
    )
    bundle = build_batch([signed])[0]
    registry.anchor(bundle.root, 1, registry.local_key)
    assert registry.get_batch(bundle.batchId)[3] >= later
    assert verify_receipt(b"after idle", bundle, registry, now=later).status == "valid"
