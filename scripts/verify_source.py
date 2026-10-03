"""Publish this deployed MIT contract's compiler input to Sourcify API v2.

No keys or transactions. One verification ticket is journaled before polling.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://sourcify.dev/server"
RECORD = ROOT / "artifacts/verification/sourcify-record.json"


def save(record):
    RECORD.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    deployment = json.loads((ROOT / "artifacts/monad-deployment.json").read_text("utf-8"))
    compiler = json.loads((ROOT / "artifacts/verification/compiler-record.json").read_text("utf-8"))
    chain_id, address = deployment["chainId"], deployment["address"]
    if chain_id != 10143 or not deployment["runtimeMatches"]:
        raise SystemExit("Only the verified Monad testnet deployment is supported.")
    with httpx.Client(
        timeout=45,
        headers={"User-Agent": "ProofTrail/0.1 (+https://hackathon.monad.xyz/)"},
    ) as client:
        if RECORD.exists():
            record = json.loads(RECORD.read_text("utf-8"))
            if record["chainId"] != chain_id or record["address"] != address:
                raise SystemExit("Existing verification record belongs to a different deployment.")
        else:
            chains = client.get(f"{BASE}/chains")
            chains.raise_for_status()
            supported = next(c for c in chains.json() if c["chainId"] == chain_id)
            if not supported["supported"]:
                raise SystemExit("Sourcify does not currently support this chain.")
            if not args.publish:
                print("Preflight passed; use --publish to publish only the MIT contract source.")
                return
            response = client.post(
                f"{BASE}/v2/verify/{chain_id}/{address}",
                json={
                    "stdJsonInput": json.loads(
                        (ROOT / "artifacts/verification/standard-input.json").read_text("utf-8")
                    ),
                    "compilerVersion": compiler["compiler"].removesuffix(".Emscripten.clang"),
                    "contractIdentifier": compiler["contract"],
                    "creationTransactionHash": deployment["transactionHash"],
                },
            )
            response.raise_for_status()
            record = {
                "chainId": chain_id,
                "address": address,
                "requestedAtUtc": datetime.now(UTC).isoformat(),
                "ticket": response.json(),
                "sourceSha256": compiler["sourceSha256"],
                "repositoryUrl": f"https://repo.sourcify.dev/{chain_id}/{address}",
            }
            save(record)
        ticket = record["ticket"]["verificationId"]
        job = client.get(f"{BASE}/v2/verify/{ticket}")
        job.raise_for_status()
        record["job"] = job.json()
        record["checkedAtUtc"] = datetime.now(UTC).isoformat()
        save(record)
        print(json.dumps(record["job"], indent=2))


if __name__ == "__main__":
    main()
