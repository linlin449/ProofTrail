"""Application B: an independent publishing preflight, with no issuer API dependency."""

import mimetypes
from importlib.resources import files

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .chain import Registry
from .models import ReceiptBundle, StrictModel
from .protocol import verify_receipt
from .public_example import public_example
from .web_security import protect_app


class AssessmentRequest(StrictModel):
    content: str = Field(max_length=50000)
    bundle: ReceiptBundle


def create_consumer_app(registry: Registry) -> FastAPI:
    app = FastAPI(title="Knowledge Publisher · ProofTrail consumer", docs_url=None, redoc_url=None)
    protect_app(app)
    static = files("prooftrail").joinpath("consumer_static")
    mimetypes.add_type("text/javascript", ".js")
    app.mount("/static", StaticFiles(directory=str(static)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(static.joinpath("index.html")))

    @app.get("/api/info")
    def info():
        return {
            "mode": registry.mode,
            "chainId": registry.domain.chainId,
            "contract": registry.domain.verifyingContract,
            "issuerApiRequired": False,
            "exampleAvailable": public_example(registry) is not None,
        }

    @app.get("/api/example")
    def example():
        data = public_example(registry)
        if data is None:
            raise HTTPException(404, "当前可信网络与合约没有预置公开样例")
        return data

    @app.get("/health")
    def health():
        try:
            registry.assert_trusted()
            return {"status": "ok", "chainId": registry.domain.chainId}
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    @app.post("/api/assess")
    def assess(payload: AssessmentRequest):
        with registry.lock:
            result = verify_receipt(payload.content.encode("utf-8"), payload.bundle, registry)
        # This is a preflight, not a permanent endorsement or a public publishing action.
        return {
            "eligibleForPreview": result.status == "valid",
            "verification": result.model_dump(),
            "preview": {
                "title": payload.bundle.metadata.title,
                "content": payload.content,
                "issuer": payload.bundle.claim.issuer,
            }
            if result.status == "valid"
            else None,
        }

    return app
