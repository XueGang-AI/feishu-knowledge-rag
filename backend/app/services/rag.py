from __future__ import annotations

import re

from backend.app.core.config import Settings
from backend.app.schemas.rag import ChatResponse, SearchHit, SearchResponse, SourceRef
from backend.app.services.embedding import EmbeddingClient
from backend.app.services.llm import LLMClient
from backend.app.services.reranker import RerankerClient, RerankerClientError
from backend.app.services.vector_store import MilvusVectorStore


class RAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        top_n: int | None = None,
        account_id: str | None = None,
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
            legacy_collection_name=self.settings.milvus_legacy_collection,
        )
        raw_hits = vector_store.search(
            query_embedding,
            top_k=top_k,
            filters=self._build_filter(account_id, space_id, doc_token),
            legacy_filters=self._build_legacy_filter(account_id, space_id, doc_token),
            legacy_account_id="default" if account_id == "default" else None,
        )

        reranker = RerankerClient(
            self.settings.reranker_base_url,
            self.settings.reranker_model,
            self.settings.reranker_timeout_seconds,
        )
        raw_by_id = {hit["chunk_id"]: hit for hit in raw_hits}
        try:
            rerank_results = await reranker.rerank(
                query=query,
                documents=[{"id": hit["chunk_id"], "text": hit["content"]} for hit in raw_hits],
                top_n=top_n,
            )
            ranked_hits = [
                (raw_by_id[result.id], result.score)
                for result in rerank_results
                if result.id in raw_by_id
            ]
        except RerankerClientError:
            ranked_hits = [(hit, None) for hit in raw_hits[:top_n]]

        hits: list[SearchHit] = []
        for raw, rerank_score in ranked_hits:
            hits.append(
                SearchHit(
                    chunk_id=raw["chunk_id"],
                    account_id=raw.get("account_id") or "default",
                    space_id=raw["space_id"],
                    node_token=raw["node_token"],
                    doc_token=raw["doc_token"],
                    tenant_name=self._tenant_name(raw.get("account_id") or "default"),
                    title=raw["title"],
                    section_path=raw["section_path"],
                    source_url=raw.get("source_url"),
                    block_ids=raw.get("block_ids") or [],
                    content=raw["content"],
                    score=raw.get("score"),
                    rerank_score=rerank_score,
                    updated_time=raw.get("updated_time"),
                )
            )
        return SearchResponse(query=query, hits=hits)

    async def chat(
        self,
        query: str,
        mode: str = "auto",
        top_k: int | None = None,
        top_n: int | None = None,
        account_id: str | None = None,
        space_id: str | None = None,
        doc_token: str | None = None,
    ) -> ChatResponse:
        resolved_mode = self._resolve_chat_mode(
            query=query,
            requested_mode=mode,
            account_id=account_id,
            space_id=space_id,
            doc_token=doc_token,
        )
        if resolved_mode == "direct":
            return await self._direct_chat(query)

        search_response = await self.search(
            query=query,
            top_k=top_k,
            top_n=top_n or self.settings.llm_context_top_n,
            account_id=account_id,
            space_id=space_id,
            doc_token=doc_token,
        )
        sources = [
            SourceRef(
                source_id=f"S{index}",
                chunk_id=hit.chunk_id,
                account_id=hit.account_id,
                space_id=hit.space_id,
                node_token=hit.node_token,
                doc_token=hit.doc_token,
                tenant_name=hit.tenant_name,
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
            return ChatResponse(
                answer="当前知识库未找到相关内容。",
                sources=[],
                mode="rag",
                retrieval_used=True,
            )

        llm = LLMClient(
            self.settings.llm_base_url,
            self.settings.llm_model,
            self.settings.llm_timeout_seconds,
            self.settings.llm_temperature,
            self.settings.llm_max_tokens,
        )
        answer = await llm.chat(self._build_rag_messages(query, search_response.hits))
        return ChatResponse(answer=answer, sources=sources, mode="rag", retrieval_used=True)

    async def _direct_chat(self, query: str) -> ChatResponse:
        if self._is_model_identity_question(query):
            return ChatResponse(
                answer=self._model_identity_answer(),
                sources=[],
                mode="direct",
                retrieval_used=False,
            )

        llm = LLMClient(
            self.settings.llm_base_url,
            self.settings.llm_model,
            self.settings.llm_timeout_seconds,
            self.settings.llm_temperature,
            self.settings.llm_max_tokens,
        )
        answer = await llm.chat(self._build_direct_messages(query))
        return ChatResponse(answer=answer, sources=[], mode="direct", retrieval_used=False)

    def _resolve_chat_mode(
        self,
        query: str,
        requested_mode: str,
        account_id: str | None,
        space_id: str | None,
        doc_token: str | None,
    ) -> str:
        if requested_mode in {"direct", "rag"}:
            return requested_mode

        explicit_scope = bool(space_id or doc_token or (account_id and account_id != "all"))
        if explicit_scope or self._should_use_rag(query):
            return "rag"
        return "direct"

    @staticmethod
    def _should_use_rag(query: str) -> bool:
        normalized = query.lower()
        rag_keywords = (
            "飞书",
            "知识库",
            "知识空间",
            "文档",
            "资料",
            "周报",
            "日报",
            "月报",
            "年报",
            "报告",
            "公司内部",
            "内部资料",
            "来源",
            "引用",
            "同步",
            "检索",
            "milvus",
            "文搜图",
            "xue-ai",
            "账号",
            "block",
            "chunk",
            "当前项目",
            "这个项目",
            "项目资料",
            "项目记录",
            "项目文档",
            "项目进展",
            "项目状态",
        )
        if any(keyword in normalized for keyword in rag_keywords):
            return True
        return bool(re.search(r"\b\d{1,2}[./-]\d{1,2}\b", normalized))

    @staticmethod
    def _is_model_identity_question(query: str) -> bool:
        normalized = query.lower()
        identity_patterns = (
            "你是什么模型",
            "你是什麼模型",
            "当前模型",
            "當前模型",
            "模型是什么",
            "模型是什麼",
            "你是谁",
            "你是誰",
            "介绍你自己",
            "自我介绍",
            "who are you",
            "what model are you",
            "which model are you",
        )
        return any(pattern in normalized for pattern in identity_patterns)

    def _model_identity_answer(self) -> str:
        model = self.settings.llm_model
        label = "Gemma 4 12B-it QAT Q4_0" if "gemma" in model.lower() else model
        return (
            f"我是本地知识库个人助手，当前生成模型是 {label}（{model}），"
            f"服务地址为 {self.settings.llm_base_url}。普通问题我会直接回答；"
            "涉及飞书知识库、项目资料或文档时才会检索本地知识库并返回来源。"
        )

    def _build_filter(
        self,
        account_id: str | None,
        space_id: str | None,
        doc_token: str | None,
    ) -> str | None:
        clauses = []
        if account_id:
            clauses.append(f'account_id == "{self._escape_filter_value(account_id)}"')
        if space_id:
            clauses.append(f'space_id == "{self._escape_filter_value(space_id)}"')
        if doc_token:
            clauses.append(f'doc_token == "{self._escape_filter_value(doc_token)}"')
        return " and ".join(clauses) if clauses else None

    def _build_legacy_filter(
        self,
        account_id: str | None,
        space_id: str | None,
        doc_token: str | None,
    ) -> str | None:
        if account_id not in {None, "default"}:
            return None
        return self._build_filter(None, space_id, doc_token)

    def _tenant_name(self, account_id: str) -> str | None:
        account = self.settings.get_feishu_account(account_id)
        return account.tenant_name if account else None

    @staticmethod
    def _escape_filter_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _build_direct_messages(self, query: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "你是本地知识库个人助手。"
                    f"当前默认生成模型是 {self.settings.llm_model}，"
                    f"服务地址是 {self.settings.llm_base_url}。"
                    "普通问题可以基于模型能力直接回答。"
                    "不要声称使用了飞书知识库或引用来源；"
                    "不要编造飞书链接、标题、block_id 或内部资料。"
                    "如果无法确定，直接说明不确定。"
                ),
            },
            {"role": "user", "content": query},
        ]

    def _build_rag_messages(self, query: str, hits: list[SearchHit]) -> list[dict[str, str]]:
        context_parts = []
        for index, hit in enumerate(hits, start=1):
            context_parts.append(
                "\n".join(
                    [
                        f"[S{index}]",
                        f"account: {hit.tenant_name or hit.account_id}",
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
