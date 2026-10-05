# Monad 真实部署与检查 · 2026-10-03

本页对应真实 Monad 测试网；样例是公开的合成测试笔记，不代表外部用户采用。网站项目仍为草稿，未提交。

## 合约与源码

- Chain ID：10143，RPC：`https://testnet-rpc.monad.xyz`。
- 合约：`0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7`。
- 部署交易：`0x9e0e482c6b05f6d50db436e524eb0df3475b01340e496692ef845400eda8f45d`，区块 67,709,389，Gas 318,157，交易成功。
- 专用发行地址：`0xFDef1C2f141Ab9B55E8fDefB27bD6F43aF4987e0`。私钥仅在本机被忽略的目录，不进入 API、容器、仓库或审阅包。
- 本机直接比对链上 runtime 与编译 artifact 一致；Sourcify 返回 creationMatch 与 runtimeMatch 均为 `exact_match`。
- [公开源码核对](https://repo.sourcify.dev/10143/0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7)。发布源码不等于第三方安全审计。

证据：`artifacts/monad-deployment.json`、`artifacts/verification/standard-input.json`、`compiler-record.json`、`sourcify-record.json`。

## 实际批量登记

| 凭证数 | 登记交易数 | Gas 总量 | 均摊 Gas/条 | 测试 MON 费用/批 | 发送至取得回执 ms |
|---|---|---|---|---|---|
| 1 | 1 | 88,261 | 88,261 | 0.009002622 | 550.53 |
| 4 | 1 | 88,261 | 22,065.25 | 0.009002622 | 1,236.59 |
| 16 | 1 | 88,261 | 5,516.3125 | 0.009002622 | 546.33 |
| 32 | 1 | 88,261 | 2,758.15625 | 0.009002622 | 560.19 |

这四个单次样本说明当前固定根登记的均摊成本随批量下降；不证明吞吐量、普遍延迟或共识最终性。耗时包含 RPC 传输和回执轮询，不含签名、树构建和用户交互。Gas 可能随 calldata 等变化；测试 MON 没有真实货币价值，不换算美元。

53 份凭证的签名与 Merkle 路径全部离线检查；每批首尾样本读取链上状态，共 7 次。32 份中的首条随后用于撤销实验，当前应验证为无效。完整合成内容、凭证、交易和测量在 `artifacts/monad-acceptance.json`。

1/4/16/32 登记交易依次为：

```text
0x53e686b015fff1ea51376deb20a48de65e566fb51d096594ebc498ddb78beb2b
0x0ad7891a76c818533f7caa623e2b454bdf4e8feaff8e4ba6df29342c8953dc5f
0x15efb81838aecf29ac7e8487045d821f6c560ee84f1aee9ebe51c32c2406fb67
0x6ede8a4598c1e35e3a939ba08d2b800ab0d7406a2e47a479d61d3ab46e91545f
```

## 撤销语义

另一个专用测试账户对同一 receiptId 撤销成功，但只写入自己的命名空间，原发行者凭证仍有效。不是声称另一账户交易回退。交易：`0x15ab1288653ec6202c1634d14950c7720d474a221e09e4d4b5467394d048e150`。

原发行者撤销后，独立验证器读到撤销并拒绝凭证。交易：`0xf6cadd87de445d5a3aa3962dfffa3be6d868ff11a62b335c63d3ebc22eedc780`。

## 无钱包也能检查已登记凭证

当前本机发行工作台 `http://127.0.0.1:8785` 与独立发布站 `http://127.0.0.1:8786` 是两个进程，各自读取真实 Monad，无共享内存链。它们不是外网托管地址。

在发布站粘贴 `artifacts/monad-demo/content.txt` 原文与 `receipt.json`，点击检查后生成私有预览。修改原文应拒绝。换成 `revoked-content.txt` 与 `revoked-receipt.json` 应在撤销项失败。注意精确保留空格与换行。

重新运行发布站：

```powershell
uv run python -m prooftrail consumer --contract 0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7 --port 8786
```

脱离两款 API 的独立 CLI：

```powershell
uv run python -m prooftrail verify artifacts/monad-demo/content.txt artifacts/monad-demo/receipt.json --contract 0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7
uv run python -m prooftrail verify artifacts/monad-demo/revoked-content.txt artifacts/monad-demo/revoked-receipt.json --contract 0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7
```

实际独立进程结果：第一份 valid/退出码 0；撤销份 invalid/退出码 2。保存于 `artifacts/monad-demo/independent-cli-checks.json`。

## 仍待验收

2026-10-03 用户在外置浏览器完成账户授权、EIP-712 钱包签名与实际登记交易，下载凭证经独立 SDK 和公网消费端九项检查通过，修改原文后拒绝预览、恢复后重新通过。登记 status=1、区块 67784181、Gas 88,261；本机原始证据见 `artifacts/review/user-wallet-registration.json`、`user-wallet-verification.json` 和 `user-wallet-browser-check.json`。这些用户证据不进入公开源码。公开 GitHub 与 Vercel 双服务已完成；匿名公网验证记录在 `artifacts/public-hosting-probe.json`。最终真实操作录像与用户审阅仍待完成。
