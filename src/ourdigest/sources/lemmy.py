"""Lemmy source: pulls a community listing JSON (no auth required for read)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import Source
from ..models import Story


class LemmySource(Source):
    source_type = "lemmy"

    def __init__(
        self,
        name: str,
        community: str,
        instance: str | None = None,
        sort: str = "Hot",
    ) -> None:
        super().__init__(name=name)
        if sort not in {"Hot", "New", "TopDay", "TopWeek", "TopMonth", "Active"}:
            raise ValueError(f"lemmy sort invalid: {sort!r}")
        self.sort = sort
        # "ai@lemmy.world" → instance=lemmy.world, name=ai
        if "@" in community:
            self.community_name, _, self.instance = community.partition("@")
            self.instance = self.instance or instance or "lemmy.world"
        else:
            if not instance:
                raise ValueError("lemmy community must be 'name@instance' or supply instance=")
            self.community_name = community
            self.instance = instance

    async def fetch(
        self,
        client: httpx.AsyncClient,
        *,
        lookback_hours: int,
        limit: int,
    ) -> list[Story]:
        url = f"https://{self.instance}/api/v3/post/list"
        params = {
            "community_name": self.community_name,
            "sort": self.sort,
            "limit": str(min(limit, 50)),
            "type_": "All",
        }
        resp = await client.get(url, params=params, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        posts: list[dict[str, Any]] = data.get("posts", []) or []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        out: list[Story] = []
        for post in posts:
            p = post.get("post", {}) or {}
            ts = p.get("published") or ""
            try:
                created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if created < cutoff:
                continue
            ap_id = p.get("ap_id") or ""
            snippet = (p.get("body") or "")[:500]
            title = p.get("name", "").strip()
            counts = post.get("counts", {}) or {}
            score = int(counts.get("score", 0) or 0)
            out.append(
                Story(
                    source=f"!{self.community_name}@{self.instance}",
                    source_type=self.source_type,
                    url=ap_id,
                    title=title or "(untitled)",
                    snippet=snippet,
                    author=(post.get("creator") or {}).get("name", ""),
                    published=created,
                    score=score,
                    comments_url=ap_id,
                )
            )
            if len(out) >= limit:
                break
        return out
