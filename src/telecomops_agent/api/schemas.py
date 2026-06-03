"""Pydantic schemas for API request and response models.

Note: Only minimal schemas are defined in Milestone 1.
Full diagnosis schemas will be added in later milestones.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str
    version: str


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error_code: str
    message: str
    details: dict | None = None
    suggestion: str | None = None
