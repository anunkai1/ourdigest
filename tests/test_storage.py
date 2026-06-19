from pathlib import Path
from ourdigest.storage import DedupStore


def test_dedup_round_trip(tmp_path: Path):
    db = tmp_path / 's.sqlite'
    with DedupStore(db) as s:
        assert not s.is_seen('abc', 't1')
        s.mark_seen(['abc', 'def'], 't1', seen_at_ms=1000)
        assert s.is_seen('abc', 't1')
        assert s.is_seen('def', 't1')
        # same id, different topic is not a dup
        assert not s.is_seen('abc', 't2')


def test_vacuum_old(tmp_path: Path):
    with DedupStore(tmp_path / 's.sqlite') as s:
        s.mark_seen(['a'], 't', seen_at_ms=100)
        s.mark_seen(['b'], 't', seen_at_ms=5000)
        deleted = s.vacuum_old(older_than_ms=1000)
        assert deleted == 1
        assert s.is_seen('b', 't')
        assert not s.is_seen('a', 't')
