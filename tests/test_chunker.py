from backend.app.services.chunker import chunk_document
from backend.app.services.feishu import FeishuBlock, FeishuNode


def test_chunk_document_preserves_source_fields() -> None:
    node = FeishuNode(
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
