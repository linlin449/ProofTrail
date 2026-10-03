"""Run inside the built Linux runtime as a non-root user with a read-only filesystem."""

import json
import os
import sys
from importlib.resources import files
from pathlib import Path

from fastapi.testclient import TestClient

import prooftrail
from prooftrail.api import create_app
from prooftrail.chain import Registry
from prooftrail.consumer_app import create_consumer_app

assert sys.platform == "linux"
assert os.geteuid() == 10001
assert "site-packages" in prooftrail.__file__
assert not Path("/app/src").exists(), (
    "Runtime must import the installed wheel, not an editable tree"
)
assert not Path("/app/.local").exists()
assert not Path("/app/.env").exists()
for path in [
    "static/index.html",
    "static/app.js",
    "consumer_static/index.html",
    "consumer_static/app.js",
]:
    assert files("prooftrail").joinpath(path).is_file()

registry = Registry.local()
issuer_app = create_app(registry)
issuer = TestClient(issuer_app)
content = "Linux container · 独立消费者\n"
issued = issuer.post(
    "/api/demo/issue",
    json={"artifacts": [{"content": content, "metadata": {"title": "只读运行环境验收"}}]},
)
assert issued.status_code == 200, issued.text
document = issued.json()
bundle = document["bundles"][0]
issuer_app.state.bundles.clear()
reader = Registry(
    registry.w3,
    registry.domain.verifyingContract,
    mode="local",
    expected_chain_id=registry.domain.chainId,
)
assert not hasattr(reader, "local_key")
consumer = TestClient(create_consumer_app(reader))
payload = {"content": content, "bundle": bundle}
assert consumer.get("/health").status_code == 200
assert consumer.post("/api/assess", json=payload).json()["eligibleForPreview"]
assert not consumer.post("/api/assess", json=payload | {"content": content + "changed"}).json()[
    "eligibleForPreview"
]
registry.revoke(bundle["receiptId"], registry.local_key)
revoked = consumer.post("/api/assess", json=payload).json()
assert revoked["preview"] is None
assert (
    next(c for c in revoked["verification"]["checks"] if c["key"] == "revocation")["passed"]
    is False
)
assert consumer.post("/api/demo/issue", json={}).status_code == 404
assert "PROOFTRAIL_PRIVATE_KEY" not in os.environ
assert consumer.get("/static/app.js").headers["content-type"].startswith("text/javascript")
result = {
    "platform": sys.platform,
    "uid": os.geteuid(),
    "installedPackage": prooftrail.__file__,
    "localEvmOnly": True,
    "issue": "passed",
    "independentConsumer": "passed",
    "tampering": "rejected",
    "revocation": "rejected",
    "privateKeyConfigured": False,
    "transaction": document["transaction"]["transactionHash"],
    "note": "Linux installation and local EVM checks only; not Monad deployment or hosting evidence",
}
print(json.dumps(result, ensure_ascii=False, indent=2))
