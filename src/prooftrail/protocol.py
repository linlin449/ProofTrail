"""Versioned EIP-712 receipts and deterministic sorted-pair Merkle proofs.

Verification never relies on the issuing server's database.
"""

import hashlib
import json
import secrets
import time
from typing import TYPE_CHECKING

from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak

from .models import (
    Check,
    Claim,
    Domain,
    Metadata,
    ReceiptBundle,
    SignedReceipt,
    Verification,
)

if TYPE_CHECKING:
    from .chain import Registry

ZERO_HASH = "0x" + "00" * 32
TYPES = {
    "Receipt": [
        {"name": "issuer", "type": "address"},
        {"name": "contentHash", "type": "bytes32"},
        {"name": "metadataHash", "type": "bytes32"},
        {"name": "parentId", "type": "bytes32"},
        {"name": "salt", "type": "bytes32"},
        {"name": "issuedAt", "type": "uint64"},
        {"name": "expiresAt", "type": "uint64"},
    ]
}


def sha256(data: bytes) -> str:
    return "0x" + hashlib.sha256(data).hexdigest()


def metadata_hash(metadata: Metadata) -> str:
    encoded = json.dumps(
        metadata.model_dump(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded)


def signable(domain: Domain, claim: Claim):
    return encode_typed_data(domain.model_dump(), TYPES, claim.model_dump())


def receipt_id(domain: Domain, claim: Claim) -> str:
    message = signable(domain, claim)
    return "0x" + keccak(b"\x19" + message.version + message.header + message.body).hex()


def typed_data(domain: Domain, claim: Claim) -> dict:
    return {
        "domain": domain.model_dump(),
        "primaryType": "Receipt",
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            **TYPES,
        },
        "message": claim.model_dump(),
    }


def create_claim(
    content: bytes,
    metadata: Metadata,
    issuer: str,
    *,
    parent_id: str = ZERO_HASH,
    expires_at: int = 0,
    issued_at: int | None = None,
    salt: str | None = None,
) -> Claim:
    issued = int(time.time()) if issued_at is None else issued_at
    if expires_at and expires_at <= issued:
        raise ValueError("有效期必须晚于签发时间")
    return Claim(
        issuer=issuer,
        contentHash=sha256(content),
        metadataHash=metadata_hash(metadata),
        parentId=parent_id,
        salt=salt or "0x" + secrets.token_hex(32),
        issuedAt=issued,
        expiresAt=expires_at,
    )


def create_receipt(
    content: bytes,
    metadata: Metadata,
    domain: Domain,
    private_key,
    *,
    parent_id: str = ZERO_HASH,
    expires_at: int = 0,
    issued_at: int | None = None,
) -> SignedReceipt:
    account = Account.from_key(private_key)
    claim = create_claim(
        content,
        metadata,
        account.address,
        parent_id=parent_id,
        expires_at=expires_at,
        issued_at=issued_at,
    )
    signature = "0x" + account.sign_message(signable(domain, claim)).signature.hex()
    return SignedReceipt(
        domain=domain,
        claim=claim,
        metadata=metadata,
        signature=signature,
        receiptId=receipt_id(domain, claim),
    )


def signature_valid(receipt: SignedReceipt) -> bool:
    try:
        raw = bytes.fromhex(receipt.signature[2:])
        # Reject high-s malleable signatures even though recovery can succeed.
        order = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        if raw[64] not in (27, 28) or not 0 < int.from_bytes(raw[32:64]) <= order // 2:
            return False
        recovered = Account.recover_message(signable(receipt.domain, receipt.claim), signature=raw)
        return recovered.lower() == receipt.claim.issuer.lower()
    except Exception:
        # Malformed curve points/signatures must fail closed, not break verification.
        return False


def leaf_hash(receipt: SignedReceipt) -> bytes:
    return keccak(bytes.fromhex(receipt_id(receipt.domain, receipt.claim)[2:]))


def pair_hash(left: bytes, right: bytes) -> bytes:
    return keccak(min(left, right) + max(left, right))


def batch_id(issuer: str, root: str) -> str:
    return "0x" + keccak(encode(["address", "bytes32"], [issuer, bytes.fromhex(root[2:])])).hex()


