from fastapi.testclient import TestClient

from prooftrail.api import create_app

PAYLOAD = {"artifacts": [{"content": "中文笔记\n", "metadata": {"title": "测试笔记"}}]}


def test_render_hostname_and_explicit_host_override(registry, monkeypatch):
    monkeypatch.delenv("PROOFTRAIL_ALLOWED_HOSTS", raising=False)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "prooftrail-review.onrender.com")
    client = TestClient(create_app(registry))
    assert (
        client.get("/health", headers={"host": "prooftrail-review.onrender.com"}).status_code == 200
    )
    assert client.get("/health", headers={"host": "127.0.0.1"}).status_code == 200
    assert client.get("/health", headers={"host": "another-app.onrender.com"}).status_code == 400
    monkeypatch.setenv("PROOFTRAIL_ALLOWED_HOSTS", "custom.example")
    configured = TestClient(create_app(registry))
    assert configured.get("/health", headers={"host": "custom.example"}).status_code == 200
    assert (
        configured.get("/health", headers={"host": "prooftrail-review.onrender.com"}).status_code
        == 400
    )


def test_product_api_end_to_end(registry):
    client = TestClient(create_app(registry))
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    assert "api/verify" in client.get("/docs").text
    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert client.get("/api/info").json()["mode"] == "local"
    issued = client.post("/api/demo/issue", json=PAYLOAD)
    assert issued.status_code == 200, issued.text
    bundle = issued.json()["bundles"][0]
    body = {"content": "中文笔记\n", "bundle": bundle}
    assert client.post("/api/verify", json=body).json()["status"] == "valid"
    assert client.post("/api/verify", json=body | {"content": "篡改"}).json()["status"] == "invalid"
    assert (
        client.post("/api/demo/revoke", json={"receiptId": bundle["receiptId"]}).status_code == 200
    )
    assert client.post("/api/verify", json=body).json()["status"] == "invalid"
    assert (
        client.post("/api/demo/revoke", json={"receiptId": bundle["receiptId"]}).status_code == 409
    )
    assert "content" not in client.get("/api/receipts").json()["bundles"][0]
    tx = issued.json()["transaction"]["transactionHash"]
    assert client.get("/api/transactions/" + tx).json()["status"] == 1


def test_invalid_inputs_and_request_cap(registry):
    client = TestClient(create_app(registry))
    assert client.post("/api/demo/issue", json={"artifacts": []}).status_code == 422
    assert (
        client.post("/api/demo/issue", json={"artifacts": PAYLOAD["artifacts"] * 65}).status_code
        == 422
    )
    assert client.post("/api/verify", json={"content": "x", "bundle": {}}).status_code == 422
    assert client.post("/api/demo/issue", content=b"x" * (4 * 1024 * 1024 + 1)).status_code == 413


def test_cross_site_and_remote_local_mutations_blocked(registry):
    app = create_app(registry)
    client = TestClient(app)
    assert (
        client.post(
            "/api/demo/issue", json=PAYLOAD, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/demo/issue", json=PAYLOAD, headers={"Host": "evil.example"}).status_code
        == 400
    )
    remote = TestClient(app, client=("198.51.100.2", 50000))
    assert remote.post("/api/demo/issue", json=PAYLOAD).status_code == 403


def test_monad_mode_disables_server_signing(registry):
    registry.mode = "monad"
    client = TestClient(create_app(registry))
    assert client.post("/api/demo/issue", json=PAYLOAD).status_code == 403


def test_wallet_prepare_and_batch(registry):
    from eth_account import Account
    from eth_account.messages import encode_typed_data

    client = TestClient(create_app(registry))
    prepared = client.post(
        "/api/prepare", json=PAYLOAD["artifacts"][0] | {"issuer": registry.w3.eth.accounts[0]}
    ).json()
    signature = Account.sign_message(
        encode_typed_data(full_message=prepared["typedData"]), registry.local_key
    ).signature
    receipt = {
        "domain": prepared["typedData"]["domain"],
        "claim": prepared["claim"],
        "metadata": prepared["metadata"],
        "signature": "0x" + signature.hex(),
        "receiptId": prepared["receiptId"],
    }
    response = client.post("/api/batch", json={"receipts": [receipt]})
    assert response.status_code == 200, response.text
    data = response.json()
    registry.w3.eth.send_transaction(data["transaction"])
    assert (
        client.post(
            "/api/verify", json={"content": "中文笔记\n", "bundle": data["bundles"][0]}
        ).json()["status"]
        == "valid"
    )


def test_security_headers_and_health(registry, monkeypatch):
    client = TestClient(create_app(registry))
    response = client.get("/api/info")
    assert response.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/health").status_code == 200

    def unavailable():
        raise ConnectionError()

    monkeypatch.setattr(registry, "assert_trusted", unavailable)
    assert client.get("/health").status_code == 503
