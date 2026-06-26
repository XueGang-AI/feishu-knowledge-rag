from __future__ import annotations

from backend.app.core.config import Settings, get_settings
from backend.app.services.chunker import chunk_document
from backend.app.services.embedding import EmbeddingClient
from backend.app.services.feishu import FeishuClient, FeishuNode
from backend.app.services.repository import StateRepository
from backend.app.services.vector_store import MilvusVectorStore


class SyncServiceError(RuntimeError):
    pass


class SyncService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = StateRepository(settings.sqlite_path)

    async def run_job(self, job_id: str) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            raise SyncServiceError(f"sync job not found: {job_id}")

        self.repository.mark_job_running(job_id)
        try:
            if not self.settings.feishu_credentials_configured:
                raise SyncServiceError("Feishu APP_ID/APP_SECRET is not configured")

            client = FeishuClient(
                base_url=self.settings.feishu_base_url,
                app_id=self.settings.feishu_app_id or "",
                app_secret=self.settings.feishu_app_secret or "",
                timeout_seconds=self.settings.feishu_request_timeout_seconds,
                page_size=self.settings.feishu_page_size,
            )
            nodes = await self._collect_nodes(client, job["scope_type"], job["scope_id"])
            self.repository.set_job_total(job_id, len(nodes))

            for node in nodes:
                await self._sync_node(client, node)
                self.repository.increment_job_processed(job_id)

            self.repository.mark_job_succeeded(job_id)
        except Exception as exc:
            self.repository.mark_job_failed(job_id, str(exc))

    async def _collect_nodes(
        self,
        client: FeishuClient,
        scope_type: str,
        scope_id: str | None,
    ) -> list[FeishuNode]:
        if scope_type == "all":
            spaces = await client.list_spaces()
            for space in spaces:
                self.repository.upsert_space(space)
            all_nodes: list[FeishuNode] = []
            for space in spaces:
                all_nodes.extend(await self._collect_space_nodes(client, space.space_id))
            return all_nodes

        if scope_type == "space":
            if not scope_id:
                raise SyncServiceError("space sync requires scope_id")
            return await self._collect_space_nodes(client, scope_id)

        if scope_type == "node":
            if not scope_id:
                raise SyncServiceError("node sync requires scope_id")
            # A node sync requires the scope id format "space_id:node_token".
            if ":" not in scope_id:
                raise SyncServiceError("node sync scope_id must be space_id:node_token")
            space_id, node_token = scope_id.split(":", 1)
            root = await client.get_node(space_id, node_token)
            descendants = await self._collect_space_nodes(client, space_id, node_token)
            return [root, *descendants]

        if scope_type == "document":
            if not scope_id or ":" not in scope_id:
                raise SyncServiceError("document sync scope_id must be space_id:node_token")
            space_id, node_token = scope_id.split(":", 1)
            return [await client.get_node(space_id, node_token)]

        raise SyncServiceError(f"unsupported sync scope_type: {scope_type}")

    async def _collect_space_nodes(
        self,
        client: FeishuClient,
        space_id: str,
        parent_node_token: str | None = None,
    ) -> list[FeishuNode]:
        nodes = await client.list_child_nodes(space_id, parent_node_token)
        collected: list[FeishuNode] = []
        for node in nodes:
            self.repository.upsert_node(node)
            collected.append(node)
            collected.extend(await self._collect_space_nodes(client, space_id, node.node_token))
        return collected

    async def _sync_node(self, client: FeishuClient, node: FeishuNode) -> None:
        self.repository.upsert_node(node)
        if not node.obj_token:
            return
        if node.obj_type and node.obj_type not in {"docx", "doc", "wiki", "document"}:
            return

        blocks = await client.list_docx_blocks(node.obj_token)
        changed = self.repository.upsert_document(node, blocks)
        if not changed:
            return

        self.repository.replace_blocks(node.obj_token, blocks)
        chunks = chunk_document(
            node,
            blocks,
            target_chars=self.settings.chunk_target_chars,
            max_chars=self.settings.chunk_max_chars,
            overlap_chars=self.settings.chunk_overlap_chars,
        )
        self.repository.replace_chunks(node.obj_token, chunks)

        if not chunks:
            return

        embedding_client = EmbeddingClient(
            self.settings.embedding_base_url,
            self.settings.embedding_model,
            self.settings.embedding_timeout_seconds,
        )
        embeddings = await embedding_client.embed([chunk.content for chunk in chunks])
        vector_store = MilvusVectorStore(
            uri=self.settings.milvus_uri,
            collection_name=self.settings.milvus_collection,
            dim=self.settings.embedding_dim,
        )
        vector_store.upsert_chunks(chunks, embeddings)
        self.repository.mark_chunks_indexed([chunk.chunk_id for chunk in chunks])


async def run_sync_job(job_id: str) -> None:
    await SyncService(get_settings()).run_job(job_id)
