"""API error handling — custom exceptions and error response helpers."""

from fastapi import HTTPException


class TelecomOpsError(Exception):
    """Base exception for TelecomOps-Agent application errors."""

    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class InvalidRequestError(TelecomOpsError):
    """Raised when the incoming request is malformed or missing required fields."""

    def __init__(self, message: str):
        super().__init__(message, error_code="INVALID_REQUEST")


class ToolExecutionError(TelecomOpsError):
    """Raised when a tool call fails during diagnosis."""

    def __init__(self, message: str):
        super().__init__(message, error_code="TOOL_EXECUTION_FAILED")


class InsufficientEvidenceError(TelecomOpsError):
    """Raised when evidence is insufficient for a reliable diagnosis."""

    def __init__(self, message: str):
        super().__init__(message, error_code="INSUFFICIENT_EVIDENCE")
