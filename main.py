"""Vercel discovers this FastAPI app; both projects run strictly in Monad mode."""

from prooftrail.serverless import create_public_app

app = create_public_app()
