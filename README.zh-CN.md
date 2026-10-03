# ProofTrail · 让 AI 输出带着可验证的出处流动

ProofTrail 面向 AI 应用开发者与内容平台，提供 Python SDK、独立验证 API 和可移植 JSON 凭证。发行者签名证明其声明，一批凭证通过 Merkle 根登记在 Monad；另一应用持有原文与凭证即可验证，不需要相信 ProofTrail 的数据库。

**项目状态：开发中。比赛草稿已建立，未正式提交。** 当前真实进度和证据以 [工作计划](docs/工作计划.md) 与 [检查记录](docs/检查记录.md) 为准。获奖不是已验证结果。

**Monad 测试网已经实际部署并验收**：链 10143，合约 `0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7`。[Sourcify 源码精确匹配](https://repo.sourcify.dev/10143/0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7)，批量登记、独立消费与发行者撤销通过。查看 [真实交易、测量与检查步骤](docs/Monad实测与检查.md)。本机运行的页面读取真实测试网，但尚未公开托管。

## 先看这些中文文档

- [要完成的工作、验收门槛与排期](docs/工作计划.md)
- [架构、凭证格式与信任边界](docs/架构与协议.md)
- [测试与人工检查记录](docs/检查记录.md)
- [安全与隐私说明](docs/安全与隐私.md)
- [签发端 → 独立知识发布站检查](docs/双应用检查.md)
- [Pitch 审阅视频与容器复现](docs/视频与容器复现.md)
- [公开源码与在线发布](docs/在线发布.md)

## 产品的四个动作

1. **签发**：对原始 UTF-8 字节计算 SHA-256，发行者签署包含内容、元数据、父凭证和有效期的 EIP-712 声明。
2. **批量登记**：一笔交易登记一批凭证的 Merkle 根；逐项凭证包含自己的证明路径。
3. **独立验证**：检查签名、内容、证明路径、可信合约中的发行者、撤销状态和有效期，逐项展示证据。
4. **撤销**：发行者在链上撤销单张凭证；既有下载副本的验证结果随之改变。

签名证明的是“该地址声明了这份内容”，不能证明内容真实、版权属于签名人，也不能证明实际使用了某个模型。

## 本地运行（Windows PowerShell）

```powershell
cd C:\Users\lin17\Desktop\project\prooftrail
uv sync --extra dev
npm ci
npm run compile
uv run python -m prooftrail serve --host 127.0.0.1 --port 8765
```

打开 http://127.0.0.1:8765 。默认模式使用真实本地 EVM 执行同一份 Solidity 合约，界面明确标注“本地 EVM”，不冒充 Monad 部署。本地链重启会重置；导出的凭证应在同一次运行中测试。

```powershell
uv run pytest
uv run ruff check .
```

## 参赛交付

主赛道：Trust, Identity & AI Infrastructure。平台面板截止时间：2026-10-14 11:59（GMT+8）。最终需要公开 GitHub、Logo、真实 Monad 部署与在线产品、3 分钟技术演示、2 分钟 pitch 和用户获取计划。会在用户检查确认后才执行比赛提交。

## 开源与 AI 使用

MIT License。使用 OpenAI Codex 辅助设计、编码、测试和文档；作者对最终实现与声明负责。协议采用 EIP-712 与标准 SHA-256/Keccak 算法，密码学操作使用 eth-account/eth-utils，不自创签名算法。依赖来源见锁文件。