def build_batch(receipts: list[SignedReceipt]) -> list[ReceiptBundle]:
    if not 1 <= len(receipts) <= 4096:
        raise ValueError("批次必须包含 1 至 4096 张凭证")
    domain = receipts[0].domain
    issuer = receipts[0].claim.issuer
    ids = [receipt.receiptId for receipt in receipts]
    if len(set(ids)) != len(ids):
        raise ValueError("批次不能包含重复凭证")
    for receipt in receipts:
        if receipt.domain != domain or receipt.claim.issuer != issuer:
            raise ValueError("批次必须使用相同网络、合约与发行者")
        if receipt.receiptId != receipt_id(receipt.domain, receipt.claim):
            raise ValueError("凭证 ID 与声明不匹配")
        if (
            not signature_valid(receipt)
            or metadata_hash(receipt.metadata) != receipt.claim.metadataHash
        ):
            raise ValueError("凭证签名或元数据不匹配")
    levels = [[leaf_hash(receipt) for receipt in receipts]]
    while len(levels[-1]) > 1:
        level = levels[-1]
        levels.append(
            [
                pair_hash(level[i], level[min(i + 1, len(level) - 1)])
                for i in range(0, len(level), 2)
            ]
        )
    root = "0x" + levels[-1][0].hex()
    bundles = []
    for index, receipt in enumerate(receipts):
        cursor = index
        proof = []
        for level in levels[:-1]:
            sibling = cursor ^ 1
            proof.append("0x" + level[min(sibling, len(level) - 1)].hex())
            cursor //= 2
        bundles.append(
            ReceiptBundle(
                **receipt.model_dump(),
                batchId=batch_id(issuer, root),
                root=root,
                proof=proof,
                batchCount=len(receipts),
            )
        )
    return bundles


def proof_valid(bundle: ReceiptBundle) -> bool:
    value = leaf_hash(bundle)
    for sibling in bundle.proof:
        value = pair_hash(value, bytes.fromhex(sibling[2:]))
    return "0x" + value.hex() == bundle.root


def verify_receipt(
    content: bytes, bundle: ReceiptBundle, registry: "Registry", *, now: int | None = None
) -> Verification:
    checks: list[Check] = []

    def check(key: str, label: str, passed: bool | None, detail: str):
        checks.append(Check(key=key, label=label, passed=passed, detail=detail))

    check("schema", "凭证格式", True, "prooftrail/1 · 严格字段与格式检查")
    trusted = bundle.domain == registry.domain
    check(
        "domain",
        "可信网络与合约",
        trusted,
        f"期望链 {registry.domain.chainId} / {registry.domain.verifyingContract}",
    )
    check(
        "content",
        "内容完整性",
        sha256(content) == bundle.claim.contentHash,
        "原始字节 SHA-256；包含空格、换行与 Unicode 差异",
    )
    check(
        "metadata",
        "元数据完整性",
        metadata_hash(bundle.metadata) == bundle.claim.metadataHash,
        "标题、应用、媒体类型与模型声明均纳入签名",
    )
    id_valid = receipt_id(bundle.domain, bundle.claim) == bundle.receiptId
    check(
        "signature",
        "发行者签名",
        id_valid and signature_valid(bundle),
        "EIP-712 / secp256k1 · 发行者地址与签名恢复地址比较",
    )
    check(
        "merkle",
        "批量包含证明",
        proof_valid(bundle) and batch_id(bundle.claim.issuer, bundle.root) == bundle.batchId,
        f"{len(bundle.proof)} 层证明 · 独立重算 Merkle 根",
    )
    timestamp = int(time.time()) if now is None else now
    temporal = (
        bundle.claim.issuedAt <= timestamp
        and (bundle.claim.expiresAt == 0 or bundle.claim.expiresAt > timestamp)
        and (bundle.claim.expiresAt == 0 or bundle.claim.expiresAt > bundle.claim.issuedAt)
    )
    check("expiry", "凭证有效期", temporal, "校验签发时间非未来且未过期；签发时间是发行者声明")
    anchored_at = None
    if trusted:
        try:
            registry.assert_trusted()
            anchored = registry.get_batch(bundle.batchId)
            exists = (
                anchored[0].lower() == bundle.claim.issuer.lower()
                and "0x" + anchored[1].hex() == bundle.root
                and anchored[2] == bundle.batchCount
                and anchored[3] > 0
                and bundle.claim.issuedAt <= anchored[3]
            )
            anchored_at = int(anchored[3]) if exists else None
            check(
                "anchor",
                "链上登记",
                exists,
                f"已查可信合约 · 登记区块时间 {anchored_at}"
                if exists
                else "可信合约未发现匹配批次",
            )
            revoked = registry.is_revoked(bundle.claim.issuer, bundle.receiptId)
            check(
                "revocation",
                "撤销状态",
                not revoked,
                "发行者已撤销该凭证" if revoked else "可信合约当前未记录撤销",
            )
        except Exception:
            # Do not leak provider URLs, credentials, or internal exceptions to callers.
            check("anchor", "链上登记", None, "链上查询失败；无法确认，请检查 RPC 与可信合约")
            check("revocation", "撤销状态", None, "无法读取最新撤销状态")
    else:
        check("anchor", "链上登记", False, "凭证不属于配置的可信域，不查询凭证自报的网络")
        check("revocation", "撤销状态", False, "可信域不匹配")
    status = (
        "invalid"
        if any(c.passed is False for c in checks)
        else ("unavailable" if any(c.passed is None for c in checks) else "valid")
    )
    return Verification(
        status=status,
        receiptId=bundle.receiptId,
        checks=checks,
        anchoredAt=anchored_at,
        issuer=bundle.claim.issuer,
        network=registry.mode,
    )
