"""Tests for time_utils.py — playtime parsing, last launch cache, formatting.

Key regression areas (from git history):
- Spaced exe names in last launch cache (764bb3c)
- SHA256 hash matching + L5- launch index (7a02b6b)
- Malformed playtime data robustness (dd65021)
- #@_@# space encoding in stat paths
"""
from datetime import datetime

from portprotonqt.time_utils import (
    _parse_last_launch_line,
    save_last_launch,
    get_last_launch,
    get_last_launch_timestamp,
    get_cache_file_path,
    parse_playtime_file,
    get_playtime_for_exe,
    format_playtime,
)


# ── _parse_last_launch_line ──────────────────────────────────────────────────

class TestParseLastLaunchLine:
    def test_normal(self):
        result = _parse_last_launch_line("game.exe 2026-01-15T10:30:00")
        assert result == ("game.exe", "2026-01-15T10:30:00")

    def test_spaced_exe_name(self):
        result = _parse_last_launch_line("my game.exe 2026-01-15T10:30:00")
        assert result == ("my game.exe", "2026-01-15T10:30:00")

    def test_many_spaces_in_exe(self):
        result = _parse_last_launch_line("path/to/my great game.exe 2026-01-15T10:30:00")
        assert result == ("path/to/my great game.exe", "2026-01-15T10:30:00")

    def test_empty_line(self):
        assert _parse_last_launch_line("") is None

    def test_whitespace_only(self):
        assert _parse_last_launch_line("   ") is None

    def test_no_timestamp(self):
        assert _parse_last_launch_line("game.exe") is None

    def test_only_timestamp(self):
        assert _parse_last_launch_line("2026-01-15T10:30:00") is None

    def test_leading_trailing_whitespace(self):
        result = _parse_last_launch_line("  game.exe 2026-01-15T10:30:00  ")
        assert result == ("game.exe", "2026-01-15T10:30:00")


# ── get_cache_file_path ──────────────────────────────────────────────────────

class TestGetCacheFilePath:
    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        result = get_cache_file_path()
        assert result.endswith("PortProtonQt/last_launch")
        assert ".cache" in result

    def test_xdg_cache_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        result = get_cache_file_path()
        assert result.startswith(str(tmp_path))
        assert "PortProtonQt/last_launch" in result


# ── save_last_launch / get_last_launch ───────────────────────────────────────

