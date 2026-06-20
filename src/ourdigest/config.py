"""YAML config loader and Pydantic models."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GlobalConfig(BaseModel):
    user_agent: str = "ourdigest/0.1"
    http_timeout_seconds: int = 15
    max_items_per_source: int = 25
    lookback_hours: int = 36
    data_dir: str = "./data"
    summarize: bool = True
    summarize_model: str = "qwen2.5-7b-instruct"
    summarize_max_input_chars: int = 1500


_SENTINEL: Any = object()


class SourceConfig(BaseModel):
    """A source block from the YAML.

    Source-specific fields (subreddit:, query:, category:, community:, ...)
    appear at the top level of each YAML entry. We accept them as extras and
    fold them into `params` so plugins receive them as keyword arguments.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        allowed = {"reddit", "reddit_oauth", "hackernews", "lemmy", "arxiv", "googlenews"}
        if v not in allowed:
            raise ValueError(f"unknown source type {v!r}; allowed: {sorted(allowed)}")
        return v

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # type: ignore[override]
        # When pydantic hands us a raw dict (the normal YAML/JSON path),
        # collect all extra keys (anything that isn't type/name/params) into params.
        if isinstance(obj, dict):
            cleaned: dict[str, Any] = {}
            params: dict[str, Any] = {}
            for k, v in obj.items():
                if k in {"type", "name", "params"}:
                    cleaned[k] = v
                else:
                    params[k] = v
            if params and "params" not in cleaned:
                cleaned["params"] = params
            obj = cleaned
        return super().model_validate(obj, *args, **kwargs)

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> "SourceConfig":
        # Just delegate to model_validate; it does the right thing.
        return cls.model_validate(data)


class TopicConfig(BaseModel):
    key: str
    title: str
    description: str = ""
    keywords_any: list[str] = Field(default_factory=list)
    keywords_all: list[str] = Field(default_factory=list)
    keywords_none: list[str] = Field(default_factory=list)
    sources: list[SourceConfig] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> "TopicConfig":
        sources = [SourceConfig.from_yaml(s) for s in data.get("sources", [])]
        return cls(
            key=data["key"],
            title=data["title"],
            description=data.get("description", ""),
            keywords_any=[k.lower() for k in data.get("keywords_any", [])],
            keywords_all=[k.lower() for k in data.get("keywords_all", [])],
            keywords_none=[k.lower() for k in data.get("keywords_none", [])],
            sources=sources,
        )


class Config(BaseModel):
    # The YAML key is "global" (Python reserved word) so we validate from a dict.
    model_config = ConfigDict(populate_by_name=True)

    global_: GlobalConfig = Field(alias="global")
    topics: list[TopicConfig]

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        raw = yaml.safe_load(Path(path).read_text())
        global_cfg = GlobalConfig(**(raw.get("global") or {}))
        topics = [TopicConfig.from_yaml(t) for t in raw.get("topics", [])]
        if not topics:
            raise ValueError("config must define at least one topic")
        # Build directly so we do not re-validate already-constructed
        # SourceConfig/TopicConfig instances (which would re-fold extras).
        return cls.model_construct(global_=global_cfg, topics=topics)

    def topic_by_key(self, key: str) -> TopicConfig | None:
        return next((t for t in self.topics if t.key == key), None)
