from datetime import datetime, timezone
from ourdigest.models import Story, url_id


def test_url_id_stable():
    assert url_id('https://example.com/a') == url_id('https://example.com/a')
    assert url_id('https://example.com/a') != url_id('https://example.com/b')


def test_story_id_defaults_from_url():
    s = Story(source='x', source_type='reddit', url='https://r.example/1', title='t')
    assert s.id == url_id('https://r.example/1')


def test_published_iso_rfc822():
    s = Story(
        source='x', source_type='reddit', url='u',
        title='t',
        published=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert s.published_iso.startswith('Sun, 01 Jun 2025')
