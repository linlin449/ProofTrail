# ProofTrail

Portable AI-output provenance receipts, issuer-owned Merkle batch anchors and revocations, and an independent Python verifier for Monad.

The hackathon draft is in **Trust, Identity & AI Infrastructure**. Implementation is under review; it has **not been submitted**. The registry is deployed on Monad testnet (chain 10143) at `0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7`, with [exact-match source verification](https://repo.sourcify.dev/10143/0xd4c01FEdb19eF081AAF3c6814316d8CeF7579Cd7). The [issuer workbench](https://prooftrail-issuer.vercel.app) and [independent consumer](https://prooftrail-consumer.vercel.app) run Python FastAPI on Vercel Hobby. Anonymous public HTTP checks passed for valid, tampered and revoked receipts; the browser wallet transaction flow remains to be reviewed. Chinese project documentation starts at [README.zh-CN.md](README.zh-CN.md); real transaction evidence and reproducible checks are in [the testnet walkthrough](docs/Monad实测与检查.md).

## Run locally

No wallet is required to try the [independent consumer](https://prooftrail-consumer.vercel.app): choose the public live-chain example and run the check. The sample is synthetic, its original signed bytes are preserved, and verification reads current Monad state rather than returning a canned verdict.

```sh
uv sync --extra dev --group dev
npm ci --ignore-scripts
npm run compile
uv run python -m prooftrail serve
```

Open http://127.0.0.1:8765. The default uses a real local PyEVM execution of the same Solidity registry and explicitly identifies itself as **local EVM**, not a Monad deployment. Restarting resets that chain.

## Verify

```sh
uv run pytest -q
npm run test:vectors
npm run test:wallet-ui
uv run ruff check .
```

EIP-712 binds issuer claims to a configured chain and registry. Original bytes and constrained metadata use SHA-256. Receipt digests become double-hashed Merkle leaves. The verifier checks issuer signature, content, metadata, proof, trusted deployment, anchor ownership, expiry, and current revocation; RPC failures never produce a valid result.

An independent consumer is in `examples/consumer.py`; the issuing service is not part of its trust model. CLI signing takes a dedicated testnet key only from the local environment. Public mode never exposes server-side signing.

Run `uv run python examples/two_apps.py` for the local issuer at port 8775 and the independent Knowledge Publisher at port 8776. They share a local in-memory EVM, but the consumer has no issuer API or database dependency. On Monad, `prooftrail consumer --contract <trusted-address>` runs the read-only consumer as a separate service. See [the Chinese integration walkthrough](docs/双应用检查.md).

## Limits

Issuer attribution is not factual truth, copyright ownership, real-world identity, or proof of actual model execution. This is not a C2PA implementation or independently audited production system. Local gas measurements are not Monad performance evidence. Current known gaps and acceptance requirements are maintained in `docs/工作计划.md`.

MIT. Built with OpenAI Codex assistance, disclosed in the Chinese documentation and project description. No fake traction or deployment claims.
