"""Tests for steam_api/cache.py — exiftool skip and search functions."""
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from portprotonqt.steam_api.cache import (
    get_exiftool_data,
    delete_cached_app_files,
    _EXIFTOOL_CACHE,
    _CACHE_MAX_ENTRIES,
    _CACHE_TTL,
)


@pytest.fixture(autouse=True)
def clear_exiftool_cache():
    _EXIFTOOL_CACHE.clear()
    yield
    _EXIFTOOL_CACHE.clear()


class TestGetExiftoolData:
    def test_skips_missing_executable(self, tmp_path: Path):
        fake_exe = tmp_path / "game.exe"
        fake_exe.touch()
        with patch("shutil.which", return_value=None):
            assert get_exiftool_data(str(fake_exe)) == {}

    def test_skips_nonexistent_file(self):
        assert get_exiftool_data("/nonexistent/game.exe") == {}

    def test_returns_empty_on_nonzero_returncode(self, tmp_path: Path):
        fake_exe = tmp_path / "game.exe"
        fake_exe.touch()
        mock_proc = MagicMock(returncode=1, stderr="error")
        with (
            patch("shutil.which", return_value="/usr/bin/exiftool"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            assert get_exiftool_data(str(fake_exe)) == {}

    def test_returns_metadata(self, tmp_path: Path):
        import orjson
        fake_exe = tmp_path / "game.exe"
        fake_exe.touch()
        meta = [{"FileName": "game.exe", "FileSize": 1024}]
        mock_proc = MagicMock(returncode=0, stdout=orjson.dumps(meta).decode())
        with (
            patch("shutil.which", return_value="/usr/bin/exiftool"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            result = get_exiftool_data(str(fake_exe))
            assert result == {"FileName": "game.exe", "FileSize": 1024}

    def test_caches_result(self, tmp_path: Path):
        import orjson
        fake_exe = tmp_path / "game.exe"
        fake_exe.touch()
        meta = [{"FileName": "game.exe"}]
        mock_proc = MagicMock(returncode=0, stdout=orjson.dumps(meta).decode())
        with (
            patch("shutil.which", return_value="/usr/bin/exiftool"),
            patch("subprocess.run", return_value=mock_proc) as mock_run,
        ):
            get_exiftool_data(str(fake_exe))
            get_exiftool_data(str(fake_exe))
            assert mock_run.call_count == 1

    def test_expired_cache_fetched_again(self, tmp_path: Path):
        import orjson
        fake_exe = tmp_path / "game.exe"
        fake_exe.touch()
        meta = [{"FileName": "game.exe"}]
        mock_proc = MagicMock(returncode=0, stdout=orjson.dumps(meta).decode())

        _EXIFTOOL_CACHE[str(fake_exe)] = (meta[0], time.time() - _CACHE_TTL - 1)

        with (
            patch("shutil.which", return_value="/usr/bin/exiftool"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            result = get_exiftool_data(str(fake_exe))
            assert result == {"FileName": "game.exe"}

    def test_cache_eviction(self, tmp_path: Path):
        for i in range(_CACHE_MAX_ENTRIES // 2 + 1):
            exe = tmp_path / f"game{i}.exe"
            exe.touch()
            _EXIFTOOL_CACHE[str(exe)] = ({"file": i}, time.time() - _CACHE_TTL - 1)

        import orjson
        new_exe = tmp_path / "new.exe"
        new_exe.touch()
        meta = [{"FileName": "new.exe"}]
        mock_proc = MagicMock(returncode=0, stdout=orjson.dumps(meta).decode())
        with (
            patch("shutil.which", return_value="/usr/bin/exiftool"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            get_exiftool_data(str(new_exe))
        assert str(new_exe) in _EXIFTOOL_CACHE


class TestDeleteCachedAppFiles:
    def test_deletes_matching_files(self, tmp_path: Path):
        for name in ("steam_app_1.json", "steam_app_2.json", "other.json"):
            (tmp_path / name).write_text("{}")
        delete_cached_app_files(str(tmp_path), "steam_app_*.json")
        assert not (tmp_path / "steam_app_1.json").exists()
        assert not (tmp_path / "steam_app_2.json").exists()
        assert (tmp_path / "other.json").exists()

    def test_no_matching_files(self, tmp_path: Path):
        (tmp_path / "other.txt").write_text("hello")
        delete_cached_app_files(str(tmp_path), "steam_app_*.json")
        assert (tmp_path / "other.txt").exists()
