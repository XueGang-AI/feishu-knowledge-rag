from backend.app.services.feishu import FeishuClient


def test_parse_node_accepts_feishu_variants() -> None:
    client = FeishuClient("https://open.feishu.cn", "default", "app", "secret")

    node = client._parse_node(
        "spc_1",
        {
            "node_token": "nod_1",
            "parent_node_token": "parent",
            "obj_token": "doc_1",
            "obj_type": "docx",
            "title": "文档标题",
            "url": "https://example.feishu.cn/wiki/doc_1",
            "obj_edit_time": "123",
        },
        None,
    )

    assert node.space_id == "spc_1"
    assert node.node_token == "nod_1"
    assert node.parent_node_token == "parent"
    assert node.obj_token == "doc_1"
    assert node.obj_type == "docx"
    assert node.title == "文档标题"
    assert node.updated_time == 123


def test_parse_node_builds_wiki_source_url_when_missing() -> None:
    client = FeishuClient("https://open.feishu.cn", "default", "app", "secret")

    node = client._parse_node(
        "spc_1",
        {
            "node_token": "nod_1",
            "obj_token": "doc_1",
            "obj_type": "docx",
            "title": "文档标题",
        },
        None,
    )

    assert node.source_url == "https://feishu.cn/wiki/nod_1"
