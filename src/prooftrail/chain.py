import json
import threading
import time
from importlib.resources import files

from eth_account import Account
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3
from web3.providers.eth_tester import EthereumTesterProvider

from .models import Domain


def artifact() -> dict:
    return json.loads(files("prooftrail").joinpath("data/registry.json").read_text("utf-8"))


class Registry:
    def __init__(self, web3: Web3, address: str, *, mode: str, expected_chain_id: int):
        self.w3 = web3
        self.mode = mode
        self.domain = Domain(chainId=expected_chain_id, verifyingContract=address)
        self.contract = web3.eth.contract(
            address=self.domain.verifyingContract, abi=artifact()["abi"]
        )
        self.lock = threading.RLock()
        self.assert_trusted()

    def assert_trusted(self):
        if self.w3.eth.chain_id != self.domain.chainId:
            raise ValueError("RPC chain ID does not match configured chain")
        expected_code = bytes.fromhex(artifact()["deployedBytecode"][2:])
        if bytes(self.w3.eth.get_code(self.domain.verifyingContract)) != expected_code:
            raise ValueError("Registry bytecode does not match the audited project artifact")

    @classmethod
    def local(cls):
        backend = PyEVMBackend()
        tester = EthereumTester(backend=backend)
        w3 = Web3(EthereumTesterProvider(tester))
        data = artifact()
        factory = w3.eth.contract(abi=data["abi"], bytecode=data["bytecode"])
        receipt = w3.eth.wait_for_transaction_receipt(
            factory.constructor().transact({"from": w3.eth.accounts[0]})
        )
        if receipt.status != 1:
            raise RuntimeError("Local EVM deployment failed")
        registry = cls(w3, receipt.contractAddress, mode="local", expected_chain_id=w3.eth.chain_id)
        registry.local_key = backend.account_keys[0].to_bytes()
        registry.tester = tester
        registry.deployment_tx = "0x" + receipt.transactionHash.hex()
        return registry

    @classmethod
    def monad(cls, rpc_url: str, address: str):
        return cls(
            Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15})),
            address,
            mode="monad",
            expected_chain_id=10143,
        )

    def get_batch(self, batch_id: str):
        return self.contract.functions.batches(bytes.fromhex(batch_id[2:])).call()

    def is_revoked(self, issuer: str, receipt_id: str) -> bool:
        return self.contract.functions.revoked(issuer, bytes.fromhex(receipt_id[2:])).call()

    def anchor_data(self, root: str, count: int) -> str:
        return self.contract.encode_abi("anchorBatch", args=[bytes.fromhex(root[2:]), count])

    def revoke_data(self, receipt_id: str) -> str:
        return self.contract.encode_abi("revoke", args=[bytes.fromhex(receipt_id[2:])])

    def transact(self, function, key) -> dict:
        with self.lock:
            self.assert_trusted()
            account = Account.from_key(key)
            if self.mode == "local":
                # PyEVM's timestamp otherwise advances one second per block even after idle time.
                target_time = max(int(time.time()), self.w3.eth.get_block("latest").timestamp + 1)
                self.tester.time_travel(target_time)
                tx_hash = function.transact({"from": account.address})
            else:
                tx = function.build_transaction(
                    {
                        "from": account.address,
                        "nonce": self.w3.eth.get_transaction_count(account.address, "pending"),
                        "chainId": self.domain.chainId,
                    }
                )
                tx_hash = self.w3.eth.send_raw_transaction(
                    account.sign_transaction(tx).raw_transaction
                )
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
            if receipt.status != 1:
                raise RuntimeError("Transaction reverted")
            block = self.w3.eth.get_block(receipt.blockNumber)
            return {
                "transactionHash": "0x" + tx_hash.hex(),
                "blockNumber": receipt.blockNumber,
                "gasUsed": receipt.gasUsed,
                "gasPriceWei": receipt.effectiveGasPrice,
                "blockTimestamp": block.timestamp,
                "network": self.mode,
            }

    def anchor(self, root: str, count: int, key) -> dict:
        return self.transact(
            self.contract.functions.anchorBatch(bytes.fromhex(root[2:]), count), key
        )

    def revoke(self, receipt_id: str, key) -> dict:
        return self.transact(self.contract.functions.revoke(bytes.fromhex(receipt_id[2:])), key)
