"""Tests for debug environment helpers."""

from typing import Any

from portprotonqt.debug_utils import env_utils


def test_get_runtime_status_enabled(monkeypatch: Any) -> None:
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    assert env_utils.get_runtime_status("", env_vars={"PW_USE_RUNTIME": "1"}) == (
        "RUNTIME is enabled"
    )


def test_get_runtime_status_disabled(monkeypatch: Any) -> None:
    monkeypatch.delenv("FLATPAK_ID", raising=False)

    assert env_utils.get_runtime_status("", env_vars={"PW_USE_RUNTIME": "0"}) == (
        "RUNTIME is disabled"
    )


def test_get_runtime_status_detects_flatpak(monkeypatch: Any) -> None:
    monkeypatch.setenv("FLATPAK_ID", "ru.linux_gaming.PortProtonQt")

    assert env_utils.get_runtime_status("", env_vars={"PW_USE_RUNTIME": "1"}) == (
        "FLATPAK in used"
    )


def test_get_vulkan_use_info_includes_d7vk(monkeypatch: Any) -> None:
    env_vars = {
        "PW_VULKAN_USE": "6",
        "DXVK_NEW_VER": "2.7.1-509",
        "VKD3D_NEW_VER": "1.1-5122",
        "PW_USE_D7VK": "1",
        "D7VK_VAR_VER": "v1.10",
    }

    monkeypatch.setattr(env_utils, "get_portproton_env", lambda _exe_path: env_vars)

    assert env_utils.get_vulkan_use_info("") == (
        "PW_VULKAN_USE=6 - DXVK v.2.7.1-509, "
        "VKD3D-PROTON v.1.1-5122, D7VK v1.10"
    )


def test_get_wine_version_resolves_lg_alias(monkeypatch: Any) -> None:
    env_vars = {
        "PW_WINE_USE": "PROTON_LG",
        "PW_PROTON_LG_VER": "PROTON_LG_10-30",
    }

    monkeypatch.setattr(env_utils, "get_portproton_env", lambda _exe_path: env_vars)

    assert env_utils.get_wine_version("") == "PROTON_LG_10-30"


def test_get_wine_version_normalizes_absolute_dist(monkeypatch: Any) -> None:
    env_vars = {
        "PW_WINE_USE": "/home/user/.local/share/PortProtonQt/data/dist/WINE LG 11-10",
    }

    monkeypatch.setattr(env_utils, "get_portproton_env", lambda _exe_path: env_vars)

    assert env_utils.get_wine_version("") == "WINE_LG_11-10"


def test_get_d3d_extras_status_enabled_by_default(monkeypatch: Any) -> None:
    monkeypatch.setattr(env_utils, "get_portproton_env", lambda _exe_path: {})

    assert env_utils.get_d3d_extras_status("") == "D3D_EXTRAS - enabled"


def test_get_d3d_extras_status_disabled(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        env_utils,
        "get_portproton_env",
        lambda _exe_path: {"PW_USE_D3D_EXTRAS": "0"},
    )

    assert env_utils.get_d3d_extras_status("") == "D3D_EXTRAS - disabled"
