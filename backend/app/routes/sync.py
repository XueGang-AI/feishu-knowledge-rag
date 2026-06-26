from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings
from backend.app.db.sqlite import connect, initialize_database

router = APIRouter(prefix="/sync", tags=["sync"])


class CreateSyncJobRequest(BaseModel):
    scope_type: str = Field(default="all", pattern="^(all|space|node|document)$")
    scope_id: str | None = None


class SyncJobResponse(BaseModel):
    job_id: str
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


def _row_to_job(row: Any) -> SyncJobResponse:
    return SyncJobResponse(
        job_id=row["job_id"],
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


@router.post("/jobs", response_model=SyncJobResponse)
def create_sync_job(request: CreateSyncJobRequest) -> SyncJobResponse:
    settings = get_settings()
    initialize_database(settings.sqlite_path)

    job_id = str(uuid4())
    now = datetime.now(UTC).isoformat()

    with connect(settings.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO sync_jobs (
                job_id, scope_type, scope_id, status,
                total_items, processed_items, failed_items,
                error_message, created_at, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, 0, 0, 0, NULL, ?, NULL, NULL)
            """,
            (job_id, request.scope_type, request.scope_id, "pending", now),
        )
        row = connection.execute(
            "SELECT * FROM sync_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()

    return _row_to_job(row)


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
    return {
        "counts": counts,
        "latest_job": _row_to_job(latest_job).model_dump() if latest_job else None,
    }
