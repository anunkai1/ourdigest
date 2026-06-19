"""FastAPI app: serves generated feeds + a /refresh endpoint."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from .config import Config
from .feed import write_all_feed, write_feed
from .fetcher import fetch_all
from .storage import DedupStore


def _load_config() -> Config:
    cfg_path = os.environ.get("OURDIGEST_CONFIG")
    if not cfg_path:
        raise RuntimeError("OURDIGEST_CONFIG env var must point at config.yaml")
    return Config.load(cfg_path)


def _feeds_dir(cfg: Config) -> Path:
    p = Path(os.environ.get("OURDIGEST_FEEDS_DIR", cfg.global_.data_dir)) / "feeds"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _store_path(cfg: Config) -> Path:
    p = Path(cfg.global_.data_dir) / "ourdigest.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _base_url() -> str:
    return os.environ.get("OURDIGEST_BASE_URL", "http://localhost:8088").rstrip("/")


async def _do_refresh(cfg: Config) -> dict[str, int]:
    counts: dict[str, int] = {}
    with DedupStore(_store_path(cfg)) as store:
        topic_stories = await fetch_all(cfg, store=store, summarize=cfg.global_.summarize)
        base = _base_url()
        fdir = _feeds_dir(cfg)
        for topic in cfg.topics:
            stories = topic_stories.get(topic.key, [])
            write_feed(fdir / f"{topic.key}.xml", topic, stories, base_url=base)
            counts[topic.key] = len(stories)
        write_all_feed(fdir / "all.xml", cfg, topic_stories, base_url=base)
        counts["all"] = sum(len(v) for v in topic_stories.values())
    return counts


def create_app() -> FastAPI:
    app = FastAPI(title="ourdigest", version="0.1.0")
    cfg = _load_config()

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.get("/feed/{name}.xml")
    async def feed(name: str) -> FileResponse:
        if name == "all":
            p = _feeds_dir(cfg) / "all.xml"
        else:
            if cfg.topic_by_key(name) is None:
                raise HTTPException(404, f"unknown topic: {name}")
            p = _feeds_dir(cfg) / f"{name}.xml"
        if not p.exists():
            raise HTTPException(404, f"feed not yet generated: {name}")
        return FileResponse(p, media_type="application/rss+xml")

    @app.post("/refresh")
    async def refresh() -> dict[str, object]:
        counts = await _do_refresh(cfg)
        return {"ok": True, "stories_per_topic": counts}

    return app


if os.environ.get("OURDIGEST_CONFIG"):
    app = create_app()
else:
    app = None  # type: ignore[assignment]
