"""CLI: `ourdigest fetch` to refresh feeds, `ourdigest serve` to run the server."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import click

from .config import Config
from .feed import write_all_feed, write_feed
from .fetcher import fetch_all
from .storage import DedupStore


def _cfg_path() -> str:
    p = os.environ.get("OURDIGEST_CONFIG")
    if not p:
        raise click.UsageError("set OURDIGEST_CONFIG=/path/to/config.yaml")
    return p


@click.group()
@click.option("--verbose", "-v", is_flag=True)
def main(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@main.command()
def fetch() -> None:
    """Fetch all topics once, write feeds to <data_dir>/feeds/."""
    cfg = Config.load(_cfg_path())
    base = os.environ.get("OURDIGEST_BASE_URL", "http://localhost:8088").rstrip("/")
    fdir = Path(cfg.global_.data_dir) / "feeds"
    fdir.mkdir(parents=True, exist_ok=True)
    with DedupStore(Path(cfg.global_.data_dir) / "ourdigest.sqlite") as store:
        topic_stories = asyncio.run(
            fetch_all(cfg, store=store, summarize=cfg.global_.summarize)
        )
        for topic in cfg.topics:
            stories = topic_stories.get(topic.key, [])
            write_feed(fdir / f"{topic.key}.xml", topic, stories, base_url=base)
            click.echo(f"{topic.key}: {len(stories)} new stories -> {fdir}/{topic.key}.xml")
        write_all_feed(fdir / "all.xml", cfg, topic_stories, base_url=base)
        click.echo(f"all: {sum(len(v) for v in topic_stories.values())} total -> {fdir}/all.xml")


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8088, show_default=True)
def serve(host: str, port: int) -> None:
    """Run the FastAPI server."""
    import uvicorn

    Config.load(_cfg_path())  # fail fast if config is bad
    uvicorn.run("ourdigest.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
