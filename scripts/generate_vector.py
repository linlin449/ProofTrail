"""Deterministic public conformance fixture, using a known test-only key (integer 1)."""

import json
from pathlib import Path

from eth_account import Account

from prooftrail.models import Domain, Metadata, SignedReceipt
from prooftrail.protocol import build_batch, create_claim, receipt_id, signable, typed_data

domain = Domain(chainId=10143, verifyingContract="0x1111111111111111111111111111111111111111")
account = Account.from_key((1).to_bytes(32))  # Public test key; NEVER used by deployment scripts.
metadata = Metadata(title="跨语言测试 · Research", application="Fixture Studio", model="test-only")
content = "研究笔记\nExact bytes matter.\n"
receipts = []
for i in range(2):
    claim = create_claim(
        content.encode(),
        metadata,
        account.address,
        issued_at=1700000000,
        salt="0x" + bytes([42 + i]).hex() * 32,
    )
    receipts.append(
        SignedReceipt(
            domain=domain,
            claim=claim,
            metadata=metadata,
            signature="0x" + account.sign_message(signable(domain, claim)).signature.hex(),
            receiptId=receipt_id(domain, claim),
        )
    )
document = {
    "testOnly": True,
    "content": content,
    "typedData": typed_data(domain, receipts[0].claim),
    "bundles": [b.model_dump() for b in build_batch(receipts)],
}
out = Path("artifacts/protocol-vector.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Wrote public EIP-712/Merkle fixture to", out)
