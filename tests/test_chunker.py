from backend.app.services.chunker import (
    MILVUS_CONTENT_MAX_BYTES,
    Chunk,
    chunk_document,
    chunk_to_milvus_metadata,
    utf8_len,
)
from backend.app.services.feishu import FeishuBlock, FeishuNode


def test_chunk_document_preserves_source_fields() -> None:
    node = FeishuNode(
        account_id="default",
        space_id="spc_1",
        node_token="nod_1",
        parent_node_token=None,
        obj_token="doc_1",
        obj_type="docx",
        title="接入说明",
        source_url="https://example.feishu.cn/wiki/doc_1",
        updated_time=123,
    )
    blocks = [
        FeishuBlock(
            block_id="blk_h1",
            parent_block_id=None,
            block_type="heading1",
            raw={"block_id": "blk_h1", "heading_level": 1, "text": {"content": "权限配置"}},
        ),
        FeishuBlock(
            block_id="blk_body",
            parent_block_id=None,
            block_type="text",
            raw={"block_id": "blk_body", "text": {"content": "先创建飞书应用，再配置权限。"}},
        ),
    ]

    chunks = chunk_document(node, blocks, target_chars=100, max_chars=200, overlap_chars=0)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.space_id == "spc_1"
    assert chunk.node_token == "nod_1"
    assert chunk.doc_token == "doc_1"
    assert chunk.section_path == "权限配置"
    assert chunk.source_url == "https://example.feishu.cn/wiki/doc_1"
    assert chunk.block_ids == ["blk_body"]
    assert "飞书应用" in chunk.content
    assert chunk.content_hash


def test_chunk_to_milvus_metadata_normalizes_empty_varchar_fields() -> None:
    chunk = Chunk(
        chunk_id="chunk_1",
        account_id="default",
        space_id="spc_1",
        node_token="nod_1",
        doc_token="doc_1",
        doc_type="docx",
        title="文档标题",
        section_path="文档标题",
        source_url=None,
        block_ids=["blk_1"],
        content="文档内容",
        content_hash="hash_1",
        updated_time=None,
    )

    metadata = chunk_to_milvus_metadata(chunk)

    for field in (
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
    ):
        assert isinstance(metadata[field], str)
    assert metadata["source_url"] == ""
    assert metadata["account_id"] == "default"
    assert metadata["updated_time"] == 0


def test_chunk_document_splits_single_block_by_milvus_content_bytes() -> None:
    node = FeishuNode(
        account_id="default",
        space_id="spc_1",
        node_token="nod_long",
        parent_node_token=None,
        obj_token="doc_long",
        obj_type="docx",
        title="超长文档",
        source_url="https://example.feishu.cn/wiki/doc_long",
        updated_time=456,
    )
    long_mixed_text = ("中文内容" * 1600) + "\n" + ("print('hello world')\n" * 300)
    blocks = [
        FeishuBlock(
            block_id="blk_long",
            parent_block_id=None,
            block_type="text",
            raw={"block_id": "blk_long", "text": {"content": long_mixed_text}},
        )
    ]

    chunks = chunk_document(node, blocks, target_chars=800, max_chars=1400, overlap_chars=0)

    assert utf8_len(long_mixed_text) > MILVUS_CONTENT_MAX_BYTES
    assert len(chunks) > 1
    for chunk in chunks:
        assert utf8_len(chunk.content) <= MILVUS_CONTENT_MAX_BYTES
        assert chunk.block_ids == ["blk_long"]
        assert chunk.source_url == "https://example.feishu.cn/wiki/doc_long"
