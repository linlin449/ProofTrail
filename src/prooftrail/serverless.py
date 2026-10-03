"""Keyless ASGI entrypoint; defer RPC I/O until requests, including build inspection."""

import os
import threading

from .api import create_app
from .chain import Registry
from .consumer_app import create_consumer_app
from .models import Domain

MONAD_RPC = "https://testnet-rpc.monad.xyz"
MONAD_CONTRACT = "0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7"


class DeferredMonadRegistry:
    """Keep public configuration available; every network operation uses a checked Registry."""

    def __init__(self, rpc_url: str, address: str):
        self.mode = "monad"
        self.domain = Domain(chainId=10143, verifyingContract=address)
        self.lock = threading.RLock()
        self._rpc_url = rpc_url
        self._registry = None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        with self.lock:
            if self._registry is None:
                # Assignment happens only after chain ID and deployed bytecode checks succeed.
                self._registry = Registry.monad(self._rpc_url, self.domain.verifyingContract)
            return getattr(self._registry, name)


def create_public_app():
    role = os.getenv("PROOFTRAIL_APP", "issuer")
    if role not in ("issuer", "consumer"):
        raise ValueError("PROOFTRAIL_APP must be issuer or consumer")
    registry = DeferredMonadRegistry(
        os.getenv("PROOFTRAIL_RPC_URL", MONAD_RPC),
        os.getenv("PROOFTRAIL_CONTRACT", MONAD_CONTRACT),
    )
    return create_app(registry) if role == "issuer" else create_consumer_app(registry)
