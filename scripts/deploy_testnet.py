"""只部署至链 10143。默认只做只读预检；显式 --broadcast 才发送交易。"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from eth_account import Account
from web3 import Web3

from prooftrail.chain import Registry, artifact

parser = argparse.ArgumentParser(description="ProofTrail Monad 测试网部署")
parser.add_argument("--rpc", default="https://testnet-rpc.monad.xyz")
parser.add_argument("--broadcast", action="store_true", help="发送专用测试账户的部署交易")
args = parser.parse_args()
w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": 20}))
if w3.eth.chain_id != 10143:
    raise SystemExit("拒绝操作：网络不是 Monad 测试网（10143）")
key = os.getenv("PROOFTRAIL_PRIVATE_KEY")
if not key:
    print(
        json.dumps(
            {
                "chainId": w3.eth.chain_id,
                "block": w3.eth.block_number,
                "state": "只读连接通过；尚未配置专用测试签名账户",
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if not args.broadcast else 2)
account = Account.from_key(key)
data = artifact()
factory = w3.eth.contract(abi=data["abi"], bytecode=data["bytecode"])
balance = w3.eth.get_balance(account.address)
print(
    json.dumps(
        {
            "chainId": 10143,
            "account": account.address,
            "balanceWei": balance,
            "broadcast": args.broadcast,
        },
        ensure_ascii=False,
    )
)
if not args.broadcast:
    raise SystemExit(0)
record = Path("artifacts/monad-deployment.json")
if record.exists():
    raise SystemExit("已有部署记录，拒绝自动覆盖。先检查现有地址。")
transaction = factory.constructor().build_transaction(
    {
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address, "pending"),
        "chainId": 10143,
    }
)
maximum_fee = transaction.get("maxFeePerGas", transaction.get("gasPrice", 0)) * transaction["gas"]
if balance < maximum_fee:
    raise SystemExit("测试 MON 余额不足，先通过官方水龙头为专用账户领取。")
tx_hash = w3.eth.send_raw_transaction(account.sign_transaction(transaction).raw_transaction)
print("部署交易：0x" + tx_hash.hex())
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
if receipt.status != 1:
    raise SystemExit("部署交易失败，不写入成功记录")
registry = Registry.monad(args.rpc, receipt.contractAddress)
document = {
    "network": "Monad Testnet",
    "chainId": 10143,
    "address": registry.domain.verifyingContract,
    "deployer": account.address,
    "transactionHash": "0x" + tx_hash.hex(),
    "blockNumber": receipt.blockNumber,
    "gasUsed": receipt.gasUsed,
    "sourceSha256": data["sourceSha256"],
    "compiler": data["compiler"],
    "runtimeMatches": True,
    "checkedAtUtc": datetime.now(UTC).isoformat(),
}
record.parent.mkdir(exist_ok=True)
record.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
print(json.dumps(document, indent=2))
