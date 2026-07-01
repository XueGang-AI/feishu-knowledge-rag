from pathlib import Path

from backend.app.db.sqlite import connect
from backend.app.services.feishu import FeishuBlock, FeishuNode, FeishuSpace
from backend.app.services.rag import RAGService
from backend.app.services.repository import StateRepository
from backend.app.services.vector_store import MilvusVectorStore


def _node(account_id: str) -> FeishuNode:
    return FeishuNode(
        account_id=account_id,
        space_id="same_space",
        node_token="same_node",
        parent_node_token=None,
        obj_token="same_doc",
        obj_type="docx",
        title=f"{account_id} 文档",
        source_url=f"https://feishu.cn/wiki/{account_id}",
        updated_time=1,
    )


def test_same_tokens_do_not_conflict_across_accounts(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state" / "test.sqlite3")
    blocks = [
        FeishuBlock(
            block_id="same_block",
            parent_block_id=None,
            block_type="text",
            raw={"text": {"content": "正文"}},
        )
    ]

    for account_id in ("default", "tenant_2"):
        repository.upsert_space(
            FeishuSpace(account_id=account_id, space_id="same_space", name=account_id)
        )
        node = _node(account_id)
        repository.upsert_node(node)
        assert repository.upsert_document(node, blocks) is True
        repository.replace_blocks(account_id, "same_doc", blocks)

    with connect(repository.sqlite_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM spaces").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 2


def test_rag_filter_includes_account_id() -> None:
    service = RAGService(settings=object())  # type: ignore[arg-type]

    assert service._build_filter("tenant_2", "space_1", "doc_1") == (
        'account_id == "tenant_2" and space_id == "space_1" and doc_token == "doc_1"'
    )


def test_default_account_builds_legacy_filter_without_account_id() -> None:
    service = RAGService(settings=object())  # type: ignore[arg-type]

    assert service._build_legacy_filter("default", "space_1", "doc_1") == (
        'space_id == "space_1" and doc_token == "doc_1"'
    )
    assert service._build_legacy_filter("tenant_2", "space_1", "doc_1") is None


class FakeMilvusClient:
    def __init__(self) -> None:
        self.search_calls: list[tuple[str, str | None]] = []

    def has_collection(self, collection_name: str) -> bool:
        return collection_name in {"feishu_chunks_v2", "feishu_chunks_v1"}

    def search(self, collection_name: str, **kwargs):
        filters = kwargs.get("filter")
        self.search_calls.append((collection_name, filters))
        if collection_name == "feishu_chunks_v2":
            return [[]]
        if filters == 'space_id == "space_1"':
            return [
                [
                    {
                        "distance": 0.8,
                        "entity": {
                            "chunk_id": "legacy_chunk",
                            "space_id": "space_1",
                            "node_token": "node_1",
                            "doc_token": "doc_1",
                            "doc_type": "docx",
                            "title": "旧集合文档",
                            "section_path": "旧集合文档",
                            "source_url": "https://feishu.cn/wiki/node_1",
                            "block_ids": "[\"block_1\"]",
                            "content": "旧集合内容",
                            "content_hash": "hash_1",
                            "updated_time": 1,
                        },
                    }
                ]
            ]
        return [[]]


class FakeVectorStore(MilvusVectorStore):
    def __init__(self, client: FakeMilvusClient) -> None:
        super().__init__(
            uri="http://127.0.0.1:19530",
            collection_name="feishu_chunks_v2",
            legacy_collection_name="feishu_chunks_v1",
        )
        self.client = client

    def _client(self):
        return self.client

    def ensure_collection(self) -> None:
        return None


def test_default_account_filter_falls_back_to_legacy_collection() -> None:
    client = FakeMilvusClient()
    vector_store = FakeVectorStore(client)

    hits = vector_store.search(
        embedding=[0.1, 0.2],
        top_k=3,
        filters='account_id == "default" and space_id == "space_1"',
        legacy_filters='space_id == "space_1"',
        legacy_account_id="default",
    )

    assert client.search_calls == [
        ("feishu_chunks_v2", 'account_id == "default" and space_id == "space_1"'),
        ("feishu_chunks_v1", 'space_id == "space_1"'),
    ]
    assert hits[0]["chunk_id"] == "legacy_chunk"
    assert hits[0]["account_id"] == "default"
    assert hits[0]["block_ids"] == ["block_1"]


def test_non_default_account_filter_does_not_fall_back_to_legacy_collection() -> None:
    client = FakeMilvusClient()
    vector_store = FakeVectorStore(client)

    hits = vector_store.search(
        embedding=[0.1, 0.2],
        top_k=3,
        filters='account_id == "tenant_2"',
        legacy_filters=None,
        legacy_account_id=None,
    )

    assert hits == []
    assert client.search_calls == [("feishu_chunks_v2", 'account_id == "tenant_2"')]
