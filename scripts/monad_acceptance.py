"""Real Monad testnet transactions and independent lifecycle checks. Never runs on mainnet."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from eth_account import Account

from prooftrail import Metadata, build_batch, create_receipt, verify_receipt
from prooftrail.chain import Registry
from prooftrail.protocol import proof_valid, signature_valid

parser = argparse.ArgumentParser()
parser.add_argument("--broadcast", action="store_true")
args = parser.parse_args()
if not args.broadcast:
    raise SystemExit("This acceptance run sends TESTNET transactions. Use --broadcast explicitly.")
output = Path("artifacts/monad-acceptance.json")
if output.exists():
    raise SystemExit("Acceptance record exists. Inspect its hashes and state before any rerun.")
deployment = json.loads(Path("artifacts/monad-deployment.json").read_text("utf-8"))
registry = Registry.monad("https://testnet-rpc.monad.xyz", deployment["address"])
reader = Registry.monad("https://testnet-rpc.monad.xyz", deployment["address"])
key = os.environ["PROOFTRAIL_PRIVATE_KEY"]
issuer = Account.from_key(key)
if issuer.address != deployment["deployer"]:
    raise SystemExit("Configured signer is not the dedicated deployment test account.")
document = {
    "network": "Monad Testnet",
    "chainId": 10143,
    "contract": deployment["address"],
    "startedAtUtc": datetime.now(UTC).isoformat(),
    "status": "in-progress",
    "issuer": issuer.address,
    "measurements": [],
    "transactions": [],
    "limitations": [
        "Synthetic test content, not user adoption",
        "Elapsed time includes RPC transport and polling; not a consensus-finality benchmark",
        "Root registration excludes per-item signing and tree-building costs",
        "All leaf signatures/proofs checked offline; first/last leaf per batch checked against live chain",
    ],
}


def save():
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", "utf-8")


def send(function, signing_key, label):
    registry.assert_trusted()
    account = Account.from_key(signing_key)
    transaction = function.build_transaction(
        {
            "from": account.address,
            "nonce": registry.w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": 10143,
        }
    )
    return send_transaction(transaction, signing_key, label)


def send_transaction(transaction, signing_key, label):
    if transaction["chainId"] != 10143:
        raise ValueError("Refuse transaction outside Monad Testnet")
    account = Account.from_key(signing_key)
    max_price = transaction.get("maxFeePerGas", transaction.get("gasPrice", 0))
    if (
        registry.w3.eth.get_balance(account.address)
        < transaction.get("value", 0) + transaction["gas"] * max_price
    ):
        raise ValueError("Insufficient test MON for maximum transaction fee")
    signed = account.sign_transaction(transaction)
    expected_hash = "0x" + signed.hash.hex()
    entry = {
        "label": label,
        "transactionHash": expected_hash,
        "from": account.address,
        "state": "signed-before-broadcast",
        "nonce": transaction["nonce"],
    }
    document["transactions"].append(entry)
    save()  # Persist hash before sending; never silently retry an uncertain transaction.
    started = time.perf_counter()
    returned = registry.w3.eth.send_raw_transaction(signed.raw_transaction)
    assert "0x" + returned.hex() == expected_hash
    entry["state"] = "pending"
    save()
    receipt = registry.w3.eth.wait_for_transaction_receipt(returned, timeout=90)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    entry.update(
        state="confirmed" if receipt.status == 1 else "reverted",
        blockNumber=receipt.blockNumber,
        gasUsed=receipt.gasUsed,
        effectiveGasPriceWei=receipt.effectiveGasPrice,
        elapsedMs=elapsed,
    )
    save()
    if receipt.status != 1:
        raise ValueError("Transaction reverted; preserve acceptance journal")
    print(
        json.dumps(
            {
                "label": label,
                "transactionHash": expected_hash,
                "gasUsed": receipt.gasUsed,
                "elapsedMs": elapsed,
            }
        ),
        flush=True,
    )
    return entry


save()
try:
    for size in (1, 4, 16, 32):
        items = [
            {
                "content": f"ProofTrail Monad testnet synthetic note {size}/{i}\n来源证明不等于事实证明。",
                "metadata": Metadata(
                    title=f"Monad 实测 · {size} 份 · 第 {i + 1} 份",
                    application="Research Studio · synthetic test",
                ),
            }
            for i in range(size)
        ]
        receipts = [
            create_receipt(item["content"].encode(), item["metadata"], registry.domain, key)
            for item in items
        ]
        bundles = build_batch(receipts)
        assert all(proof_valid(bundle) and signature_valid(bundle) for bundle in bundles)
        measurement = {
            "size": size,
            "batchId": bundles[0].batchId,
            "root": bundles[0].root,
            "items": [
                {"content": item["content"], "bundle": bundle.model_dump()}
                for item, bundle in zip(items, bundles, strict=True)
            ],
        }
        document["measurements"].append(measurement)
        save()
        transaction = send(
            registry.contract.functions.anchorBatch(bytes.fromhex(bundles[0].root[2:]), size),
            key,
            f"anchor-{size}",
        )
        measurement.update(
            transaction=transaction.copy(),
            gasPerReceipt=transaction["gasUsed"] / size,
            feeTestMon=transaction["gasUsed"] * transaction["effectiveGasPriceWei"] / 10**18,
        )
        samples = sorted({0, size - 1})
        measurement["liveChecks"] = []
        for index in samples:
            result = verify_receipt(items[index]["content"].encode(), bundles[index], reader)
            measurement["liveChecks"].append(result.model_dump())
            save()
            assert result.status == "valid", result.model_dump_json()
        demo = Path("artifacts/monad-demo")
        demo.mkdir(exist_ok=True)
        if size == 1:
            (demo / "content.txt").write_bytes(items[0]["content"].encode())
            (demo / "receipt.json").write_text(bundles[0].model_dump_json(indent=2) + "\n", "utf-8")
        if size == 32:
            target_content, target = items[0]["content"].encode(), bundles[0]

    # A second TESTNET-only address can revoke only within its own namespace.
    secondary_path = Path(".local/testnet-secondary-key.txt")
    if secondary_path.exists():
        secondary = Account.from_key(secondary_path.read_text("utf-8").strip())
    else:
        secondary = Account.create()
        with secondary_path.open("x", encoding="utf-8") as handle:
            handle.write("0x" + secondary.key.hex() + "\n")
    document["secondaryTestAddress"] = secondary.address
    funding = {
        "to": secondary.address,
        "value": 5 * 10**16,
        "gas": 21000,
        "gasPrice": registry.w3.eth.gas_price,
        "chainId": 10143,
        "nonce": registry.w3.eth.get_transaction_count(issuer.address, "pending"),
    }
    send_transaction(funding, key, "fund-secondary-test-address-0.05-MON")
    send(
        registry.contract.functions.revoke(bytes.fromhex(target.receiptId[2:])),
        secondary.key,
        "other-account-namespace-revoke",
    )
    before = verify_receipt(target_content, target, reader)
    assert before.status == "valid"
    assert registry.is_revoked(secondary.address, target.receiptId)
    assert not registry.is_revoked(issuer.address, target.receiptId)
    document["otherAccountRevocation"] = {
        "ownNamespaceRecorded": True,
        "originalIssuerUnaffected": True,
        "consumerResult": before.model_dump(),
    }
    save()
    send(
        registry.contract.functions.revoke(bytes.fromhex(target.receiptId[2:])),
        key,
        "issuer-revoke",
    )
    after = verify_receipt(target_content, target, reader)
    assert after.status == "invalid"
    assert next(c for c in after.checks if c.key == "revocation").passed is False
    document["issuerRevocation"] = after.model_dump()
    (demo / "revoked-content.txt").write_bytes(target_content)
    (demo / "revoked-receipt.json").write_text(target.model_dump_json(indent=2) + "\n", "utf-8")
    document["status"] = "passed"
    document["completedAtUtc"] = datetime.now(UTC).isoformat()
    document["remainingIssuerBalanceWei"] = registry.w3.eth.get_balance(issuer.address)
    save()
    print("Real Monad acceptance passed; unrevoked and revoked public synthetic bundles saved.")
except Exception:
    document["status"] = "incomplete-inspect-journal-before-retry"
    save()
    raise
