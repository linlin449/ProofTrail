import pytest
from eth_tester.exceptions import TransactionFailed

from prooftrail import verify_receipt
from prooftrail.chain import Registry
from prooftrail.protocol import ZERO_HASH


def test_anchor_event_and_record(registry, issued):
    _, bundle = issued
    batch = registry.get_batch(bundle.batchId)
    assert batch[0] == bundle.claim.issuer
    assert batch[1].hex() == bundle.root[2:]
    assert batch[2] == 1 and batch[3] > 0
    logs = registry.contract.events.BatchAnchored().get_logs(from_block=0)
    assert len(logs) == 1 and logs[0]["args"]["issuer"] == bundle.claim.issuer


def test_attacker_cannot_revoke_issuer(registry, issued):
    content, bundle = issued
    attacker = registry.w3.eth.accounts[1]
    registry.contract.functions.revoke(bytes.fromhex(bundle.receiptId[2:])).transact(
        {"from": attacker}
    )
    assert registry.is_revoked(attacker, bundle.receiptId)
    assert not registry.is_revoked(bundle.claim.issuer, bundle.receiptId)
    assert verify_receipt(content, bundle, registry).status == "valid"


def test_duplicate_anchor_reverts(registry, issued):
    _, bundle = issued
    with pytest.raises(TransactionFailed):
        registry.anchor(bundle.root, 1, registry.local_key)


@pytest.mark.parametrize(
    "root,count", [(ZERO_HASH, 1), ("0x" + "01" * 32, 0), ("0x" + "01" * 32, 4097)]
)
def test_invalid_batch_reverts(registry, root, count):
    with pytest.raises(TransactionFailed):
        registry.anchor(root, count, registry.local_key)


def test_revocation_id_validation_and_duplicate(registry, issued):
    _, bundle = issued
    with pytest.raises(TransactionFailed):
        registry.revoke(ZERO_HASH, registry.local_key)
    registry.revoke(bundle.receiptId, registry.local_key)
    with pytest.raises(TransactionFailed):
        registry.revoke(bundle.receiptId, registry.local_key)


def test_different_issuer_can_anchor_same_root_without_stealing(registry, issued):
    content, bundle = issued
    root = bytes.fromhex(bundle.root[2:])
    registry.contract.functions.anchorBatch(root, 1).transact({"from": registry.w3.eth.accounts[1]})
    assert verify_receipt(content, bundle, registry).status == "valid"
    assert registry.get_batch(bundle.batchId)[0] == bundle.claim.issuer


def test_bad_registry_bytecode_rejected(registry):
    with pytest.raises(ValueError, match="bytecode"):
        Registry(
            registry.w3,
            registry.w3.eth.accounts[2],
            mode="local",
            expected_chain_id=registry.domain.chainId,
        )


def test_wrong_chain_rejected(registry):
    with pytest.raises(ValueError, match="chain ID"):
        Registry(
            registry.w3, registry.domain.verifyingContract, mode="monad", expected_chain_id=10143
        )
