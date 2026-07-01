from pathlib import Path

from backend.app.core.config import Settings
from backend.app.db.sqlite import connect
from backend.app.services.weekly_scheduler import WeeklyScanScheduler, create_weekly_scan_jobs


def test_weekly_scheduler_does_not_start_when_disabled(tmp_path: Path) -> None:
    scheduler = WeeklyScanScheduler(
        Settings(SQLITE_PATH=tmp_path / "state" / "test.sqlite3", WEEKLY_SCAN_ENABLED=False)
    )

    scheduler.start()

    assert scheduler._task is None


def test_create_weekly_scan_jobs_skips_running_same_account(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "state" / "test.sqlite3"
    settings = Settings(
        SQLITE_PATH=sqlite_path,
        FEISHU_ACCOUNTS_JSON=(
            '[{"account_id":"default","tenant_name":"当前企业","app_id":"cli_1",'
            '"app_secret":"secret_1","enabled":true}]'
        ),
    )
    first_job_ids = create_weekly_scan_jobs(settings)

    with connect(sqlite_path) as connection:
        connection.execute(
            "UPDATE sync_jobs SET status = 'running' WHERE job_id = ?",
            (first_job_ids[0],),
        )

    assert len(first_job_ids) == 1
    assert create_weekly_scan_jobs(settings) == []
