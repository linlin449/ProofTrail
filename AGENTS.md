# ProofTrail 项目约定

- 用户授权：完成参赛项目与中文文档，持续提供本地检查；未经用户确认不得提交比赛。
- 主技术栈：Python 3.12、FastAPI、web3.py、eth-account、Solidity 0.8.28；前端使用原生 HTML/CSS/JS。
- 阅读入口：README.zh-CN.md、docs/工作计划.md、docs/架构与协议.md。
- 不伪造部署、用户、性能、集成或获奖证据。明确区分本地 EVM 与 Monad 测试网。
- 不提交 .env、私钥、真实内容或个人资料。测试签名使用专用测试账户。
- 凭证使用 EIP-712；SHA-256 对原始字节做哈希；Merkle 叶子双哈希，节点排序。
- 验证必须检查可信网络和合约、签名、内容、Merkle 证明、链上发行者、撤销和过期；RPC 失败不应显示“验证通过”。
- 公共部署不开放服务器签名写入接口；浏览器用户从自己的钱包签名。演示服务器写入仅限回环地址。
- 常用命令：`uv sync --extra dev`、`npm ci`、`npm run compile`、`uv run pytest`、`uv run python -m prooftrail serve`。
- 更新 docs/工作计划.md 和 docs/检查记录.md，记录证据和未完成项。
