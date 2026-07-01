from pathlib import Path
from typing import Any

import pytest

from backend.app.core.config import Settings
from backend.app.db.sqlite import connect, initialize_database
from backend.app.services import sync_service as sync_service_module
from backend.app.services.feishu import FeishuNode, FeishuSpace
from backend.app.services.sync_service import SyncService


class FakeFeishuClient:
    def __init__(self, **_: Any) -> None:
        pass

    async def list_spaces(self) -> list[FeishuSpace]:
        return [FeishuSpace(account_id="default", space_id="spc_1", name="测试空间")]

    async def list_child_nodes(
        self,
        space_id: str,
        parent_node_token: str | None = None,
    ) -> list[FeishuNode]:
        if parent_node_token == "nod_1":
            raise RuntimeError("子节点接口失败")
        return [
            FeishuNode(
                account_id="default",
                space_id=space_id,
                node_token="nod_1",
                parent_node_token=None,
                obj_token=None,
                obj_type=None,
                title="测试节点",
                source_url="https://feishu.cn/wiki/nod_1",
                updated_time=None,
            )
        ]


@pytest.mark.asyncio
async def test_all_sync_keeps_progress_when_child_collection_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sqlite_path = tmp_path / "state" / "test.sqlite3"
    initialize_database(sqlite_path)
    job_id = "job_all_progress"
    with connect(sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO sync_jobs (
                job_id, scope_type, scope_id, status,
                account_id,
                total_items, processed_items, failed_items,
                error_message, created_at, started_at, finished_at
            )
            VALUES (
                ?, 'all', NULL, 'pending', NULL, 0, 0, 0, NULL,
                '2026-06-29T00:00:00Z', NULL, NULL
            )
            """,
            (job_id,),
        )

    processed_nodes: list[str] = []

    async def fake_sync_node(self: SyncService, client: FakeFeishuClient, node: FeishuNode) -> None:
        processed_nodes.append(node.node_token)

    monkeypatch.setattr(sync_service_module, "FeishuClient", FakeFeishuClient)
    monkeypatch.setattr(SyncService, "_sync_node", fake_sync_node)

    settings = Settings(
        _env_file=None,
        SQLITE_PATH=sqlite_path,
        FEISHU_APP_ID="app",
        FEISHU_APP_SECRET="secret",
        FEISHU_ACCOUNTS_JSON="",
    )
    await SyncService(settings).run_job(job_id)

    with connect(sqlite_path) as connection:
        row = connection.execute("SELECT * FROM sync_jobs WHERE job_id = ?", (job_id,)).fetchone()

    assert processed_nodes == ["nod_1"]
    assert row["status"] == "failed"
    assert row["total_items"] == 1
    assert row["processed_items"] == 1
    assert "子节点接口失败" in row["error_message"]
