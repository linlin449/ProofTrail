"""应用 B：不调用 ProofTrail 签发服务，独立消费下载的凭证。"""

import argparse
from pathlib import Path

from prooftrail import ReceiptBundle, verify_receipt
from prooftrail.chain import Registry

parser = argparse.ArgumentParser(description="应用 B · 独立研究笔记发布检查")
parser.add_argument("content", type=Path)
parser.add_argument("receipt", type=Path)
parser.add_argument("--contract", required=True, help="部署记录中经核对的可信合约地址")
parser.add_argument("--rpc", default="https://testnet-rpc.monad.xyz")
args = parser.parse_args()
registry = Registry.monad(args.rpc, args.contract)
bundle = ReceiptBundle.model_validate_json(args.receipt.read_text("utf-8"))
result = verify_receipt(args.content.read_bytes(), bundle, registry)
print(result.model_dump_json(indent=2))
print("可发布：来源证据检查通过" if result.status == "valid" else "暂停发布：证据未通过或无法确认")
raise SystemExit(0 if result.status == "valid" else 2)
