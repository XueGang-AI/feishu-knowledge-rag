from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings
from backend.app.db.sqlite import connect, initialize_database
from backend.app.services.repository import StateRepository
from backend.app.services.sync_service import run_sync_job
from backend.app.services.weekly_scheduler import create_weekly_scan_jobs

router = APIRouter(prefix="/sync", tags=["sync"])


class CreateSyncJobRequest(BaseModel):
    scope_type: str = Field(default="all", pattern="^(all|account|space|node|document)$")
    scope_id: str | None = None
    account_id: str | None = None
    auto_start: bool = False


class ReindexRequest(BaseModel):
    scope_type: str = Field(default="all", pattern="^(all|account|space|node|document)$")
    scope_id: str | None = None
    account_id: str | None = None


class SyncJobResponse(BaseModel):
    job_id: str
    account_id: str | None = None
    scope_type: str
    scope_id: str | None
    status: str
    total_items: int
    processed_items: int
    failed_items: int
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class WeeklyScanResponse(BaseModel):
    job_ids: list[str]


def _row_to_job(row: Any) -> SyncJobResponse:
    return SyncJobResponse(
        job_id=row["job_id"],
        account_id=row["account_id"],
        scope_type=row["scope_type"],
        scope_id=row["scope_id"],
        status=row["status"],
        total_items=row["total_items"],
        processed_items=row["processed_items"],
        failed_items=row["failed_items"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _job_time(row: Any) -> str:
    return row["finished_at"] or row["started_at"] or row["created_at"] or ""


def _unresolved_account_failure(account_id: str, rows: list[Any]) -> tuple[int, str | None]:
    account_rows = [row for row in rows if row["account_id"] == account_id]
    last_success = max(
        (
            _job_time(row)
            for row in account_rows
            if row["status"] == "succeeded" and int(row["failed_items"] or 0) == 0
        ),
        default="",
    )
    unresolved = [
        row
        for row in account_rows
        if _job_time(row) > last_success
        and (row["failed_items"] > 0 or row["status"] == "failed")
        and row["error_message"]
    ]
    if not unresolved:
        return 0, None
    latest = max(unresolved, key=_job_time)
    failed_items = sum(int(row["failed_items"] or 0) for row in unresolved)
    return failed_items, latest["error_message"]


@router.post("/jobs", response_model=SyncJobResponse)
def create_sync_job(
    request: CreateSyncJobRequest,
    background_tasks: BackgroundTasks,
) -> SyncJobResponse:
    settings = get_settings()
    repository = StateRepository(settings.sqlite_path)
    row = repository.create_job(
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        account_id=request.account_id,
    )
    response = _row_to_job(row)
    if request.auto_start:
        background_tasks.add_task(run_sync_job, row["job_id"])
    return response


@router.get("/jobs", response_model=list[SyncJobResponse])
def list_sync_jobs() -> list[SyncJobResponse]:
    settings = get_settings()
    initialize_database(settings.sqlite_path)
    with connect(settings.sqlite_path) as connection:
        rows = connection.execute(
            "SELECT * FROM sync_jobs ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return [_row_to_job(row) for row in rows]


@router.get("/jobs/{job_id}", response_model=SyncJobResponse)
def get_sync_job(job_id: str) -> SyncJobResponse:
    settings = get_settings()
    initialize_database(settings.sqlite_path)
    with connect(settings.sqlite_path) as connection:
        row = connection.execute(
            "SELECT * FROM sync_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="sync job not found")
    return _row_to_job(row)


@router.post("/jobs/{job_id}/run", response_model=SyncJobResponse)
def run_existing_sync_job(job_id: str, background_tasks: BackgroundTasks) -> SyncJobResponse:
    settings = get_settings()
    initialize_database(settings.sqlite_path)
    with connect(settings.sqlite_path) as connection:
        row = connection.execute(
            "SELECT * FROM sync_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="sync job not found")
    if row["status"] == "running":
        raise HTTPException(status_code=409, detail="sync job is already running")
    background_tasks.add_task(run_sync_job, job_id)
    return _row_to_job(row)


@router.post("/jobs/{job_id}/cancel", response_model=SyncJobResponse)
def cancel_sync_job(job_id: str) -> SyncJobResponse:
    settings = get_settings()
    initialize_database(settings.sqlite_path)
    now = datetime.now(UTC).isoformat()
    with connect(settings.sqlite_path) as connection:
        row = connection.execute(
            "SELECT * FROM sync_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="sync job not found")
        if row["status"] not in {"pending", "running"}:
            raise HTTPException(
                status_code=409, detail="only pending or running jobs can be cancelled"
            )
        connection.execute(
            "UPDATE sync_jobs SET status = 'cancelled', finished_at = ? WHERE job_id = ?",
            (now, job_id),
        )
        updated = connection.execute(
            "SELECT * FROM sync_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return _row_to_job(updated)


@router.post("/reindex", response_model=SyncJobResponse)
def reindex(request: ReindexRequest, background_tasks: BackgroundTasks) -> SyncJobResponse:
    return create_sync_job(
        CreateSyncJobRequest(
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            account_id=request.account_id,
            auto_start=True,
        ),
        background_tasks,
    )


@router.post("/weekly-scan/run", response_model=WeeklyScanResponse)
def run_weekly_scan(background_tasks: BackgroundTasks) -> WeeklyScanResponse:
    job_ids = create_weekly_scan_jobs(get_settings())
    for job_id in job_ids:
        background_tasks.add_task(run_sync_job, job_id)
    return WeeklyScanResponse(job_ids=job_ids)


@router.get("/status")
def sync_status() -> dict[str, Any]:
    settings = get_settings()
    initialize_database(settings.sqlite_path)
    with connect(settings.sqlite_path) as connection:
        counts = {
            "spaces": connection.execute("SELECT COUNT(*) FROM spaces").fetchone()[0],
            "nodes": connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
            "documents": connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "blocks": connection.execute("SELECT COUNT(*) FROM blocks").fetchone()[0],
            "chunks": connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE deleted_at IS NULL"
            ).fetchone()[0],
            "sync_jobs": connection.execute("SELECT COUNT(*) FROM sync_jobs").fetchone()[0],
        }
        latest_job = connection.execute(
            "SELECT * FROM sync_jobs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        account_rows = connection.execute(
            """
            SELECT
                account_id,
                (SELECT COUNT(*) FROM spaces s WHERE s.account_id = a.account_id) AS spaces,
                (SELECT COUNT(*) FROM nodes n WHERE n.account_id = a.account_id) AS nodes,
                (SELECT COUNT(*) FROM documents d WHERE d.account_id = a.account_id) AS documents,
                (SELECT COUNT(*) FROM blocks b WHERE b.account_id = a.account_id) AS blocks,
                (SELECT COUNT(*) FROM chunks c
                 WHERE c.account_id = a.account_id AND c.deleted_at IS NULL) AS chunks,
                (SELECT MAX(finished_at) FROM sync_jobs j
                 WHERE j.account_id = a.account_id) AS last_scan_at,
                0 AS failed_items,
                NULL AS latest_error
            FROM (
                SELECT account_id FROM spaces
                UNION SELECT account_id FROM nodes
                UNION SELECT account_id FROM documents
                UNION SELECT account_id FROM blocks
                UNION SELECT account_id FROM chunks
                UNION SELECT account_id FROM sync_jobs WHERE account_id IS NOT NULL
            ) a
            ORDER BY account_id
            """
        ).fetchall()
        job_rows = connection.execute(
            """
            SELECT account_id, scope_type, scope_id, status, failed_items, error_message,
                   created_at, started_at, finished_at
            FROM sync_jobs
            WHERE account_id IS NOT NULL
            """
        ).fetchall()

    configured_accounts = {item["account_id"]: item for item in settings.public_feishu_accounts}
    accounts = []
    seen: set[str] = set()
    for row in account_rows:
        account_id = row["account_id"]
        unresolved_failed_items, latest_error = _unresolved_account_failure(account_id, job_rows)
        seen.add(account_id)
        configured = configured_accounts.get(account_id, {})
        accounts.append(
            {
                "account_id": account_id,
                "tenant_name": configured.get("tenant_name") or account_id,
                "enabled": configured.get("enabled", True),
                "configured": configured.get("configured", False),
                "spaces": row["spaces"],
                "nodes": row["nodes"],
                "documents": row["documents"],
                "blocks": row["blocks"],
                "chunks": row["chunks"],
                "last_scan_at": row["last_scan_at"],
                "failed_items": unresolved_failed_items,
                "latest_error": latest_error,
            }
        )
    for account_id, configured in configured_accounts.items():
        if account_id in seen:
            continue
        accounts.append(
            {
                "account_id": account_id,
                "tenant_name": configured["tenant_name"],
                "enabled": configured["enabled"],
                "configured": configured["configured"],
                "spaces": 0,
                "nodes": 0,
                "documents": 0,
                "blocks": 0,
                "chunks": 0,
                "last_scan_at": None,
                "failed_items": 0,
                "latest_error": None,
            }
        )
    return {
        "counts": counts,
        "accounts": accounts,
        "latest_job": _row_to_job(latest_job).model_dump() if latest_job else None,
    }
