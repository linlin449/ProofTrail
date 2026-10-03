"""Package an explicit source allowlist for local review; never publish or submit."""

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
exact = [
    ".env.example",
    ".gitignore",
    ".gitattributes",
    ".vercelignore",
    "vercel.json",
    "main.py",
    ".dockerignore",
    "Dockerfile",
    "compose.yaml",
    "render.yaml",
    "AGENTS.md",
    "LICENSE",
    "README.md",
    "README.zh-CN.md",
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "启动演示.ps1",
    "artifacts/local-benchmark.json",
    "artifacts/protocol-vector.json",
    "artifacts/verification/standard-input.json",
    "artifacts/verification/compiler-record.json",
    "artifacts/container-smoke.json",
    "artifacts/container-http-probe.json",
    "artifacts/container-build-record.json",
    "artifacts/monad-deployment.json",
    "artifacts/vercel-entrypoint-probe.json",
    "artifacts/monad-acceptance.json",
    "artifacts/monad-container-probe.json",
    "artifacts/verification/sourcify-record.json",
    "artifacts/monad-demo/content.txt",
    "artifacts/monad-demo/receipt.json",
    "artifacts/monad-demo/revoked-content.txt",
    "artifacts/monad-demo/revoked-receipt.json",
    "artifacts/monad-demo/independent-cli-checks.json",
]
patterns = {
    "src": {".py", ".json", ".html", ".css", ".js", ".svg"},
    "tests": {".py"},
    "contracts": {".sol"},
    "examples": {".py"},
    "scripts": {".py", ".cjs", ".ps1"},
    "docs": {".md"},
    "assets": {".png", ".svg", ".json"},
}
paths = [root / name for name in exact]
for folder, suffixes in patterns.items():
    paths.extend(
        path
        for path in (root / folder).rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and not any(
            part.startswith(".") or part == "__pycache__" for part in path.relative_to(root).parts
        )
    )
paths = sorted(set(paths), key=lambda p: p.relative_to(root).as_posix())
if any(not path.is_file() for path in paths):
    raise SystemExit("Source allowlist includes missing files; stop packaging.")
data = json.loads((root / "src/prooftrail/data/registry.json").read_text("utf-8"))
source_hash = hashlib.sha256((root / "contracts/ProofTrailRegistry.sol").read_bytes()).hexdigest()
if data["sourceSha256"] != source_hash:
    raise SystemExit("Compiled artifact and source differ; run npm run compile first.")
manifest = {
    path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in paths
}
output = root / "artifacts/review"
output.mkdir(parents=True, exist_ok=True)
archive = output / "ProofTrail-source.zip"
temporary = archive.with_suffix(".zip.tmp")
with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in paths:
        bundle.write(path, arcname="prooftrail/" + path.relative_to(root).as_posix())
with zipfile.ZipFile(temporary) as bundle:
    if bundle.testzip() is not None or len(bundle.namelist()) != len(paths):
        raise SystemExit("Archive verification failed.")
temporary.replace(archive)
record = {
    "builtAtUtc": datetime.now(UTC).isoformat(),
    "fileCount": len(paths),
    "archiveSha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "sourceSha256": source_hash,
    "files": manifest,
    "scope": "local source review only; no competition submission or external publication",
}
(output / "manifest.json").write_text(
    json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8"
)
print(
    json.dumps(
        {
            "archive": str(archive),
            "fileCount": len(paths),
            "archiveSha256": record["archiveSha256"],
            "bytes": archive.stat().st_size,
        },
        indent=2,
    )
)
