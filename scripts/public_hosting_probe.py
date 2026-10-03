"""Anonymous public HTTP checks using public testnet receipts; no keys or chain writes."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7"


def probe(role, base):
    if urlparse(base).scheme != "https":
        raise ValueError("Public hosting check requires HTTPS")
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        checks = {}
        for path in ("/", "/health", "/api/info", "/static/app.js", "/static/style.css"):
            response = client.get(base + path)
            response.raise_for_status()
            assert response.status_code == 200
            checks[path] = {"httpStatus": response.status_code}
            if path in ("/health", "/api/info"):
                checks[path]["body"] = response.json()
        info = checks["/api/info"]["body"]
        assert info["mode"] == "monad" and info["chainId"] == 10143
        assert info["contract"] == CONTRACT
        assert info["exampleAvailable"] is True
        example_response = client.get(base + "/api/example")
        example_response.raise_for_status()
        example = example_response.json()
        assert example["content"].encode("utf-8") == (ROOT / "artifacts/monad-demo/content.txt").read_bytes()
        assert example["bundle"] == json.loads((ROOT / "artifacts/monad-demo/receipt.json").read_text("utf-8"))
        assert "status" not in example and "verification" not in example
        checks["/api/example"] = {"httpStatus": example_response.status_code, "originalBytesPreserved": True, "containsVerdict": False}
        cases = {}
        endpoint = "/api/verify" if role == "issuer" else "/api/assess"
        for name, prefix, altered, expected in (
            ("valid", "", False, "valid"),
            ("tampered", "", True, "invalid"),
            ("revoked", "revoked-", False, "invalid"),
        ):
            content = (ROOT / f"artifacts/monad-demo/{prefix}content.txt").read_bytes()
            bundle = json.loads(
                (ROOT / f"artifacts/monad-demo/{prefix}receipt.json").read_text("utf-8")
            )
            text = content.decode("utf-8") + (" changed" if altered else "")
            response = client.post(base + endpoint, json={"content": text, "bundle": bundle})
            response.raise_for_status()
            data = response.json()
            result = data if role == "issuer" else data["verification"]
            assert result["status"] == expected, result
            if role == "consumer":
                assert data["eligibleForPreview"] == (expected == "valid")
                assert (data["preview"] is not None) == (expected == "valid")
            cases[name] = {
                "httpStatus": response.status_code,
                "status": result["status"],
                "checks": result["checks"],
                "originalContentSha256": hashlib.sha256(content).hexdigest(),
            }
        if role == "issuer":
            response = client.post(
                base + "/api/demo/issue",
                json={"artifacts": [{"content": "x", "metadata": {"title": "public check"}}]},
            )
            assert response.status_code == 403
            checks["serverSigningDisabled"] = {"httpStatus": 403}
        else:
            assert info["issuerApiRequired"] is False
            assert client.post(base + "/api/demo/issue", json={}).status_code == 404
        return {"url": base, "anonymous": True, "checks": checks, "cases": cases}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--commit", required=True, help="Commit observed in successful hosting deployment"
    )
    args = parser.parse_args()
    targets = [
        ("issuer", "https://prooftrail-issuer.vercel.app"),
        ("consumer", "https://prooftrail-consumer.vercel.app"),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda target: probe(*target), targets))
    record = {
        "status": "passed",
        "checkedAt": datetime.now(UTC).isoformat(),
        "deployedCommit": args.commit,
        "checks": dict(zip((role for role, _ in targets), results, strict=True)),
    }
    output = ROOT / "artifacts/public-hosting-probe.json"
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "urls": [result["url"] for result in results],
                "record": str(output),
            }
        )
    )


if __name__ == "__main__":
    main()
