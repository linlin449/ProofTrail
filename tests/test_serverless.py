from fastapi.testclient import TestClient

from prooftrail.chain import Registry
from prooftrail.serverless import MONAD_CONTRACT, create_public_app


def test_public_entrypoint_defers_rpc_and_fails_closed(monkeypatch):
    calls = []

    def disconnected(*args):
        calls.append(args)
        raise ConnectionError("offline")

    monkeypatch.setattr(Registry, "monad", disconnected)
    monkeypatch.setenv("PROOFTRAIL_APP", "issuer")
    client = TestClient(create_public_app())
    assert not calls
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert (
        client.post(
            "/api/demo/issue", json={"artifacts": [{"content": "x", "metadata": {"title": "x"}}]}
        ).status_code
        == 403
    )
    assert not calls
    assert client.get("/health").status_code == 503
    assert len(calls) == 1
    assert client.get("/health").status_code == 503  # failure is not cached as a trusted deployment
    assert len(calls) == 2


def test_independent_serverless_consumer_and_host_scope(registry, monkeypatch):
    monkeypatch.setattr(Registry, "monad", lambda *args: registry)
    monkeypatch.setenv("PROOFTRAIL_APP", "consumer")
    monkeypatch.delenv("PROOFTRAIL_ALLOWED_HOSTS", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", "prooftrail-review-123.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "prooftrail-consumer.vercel.app")
    client = TestClient(create_public_app())
    assert client.get("/api/info").json()["contract"] == MONAD_CONTRACT
    assert client.get("/api/info").json()["issuerApiRequired"] is False
    assert client.post("/api/demo/issue", json={}).status_code == 404
    assert (
        client.get("/health", headers={"host": "prooftrail-consumer.vercel.app"}).status_code == 200
    )
    assert (
        client.get("/health", headers={"host": "prooftrail-review-123.vercel.app"}).status_code
        == 200
    )
    assert client.get("/health", headers={"host": "other-project.vercel.app"}).status_code == 400
    monkeypatch.setenv("PROOFTRAIL_ALLOWED_HOSTS", "custom.example")
    explicit = TestClient(create_public_app())
    assert (
        explicit.get("/health", headers={"host": "prooftrail-consumer.vercel.app"}).status_code
        == 400
    )
    assert explicit.get("/health", headers={"host": "custom.example"}).status_code == 200
