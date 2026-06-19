import pytest
from pydantic import ValidationError
from ourdigest.config import Config, SourceConfig, TopicConfig


def test_loads_example_config(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        "global:\n"
        "  lookback_hours: 24\n"
        "topics:\n"
        "  - key: ai\n"
        "    title: AI Digest\n"
        "    keywords_any: [llm, agent]\n"
        "    sources:\n"
        "      - type: hackernews\n"
        "        name: HN\n"
        "        query_tags: [front_page]\n"
        "        limit: 10\n"
    )
    cfg = Config.load(cfg_path)
    assert cfg.global_.lookback_hours == 24
    assert len(cfg.topics) == 1
    assert cfg.topics[0].key == "ai"
    assert cfg.topics[0].sources[0].type == "hackernews"


def test_unknown_source_type_rejected():
    with pytest.raises(ValidationError):
        SourceConfig(type="telegram", name="x")


def test_keywords_lowercased():
    t = TopicConfig.from_yaml({"key": "k", "title": "T", "keywords_any": ["LLM", "Ai"]})
    assert t.keywords_any == ["llm", "ai"]
