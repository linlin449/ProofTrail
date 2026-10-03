"""Create/reuse a dedicated, unfunded TESTNET key locally. Never print the private key."""

import json
from pathlib import Path

from eth_account import Account
from web3 import Web3

folder = Path(".local")
folder.mkdir(exist_ok=True)
key_path = folder / "testnet-private-key.txt"
if not key_path.exists():
    account = Account.create()
    with key_path.open("x", encoding="utf-8") as handle:
        handle.write("0x" + account.key.hex() + "\n")
else:
    account = Account.from_key(key_path.read_text("utf-8").strip())
w3 = Web3(Web3.HTTPProvider("https://testnet-rpc.monad.xyz", request_kwargs={"timeout": 20}))
if w3.eth.chain_id != 10143:
    raise SystemExit("RPC is not Monad Testnet")
result = {
    "purpose": "ProofTrail dedicated TESTNET account only",
    "address": account.address,
    "chainId": 10143,
    "balanceWei": w3.eth.get_balance(account.address),
    "privateKeyPrinted": False,
    "localSecretPath": str(key_path),
    "note": "本地明文密钥只用于测试网，不向其中转入真实资产；目录必须保持 Git 忽略",
}
(folder / "testnet-account-public.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2))
