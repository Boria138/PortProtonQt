"""Tests for debug environment helpers."""

import subprocess
from typing import Any

from portprotonqt.debug_utils import env_utils
from portprotonqt.debug_utils import gpu_info


def test_get_cached_vk_gpu_info_uses_build_aux_binary(monkeypatch: Any) -> None:
    calls = []
    result = subprocess.CompletedProcess([], 0, stdout="GPU #0:\n", stderr="")

    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess:
        calls.append(command)
        return result

    monkeypatch.setattr(gpu_info.subprocess, "run", run)
    monkeypatch.setattr(gpu_info, "_vk_gpu_info_output", None)

    assert gpu_info.get_cached_vk_gpu_info() == "GPU #0:\n"
    assert calls[0][0].endswith("build-aux/bin/vk_gpu_info")


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


def test_parse_glxinfo_output_adds_primary_gpu_line() -> None:
    glxinfo_output = """name of display: :0
display: :0  screen: 0
direct rendering: Yes
OpenGL vendor string: NVIDIA Corporation
OpenGL renderer string: NVIDIA GeForce GTX 1060 3GB/PCIe/SSE2
OpenGL version string: 4.6.0 NVIDIA 580.142
"""
    vk_output = """GPU #0:
    device_name: Intel(R) UHD Graphics 630
    device_type: INTEGRATED_GPU
    driver_name: Intel open-source Mesa driver
    api_version: 1.3.289
    driver_version: 24.3.4

GPU #1:
    device_name: NVIDIA GeForce GTX 1060 3GB
    device_type: DISCRETE_GPU
    driver_name: NVIDIA
    api_version: 1.4.312
    driver_info: 580.142
"""

    assert gpu_info._format_glxinfo_gpu_line(glxinfo_output, vk_output) == (
        'export PW_GPU_INFO="NVIDIA GeForce GTX 1060 3GB"'
    )
