"""实际 EVM 交易的本地 Gas 对照。不能用作 Monad 网络性能数据。"""

import json
from pathlib import Path

from prooftrail import Metadata, build_batch, create_receipt, verify_receipt
from prooftrail.chain import Registry

registry = Registry.local()
results = []
for size in (1, 4, 16, 32):
    receipts = [
        create_receipt(
            f"Synthetic benchmark item {i}".encode(),
            Metadata(title=f"Benchmark {i}"),
            registry.domain,
            registry.local_key,
        )
        for i in range(size)
    ]
    bundles = build_batch(receipts)
    tx = registry.anchor(bundles[0].root, size, registry.local_key)
    assert all(
        verify_receipt(f"Synthetic benchmark item {i}".encode(), bundle, registry).status == "valid"
        for i, bundle in enumerate(bundles)
    )
    results.append({"size": size, **tx, "gasPerReceipt": tx["gasUsed"] / size})
document = {
    "environment": "local PyEVM; not Monad performance evidence",
    "compiler": "solc 0.8.28 optimizer 200 paris",
    "chainId": registry.domain.chainId,
    "contract": registry.domain.verifyingContract,
    "measurements": results,
    "limitations": [
        "签名数量随批次线性增加；根登记 Gas 不包含签名与离线构树成本",
        "本地 EVM Gas 与真实 Monad 的 Gas 计费可能不同，必须另外实测",
        "批内叶子数量为发行者承诺，Merkle 根本身不证明计数语义",
    ],
}
output = Path("artifacts/local-benchmark.json")
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(document, ensure_ascii=False, indent=2))
