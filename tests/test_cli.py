"""Tests for cli.py — URL parsing, path normalization, file detection, resolution parsing."""
import os
from pathlib import Path

from portprotonqt.cli import (
    normalize_launch_path,
    is_launch_file,
    is_prefix_backup_file,
    parse_portproton_url,
    parse_resolution,
    LAUNCH_FILE_EXTENSIONS,
    PREFIX_BACKUP_EXTENSION,
)


class TestNormalizeLaunchPath:
    def test_plain_path(self):
        assert normalize_launch_path("/tmp/game.exe") == "/tmp/game.exe"

    def test_expanduser(self):
        result = normalize_launch_path("~/game.exe")
        assert result.startswith(os.path.expanduser("~"))
        assert result.endswith("game.exe")

    def test_file_uri(self):
        result = normalize_launch_path("file:///tmp/game.exe")
        assert result == "/tmp/game.exe"

    def test_file_uri_with_spaces(self):
        result = normalize_launch_path("file:///tmp/my%20game.exe")
        assert result == "/tmp/my game.exe"

    def test_file_uri_with_tilde(self):
        result = normalize_launch_path("file:///~/game.exe")
        assert result == "/~/game.exe"

    def test_relative_path_becomes_absolute(self):
        result = normalize_launch_path("game.exe")
        assert os.path.isabs(result)


class TestIsLaunchFile:
    def test_exe_file(self, tmp_path: Path):
        exe = tmp_path / "game.exe"
        exe.touch()
        assert is_launch_file(str(exe)) is True

    def test_bat_file(self, tmp_path: Path):
        bat = tmp_path / "setup.bat"
        bat.touch()
        assert is_launch_file(str(bat)) is True

    def test_cmd_file(self, tmp_path: Path):
        cmd = tmp_path / "launch.cmd"
        cmd.touch()
        assert is_launch_file(str(cmd)) is True

    def test_msi_file(self, tmp_path: Path):
        msi = tmp_path / "installer.msi"
        msi.touch()
        assert is_launch_file(str(msi)) is True

    def test_iso_file(self, tmp_path: Path):
        iso = tmp_path / "game.iso"
        iso.touch()
        assert is_launch_file(str(iso)) is True

    def test_not_launch_file(self, tmp_path: Path):
        txt = tmp_path / "readme.txt"
        txt.touch()
        assert is_launch_file(str(txt)) is False

    def test_nonexistent_file(self):
        assert is_launch_file("/nonexistent/game.exe") is False

    def test_launch_file_extensions_complete(self):
        assert ".exe" in LAUNCH_FILE_EXTENSIONS
        assert ".bat" in LAUNCH_FILE_EXTENSIONS
        assert ".cmd" in LAUNCH_FILE_EXTENSIONS
        assert ".msi" in LAUNCH_FILE_EXTENSIONS
        assert ".reg" in LAUNCH_FILE_EXTENSIONS
        assert ".iso" in LAUNCH_FILE_EXTENSIONS
        assert ".mdf" in LAUNCH_FILE_EXTENSIONS
        assert ".nrg" in LAUNCH_FILE_EXTENSIONS


class TestIsPrefixBackupFile:
    def test_ppack_file(self, tmp_path: Path):
        ppack = tmp_path / "backup.ppack"
        ppack.touch()
        assert is_prefix_backup_file(str(ppack)) is True

    def test_not_ppack(self, tmp_path: Path):
        txt = tmp_path / "backup.zip"
        txt.touch()
        assert is_prefix_backup_file(str(txt)) is False

    def test_nonexistent_file(self):
        assert is_prefix_backup_file("/nonexistent/backup.ppack") is False

    def test_ppack_extension_constant(self):
        assert PREFIX_BACKUP_EXTENSION == ".ppack"


class TestParsePortprotonUrl:
    def test_https_url(self):
        url = "portproton://https//ppdb.linux-gaming.ru/api/games/130127/ppdb/download"
        result = parse_portproton_url(url)
        assert result == "https://ppdb.linux-gaming.ru/api/games/130127/ppdb/download"

    def test_http_url(self):
        url = "portproton://http//example.com/download"
        result = parse_portproton_url(url)
        assert result == "http://example.com/download"

    def test_bare_url_without_protocol(self):
        url = "portproton://example.com/game"
        result = parse_portproton_url(url)
        assert result == "https://example.com/game"

    def test_url_with_existing_protocol(self):
        url = "portproton://https://example.com/game"
        result = parse_portproton_url(url)
        assert result == "https://example.com/game"

    def test_invalid_prefix(self):
        assert parse_portproton_url("http://example.com") is None

    def test_empty_string(self):
        assert parse_portproton_url("") is None


class TestParseResolution:
    def test_standard_1080p(self):
        assert parse_resolution("1920x1080") == (1920, 1080)

    def test_standard_4k(self):
        assert parse_resolution("3840x2160") == (3840, 2160)

    def test_case_insensitive(self):
        assert parse_resolution("1920X1080") == (1920, 1080)

    def test_invalid_format(self):
        assert parse_resolution("1920") is None

    def test_invalid_letters(self):
        assert parse_resolution("abcxdef") is None

    def test_too_small_width(self):
        assert parse_resolution("100x1080") is None

    def test_too_small_height(self):
        assert parse_resolution("1920x100") is None

    def test_too_large_width(self):
        assert parse_resolution("9999x1080") is None

    def test_too_large_height(self):
        assert parse_resolution("1920x9999") is None

    def test_min_valid(self):
        assert parse_resolution("320x200") == (320, 200)

    def test_max_valid(self):
        assert parse_resolution("7680x4320") == (7680, 4320)

    def test_empty_string(self):
        assert parse_resolution("") is None
