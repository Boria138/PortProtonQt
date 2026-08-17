"""Tests for AppImage self-update support."""
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from portprotonqt.config.ui import UIConfig
from portprotonqt import appimage_updater
from portprotonqt.dialogs.appimage_update import AppImageUpdateDialog

FAKE_UPDATE_MARKER = "FAKE_UPDATE_APPLIED"


def test_update_dialog_done_disables_input_mode() -> None:
    app = QApplication.instance() or QApplication([])
    parent: Any = QWidget()
    disabled: list[bool] = []
    parent.input_manager = type(
        "InputManagerStub",
        (),
        {
            "enable_appimage_update_mode": lambda _self, _dialog: None,
            "disable_appimage_update_mode": lambda _self: disabled.append(True),
        },
    )()
    dialog = AppImageUpdateDialog(parent=parent)

    dialog.done(AppImageUpdateDialog.LATER)

    assert disabled == [True]
    assert dialog.result() == AppImageUpdateDialog.LATER
    assert app is not None


def test_auto_appimage_updates_config_roundtrip(tmp_path: Path) -> None:
    config = UIConfig(config_file=tmp_path / "PortProtonQt.conf")

    assert config.get_auto_appimage_updates() is True
    config.set_auto_appimage_updates(False)

    assert config.get_auto_appimage_updates() is False


def test_extract_latest_version_changelog_skips_unreleased() -> None:
    changelog = (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "- Future change\n\n"
        "## [1.2.0] - 2026-06-10\n\n"
        "- New release change\n\n"
        "## [1.1.0] - 2026-05-01\n\n"
        "- Old release change\n"
    )

    section = appimage_updater._extract_latest_version_changelog(changelog)

    assert "## [1.2.0] - 2026-06-10" in section
    assert "New release change" in section
    assert "Future change" not in section
    assert "Old release change" in section


def test_extract_changelog_from_current_version() -> None:
    changelog = (
        "## [Unreleased]\n\n"
        "- Future change\n\n"
        "## [1.3.0] - 2026-07-01\n\n"
        "- Latest change\n\n"
        "## [1.2.0] - 2026-06-10\n\n"
        "- Middle change\n\n"
        "## [1.1.0] - 2026-05-01\n\n"
        "- Old change\n"
    )

    section = appimage_updater._extract_latest_version_changelog(changelog, "1.1.0")

    assert "Latest change" in section
    assert "Middle change" in section
    assert "Old change" not in section
    assert "Future change" not in section


def test_parse_appimage_update_progress_line() -> None:
    line = "PortProtonQt.AppImage [bar]  42% \u2193 54.0 MB/128.0 MB"

    progress = appimage_updater._parse_progress(line)

    assert progress == (42, "42% \u2193 54.0 MB/128.0 MB")


def test_appimage_update_worker_skips_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appimage = tmp_path / "PortProtonQt.AppImage"
    appimage.write_text("", encoding="utf-8")
    monkeypatch.setenv("APPIMAGE", str(appimage))
    monkeypatch.setattr(
        appimage_updater.ui_config,
        "get_auto_appimage_updates",
        lambda: False,
    )
    monkeypatch.setattr(
        appimage_updater,
        "_ensure_appimageupdatetool",
        lambda: (_ for _ in ()).throw(AssertionError("tool should not start")),
    )

    appimage_updater.AppImageUpdateWorker().run()


