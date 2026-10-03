"""Local-only two-app demo; shared in-memory EVM, independent verifier with no issuer DB."""

import threading

import uvicorn

from prooftrail.api import create_app
from prooftrail.chain import Registry
from prooftrail.consumer_app import create_consumer_app

issuer = Registry.local()
reader = Registry(
    issuer.w3,
    issuer.domain.verifyingContract,
    mode="local",
    expected_chain_id=issuer.domain.chainId,
)
reader.lock = issuer.lock  # The in-memory test provider needs synchronized access.
consumer = uvicorn.Server(uvicorn.Config(create_consumer_app(reader), host="127.0.0.1", port=8776))
thread = threading.Thread(target=consumer.run, daemon=True)
thread.start()
print("应用 A http://127.0.0.1:8775 / 应用 B http://127.0.0.1:8776 · 本地共享测试链")
try:
    uvicorn.run(create_app(issuer), host="127.0.0.1", port=8775)
finally:
    consumer.should_exit = True
    thread.join(timeout=5)
