from fastapi import APIRouter, HTTPException

from backend.app.core.config import get_settings
from backend.app.schemas.rag import ChatRequest, ChatResponse, SearchRequest, SearchResponse
from backend.app.services.rag import RAGService

router = APIRouter(tags=["rag"])


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    try:
        return await RAGService(get_settings()).search(
            query=request.query,
            top_k=request.top_k,
            top_n=request.top_n,
            account_id=request.account_id,
            space_id=request.space_id,
            doc_token=request.doc_token,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await RAGService(get_settings()).chat(
            query=request.query,
            mode=request.mode,
            top_k=request.top_k,
            top_n=request.top_n,
            account_id=request.account_id,
            space_id=request.space_id,
            doc_token=request.doc_token,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