def test_appimage_update_worker_runs_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appimage = tmp_path / "PortProtonQt.AppImage"
    appimage.write_text("", encoding="utf-8")
    monkeypatch.setenv("APPIMAGE", str(appimage))
    monkeypatch.setattr(
        appimage_updater.ui_config,
        "get_auto_appimage_updates",
        lambda: True,
    )
    monkeypatch.setattr(appimage_updater, "_ensure_appimageupdatetool", lambda: "/tool")

    calls: list[tuple[list[str], int]] = []

    def run_tool(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        calls.append((args, timeout))
        return subprocess.CompletedProcess(args, 1 if args[1] == "-j" else 0)

    monkeypatch.setattr(appimage_updater, "_run_appimageupdatetool", run_tool)
    monkeypatch.setattr(
        appimage_updater.AppImageUpdateWorker,
        "_get_changelog",
        lambda _self: "Repo changelog",
    )

    available: list[tuple[str, str]] = []
    worker = appimage_updater.AppImageUpdateWorker()
    worker.update_available.connect(
        lambda changelog, update_info: available.append((changelog, update_info))
    )
    worker.run()

    assert calls == [
        (["/tool", "-j", str(appimage)], appimage_updater.APPIMAGE_UPDATE_CHECK_TIMEOUT),
    ]
    assert available == [("Repo changelog", "")]


def test_appimage_update_worker_uses_fallback_mirror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appimage = tmp_path / "PortProtonQt.AppImage"
    appimage.write_text("", encoding="utf-8")
    monkeypatch.setenv("APPIMAGE", str(appimage))
    monkeypatch.setattr(
        appimage_updater.ui_config,
        "get_auto_appimage_updates",
        lambda: True,
    )
    monkeypatch.setattr(appimage_updater, "_ensure_appimageupdatetool", lambda: "/tool")

    calls: list[list[str]] = []

    def run_tool(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if "-u" not in args:
            return subprocess.CompletedProcess(args, 0, stderr=" Error: primary failed")
        return subprocess.CompletedProcess(args, 1)

    monkeypatch.setattr(appimage_updater, "_run_appimageupdatetool", run_tool)
    monkeypatch.setattr(
        appimage_updater.AppImageUpdateWorker,
        "_get_changelog",
        lambda _self: "Repo changelog",
    )

    available: list[tuple[str, str]] = []
    worker = appimage_updater.AppImageUpdateWorker()
    worker.update_available.connect(
        lambda changelog, update_info: available.append((changelog, update_info))
    )
    worker.run()

    assert calls == [
        ["/tool", "-j", str(appimage)],
        [
            "/tool",
            "-j",
            "-u",
            appimage_updater.FALLBACK_UPDATE_INFO,
            str(appimage),
        ],
    ]
    assert available == [("Repo changelog", appimage_updater.FALLBACK_UPDATE_INFO)]


def test_appimage_update_worker_emits_pty_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appimage = tmp_path / "PortProtonQt.AppImage"
    appimage.write_text("old version\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_path = bin_dir / "appimageupdatetool"
    tool_path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-Or\" ]; then\n"
        "  printf 'PortProtonQt.AppImage [bar]  25%% \\342\\206\\223 32.0 MB/128.0 MB\\r'\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
        encoding="utf-8",
    )
    tool_path.chmod(0o755)
    monkeypatch.setenv("APPIMAGE", str(appimage))
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(
        appimage_updater.ui_config,
        "get_auto_appimage_updates",
        lambda: True,
    )

    progress_values: list[tuple[int, str]] = []
    worker = appimage_updater.AppImageUpdateWorker("update")
    worker.update_progress.connect(
        lambda percent, message: progress_values.append((percent, message))
    )
    worker.run()

    assert progress_values == [(25, "25% \u2193 32.0 MB/128.0 MB")]


def test_appimage_update_worker_applies_fake_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appimage = tmp_path / "PortProtonQt.AppImage"
    appimage.write_text("old version\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_path = bin_dir / "appimageupdatetool"
    tool_path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-j\" ]; then\n"
        "  exit 1\n"
        "fi\n"
        "if [ \"$1\" = \"-Or\" ]; then\n"
        f"  printf '%s\\n' '{FAKE_UPDATE_MARKER}' >> \"$2\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
        encoding="utf-8",
    )
    tool_path.chmod(0o755)
    monkeypatch.setenv("APPIMAGE", str(appimage))
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(
        appimage_updater.ui_config,
        "get_auto_appimage_updates",
        lambda: True,
    )

    appimage_updater.AppImageUpdateWorker("update").run()

    assert FAKE_UPDATE_MARKER in appimage.read_text(encoding="utf-8")
