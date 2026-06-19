import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from ourdigest.sources import build_source


@pytest.mark.asyncio
async def test_reddit_parses_listing():
    payload = {
        'data': {
            'children': [
                {
                    'data': {
                        'title': 'Local Llama 3.3 release notes',
                        'permalink': '/r/LocalLLaMA/comments/1/abc/',
                        'url': 'https://example.com/post',
                        'selftext': 'Some notes about a new llama release.',
                        'author': 'someone',
                        'created_utc': datetime.now(timezone.utc).timestamp(),
                        'score': 123,
                    }
                },
                {
                    'data': {
                        'title': 'Old post',
                        'permalink': '/r/LocalLLaMA/comments/2/old/',
                        'url': 'https://example.com/old',
                        'selftext': '',
                        'author': 'someone',
                        'created_utc': 1.0,  # ancient
                        'score': 0,
                    }
                },
            ]
        }
    }
    with respx.mock(base_url='https://www.reddit.com') as mock:
        mock.get('/r/LocalLLaMA/top.json').respond(200, json=payload)
        async with httpx.AsyncClient() as client:
            src = build_source('reddit', 'r/LocalLLaMA', {'subreddit': 'LocalLLaMA', 'sort': 'top', 'time': 'day'})
            stories = await src.fetch(client, lookback_hours=24, limit=10)
    assert len(stories) == 1
    s = stories[0]
    assert 'Local Llama' in s.title
    assert s.source == 'r/LocalLLaMA'
    assert s.comments_url.startswith('https://www.reddit.com')
