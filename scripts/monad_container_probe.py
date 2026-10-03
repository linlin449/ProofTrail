"""Read-only real Monad checks against two independently running review containers."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
record = {"checkedAtUtc": datetime.now(UTC).isoformat(), "network": "Monad Testnet"}
with httpx.Client(timeout=45) as client:
    containers = []
    for service, port in (("issuer", 8795), ("consumer", 8796)):
        name = f"prooftrail-monad-review-{service}-1"
        inspected = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
        assert (
            inspected["Config"]["Labels"]["com.docker.compose.project"] == "prooftrail-monad-review"
        )
        assert inspected["HostConfig"]["ReadonlyRootfs"]
        assert inspected["Config"]["User"] == "10001:10001"
        assert not any(
            item.split("=", 1)[0] == "PROOFTRAIL_PRIVATE_KEY" for item in inspected["Config"]["Env"]
        )
        assert inspected["State"]["Health"]["Status"] == "healthy"
        response = client.get(f"http://127.0.0.1:{port}/health")
        response.raise_for_status()
        containers.append(
            {
                "service": service,
                "imageId": inspected["Image"],
                "nonRoot": True,
                "readOnly": True,
                "signingKeyConfigured": False,
                "health": response.json(),
                "port": port,
            }
        )
    record["containers"] = containers
    demo = root / "artifacts/monad-demo"
    normal = {
        "content": (demo / "content.txt").read_text("utf-8"),
        "bundle": json.loads((demo / "receipt.json").read_text("utf-8")),
    }
    revoked = {
        "content": (demo / "revoked-content.txt").read_text("utf-8"),
        "bundle": json.loads((demo / "revoked-receipt.json").read_text("utf-8")),
    }
    cases = []
    for name, payload, expected in (
        ("valid", normal, True),
        ("tampered", normal | {"content": normal["content"] + " modified"}, False),
        ("revoked", revoked, False),
    ):
        response = client.post("http://127.0.0.1:8796/api/assess", json=payload)
        response.raise_for_status()
        result = response.json()
        assert result["eligibleForPreview"] == expected
        assert bool(result["preview"]) == expected
        cases.append({"case": name, "result": result})
    record["consumerCases"] = cases
    response = client.post("http://127.0.0.1:8795/api/verify", json=normal)
    response.raise_for_status()
    assert response.json()["status"] == "valid"
    record["issuerVerification"] = response.json()
    response = client.post(
        "http://127.0.0.1:8795/api/demo/issue",
        json={"artifacts": [{"content": "read-only-mode-probe", "metadata": {"title": "probe"}}]},
    )
    assert response.status_code == 403
    record["serverSigningRejected"] = True
record["status"] = "passed"
(root / "artifacts/monad-container-probe.json").write_text(
    json.dumps(record, ensure_ascii=False, indent=2) + "\n", "utf-8"
)
print(
    "Two real Monad containers passed; no signing key, no chain write, independent live-state reads."
)
