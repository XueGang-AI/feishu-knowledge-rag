from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.app.core.hashing import sha256_text, stable_json_hash
from backend.app.services.feishu import FeishuBlock, FeishuNode


@dataclass(frozen=True)
class ParsedBlock:
    block_id: str
    parent_block_id: str | None
    block_type: str
    text: str
    heading_level: int | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    space_id: str
    node_token: str
    doc_token: str
    doc_type: str
    title: str
    section_path: str
    source_url: str | None
    block_ids: list[str]
    content: str
    content_hash: str
    updated_time: int | None


TEXT_KEYS = ("text", "content", "plain_text", "name", "title")


def parse_blocks(blocks: list[FeishuBlock]) -> list[ParsedBlock]:
    return [
        ParsedBlock(
            block_id=block.block_id,
            parent_block_id=block.parent_block_id,
            block_type=block.block_type,
            text=extract_text(block.raw),
            heading_level=extract_heading_level(block.raw, block.block_type),
            raw=block.raw,
        )
        for block in blocks
    ]


def extract_heading_level(raw: dict[str, Any], block_type: str) -> int | None:
    for key in ("heading_level", "level"):
        value = raw.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    match = re.search(r"heading[_-]?(\d)", block_type, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_text(value: Any) -> str:
    parts: list[str] = []
    _collect_text(value, parts)
    return normalize_text("\n".join(part for part in parts if part.strip()))


def _collect_text(value: Any, parts: list[str]) -> None:
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for item in value:
            _collect_text(item, parts)
        return
    if not isinstance(value, dict):
        return

    for key in TEXT_KEYS:
        raw_value = value.get(key)
        if isinstance(raw_value, str) and raw_value.strip():
            parts.append(raw_value)
        elif isinstance(raw_value, dict | list):
            _collect_text(raw_value, parts)

    for key, raw_value in value.items():
        if key in TEXT_KEYS:
            continue
        if isinstance(raw_value, dict | list):
            _collect_text(raw_value, parts)


def normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def chunk_document(
    node: FeishuNode,
    blocks: list[FeishuBlock],
    target_chars: int = 800,
    max_chars: int = 1400,
    overlap_chars: int = 100,
) -> list[Chunk]:
    parsed_blocks = parse_blocks(blocks)
    heading_stack: list[tuple[int, str]] = []
    chunks: list[Chunk] = []
    current_texts: list[str] = []
    current_block_ids: list[str] = []
    current_section_path = node.title

    def flush() -> None:
        nonlocal current_texts, current_block_ids
        content = normalize_text("\n\n".join(current_texts))
        if not content:
            current_texts = []
            current_block_ids = []
            return
        section_path = current_section_path or node.title
        hash_input = {
            "section_path": section_path,
            "block_ids": current_block_ids,
            "content": content,
        }
        content_hash = stable_json_hash(hash_input)
        chunk_id = sha256_text(
            f"{node.space_id}:{node.node_token}:{node.obj_token}:{content_hash}"
        )[:32]
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                space_id=node.space_id,
                node_token=node.node_token,
                doc_token=node.obj_token or node.node_token,
                doc_type=node.obj_type or "docx",
                title=node.title,
                section_path=section_path,
                source_url=node.source_url,
                block_ids=list(current_block_ids),
                content=content,
                content_hash=content_hash,
                updated_time=node.updated_time,
            )
        )
        if overlap_chars > 0 and len(content) > overlap_chars:
            overlap = content[-overlap_chars:]
            current_texts = [overlap]
            current_block_ids = list(current_block_ids[-1:])
        else:
            current_texts = []
            current_block_ids = []

    for block in parsed_blocks:
        if not block.text:
            continue

        if block.heading_level:
            flush()
            heading_stack = [
                (level, text) for level, text in heading_stack if level < block.heading_level
            ]
            heading_stack.append((block.heading_level, block.text))
            current_section_path = " > ".join(text for _, text in heading_stack) or node.title
            continue

        candidate_len = sum(len(text) for text in current_texts) + len(block.text)
        if current_texts and candidate_len > max_chars:
            flush()

        current_texts.append(block.text)
        current_block_ids.append(block.block_id)

        if sum(len(text) for text in current_texts) >= target_chars:
            flush()

    flush()
    return chunks


def block_hashes(blocks: list[FeishuBlock]) -> dict[str, str]:
    return {block.block_id: stable_json_hash(block.raw) for block in blocks}


def blocks_snapshot_hash(blocks: list[FeishuBlock]) -> str:
    return stable_json_hash([block.raw for block in blocks])


def chunk_to_milvus_metadata(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "space_id": chunk.space_id,
        "node_token": chunk.node_token,
        "doc_token": chunk.doc_token,
        "doc_type": chunk.doc_type,
        "title": chunk.title,
        "section_path": chunk.section_path,
        "source_url": chunk.source_url,
        "block_ids": json.dumps(chunk.block_ids, ensure_ascii=False),
        "content": chunk.content,
        "content_hash": chunk.content_hash,
        "updated_time": chunk.updated_time or 0,
    }
