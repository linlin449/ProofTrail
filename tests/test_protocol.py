import copy
import time

import pytest
from eth_account import Account
from pydantic import ValidationError

from prooftrail import Metadata, ReceiptBundle, build_batch, create_receipt, verify_receipt
from prooftrail.models import Domain
from prooftrail.protocol import ZERO_HASH, proof_valid


def modify(bundle, **changes):
    data = copy.deepcopy(bundle.model_dump())
    for key, value in changes.items():
        if "." in key:
            group, field = key.split(".")
            data[group][field] = value
        else:
            data[key] = value
    return ReceiptBundle.model_validate(data)


def test_receipt_valid_and_independent(registry, issued):
    content, bundle = issued
    imported = ReceiptBundle.model_validate_json(bundle.model_dump_json())
    result = verify_receipt(content, imported, registry)
    assert result.status == "valid"
    assert all(check.passed for check in result.checks)
    assert result.anchoredAt is not None


@pytest.mark.parametrize("suffix", [b" ", b"\n", "新增".encode()])
def test_original_bytes_are_exact(registry, issued, suffix):
    content, bundle = issued
    result = verify_receipt(content + suffix, bundle, registry)
    assert result.status == "invalid"
    assert not next(c for c in result.checks if c.key == "content").passed
    assert next(c for c in result.checks if c.key == "signature").passed


@pytest.mark.parametrize(
    "change",
    [
        {"metadata.title": "伪造标题"},
        {"metadata.application": "另一应用"},
        {"metadata.model": "冒名模型"},
        {"metadata.mediaType": "image/png"},
        {"claim.parentId": "0x" + "ab" * 32},
        {"claim.salt": "0x" + "cd" * 32},
        {"claim.issuedAt": 0},
        {"claim.expiresAt": 1},
        {"claim.contentHash": "0x" + "01" * 32},
        {"claim.metadataHash": "0x" + "02" * 32},
        {"receiptId": "0x" + "03" * 32},
        {"batchCount": 2},
        {"root": "0x" + "04" * 32},
        {"batchId": "0x" + "05" * 32},
        {"signature": "0x" + "00" * 65},
        {"proof": ["0x" + "06" * 32]},
    ],
)
def test_tampered_fields_fail(registry, issued, change):
    content, bundle = issued
    assert verify_receipt(content, modify(bundle, **change), registry).status == "invalid"


@pytest.mark.parametrize(
    "change",
    [
        {"domain.chainId": 10143},
        {"domain.verifyingContract": "0x" + "12" * 20},
    ],
)
def test_wrong_trusted_domain_never_queries_chain(registry, issued, change, monkeypatch):
    content, bundle = issued

    def forbidden(*args):
        raise AssertionError("must not query a domain chosen by the receipt")

    monkeypatch.setattr(registry, "get_batch", forbidden)
    assert verify_receipt(content, modify(bundle, **change), registry).status == "invalid"


def test_rpc_failure_is_not_valid(registry, issued, monkeypatch):
    content, bundle = issued

    def offline(*args):
        raise ConnectionError("private endpoint detail")

    monkeypatch.setattr(registry, "get_batch", offline)
    result = verify_receipt(content, bundle, registry)
    assert result.status == "unavailable"
    assert "private endpoint detail" not in result.model_dump_json()


def test_local_failures_dominate_rpc_failure(registry, issued, monkeypatch):
    content, bundle = issued
    monkeypatch.setattr(registry, "get_batch", lambda *_: (_ for _ in ()).throw(ConnectionError()))
    assert verify_receipt(content + b"altered", bundle, registry).status == "invalid"


def test_revocation_changes_previously_exported_receipt(registry, issued):
    content, bundle = issued
    exported = bundle.model_dump_json()
    registry.revoke(bundle.receiptId, registry.local_key)
    result = verify_receipt(content, ReceiptBundle.model_validate_json(exported), registry)
    assert result.status == "invalid"
    assert not next(c for c in result.checks if c.key == "revocation").passed


def test_unanchored_signed_receipt_invalid(registry):
    signed = create_receipt(
        b"x", Metadata(title="not anchored"), registry.domain, registry.local_key
    )
    assert verify_receipt(b"x", build_batch([signed])[0], registry).status == "invalid"


@pytest.mark.parametrize("size", [1, 2, 3, 4, 7, 16, 32])
def test_batch_every_leaf_verifies(registry, size):
    receipts = [
        create_receipt(
            str(i).encode(), Metadata(title=f"#{i}"), registry.domain, registry.local_key
        )
        for i in range(size)
    ]
    bundles = build_batch(receipts)
    assert all(proof_valid(bundle) for bundle in bundles)
    registry.anchor(bundles[0].root, size, registry.local_key)
    assert all(
        verify_receipt(str(i).encode(), b, registry).status == "valid"
        for i, b in enumerate(bundles)
    )


def test_duplicate_leaves_rejected(registry):
    signed = create_receipt(b"x", Metadata(title="x"), registry.domain, registry.local_key)
    with pytest.raises(ValueError, match="重复"):
        build_batch([signed, signed])


def test_mixed_issuers_rejected(registry):
    a = create_receipt(b"x", Metadata(title="x"), registry.domain, registry.local_key)
    b = create_receipt(b"x", Metadata(title="x"), registry.domain, Account.create().key)
    with pytest.raises(ValueError, match="发行者"):
        build_batch([a, b])


def test_expiry_and_future_time(registry):
    now = int(time.time())
    signed = create_receipt(
        b"x",
        Metadata(title="expires"),
        registry.domain,
        registry.local_key,
        issued_at=now,
        expires_at=now + 10,
    )
    bundle = build_batch([signed])[0]
    registry.anchor(bundle.root, 1, registry.local_key)
    assert verify_receipt(b"x", bundle, registry, now=now + 5).status == "valid"
    assert verify_receipt(b"x", bundle, registry, now=now + 10).status == "invalid"
    assert verify_receipt(b"x", bundle, registry, now=now - 1).status == "invalid"


def test_high_s_malleability_rejected(registry, issued):
    content, bundle = issued
    raw = bytes.fromhex(bundle.signature[2:])
    order = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    high_s = order - int.from_bytes(raw[32:64])
    changed = raw[:32] + high_s.to_bytes(32) + bytes([55 - raw[-1]])
    assert (
        verify_receipt(content, modify(bundle, signature="0x" + changed.hex()), registry).status
        == "invalid"
    )


def test_strict_schema_and_limits(issued):
    _, bundle = issued
    for changes in [
        {"unknown": True},
        {"batchCount": "1"},
        {"batchCount": True},
        {"proof": [ZERO_HASH] * 13},
        {"schemaVersion": "prooftrail/2"},
    ]:
        data = bundle.model_dump() | changes
        with pytest.raises(ValidationError):
            ReceiptBundle.model_validate(data)


def test_distinct_domains_change_receipt_id(registry):
    from prooftrail.protocol import receipt_id

    signed = create_receipt(b"x", Metadata(title="x"), registry.domain, registry.local_key)
    other = Domain(chainId=10143, verifyingContract=registry.domain.verifyingContract)
    assert receipt_id(other, signed.claim) != signed.receiptId
