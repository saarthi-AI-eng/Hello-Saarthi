"""HTTP client for AI service (backend_api_docs.md)."""

from typing import Any, Optional

import httpx
from saarthi_backend.schema.ai_client_schemas import (
    AIChatRequest,
    AIChatResponse,
    AIErrorResponse,
    AIKbStatusResponse,
    AISessionHistoryResponse,
)
from saarthi_backend.utils.exceptions import AIServiceError
from saarthi_backend.utils.logging import get_logger

logger = get_logger(__name__)


class AIClient:
    """Client for AI service: chat, KB, session."""

    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _check_error(self, response: httpx.Response, body: Any) -> None:
        """Raise AIServiceError if AI service returned error body."""
        if response.status_code >= 400:
            try:
                err = AIErrorResponse.model_validate(body)
                code = err.code or "AI_SERVICE_ERROR"
                msg = err.message or response.reason_phrase
                status = 500
                if response.status_code == 400:
                    status = 400
                elif response.status_code == 404:
                    status = 404
                elif response.status_code == 422:
                    status = 422
                raise AIServiceError(code=code, message=msg, status_code=status)
            except AIServiceError:
                raise
            except Exception:
                raise AIServiceError(
                    code="AI_SERVICE_ERROR",
                    message=response.reason_phrase or "AI service error",
                    status_code=response.status_code,
                )

    async def chat(self, body: AIChatRequest) -> AIChatResponse:
        """POST /v1/chat."""
        url = self._url("/v1/chat")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=body.model_dump(exclude_none=True))
            data = response.json() if response.content else {}
            self._check_error(response, data)
            return AIChatResponse.model_validate(data)

    async def get_kb_status(self) -> AIKbStatusResponse:
        """GET /v1/kb/status."""
        url = self._url("/v1/kb/status")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            data = response.json() if response.content else {}
            self._check_error(response, data)
            return AIKbStatusResponse.model_validate(data)

    async def upload_file(self, agent_name: str, file_content: bytes, file_name: str) -> dict:
        """POST /v1/kb/upload (multipart)."""
        url = self._url("/v1/kb/upload")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                files={"file": (file_name, file_content)},
                data={"agent_name": agent_name},
            )
            data = response.json() if response.content else {}
            self._check_error(response, data)
            return data

    async def reindex(self, agent_name: str) -> dict:
        """POST /v1/kb/reindex."""
        url = self._url("/v1/kb/reindex")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json={"agent_name": agent_name})
            data = response.json() if response.content else {}
            self._check_error(response, data)
            return data

    async def delete_file(self, agent_name: str, file_name: str) -> dict:
        """DELETE /v1/kb/file."""
        url = self._url("/v1/kb/file")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url, json={"agent_name": agent_name, "file_name": file_name})
            data = response.json() if response.content else {}
            self._check_error(response, data)
            return data

    async def get_session_history(self, session_id: str) -> AISessionHistoryResponse:
        """GET /v1/session/{session_id}/history."""
        url = self._url(f"/v1/session/{session_id}/history")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            data = response.json() if response.content else {}
            self._check_error(response, data)
            return AISessionHistoryResponse.model_validate(data)

    async def delete_session(self, session_id: str) -> dict:
        """DELETE /v1/session/{session_id}."""
        url = self._url(f"/v1/session/{session_id}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url)
            data = response.json() if response.content else {}
            self._check_error(response, data)
            return data
