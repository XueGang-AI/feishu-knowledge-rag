from __future__ import annotations

import json
from typing import Any

from backend.app.services.chunker import Chunk, chunk_to_milvus_metadata


class VectorStoreError(RuntimeError):
    pass


class MilvusVectorStore:
    def __init__(self, uri: str, collection_name: str, dim: int = 1024) -> None:
        self.uri = uri
        self.collection_name = collection_name
        self.dim = dim

    def _client(self):
        from pymilvus import MilvusClient

        return MilvusClient(uri=self.uri)

    def ensure_collection(self) -> None:
        from pymilvus import DataType

        client = self._client()
        if client.has_collection(self.collection_name):
            return

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field("space_id", DataType.VARCHAR, max_length=128)
        schema.add_field("node_token", DataType.VARCHAR, max_length=256)
        schema.add_field("doc_token", DataType.VARCHAR, max_length=256)
        schema.add_field("doc_type", DataType.VARCHAR, max_length=64)
        schema.add_field("title", DataType.VARCHAR, max_length=1024)
        schema.add_field("section_path", DataType.VARCHAR, max_length=2048)
        schema.add_field("source_url", DataType.VARCHAR, max_length=2048)
        schema.add_field("block_ids", DataType.VARCHAR, max_length=4096)
        schema.add_field("content", DataType.VARCHAR, max_length=8192)
        schema.add_field("content_hash", DataType.VARCHAR, max_length=128)
        schema.add_field("updated_time", DataType.INT64)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.dim)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("chunks and embeddings length mismatch")
        if not chunks:
            return
        self.ensure_collection()
        rows = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            metadata = chunk_to_milvus_metadata(chunk)
            metadata["embedding"] = embedding
            rows.append(metadata)
        self._client().upsert(collection_name=self.collection_name, data=rows)

    def search(
        self,
        embedding: list[float],
        top_k: int,
        filters: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        results = self._client().search(
            collection_name=self.collection_name,
            data=[embedding],
            limit=top_k,
            filter=filters,
            output_fields=[
                "chunk_id",
                "space_id",
                "node_token",
                "doc_token",
                "doc_type",
                "title",
                "section_path",
                "source_url",
                "block_ids",
                "content",
                "content_hash",
                "updated_time",
            ],
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
        )
        hits = []
        for hit in results[0] if results else []:
            entity = dict(hit.get("entity") or {})
            entity["score"] = float(hit.get("distance", 0.0))
            block_ids = entity.get("block_ids")
            if isinstance(block_ids, str):
                try:
                    entity["block_ids"] = json.loads(block_ids)
                except json.JSONDecodeError:
                    entity["block_ids"] = [block_ids]
            hits.append(entity)
        return hits
