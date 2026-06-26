from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import app


def test_create_and_get_sync_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "state" / "test.sqlite3"))
    get_settings.cache_clear()
    client = TestClient(app)

    create_response = client.post(
        "/api/sync/jobs",
        json={"scope_type": "space", "scope_id": "spc_test"},
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["scope_type"] == "space"
    assert created["scope_id"] == "spc_test"
    assert created["status"] == "pending"

    get_response = client.get(f"/api/sync/jobs/{created['job_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["job_id"] == created["job_id"]

    list_response = client.get("/api/sync/jobs")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    status_response = client.get("/api/sync/status")
    assert status_response.status_code == 200
    assert status_response.json()["counts"]["sync_jobs"] == 1


def test_get_missing_sync_job_returns_404(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "state" / "test.sqlite3"))
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/api/sync/jobs/missing")

    assert response.status_code == 404
