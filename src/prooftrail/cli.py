import argparse
import json
import os
from pathlib import Path

from .chain import Registry
from .models import Metadata, ReceiptBundle
from .protocol import build_batch, create_receipt, verify_receipt


def main():
    parser = argparse.ArgumentParser(description="ProofTrail 独立凭证 SDK 与演示服务")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="运行可检查的产品页面")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--mode", choices=["local", "monad"], default="local")
    consumer = sub.add_parser("consumer", help="独立运行应用 B：只读链上证据并生成私有预览")
    consumer.add_argument("--host", default="127.0.0.1")
    consumer.add_argument("--port", type=int, default=8776)
    consumer.add_argument("--rpc", default="https://testnet-rpc.monad.xyz")
    consumer.add_argument("--contract", required=True)
    verify = sub.add_parser("verify", help="不依赖发行 API，读取可信链验证")
    verify.add_argument("content", type=Path)
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--rpc", default="https://testnet-rpc.monad.xyz")
    verify.add_argument("--contract", required=True)
    issue = sub.add_parser("issue", help="在 Monad 测试网签发并锚定文件；密钥仅从环境读取")
    issue.add_argument("content", type=Path)
    issue.add_argument("--title", required=True)
    issue.add_argument("--output", type=Path, required=True)
    issue.add_argument("--rpc", default="https://testnet-rpc.monad.xyz")
    issue.add_argument("--contract", required=True)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from .api import create_app

        if args.mode == "local" and args.host not in ("127.0.0.1", "localhost", "::1"):
            parser.error("本地演示签名服务只能绑定回环地址；公开部署必须使用 monad 模式")
        registry = (
            Registry.local()
            if args.mode == "local"
            else Registry.monad(
                os.getenv("PROOFTRAIL_RPC_URL", "https://testnet-rpc.monad.xyz"),
                os.environ["PROOFTRAIL_CONTRACT"],
            )
        )
        uvicorn.run(create_app(registry), host=args.host, port=args.port)
    elif args.command == "consumer":
        import uvicorn

        from .consumer_app import create_consumer_app

        uvicorn.run(
            create_consumer_app(Registry.monad(args.rpc, args.contract)),
            host=args.host,
            port=args.port,
        )
    elif args.command == "verify":
        registry = Registry.monad(args.rpc, args.contract)
        bundle = ReceiptBundle.model_validate_json(args.bundle.read_text("utf-8"))
        result = verify_receipt(args.content.read_bytes(), bundle, registry)
        print(result.model_dump_json(indent=2))
        raise SystemExit(0 if result.status == "valid" else 2)
    elif args.command == "issue":
        if args.output.exists():
            parser.error("输出文件已存在；选择新路径，避免覆盖凭证")
        key = os.environ.get("PROOFTRAIL_PRIVATE_KEY")
        if not key:
            parser.error("请在本机环境配置专用测试私钥 PROOFTRAIL_PRIVATE_KEY；不要发到聊天")
        registry = Registry.monad(args.rpc, args.contract)
        signed = create_receipt(
            args.content.read_bytes(), Metadata(title=args.title), registry.domain, key
        )
        bundle = build_batch([signed])[0]
        tx = registry.anchor(bundle.root, 1, key)
        args.output.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "transaction": tx}, indent=2))
