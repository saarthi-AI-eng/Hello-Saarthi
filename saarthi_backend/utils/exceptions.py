"""Custom exceptions and error response handling."""

from typing import Any, Optional


class SaarthiBackendError(Exception):
    """Base exception for backend errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
        status_code: int = 500,
    ):
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(message)


class ValidationError(SaarthiBackendError):
    """Request validation error (400)."""

    def __init__(self, message: str = "Invalid request body.", details: Optional[dict] = None):
        super().__init__("VALIDATION_ERROR", message, details, 400)


class UnauthorizedError(SaarthiBackendError):
    """Not authenticated (401)."""

    def __init__(self, message: str = "Not authenticated.", details: Optional[dict] = None):
        super().__init__("UNAUTHORIZED", message, details, 401)


class NotFoundError(SaarthiBackendError):
    """Resource not found (404)."""

    def __init__(self, message: str = "Resource not found.", details: Optional[dict] = None):
        super().__init__("NOT_FOUND", message, details, 404)


class ForbiddenError(SaarthiBackendError):
    """Forbidden (403)."""

    def __init__(self, message: str = "Forbidden.", details: Optional[dict] = None):
        super().__init__("FORBIDDEN", message, details, 403)


class RetrievalError(SaarthiBackendError):
    """AI/retrieval service error (500)."""

    def __init__(self, message: str = "Retrieval service temporarily unavailable.", details: Optional[dict] = None):
        super().__init__("RETRIEVAL_ERROR", message, details, 500)


class AIServiceError(SaarthiBackendError):
    """AI service returned error (map to 500 or 422)."""

    def __init__(self, code: str, message: str, status_code: int = 500, details: Optional[dict] = None):
        super().__init__(code, message, details, status_code)


def error_response(
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> dict:
    """Build error body with optional request ID for debugging."""
    body: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }
    if request_id:
        body["error"]["requestId"] = request_id
    return body
