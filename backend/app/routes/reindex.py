from fastapi import APIRouter, BackgroundTasks

from backend.app.routes.sync import (
    CreateSyncJobRequest,
    ReindexRequest,
    SyncJobResponse,
    create_sync_job,
)

router = APIRouter(tags=["sync"])


@router.post("/reindex", response_model=SyncJobResponse)
def reindex(request: ReindexRequest, background_tasks: BackgroundTasks) -> SyncJobResponse:
    return create_sync_job(
        CreateSyncJobRequest(
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            auto_start=True,
        ),
        background_tasks,
    )
