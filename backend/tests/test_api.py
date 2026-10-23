import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_cache, get_rag
from app.core.config import get_settings
from app.db.session import get_session
from app.main import create_app
from app.services.cache import Cache
from tests.conftest import FakeRag

H = {"X-API-Key": "test-key"}


@pytest.fixture()
def client(session, settings):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_rag] = lambda: FakeRag()
    cache = Cache(None)  # one instance, so rate-limit counters persist across requests
    app.dependency_overrides[get_cache] = lambda: cache
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_auth_required(client):
    assert (
        client.post("/v1/chat", json={"customer_id": "CUST-001", "message": "hi"}).status_code
        == 401
    )


def test_validation_rejects_bad_customer_id(client):
    r = client.post("/v1/chat", json={"customer_id": "bob", "message": "hi"}, headers=H)
    assert r.status_code == 422


def test_unknown_customer_404(client):
    r = client.post("/v1/chat", json={"customer_id": "CUST-999", "message": "hi"}, headers=H)
    assert r.status_code == 404


def test_full_approval_lifecycle(client):
    r = client.post(
        "/v1/chat",
        headers=H,
        json={"customer_id": "CUST-001", "message": "Please start the return for ORD-1001"},
    )
    assert r.status_code == 200 and r.json()["approval"]["status"] == "pending"
    approval_id = r.json()["approval"]["id"]

    assert len(client.get("/v1/approvals?status=pending", headers=H).json()) == 1
    d = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers=H,
        json={"decision": "approved", "decided_by": "manager.sara"},
    )
    assert d.status_code == 200 and d.json()["status"] == "approved"
    again = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers=H,
        json={"decision": "rejected", "decided_by": "manager.sara"},
    )
    assert again.status_code == 409


def test_rate_limit(client, settings):
    settings.rate_limit_per_minute = 2
    codes = [client.get("/v1/approvals", headers=H).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and codes[-1] == 429
