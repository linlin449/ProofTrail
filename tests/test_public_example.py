"""Examples carry real public evidence, not a server-side 'valid' shortcut."""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prooftrail.api import create_app
from prooftrail.chain import Registry
from prooftrail.consumer_app import create_consumer_app
from prooftrail.models import ReceiptBundle
from prooftrail.protocol import verify_receipt
from prooftrail.serverless import MONAD_CONTRACT, MONAD_RPC, DeferredMonadRegistry

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("factory", [create_app, create_consumer_app])
def test_example_preserves_real_signed_bytes_without_rpc_or_verdict(factory, monkeypatch):
    def offline(*args):
        raise ConnectionError("No RPC in this unit test")

    monkeypatch.setattr(Registry, "monad", offline)
    registry = DeferredMonadRegistry(MONAD_RPC, MONAD_CONTRACT)
    client = TestClient(factory(registry))
    response = client.get("/api/example")
    assert response.status_code == 200
    example = response.json()
    content = (ROOT / "artifacts/monad-demo/content.txt").read_bytes()
    assert example["content"].encode("utf-8") == content
    assert example["bundle"] == json.loads((ROOT / "artifacts/monad-demo/receipt.json").read_text("utf-8"))
    bundle = ReceiptBundle.model_validate(example["bundle"])
    assert "0x" + hashlib.sha256(content).hexdigest() == bundle.claim.contentHash
    assert "status" not in example and "verification" not in example
    assert registry._registry is None
    # Actual verification still consults the trusted registry, and fails closed while offline.
    result = verify_receipt(content, bundle, registry)
    assert result.status == "unavailable"
    assert all(check.passed for check in result.checks if check.key in ("content", "signature", "merkle"))
    assert registry._registry is None


@pytest.mark.parametrize("factory", [create_app, create_consumer_app])
def test_example_not_offered_on_local_or_different_domain(factory, registry):
    local = TestClient(factory(registry))
    assert local.get("/api/example").status_code == 404
    assert local.get("/api/info").json()["exampleAvailable"] is False
    other = DeferredMonadRegistry(MONAD_RPC, "0x" + "11" * 20)
    assert TestClient(factory(other)).get("/api/example").status_code == 404
