"""Probe the isolated local-EVM container over real loopback HTTP. Refuses Monad writes."""

import json
from urllib.request import Request, urlopen


def call(path, body=None):
    request = Request(
        "http://127.0.0.1:8765" + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


info = call("/api/info")
assert info["mode"] == "local", "Refuse to issue or revoke on an external network"
assert call("/health")["status"] == "ok"
content = "Runtime HTTP probe\n"
issued = call(
    "/api/demo/issue",
    {"artifacts": [{"content": content, "metadata": {"title": "Container HTTP"}}]},
)
bundle = issued["bundles"][0]
payload = {"content": content, "bundle": bundle}
assert call("/api/verify", payload)["status"] == "valid"
assert call("/api/verify", payload | {"content": content + "changed"})["status"] == "invalid"
call("/api/demo/revoke", {"receiptId": bundle["receiptId"]})
assert call("/api/verify", payload)["status"] == "invalid"
print(
    json.dumps(
        {
            "transport": "actual loopback HTTP",
            "localEvmOnly": True,
            "health": "ok",
            "issue": "passed",
            "verification": "passed",
            "tampering": "rejected",
            "revocation": "rejected",
            "transactionHash": issued["transaction"]["transactionHash"],
            "contract": info["contract"],
            "chainId": info["chainId"],
        },
        indent=2,
    )
)
