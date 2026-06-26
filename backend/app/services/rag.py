from __future__ import annotations

from backend.app.core.config import Settings
from backend.app.schemas.rag import ChatResponse, SearchHit, SearchResponse, SourceRef
from backend.app.services.embedding import EmbeddingClient
from backend.app.services.llm import LLMClient
from backend.app.services.reranker import RerankerClient
from backend.app.services.vector_store import MilvusVectorStore


class RAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        top_n: int | None = None,
        space_id: str | None = None,
        doc_token: str | None = None,
    ) -> SearchResponse:
        top_k = top_k or self.settings.retrieval_top_k
        top_n = top_n or self.settings.rerank_top_n
        embedding_client = EmbeddingClient(
            self.settings.embedding_base_url,
            self.settings.embedding_model,
            self.settings.embedding_timeout_seconds,
        )
        query_embedding = (await embedding_client.embed([query]))[0]

        vector_store = MilvusVectorStore(
            uri=self.settings.milvus_uri,
            collection_name=self.settings.milvus_collection,
            dim=self.settings.embedding_dim,
        )
        raw_hits = vector_store.search(
            query_embedding, top_k=top_k, filters=self._build_filter(space_id, doc_token)
        )

        reranker = RerankerClient(
            self.settings.reranker_base_url,
            self.settings.reranker_model,
            self.settings.reranker_timeout_seconds,
        )
        rerank_results = await reranker.rerank(
            query=query,
            documents=[{"id": hit["chunk_id"], "text": hit["content"]} for hit in raw_hits],
            top_n=top_n,
        )
        raw_by_id = {hit["chunk_id"]: hit for hit in raw_hits}
        hits: list[SearchHit] = []
        for result in rerank_results:
            raw = raw_by_id.get(result.id)
            if not raw:
                continue
            hits.append(
                SearchHit(
                    chunk_id=raw["chunk_id"],
                    title=raw["title"],
                    section_path=raw["section_path"],
                    source_url=raw.get("source_url"),
                    block_ids=raw.get("block_ids") or [],
                    content=raw["content"],
                    score=raw.get("score"),
                    rerank_score=result.score,
                    updated_time=raw.get("updated_time"),
                )
            )
        return SearchResponse(query=query, hits=hits)

    async def chat(
        self,
        query: str,
        top_k: int | None = None,
        top_n: int | None = None,
        space_id: str | None = None,
        doc_token: str | None = None,
    ) -> ChatResponse:
        search_response = await self.search(
            query=query,
            top_k=top_k,
            top_n=top_n or self.settings.llm_context_top_n,
            space_id=space_id,
            doc_token=doc_token,
        )
        sources = [
            SourceRef(
                source_id=f"S{index}",
                chunk_id=hit.chunk_id,
                title=hit.title,
                section_path=hit.section_path,
                source_url=hit.source_url,
                block_ids=hit.block_ids,
                score=hit.score,
                rerank_score=hit.rerank_score,
                updated_time=hit.updated_time,
                content_preview=hit.content[:300],
            )
            for index, hit in enumerate(search_response.hits, start=1)
        ]

        if not sources:
            return ChatResponse(answer="当前知识库未找到相关内容。", sources=[])

        llm = LLMClient(
            self.settings.llm_base_url,
            self.settings.llm_model,
            self.settings.llm_timeout_seconds,
            self.settings.llm_temperature,
            self.settings.llm_max_tokens,
        )
        answer = await llm.chat(self._build_messages(query, search_response.hits))
        return ChatResponse(answer=answer, sources=sources)

    def _build_filter(self, space_id: str | None, doc_token: str | None) -> str | None:
        clauses = []
        if space_id:
            clauses.append(f'space_id == "{space_id}"')
        if doc_token:
            clauses.append(f'doc_token == "{doc_token}"')
        return " and ".join(clauses) if clauses else None

    def _build_messages(self, query: str, hits: list[SearchHit]) -> list[dict[str, str]]:
        context_parts = []
        for index, hit in enumerate(hits, start=1):
            context_parts.append(
                "\n".join(
                    [
                        f"[S{index}]",
                        f"title: {hit.title}",
                        f"section: {hit.section_path}",
                        f"url: {hit.source_url or ''}",
                        f"block_ids: {', '.join(hit.block_ids)}",
                        "content:",
                        hit.content,
                    ]
                )
            )
        context = "\n\n".join(context_parts)
        return [
            {
                "role": "system",
                "content": (
                    "你是本地飞书知识库问答助手。只能基于提供的来源回答。"
                    "每个关键结论后必须用 [S1] 这样的来源编号标注。"
                    "如果来源不足，说明当前知识库未找到相关内容。"
                    "不要编造飞书链接、标题或 block_id。"
                ),
            },
            {
                "role": "user",
                "content": f"问题：{query}\n\n来源：\n{context}",
            },
        ]
