from __future__ import annotations

import json
from typing import Any

from backend.app.core.time import utc_now_iso
from backend.app.db.sqlite import connect, initialize_database
from backend.app.services.chunker import Chunk, block_hashes, blocks_snapshot_hash
from backend.app.services.feishu import FeishuBlock, FeishuNode, FeishuSpace


class StateRepository:
    def __init__(self, sqlite_path) -> None:
        self.sqlite_path = sqlite_path
        initialize_database(sqlite_path)

    def mark_job_running(self, job_id: str) -> None:
        now = utc_now_iso()
        with connect(self.sqlite_path) as connection:
            connection.execute(
                """
                UPDATE sync_jobs
                SET status = 'running', started_at = COALESCE(started_at, ?), error_message = NULL
                WHERE job_id = ?
                """,
                (now, job_id),
            )

    def mark_job_succeeded(self, job_id: str) -> None:
        now = utc_now_iso()
        with connect(self.sqlite_path) as connection:
            connection.execute(
                "UPDATE sync_jobs SET status = 'succeeded', finished_at = ? WHERE job_id = ?",
                (now, job_id),
            )

    def mark_job_failed(self, job_id: str, error_message: str) -> None:
        now = utc_now_iso()
        with connect(self.sqlite_path) as connection:
            connection.execute(
                """
                UPDATE sync_jobs
                SET status = 'failed', failed_items = failed_items + 1,
                    error_message = ?, finished_at = ?
                WHERE job_id = ?
                """,
                (error_message, now, job_id),
            )

    def increment_job_processed(self, job_id: str, count: int = 1) -> None:
        with connect(self.sqlite_path) as connection:
            connection.execute(
                "UPDATE sync_jobs SET processed_items = processed_items + ? WHERE job_id = ?",
                (count, job_id),
            )

    def set_job_total(self, job_id: str, total: int) -> None:
        with connect(self.sqlite_path) as connection:
            connection.execute(
                "UPDATE sync_jobs SET total_items = ? WHERE job_id = ?",
                (total, job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT * FROM sync_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_space(self, space: FeishuSpace) -> None:
        now = utc_now_iso()
        with connect(self.sqlite_path) as connection:
            connection.execute(
                """
                INSERT INTO spaces (space_id, name, description, updated_time, synced_at)
                VALUES (?, ?, ?, NULL, ?)
                ON CONFLICT(space_id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    synced_at = excluded.synced_at
                """,
                (space.space_id, space.name, space.description, now),
            )

    def upsert_node(self, node: FeishuNode) -> None:
        now = utc_now_iso()
        with connect(self.sqlite_path) as connection:
            connection.execute(
                """
                INSERT INTO nodes (
                    node_token, space_id, parent_node_token, obj_token, obj_type, title,
                    source_url, updated_time, deleted_at, synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                ON CONFLICT(node_token) DO UPDATE SET
                    space_id = excluded.space_id,
                    parent_node_token = excluded.parent_node_token,
                    obj_token = excluded.obj_token,
                    obj_type = excluded.obj_type,
                    title = excluded.title,
                    source_url = excluded.source_url,
                    updated_time = excluded.updated_time,
                    deleted_at = NULL,
                    synced_at = excluded.synced_at
                """,
                (
                    node.node_token,
                    node.space_id,
                    node.parent_node_token,
                    node.obj_token,
                    node.obj_type,
                    node.title,
                    node.source_url,
                    node.updated_time,
                    now,
                ),
            )

    def upsert_document(self, node: FeishuNode, blocks: list[FeishuBlock]) -> bool:
        now = utc_now_iso()
        doc_token = node.obj_token or node.node_token
        block_hash = blocks_snapshot_hash(blocks)
        with connect(self.sqlite_path) as connection:
            existing = connection.execute(
                "SELECT block_hash FROM documents WHERE doc_token = ?",
                (doc_token,),
            ).fetchone()
            changed = existing is None or existing["block_hash"] != block_hash
            connection.execute(
                """
                INSERT INTO documents (
                    doc_token, space_id, node_token, doc_type, title, source_url,
                    updated_time, block_hash, deleted_at, synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                ON CONFLICT(doc_token) DO UPDATE SET
                    space_id = excluded.space_id,
                    node_token = excluded.node_token,
                    doc_type = excluded.doc_type,
                    title = excluded.title,
                    source_url = excluded.source_url,
                    updated_time = excluded.updated_time,
                    block_hash = excluded.block_hash,
                    deleted_at = NULL,
                    synced_at = excluded.synced_at
                """,
                (
                    doc_token,
                    node.space_id,
                    node.node_token,
                    node.obj_type or "docx",
                    node.title,
                    node.source_url,
                    node.updated_time,
                    block_hash,
                    now,
                ),
            )
        return changed

    def replace_blocks(self, doc_token: str, blocks: list[FeishuBlock]) -> None:
        now = utc_now_iso()
        hashes = block_hashes(blocks)
        with connect(self.sqlite_path) as connection:
            connection.execute("DELETE FROM blocks WHERE doc_token = ?", (doc_token,))
            connection.executemany(
                """
                INSERT INTO blocks (
                    block_id, doc_token, parent_block_id, block_type, heading_level,
                    text, raw_json, content_hash, updated_at
                )
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?)
                """,
                [
                    (
                        block.block_id,
                        doc_token,
                        block.parent_block_id,
                        block.block_type,
                        json.dumps(block.raw, ensure_ascii=False),
                        hashes[block.block_id],
                        now,
                    )
                    for block in blocks
                ],
            )

    def replace_chunks(self, doc_token: str, chunks: list[Chunk]) -> None:
        now = utc_now_iso()
        with connect(self.sqlite_path) as connection:
            connection.execute(
                "UPDATE chunks SET deleted_at = ? WHERE doc_token = ?",
                (now, doc_token),
            )
            connection.executemany(
                """
                INSERT INTO chunks (
                    chunk_id, space_id, node_token, doc_token, doc_type, title,
                    section_path, source_url, block_ids, content, content_hash,
                    updated_time, indexed_at, deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    space_id = excluded.space_id,
                    node_token = excluded.node_token,
                    doc_token = excluded.doc_token,
                    doc_type = excluded.doc_type,
                    title = excluded.title,
                    section_path = excluded.section_path,
                    source_url = excluded.source_url,
                    block_ids = excluded.block_ids,
                    content = excluded.content,
                    content_hash = excluded.content_hash,
                    updated_time = excluded.updated_time,
                    deleted_at = NULL
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.space_id,
                        chunk.node_token,
                        chunk.doc_token,
                        chunk.doc_type,
                        chunk.title,
                        chunk.section_path,
                        chunk.source_url,
                        json.dumps(chunk.block_ids, ensure_ascii=False),
                        chunk.content,
                        chunk.content_hash,
                        chunk.updated_time,
                    )
                    for chunk in chunks
                ],
            )

    def mark_chunks_indexed(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        now = utc_now_iso()
        placeholders = ",".join("?" for _ in chunk_ids)
        with connect(self.sqlite_path) as connection:
            connection.execute(
                f"UPDATE chunks SET indexed_at = ? WHERE chunk_id IN ({placeholders})",
                [now, *chunk_ids],
            )

    def list_active_chunks(self, limit: int = 1000) -> list[dict[str, Any]]:
        with connect(self.sqlite_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM chunks
                WHERE deleted_at IS NULL
                ORDER BY updated_time DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT * FROM chunks WHERE chunk_id = ? AND deleted_at IS NULL",
                (chunk_id,),
            ).fetchone()
        return dict(row) if row else None
