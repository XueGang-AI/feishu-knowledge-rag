import json

from fastapi import APIRouter, HTTPException

from backend.app.core.config import get_settings
from backend.app.services.repository import StateRepository

router = APIRouter(tags=["sources"])


@router.get("/sources/{chunk_id}")
def get_source(chunk_id: str) -> dict:
    repository = StateRepository(get_settings().sqlite_path)
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="source chunk not found")
    block_ids = chunk.get("block_ids")
    if isinstance(block_ids, str):
        try:
            chunk["block_ids"] = json.loads(block_ids)
        except json.JSONDecodeError:
            chunk["block_ids"] = [block_ids]
    return chunk
