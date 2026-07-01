from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.db.sqlite import connect
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


def test_sync_status_clears_account_error_after_later_success(
    monkeypatch, tmp_path: Path
) -> None:
    sqlite_path = tmp_path / "state" / "test.sqlite3"
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv(
        "FEISHU_ACCOUNTS_JSON",
        '[{"account_id":"tenant_1","tenant_name":"Tenant 1","enabled":true,'
        '"app_id":"cli_x","app_secret":"secret_x"}]',
    )
    get_settings.cache_clear()
    client = TestClient(app)

    failed = client.post(
        "/api/sync/jobs",
        json={"scope_type": "account", "scope_id": "tenant_1", "account_id": "tenant_1"},
    ).json()
    succeeded = client.post(
        "/api/sync/jobs",
        json={"scope_type": "account", "scope_id": "tenant_1", "account_id": "tenant_1"},
    ).json()
    with connect(sqlite_path) as connection:
        connection.execute(
            """
            UPDATE sync_jobs
            SET status = 'failed', failed_items = 1, error_message = 'old error',
                started_at = '2026-01-01T00:00:00+00:00',
                finished_at = '2026-01-01T00:01:00+00:00'
            WHERE job_id = ?
            """,
            (failed["job_id"],),
        )
        connection.execute(
            """
            UPDATE sync_jobs
            SET status = 'succeeded',
                started_at = '2026-01-01T00:02:00+00:00',
                finished_at = '2026-01-01T00:03:00+00:00'
            WHERE job_id = ?
            """,
            (succeeded["job_id"],),
        )

    status = client.get("/api/sync/status").json()
    tenant = next(account for account in status["accounts"] if account["account_id"] == "tenant_1")

    assert tenant["failed_items"] == 0
    assert tenant["latest_error"] is None


def test_sync_status_keeps_partial_failure_after_latest_clean_success(
    monkeypatch, tmp_path: Path
) -> None:
    sqlite_path = tmp_path / "state" / "test.sqlite3"
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv(
        "FEISHU_ACCOUNTS_JSON",
        '[{"account_id":"tenant_1","tenant_name":"Tenant 1","enabled":true,'
        '"app_id":"cli_x","app_secret":"secret_x"}]',
    )
    get_settings.cache_clear()
    client = TestClient(app)

    clean = client.post(
        "/api/sync/jobs",
        json={"scope_type": "account", "scope_id": "tenant_1", "account_id": "tenant_1"},
    ).json()
    partial = client.post(
        "/api/sync/jobs",
        json={"scope_type": "account", "scope_id": "tenant_1", "account_id": "tenant_1"},
    ).json()
    with connect(sqlite_path) as connection:
        connection.execute(
            """
            UPDATE sync_jobs
            SET status = 'succeeded', failed_items = 0,
                started_at = '2026-01-01T00:00:00+00:00',
                finished_at = '2026-01-01T00:01:00+00:00'
            WHERE job_id = ?
            """,
            (clean["job_id"],),
        )
        connection.execute(
            """
            UPDATE sync_jobs
            SET status = 'succeeded', failed_items = 2,
                error_message = 'partial node error',
                started_at = '2026-01-01T00:02:00+00:00',
                finished_at = '2026-01-01T00:03:00+00:00'
            WHERE job_id = ?
            """,
            (partial["job_id"],),
        )

    status = client.get("/api/sync/status").json()
    tenant = next(account for account in status["accounts"] if account["account_id"] == "tenant_1")

    assert tenant["failed_items"] == 2
    assert tenant["latest_error"] == "partial node error"
