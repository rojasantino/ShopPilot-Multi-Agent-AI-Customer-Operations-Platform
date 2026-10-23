"""Thin typed wrapper around the ShopPilot API. The UI never touches the database directly."""

import os
from typing import Any

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "change-me-dev-key")


class ApiError(RuntimeError):
    pass


class ShopPilotClient:
    def __init__(self, base_url: str = API_URL, api_key: str = API_KEY) -> None:
        self._http = httpx.Client(base_url=base_url, headers={"X-API-Key": api_key}, timeout=60)

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(f"Cannot reach the API: {exc}") from exc
        if response.status_code >= 400:
            detail = response.json().get("detail", response.text) if response.content else ""
            raise ApiError(f"{response.status_code}: {detail}")
        return response.json()

    def chat(self, customer_id: str, message: str) -> dict:
        return self._request("POST", "/v1/chat", json={"customer_id": customer_id, "message": message})

    def orders(self, customer_id: str) -> list[dict]:
        return self._request("GET", f"/v1/customers/{customer_id}/orders")

    def approvals(self, status: str | None = None) -> list[dict]:
        return self._request("GET", "/v1/approvals", params={"status": status} if status else None)

    def decide(self, approval_id: int, decision: str, decided_by: str, note: str | None) -> dict:
        return self._request(
            "POST", f"/v1/approvals/{approval_id}/decision",
            json={"decision": decision, "decided_by": decided_by, "note": note},
        )

    def knowledge(self, limit: int = 50) -> list[dict]:
        return self._request("GET", "/v1/admin/knowledge", params={"limit": limit})

    def knowledge_search(self, query: str, k: int = 3) -> list[dict]:
        return self._request("POST", "/v1/admin/knowledge/search", json={"query": query, "k": k})

    def ready(self) -> dict:
        return self._request("GET", "/ready")
