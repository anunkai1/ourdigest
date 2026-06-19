from datetime import datetime, timezone
from ourdigest.config import TopicConfig
from ourdigest.fetcher import _matches
from ourdigest.models import Story


def _s(title: str, url: str = 'https://x', snippet: str = '') -> Story:
    return Story(
        source='src', source_type='reddit', url=url,
        title=title, snippet=snippet,
        published=datetime.now(timezone.utc),
    )


def test_keywords_any_match():
    t = TopicConfig.from_yaml({'key': 't', 'title': 'T', 'keywords_any': ['llm', 'rag']})
    assert _matches(_s('LLM news'), t)
    assert _matches(_s('something about rag'), t)
    assert not _matches(_s('cooking recipes'), t)


def test_keywords_none_excludes():
    t = TopicConfig.from_yaml({'key': 't', 'title': 'T', 'keywords_none': ['meme']})
    assert not _matches(_s('Funny meme of the day'), t)
    assert _matches(_s('A serious post'), t)


def test_keywords_all_required():
    t = TopicConfig.from_yaml({'key': 't', 'title': 'T', 'keywords_all': ['llm', 'rag']})
    assert _matches(_s('an LLM with RAG'), t)
    assert not _matches(_s('just an LLM'), t)


def test_no_keywords_keeps_all():
    t = TopicConfig.from_yaml({'key': 't', 'title': 'T'})
    assert _matches(_s('anything goes'), t)
