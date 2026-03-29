"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Basic health check -- returns 200 if the API is reachable."""
    return {"status": "ok"}
