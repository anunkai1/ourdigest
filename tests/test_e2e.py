import os, json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import respx

from ourdigest.config import Config
from ourdigest.fetcher import fetch_all
from ourdigest.feed import write_feed, write_all_feed
from ourdigest.storage import DedupStore


def _write_cfg(path: Path, *, with_latest: bool = True) -> Path:
    now_ts = datetime.now(timezone.utc).timestamp() if with_latest else 1.0
    body = f"""
global:
  lookback_hours: 24
  max_items_per_source: 10
  data_dir: "{path.as_posix()}"
  summarize: false
topics:
  - key: ai
    title: AI Digest
    keywords_any: [llm]
    sources:
      - type: reddit
        name: r/LocalLLaMA
        subreddit: LocalLLaMA
"""
    p = path / "cfg.yaml"
    p.write_text(body)
    return p


@pytest.mark.asyncio
async def test_full_pipeline_writes_feed(tmp_path):
    cfg_path = _write_cfg(tmp_path, with_latest=True)
    cfg = Config.load(cfg_path)

    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "Local LLM release notes",
                        "permalink": "/r/LocalLLaMA/comments/1/abc/",
                        "url": "https://example.com/p",
                        "selftext": "Notes.",
                        "author": "someone",
                        "created_utc": datetime.now(timezone.utc).timestamp(),
                        "score": 100,
                    }
                },
                {
                    "data": {
                        "title": "A cooking recipe",  # should be filtered out
                        "permalink": "/r/LocalLLaMA/comments/2/recipe/",
                        "url": "https://example.com/r",
                        "selftext": "",
                        "author": "someone",
                        "created_utc": datetime.now(timezone.utc).timestamp(),
                        "score": 0,
                    }
                },
            ]
        }
    }

    with respx.mock(base_url="https://www.reddit.com") as mock:
        mock.get("/r/LocalLLaMA/top.json").respond(200, json=payload)
        store = DedupStore(tmp_path / "ourdigest.sqlite")
        try:
            topic_stories = await fetch_all(cfg, store=store, summarize=False)
        finally:
            store.close()

    assert "ai" in topic_stories
    assert len(topic_stories["ai"]) == 1
    assert "Local LLM" in topic_stories["ai"][0].title

    feeds = tmp_path / "feeds"
    write_feed(feeds / "ai.xml", cfg.topics[0], topic_stories["ai"], base_url="http://x")
    write_all_feed(feeds / "all.xml", cfg, topic_stories, base_url="http://x")
    assert (feeds / "ai.xml").exists()
    assert (feeds / "all.xml").exists()
    body = (feeds / "ai.xml").read_text()
    assert "Local LLM release notes" in body
