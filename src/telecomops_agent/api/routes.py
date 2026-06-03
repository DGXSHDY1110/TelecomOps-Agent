"""API routes — health check and future diagnosis endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint — verifies the API service is running."""
    return {"status": "ok", "version": "0.1.0"}
