"""Tests for user-level AppImage integration."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from portprotonqt import appimage_integration


def test_integrate_appimage_installs_handlers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "Downloads" / "PortProtonQt.AppImage"
    appdir = tmp_path / "mount"
    source.parent.mkdir()
    appdir.mkdir()
    source.write_text("appimage", encoding="utf-8")
    (appdir / ".DirIcon").write_text("icon", encoding="utf-8")
    (appdir / f"{appimage_integration.APP_ID}.desktop").write_text(
        "[Desktop Entry]\n"
        "Name=PortProtonQt\n"
        "Exec=portprotonqt %u\n"
        "Type=Application\n"
        f"Icon={appimage_integration.APP_ID}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APPIMAGE", str(source))
    monkeypatch.setenv("APPDIR", str(appdir))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    desktop_dir = tmp_path / "Desktop"
    monkeypatch.setattr(
        appimage_integration.QStandardPaths,
        "writableLocation",
        lambda _location: str(desktop_dir),
    )
    stale_applications = tmp_path / "data" / "applications"
    stale_icons = tmp_path / "AppImages" / ".icons"
    stale_applications.mkdir(parents=True)
    stale_icons.mkdir(parents=True)
    (stale_applications / f"{appimage_integration.APP_ID}.log.desktop").write_text(
        "stale",
        encoding="utf-8",
    )
    stale_png = stale_icons / f"{appimage_integration.APP_ID}.png"
    stale_png.write_text("stale", encoding="utf-8")
    commands = []
    monkeypatch.setattr(
        appimage_integration.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(command),
    )

    destination = appimage_integration.integrate_appimage()

    assert destination == tmp_path / "AppImages" / "portprotonqt.appimage"
    assert destination.read_text(encoding="utf-8") == "appimage"
    assert not stale_png.exists()
    applications = tmp_path / "data" / "applications"
    main_entry = (
        applications / f"{appimage_integration.APP_ID}.desktop"
    ).read_text()
    assert str(destination) in main_entry
    assert "TryExec=" in main_entry
    desktop_entry = desktop_dir / f"{appimage_integration.APP_ID}.desktop"
    assert desktop_entry.read_text(encoding="utf-8") == main_entry
    assert desktop_entry.stat().st_mode & 0o111
    for mode in ("log", "silent"):
        entry = (
            applications / f"{appimage_integration.APP_ID}.{mode}.desktop"
        ).read_text()
        assert f"--{mode}" in entry
        assert "%u" in entry
        assert "NoDisplay=true" in entry
        assert "Name=PortProtonQt — " in entry
        assert "Comment=" in entry
        assert "StartupWMClass=ru.linux_gaming.PortProtonQt" in entry
        assert "StartupNotify=true" in entry
    mime_commands = [
        [
            "xdg-mime",
            "default",
            f"{appimage_integration.APP_ID}.desktop",
            mime_type,
        ]
        for mime_type in appimage_integration.WINDOWS_MIME_TYPES.rstrip(";").split(";")
    ]
    assert commands == mime_commands + [
        ["update-desktop-database", str(applications)]
    ]


def test_app_continues_startup_after_integrating_appimage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from portprotonqt import app

    integrated: list[bool] = []
    reinstalled: list[bool] = []
    monkeypatch.setenv("PORTPROTONQT_INTEGRATE_APPIMAGE", "1")
    monkeypatch.setattr(
        app,
        "parse_args",
        lambda: SimpleNamespace(
            debug_level="NOTSET",
            reinstall_steam_compat_tool=True,
        ),
    )
    monkeypatch.setattr(
        appimage_integration,
        "integrate_appimage",
        lambda: integrated.append(True),
    )
    monkeypatch.setattr(
        app,
        "reinstall_steam_compat_tool",
        lambda: reinstalled.append(True) or True,
    )

    with pytest.raises(SystemExit, match="0"):
        app.main()
    assert integrated == [True]
    assert reinstalled == [True]


def test_integrate_appimage_requires_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "PortProtonQt.AppImage"
    appdir = tmp_path / "mount"
    source.write_text("appimage", encoding="utf-8")
    appdir.mkdir()
    monkeypatch.setenv("APPIMAGE", str(source))
    monkeypatch.setenv("APPDIR", str(appdir))

    with pytest.raises(
        FileNotFoundError,
        match="AppImage desktop metadata is incomplete",
    ):
        appimage_integration.integrate_appimage()
