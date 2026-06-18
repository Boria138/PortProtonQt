"""Tests for config/cache.py — CacheManager."""
import time
from pathlib import Path

from portprotonqt.config.cache import CacheManager


class TestCacheManagerInit:
    def test_creates_cache_dir(self, tmp_path: Path):
        cache_dir = tmp_path / "test_cache"
        CacheManager(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_default_cache_dir(self):
        mgr = CacheManager()
        assert mgr.cache_dir.exists()


class TestGetCacheFilePath:
    def test_sanitizes_name(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        path = mgr._get_cache_file_path("my file/name!")
        assert " " not in path.name
        assert "/" not in path.name
        assert "!" not in path.name

    def test_custom_extension(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        path = mgr._get_cache_file_path("test", extension=".dat")
        assert path.suffix == ".dat"

    def test_strips_whitespace(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        path = mgr._get_cache_file_path("  hello  ")
        assert not path.name.startswith("_")
        assert not path.name.endswith("_")


class TestSaveLoadJson:
    def test_roundtrip(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        data = {"key": "value", "number": 42, "nested": {"a": [1, 2, 3]}}
        assert mgr.save_json("test", data) is True
        loaded = mgr.load_json("test")
        assert loaded == data

    def test_load_nonexistent(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.load_json("nonexistent") is None

    def test_overwrite(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("test", {"v": 1})
        mgr.save_json("test", {"v": 2})
        assert mgr.load_json("test") == {"v": 2}

    def test_pretty_print(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("test", {"a": 1}, pretty=True)
        loaded = mgr.load_json("test")
        assert loaded == {"a": 1}

    def test_invalid_json_file(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        cache_file = mgr._get_cache_file_path("broken")
        cache_file.write_bytes(b"not json {{{")
        assert mgr.load_json("broken") is None
        assert not cache_file.exists()


class TestSaveLoadText:
    def test_roundtrip(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.save_text("test", "hello world") is True
        assert mgr.load_text("test") == "hello world"

    def test_load_nonexistent(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.load_text("nonexistent") is None


class TestSaveLoadBinary:
    def test_roundtrip(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        data = b"\x00\x01\x02\xff"
        assert mgr.save_binary("test", data) is True
        assert mgr.load_binary("test") == data

    def test_load_nonexistent(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.load_binary("nonexistent") is None


class TestExists:
    def test_exists_after_save(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("test", {"a": 1})
        assert mgr.exists("test") is True

    def test_not_exists(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.exists("nonexistent") is False


class TestRemove:
    def test_remove_existing(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("test", {"a": 1})
        assert mgr.remove("test") is True
        assert mgr.load_json("test") is None

    def test_remove_nonexistent(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.remove("nonexistent") is False


class TestClear:
    def test_clear_removes_files(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("a", {"x": 1})
        mgr.save_json("b", {"x": 2})
        mgr.clear()
        assert mgr.load_json("a") is None
        assert mgr.load_json("b") is None
        assert tmp_path.exists()


class TestGetFileAge:
    def test_age_of_existing_file(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("test", {"a": 1})
        age = mgr.get_file_age("test")
        assert age is not None
        assert age >= 0

    def test_age_of_nonexistent_file(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.get_file_age("nonexistent") is None


class TestIsFresh:
    def test_fresh_cache(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("test", {"a": 1})
        assert mgr.is_fresh("test", max_age=3600) is True

    def test_stale_cache(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        mgr.save_json("test", {"a": 1})
        cache_file = mgr._get_cache_file_path("test")
        old_time = time.time() - 7200
        cache_file.touch()
        import os
        os.utime(cache_file, (old_time, old_time))
        assert mgr.is_fresh("test", max_age=3600) is False

    def test_nonexistent_file(self, tmp_path: Path):
        mgr = CacheManager(cache_dir=tmp_path)
        assert mgr.is_fresh("nonexistent", max_age=3600) is False
