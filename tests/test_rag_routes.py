from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import app


def test_search_returns_502_when_model_services_are_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "state" / "test.sqlite3"))
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.post("/api/search", json={"query": "测试问题"})

    assert response.status_code == 502


def test_reindex_creates_autostart_job_without_credentials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "state" / "test.sqlite3"))
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.post("/api/reindex", json={"scope_type": "all"})

    assert response.status_code == 200
    assert response.json()["scope_type"] == "all"
