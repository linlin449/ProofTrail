import mimetypes
import threading
import time
from importlib.resources import files

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .chain import Registry
from .models import Address, Metadata, ReceiptBundle, SignedReceipt, StrictModel
from .protocol import (
    ZERO_HASH,
    build_batch,
    create_claim,
    create_receipt,
    receipt_id,
    typed_data,
    verify_receipt,
)
from .web_security import protect_app


class ArtifactInput(StrictModel):
    content: str = Field(min_length=1, max_length=50000)
    metadata: Metadata
    parentId: str = Field(default=ZERO_HASH, pattern=r"^0x[0-9a-f]{64}$")
    expiresAt: int = Field(default=0, ge=0, le=2**64 - 1)


class IssueRequest(StrictModel):
    artifacts: list[ArtifactInput] = Field(min_length=1, max_length=64)


class VerifyRequest(StrictModel):
    content: str = Field(max_length=50000)
    bundle: ReceiptBundle


class PrepareRequest(ArtifactInput):
    issuer: Address


class BatchRequest(StrictModel):
    receipts: list[SignedReceipt] = Field(min_length=1, max_length=64)


class RevokeRequest(StrictModel):
    receiptId: str = Field(pattern=r"^0x[0-9a-f]{64}$")


def create_app(registry: Registry | None = None) -> FastAPI:
    registry = registry or Registry.local()
    app = FastAPI(
        title="ProofTrail",
        version="0.1.0",
        description="Independent AI provenance verification",
        docs_url=None,
        redoc_url=None,
    )
    app.state.registry = registry
    app.state.bundles = {}
    mutation_lock = threading.Lock()
    protect_app(app)

    def require_local(request: Request):
        if (
            registry.mode != "local"
            or request.client is None
            or request.client.host not in ("127.0.0.1", "::1", "testclient")
        ):
            raise HTTPException(403, "服务器演示写入仅限本机测试链；测试网请使用自己的钱包")
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
            raise HTTPException(403, "跨站演示写入被拒绝")

    @app.get("/api/info")
    def info():
        registry.assert_trusted()
        return {
            "mode": registry.mode,
            "chainId": registry.domain.chainId,
            "contract": registry.domain.verifyingContract,
            "domain": registry.domain.model_dump(),
            "localWrites": registry.mode == "local",
            "issuer": registry.w3.eth.accounts[0] if registry.mode == "local" else None,
            "protocol": "prooftrail/1",
            "maxBatchSize": 64,
            "disclaimer": "凭证证明发行者声明与字节完整性，不证明事实、版权或实际模型执行",
        }

    @app.post("/api/demo/issue")
    def issue(payload: IssueRequest, request: Request):
        require_local(request)
        with mutation_lock:
            if len(app.state.bundles) + len(payload.artifacts) > 1000:
                raise HTTPException(429, "本次本地演示最多保存 1000 张凭证；重启服务可重置")
            try:
                receipts = [
                    create_receipt(
                        item.content.encode("utf-8"),
                        item.metadata,
                        registry.domain,
                        registry.local_key,
                        parent_id=item.parentId,
                        expires_at=item.expiresAt,
                    )
                    for item in payload.artifacts
                ]
                bundles = build_batch(receipts)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            started = time.perf_counter()
            tx = registry.anchor(bundles[0].root, len(bundles), registry.local_key)
            tx["elapsedMs"] = round((time.perf_counter() - started) * 1000, 2)
            tx["gasPerReceipt"] = round(tx["gasUsed"] / len(bundles), 2)
            for bundle in bundles:
                app.state.bundles[bundle.receiptId] = bundle
            return {"bundles": [b.model_dump() for b in bundles], "transaction": tx}

    @app.post("/api/verify")
    def verify(payload: VerifyRequest):
        with registry.lock:
            return verify_receipt(payload.content.encode("utf-8"), payload.bundle, registry)

    @app.post("/api/demo/revoke")
    def revoke(payload: RevokeRequest, request: Request):
        require_local(request)
        if payload.receiptId not in app.state.bundles:
            raise HTTPException(404, "该凭证不属于本次演示会话")
        if registry.is_revoked(registry.w3.eth.accounts[0], payload.receiptId):
            raise HTTPException(409, "该凭证已撤销")
        return registry.revoke(payload.receiptId, registry.local_key)

    @app.post("/api/prepare")
    def prepare(payload: PrepareRequest):
        try:
            claim = create_claim(
                payload.content.encode("utf-8"),
                payload.metadata,
                payload.issuer,
                parent_id=payload.parentId,
                expires_at=payload.expiresAt,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "claim": claim.model_dump(),
            "metadata": payload.metadata.model_dump(),
            "receiptId": receipt_id(registry.domain, claim),
            "typedData": typed_data(registry.domain, claim),
        }

    @app.post("/api/batch")
    def batch(payload: BatchRequest):
        if any(receipt.domain != registry.domain for receipt in payload.receipts):
            raise HTTPException(422, "签名凭证不属于当前可信网络与合约")
        try:
            bundles = build_batch(payload.receipts)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "bundles": [b.model_dump() for b in bundles],
            "transaction": {
                "to": registry.domain.verifyingContract,
                "from": bundles[0].claim.issuer,
                "chainId": hex(registry.domain.chainId),
                "data": registry.anchor_data(bundles[0].root, len(bundles)),
                "value": "0x0",
            },
        }

    @app.post("/api/revoke-transaction")
    def revoke_transaction(payload: RevokeRequest):
        return {
            "to": registry.domain.verifyingContract,
            "chainId": hex(registry.domain.chainId),
            "data": registry.revoke_data(payload.receiptId),
            "value": "0x0",
        }

    @app.get("/api/receipts")
    def receipts():
        return {"bundles": [b.model_dump() for b in list(app.state.bundles.values())[-20:]][::-1]}

    @app.get("/api/transactions/{tx_hash}")
    def transaction(tx_hash: str):
        import re

        from web3.exceptions import TransactionNotFound

        if not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
            raise HTTPException(422, "无效的交易哈希")
        try:
            tx = registry.w3.eth.get_transaction(tx_hash)
            mined = registry.w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            return {"pending": True}
        if tx.to is None or tx.to.lower() != registry.domain.verifyingContract.lower():
            raise HTTPException(422, "交易目标不属于当前可信合约")
        return {
            "pending": False,
            "status": mined.status,
            "transactionHash": tx_hash,
            "blockNumber": mined.blockNumber,
            "gasUsed": mined.gasUsed,
            "gasPriceWei": mined.effectiveGasPrice,
            "network": registry.mode,
        }

    @app.get("/health")
    def health():
        try:
            registry.assert_trusted()
        except Exception as exc:
            raise HTTPException(503, "可信网络或合约暂不可用") from exc
        return {"status": "ok", "mode": registry.mode}

    # Windows registry can map .js to text/plain. nosniff rightly blocks that.
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    static = str(files("prooftrail").joinpath("static"))
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def home():
        return FileResponse(static + "/index.html")

    @app.get("/docs")
    def api_reference():
        return FileResponse(static + "/api.html")

    return app
