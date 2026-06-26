from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class FeishuError(RuntimeError):
    pass


@dataclass(frozen=True)
class FeishuSpace:
    space_id: str
    name: str
    description: str | None = None


@dataclass(frozen=True)
class FeishuNode:
    space_id: str
    node_token: str
    parent_node_token: str | None
    obj_token: str | None
    obj_type: str | None
    title: str
    source_url: str | None
    updated_time: int | None


@dataclass(frozen=True)
class FeishuBlock:
    block_id: str
    parent_block_id: str | None
    block_type: str
    raw: dict[str, Any]


class FeishuClient:
    def __init__(
        self,
        base_url: str,
        app_id: str,
        app_secret: str,
        timeout_seconds: float = 30,
        page_size: int = 50,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout_seconds = timeout_seconds
        self.page_size = page_size
        self._tenant_access_token: str | None = None

    async def _tenant_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        data = await self._request_without_auth(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json=payload,
        )
        token = data.get("tenant_access_token")
        if not token:
            raise FeishuError("Feishu tenant access token response did not include a token")
        self._tenant_access_token = token
        return token

    async def _request_without_auth(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        response.raise_for_status()
        payload = response.json()
        code = payload.get("code", 0)
        if code != 0:
            raise FeishuError(f"Feishu API error {code}: {payload.get('msg') or payload}")
        return payload

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        token = await self._tenant_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        return await self._request_without_auth(method, path, headers=headers, **kwargs)

    async def _paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        item_keys: tuple[str, ...] = ("items",),
    ) -> list[dict[str, Any]]:
        page_token: str | None = None
        items: list[dict[str, Any]] = []
        while True:
            request_params = dict(params or {})
            request_params.setdefault("page_size", self.page_size)
            if page_token:
                request_params["page_token"] = page_token
            payload = await self._request("GET", path, params=request_params)
            data = payload.get("data") or {}
            page_items: list[dict[str, Any]] = []
            for key in item_keys:
                value = data.get(key)
                if isinstance(value, list):
                    page_items = value
                    break
            items.extend(page_items)
            if not data.get("has_more"):
                return items
            page_token = data.get("page_token")
            if not page_token:
                return items

    async def list_spaces(self) -> list[FeishuSpace]:
        raw_spaces = await self._paginate(
            "/open-apis/wiki/v2/spaces", item_keys=("items", "spaces")
        )
        return [
            FeishuSpace(
                space_id=str(item.get("space_id") or item.get("space_id_str") or ""),
                name=str(item.get("name") or item.get("space_name") or "Untitled space"),
                description=item.get("description"),
            )
            for item in raw_spaces
            if item.get("space_id") or item.get("space_id_str")
        ]

    async def list_child_nodes(
        self,
        space_id: str,
        parent_node_token: str | None = None,
    ) -> list[FeishuNode]:
        params: dict[str, Any] = {}
        if parent_node_token:
            params["parent_node_token"] = parent_node_token
        raw_nodes = await self._paginate(
            f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
            params=params,
            item_keys=("items", "nodes"),
        )
        return [self._parse_node(space_id, item, parent_node_token) for item in raw_nodes]

    async def get_node(self, space_id: str, node_token: str) -> FeishuNode:
        payload = await self._request(
            "GET", f"/open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}"
        )
        data = payload.get("data") or {}
        item = data.get("node") or data
        return self._parse_node(space_id, item, item.get("parent_node_token"))

    async def list_docx_blocks(self, document_id: str) -> list[FeishuBlock]:
        raw_blocks = await self._paginate(
            f"/open-apis/docx/v1/documents/{document_id}/blocks",
            item_keys=("items", "blocks"),
        )
        return [self._parse_block(item) for item in raw_blocks if item.get("block_id")]

    def _parse_node(
        self,
        space_id: str,
        item: dict[str, Any],
        fallback_parent_node_token: str | None,
    ) -> FeishuNode:
        node_token = str(item.get("node_token") or "")
        obj_token = item.get("obj_token") or item.get("origin_node_token")
        updated_time = (
            item.get("obj_edit_time") or item.get("updated_time") or item.get("edit_time")
        )
        return FeishuNode(
            space_id=space_id,
            node_token=node_token,
            parent_node_token=item.get("parent_node_token") or fallback_parent_node_token,
            obj_token=obj_token,
            obj_type=item.get("obj_type") or item.get("node_type"),
            title=str(item.get("title") or item.get("name") or "Untitled document"),
            source_url=item.get("url") or item.get("source_url"),
            updated_time=int(updated_time)
            if updated_time is not None and str(updated_time).isdigit()
            else None,
        )

    def _parse_block(self, item: dict[str, Any]) -> FeishuBlock:
        block_type = str(item.get("block_type") or item.get("type") or "unknown")
        return FeishuBlock(
            block_id=str(item["block_id"]),
            parent_block_id=item.get("parent_id") or item.get("parent_block_id"),
            block_type=block_type,
            raw=item,
        )