class TestSaveAndGetLastLaunch:
    def test_roundtrip(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        now = datetime(2026, 6, 15, 12, 0, 0)
        save_last_launch("game.exe", now)
        result = get_last_launch("game.exe")
        assert result is not None
        assert "Never" != result

    def test_spaced_exe_name_roundtrip(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        now = datetime(2026, 6, 15, 12, 0, 0)
        save_last_launch("my great game.exe", now)
        result = get_last_launch("my great game.exe")
        assert result is not None
        assert "Never" != result

    def test_multiple_exe_names(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        save_last_launch("game1.exe", datetime(2026, 1, 1))
        save_last_launch("game2.exe", datetime(2026, 2, 1))
        assert "Never" != get_last_launch("game1.exe")
        assert "Never" != get_last_launch("game2.exe")

    def test_overwrites_existing(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        save_last_launch("game.exe", datetime(2026, 1, 1))
        save_last_launch("game.exe", datetime(2026, 6, 1))
        with open(str(cache_file)) as f:
            lines = [line for line in f if line.strip()]
        assert len(lines) == 1

    def test_unknown_exe_returns_never(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        result = get_last_launch("nonexistent.exe")
        assert result is not None
        assert result != ""

    def test_no_cache_file_returns_never(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: "/nonexistent/path/last_launch",
        )
        result = get_last_launch("game.exe")
        assert result is not None
        assert result != ""


# ── get_last_launch_timestamp ────────────────────────────────────────────────

class TestGetLastLaunchTimestamp:
    def test_returns_timestamp(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        dt = datetime(2026, 6, 15, 12, 0, 0)
        save_last_launch("game.exe", dt)
        result = get_last_launch_timestamp("game.exe")
        assert result > 0

    def test_returns_zero_for_unknown(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: "/nonexistent/path",
        )
        assert get_last_launch_timestamp("game.exe") == 0

    def test_returns_zero_for_missing_exe(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        save_last_launch("game.exe", datetime(2026, 6, 15))
        assert get_last_launch_timestamp("other.exe") == 0

    def test_spaced_exe_timestamp(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        dt = datetime(2026, 6, 15, 12, 0, 0)
        save_last_launch("my game.exe", dt)
        result = get_last_launch_timestamp("my game.exe")
        assert result > 0


# ── parse_playtime_file ──────────────────────────────────────────────────────

class TestParsePlaytimeFile:
    def test_normal_format(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text("/path/game.exe abc123def456 3600 platform build\n")
        result = parse_playtime_file(str(f))
        assert result["/path/game.exe"] == 3600

    def test_spaced_path_with_hash_encoding(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text("/path/my#@_@#game.exe abc123 1800 platform build\n")
        result = parse_playtime_file(str(f))
        assert result["/path/my#@_@#game.exe"] == 1800

    def test_multiple_entries(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text(
            "/path/game1.exe hash1 1000 p1 b1\n"
            "/path/game2.exe hash2 2000 p2 b2\n"
        )
        result = parse_playtime_file(str(f))
        assert len(result) == 2
        assert result["/path/game1.exe"] == 1000
        assert result["/path/game2.exe"] == 2000

    def test_skips_short_lines(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text(
            "/path/game.exe hash 3600 p b\n"
            "short\n"
            "\n"
        )
        result = parse_playtime_file(str(f))
        assert len(result) == 1

    def test_empty_file(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text("")
        result = parse_playtime_file(str(f))
        assert result == {}

    def test_nonexistent_file(self):
        result = parse_playtime_file("/nonexistent/stats.txt")
        assert result == {}

    def test_malformed_playtime_ignored(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text("/path/game.exe hash not_a_number platform build\n")
        result = parse_playtime_file(str(f))
        assert result == {}

    def test_zero_playtime(self, tmp_path):
        f = tmp_path / "stats.txt"
        f.write_text("/path/game.exe hash 0 platform build\n")
        result = parse_playtime_file(str(f))
        assert result["/path/game.exe"] == 0


# ── get_playtime_for_exe ─────────────────────────────────────────────────────

class TestGetPlaytimeFor_exe:
    def test_sha_match(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"fake exe content")
        import hashlib
        sha = hashlib.sha256(b"fake exe content").hexdigest()

        stats = tmp_path / "stats.txt"
        stats.write_text(f"/other/game.exe {sha} 5400 platform build L5-1\n")

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result == 5400

    def test_exact_path_match(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"\x00" * 100)

        stats = tmp_path / "stats.txt"
        stats.write_text(f"{exe} abc123 3600 platform build\n")

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result == 3600

    def test_fallback_name_match(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"\x00" * 100)

        stats = tmp_path / "stats.txt"
        stats.write_text("/other/path/game.exe abc123 7200 platform build\n")

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result == 7200

    def test_no_match(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"\x00" * 100)

        stats = tmp_path / "stats.txt"
        stats.write_text("/other/other.exe abc123 3600 platform build\n")

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result is None

    def test_l5_index_highest_wins(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"\x00" * 100)

        stats = tmp_path / "stats.txt"
        stats.write_text(
            "/other/path/game.exe abc123 1000 platform build L5-1\n"
            "/other/path/game.exe abc123 3000 platform build L5-3\n"
            "/other/path/game.exe abc123 2000 platform build L5-2\n"
        )

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result == 3000

    def test_no_exe_path_returns_none(self, tmp_path):
        stats = tmp_path / "stats.txt"
        stats.write_text("/path/game.exe abc123 3600 p b\n")
        assert get_playtime_for_exe(str(stats), "") is None

    def test_no_stats_file_returns_none(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"\x00")
        assert get_playtime_for_exe("/nonexistent/stats.txt", str(exe)) is None

    def test_space_encoded_path(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"\x00" * 100)

        stats = tmp_path / "stats.txt"
        encoded = str(exe).replace(" ", "#@_@#")
        stats.write_text(f"{encoded} abc123 1800 platform build\n")

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result == 1800

    def test_sha_preferred_over_exact(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"specific content")
        import hashlib
        sha = hashlib.sha256(b"specific content").hexdigest()

        stats = tmp_path / "stats.txt"
        stats.write_text(
            f"/other/path/game.exe abc123 9999 platform build L5-1\n"
            f"{exe} {sha} 1111 platform build L5-1\n"
        )

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result == 1111


# ── format_playtime ──────────────────────────────────────────────────────────

class TestFormatPlaytime:
    def test_zero_seconds_detailed(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.ui_config",
            type("obj", (), {"get_time_detail_level": lambda self: "detailed"})(),
        )
        result = format_playtime(0)
        assert "sec" in result or "0" in result

    def test_one_hour_detailed(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.ui_config",
            type("obj", (), {"get_time_detail_level": lambda self: "detailed"})(),
        )
        result = format_playtime(3600)
        assert "1" in result

    def test_one_day_detailed(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.ui_config",
            type("obj", (), {"get_time_detail_level": lambda self: "detailed"})(),
        )
        result = format_playtime(86400)
        assert "1" in result

    def test_brief_under_hour(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.ui_config",
            type("obj", (), {"get_time_detail_level": lambda self: "brief"})(),
        )
        result = format_playtime(330)
        assert "5" in result

    def test_brief_over_hour(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.ui_config",
            type("obj", (), {"get_time_detail_level": lambda self: "brief"})(),
        )
        result = format_playtime(7200)
        assert "2" in result

    def test_float_seconds_truncated(self, monkeypatch):
        monkeypatch.setattr(
            "portprotonqt.time_utils.ui_config",
            type("obj", (), {"get_time_detail_level": lambda self: "detailed"})(),
        )
        result = format_playtime(90.7)
        assert "1" in result
        assert "30" in result


# ── Regression: spaced exe names ────────────────────────────────────────────

class TestSpacedExeRegression:
    def test_save_and_read_spaced_name(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "PortProtonQt" / "last_launch"
        monkeypatch.setattr(
            "portprotonqt.time_utils.get_cache_file_path",
            lambda: str(cache_file),
        )
        names = [
            "game.exe",
            "my game.exe",
            "C:\\Program Files\\Game\\game.exe",
            "/home/user/My Games/game.exe",
        ]
        now = datetime(2026, 6, 15, 12, 0, 0)
        for name in names:
            save_last_launch(name, now)

        with open(str(cache_file)) as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == len(names)

        for name in names:
            result = get_last_launch_timestamp(name)
            assert result > 0, f"Failed for: {name}"


# ── Regression: L5- index tracking ──────────────────────────────────────────

class TestL5IndexRegression:
    def test_highest_l5_index_wins(self, tmp_path):
        exe = tmp_path / "game.exe"
        exe.write_bytes(b"\x00" * 100)

        stats = tmp_path / "stats.txt"
        lines = []
        for i in range(1, 6):
            lines.append(f"/path/game.exe sha{i:060d} {i * 1000} p b L5-{i}\n")
        stats.write_text("".join(lines))

        result = get_playtime_for_exe(str(stats), str(exe))
        assert result == 5000
