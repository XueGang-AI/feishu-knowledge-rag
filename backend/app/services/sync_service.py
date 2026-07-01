from __future__ import annotations

from collections.abc import AsyncIterator

from backend.app.core.config import FeishuAccountConfig, Settings, get_settings
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
            accounts = self._job_accounts(job)
            if not accounts:
                raise SyncServiceError("No enabled Feishu account is configured")

            errors: list[str] = []
            for account in accounts:
                if not account.configured:
                    errors.append(f"{account.account_id} is not configured")
                    self.repository.increment_job_failed(job_id, errors[-1])
                    continue
                try:
                    await self._run_account_scope(job_id, job, account)
                except Exception as exc:
                    if len(accounts) == 1:
                        raise
                    error = f"{account.account_id} sync failed: {exc}"
                    errors.append(error)
                    self.repository.increment_job_failed(job_id, error)

            if errors:
                self.repository.mark_job_failed(job_id, "; ".join(errors), increment_failed=False)
            else:
                self.repository.mark_job_succeeded(job_id)
        except Exception as exc:
            self.repository.mark_job_failed(job_id, str(exc))

    async def _run_account_scope(
        self,
        job_id: str,
        job: dict,
        account: FeishuAccountConfig,
    ) -> None:
        client = FeishuClient(
            base_url=self.settings.feishu_base_url,
            account_id=account.account_id,
            app_id=account.app_id,
            app_secret=account.app_secret,
            timeout_seconds=self.settings.feishu_request_timeout_seconds,
            page_size=self.settings.feishu_page_size,
        )
        continue_on_node_error = job["scope_type"] in {"all", "account", "space", "node"}
        async for node in self._iter_scope_nodes(client, job["scope_type"], job["scope_id"]):
            self.repository.increment_job_total(job_id)
            try:
                await self._sync_node(client, node)
            except Exception as exc:
                if not continue_on_node_error:
                    raise
                self.repository.increment_job_failed(
                    job_id,
                    self._format_node_error(node, exc),
                )
                continue
            self.repository.increment_job_processed(job_id)

    def _job_accounts(self, job: dict) -> list[FeishuAccountConfig]:
        account_id = job.get("account_id")
        if not account_id and job.get("scope_type") == "account":
            account_id = job.get("scope_id")
        if account_id:
            account = self.settings.get_feishu_account(account_id)
            return [account] if account and account.enabled else []
        return self.settings.enabled_feishu_accounts

    async def _iter_scope_nodes(
        self,
        client: FeishuClient,
        scope_type: str,
        scope_id: str | None,
    ) -> AsyncIterator[FeishuNode]:
        if scope_type in {"all", "account"}:
            spaces = await client.list_spaces()
            for space in spaces:
                self.repository.upsert_space(space)
            for space in spaces:
                async for node in self._iter_space_nodes(client, space.space_id):
                    yield node
            return

        if scope_type == "space":
            if not scope_id:
                raise SyncServiceError("space sync requires scope_id")
            async for node in self._iter_space_nodes(client, scope_id):
                yield node
            return

        if scope_type == "node":
            if not scope_id:
                raise SyncServiceError("node sync requires scope_id")
            # A node sync requires the scope id format "space_id:node_token".
            if ":" not in scope_id:
                raise SyncServiceError("node sync scope_id must be space_id:node_token")
            space_id, node_token = scope_id.split(":", 1)
            root = await client.get_node(space_id, node_token)
            self.repository.upsert_node(root)
            yield root
            async for node in self._iter_space_nodes(client, space_id, node_token):
                yield node
            return

        if scope_type == "document":
            if not scope_id or ":" not in scope_id:
                raise SyncServiceError("document sync scope_id must be space_id:node_token")
            space_id, node_token = scope_id.split(":", 1)
            root = await client.get_node(space_id, node_token)
            self.repository.upsert_node(root)
            yield root
            return

        raise SyncServiceError(f"unsupported sync scope_type: {scope_type}")

    async def _iter_space_nodes(
        self,
        client: FeishuClient,
        space_id: str,
        parent_node_token: str | None = None,
    ) -> AsyncIterator[FeishuNode]:
        nodes = await client.list_child_nodes(space_id, parent_node_token)
        for node in nodes:
            self.repository.upsert_node(node)
            yield node
            async for child in self._iter_space_nodes(client, space_id, node.node_token):
                yield child

    async def _sync_node(self, client: FeishuClient, node: FeishuNode) -> None:
        self.repository.upsert_node(node)
        if not node.obj_token:
            return
        if node.obj_type and node.obj_type not in {"docx", "doc", "wiki", "document"}:
            return

        blocks = await client.list_docx_blocks(node.obj_token)
        changed = self.repository.upsert_document(node, blocks)
        doc_token = node.obj_token or node.node_token
        index_stats = self.repository.chunk_index_stats(node.account_id, doc_token)
        if (
            not changed
            and index_stats["active_chunks"] > 0
            and index_stats["unindexed_chunks"] == 0
        ):
            return

        self.repository.replace_blocks(node.account_id, doc_token, blocks)
        chunks = chunk_document(
            node,
            blocks,
            target_chars=self.settings.chunk_target_chars,
            max_chars=self.settings.chunk_max_chars,
            overlap_chars=self.settings.chunk_overlap_chars,
        )
        self.repository.replace_chunks(node.account_id, doc_token, chunks)

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
            legacy_collection_name=self.settings.milvus_legacy_collection,
        )
        vector_store.upsert_chunks(chunks, embeddings)
        self.repository.mark_chunks_indexed(node.account_id, [chunk.chunk_id for chunk in chunks])

    @staticmethod
    def _format_node_error(node: FeishuNode, exc: Exception) -> str:
        return (
            f"{node.title} ({node.account_id}:{node.space_id}:{node.node_token}) "
            f"sync failed: {exc}"
        )


async def run_sync_job(job_id: str) -> None:
    await SyncService(get_settings()).run_job(job_id)
