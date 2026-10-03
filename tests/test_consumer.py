from fastapi.testclient import TestClient

from prooftrail.api import create_app
from prooftrail.chain import Registry
from prooftrail.consumer_app import create_consumer_app


def test_consumer_without_issuer_database_and_live_revocation(registry):
    issuer_app = create_app(registry)
    issuer = TestClient(issuer_app)
    issued = issuer.post(
        "/api/demo/issue",
        json={"artifacts": [{"content": "研究笔记\n", "metadata": {"title": "跨应用示例"}}]},
    ).json()
    reader = Registry(
        registry.w3,
        registry.domain.verifyingContract,
        mode="local",
        expected_chain_id=registry.domain.chainId,
    )
    assert not hasattr(reader, "local_key")
    consumer = TestClient(create_consumer_app(reader))
    issuer_app.state.bundles.clear()
    payload = {"content": "研究笔记\n", "bundle": issued["bundles"][0]}
    valid = consumer.post("/api/assess", json=payload).json()
    assert valid["eligibleForPreview"] is True
    assert valid["preview"]["content"] == payload["content"]
    tampered = consumer.post("/api/assess", json=payload | {"content": "篡改"}).json()
    assert tampered["eligibleForPreview"] is False
    assert tampered["preview"] is None
    registry.revoke(payload["bundle"]["receiptId"], registry.local_key)
    revoked = consumer.post("/api/assess", json=payload).json()
    assert revoked["eligibleForPreview"] is False
    assert (
        next(c for c in revoked["verification"]["checks"] if c["key"] == "revocation")["passed"]
        is False
    )
    assert consumer.get("/api/receipts").status_code == 404
    assert consumer.post("/api/demo/issue", json={}).status_code == 404


def test_consumer_limits_health_and_assets(registry, monkeypatch):
    consumer = TestClient(create_consumer_app(registry))
    assert consumer.get("/").status_code == 200
    assert consumer.get("/static/app.js").headers["content-type"].startswith("text/javascript")
    assert consumer.get("/api/info").json()["issuerApiRequired"] is False
    assert consumer.get("/health").status_code == 200
    assert consumer.post("/api/assess", json={}).status_code == 422
    assert consumer.post("/api/assess", content=b"x" * (4 * 1024 * 1024 + 1)).status_code == 413
    assert consumer.get("/", headers={"Host": "evil.example"}).status_code == 400
    monkeypatch.setattr(
        registry, "assert_trusted", lambda: (_ for _ in ()).throw(OSError("rpc down"))
    )
    assert consumer.get("/health").status_code == 503
