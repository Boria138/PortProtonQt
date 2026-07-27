from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch

from portprotonqt import compatibility_report as compatibility
from portprotonqt.scripts_utils.graphics_detector import resolve_graphics_executable


class FakePE:
    FILE_HEADER = SimpleNamespace(Machine=compatibility.PE_MACHINE_AMD64)
    DIRECTORY_ENTRY_IMPORT = [
        SimpleNamespace(dll=b"d3d11.dll"),
        SimpleNamespace(dll=b"vcruntime140.dll"),
    ]
    DIRECTORY_ENTRY_DELAY_IMPORT: list[object] = []

    def parse_data_directories(self, directories: list[int]) -> None:
        assert directories


def test_suspected_crash_requires_existing_windows_executable(tmp_path: Path) -> None:
    executable = tmp_path / "game.exe"
    executable.touch()

    assert compatibility.is_suspected_crash(1.0, False, str(executable)) is True
    assert compatibility.is_suspected_crash(1.0, True, str(executable)) is False
    assert compatibility.is_suspected_crash(6.0, False, str(executable)) is False


def test_always_report_environment_bypasses_duration(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    executable = tmp_path / "game.exe"
    executable.touch()
    monkeypatch.setenv(compatibility.COMPATIBILITY_ALWAYS_REPORT_ENV, "1")

    assert compatibility.is_suspected_crash(3600.0, False, str(executable)) is True
    assert compatibility.is_suspected_crash(3600.0, True, str(executable)) is True


def test_analyze_launch_reports_graphics_runtime_and_context(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    executable = tmp_path / "game.exe"
    executable.touch()
    monkeypatch.setattr(compatibility.pefile, "PE", lambda *_args, **_kwargs: FakePE())
    monkeypatch.setattr(compatibility, "get_portproton_env", lambda _path: {"PW_WINDOWS_VER": "10"})
    monkeypatch.setattr(compatibility, "get_prefix_name", lambda _path: "GAME")
    monkeypatch.setattr(compatibility, "get_wine_version", lambda *_args: "Proton-GE")
    monkeypatch.setattr(compatibility, "get_vulkan_use_info", lambda *_args: "DXVK")
    monkeypatch.setattr(
        compatibility,
        "analyze_executable",
        lambda _path: {"highest_directx": "DirectX 11", "uses_opengl": False},
    )

    report = compatibility.analyze_launch(
        compatibility.CompatibilityLaunch(str(executable), 1, 1.25),
        str(tmp_path),
    )

    assert "Exit code: 1" in report
    assert "Architecture: 64-bit" in report
    assert "Prefix: GAME" in report
    assert "Configured 3D API: DXVK" in report
    assert "Detected 3D API: DirectX 11" in report
    assert "Detected Runtimes: Visual C++ 2015-2022" in report


def test_analyze_launch_detects_engine_and_dotnet_markers(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    executable = tmp_path / "game.exe"
    executable.touch()
    (tmp_path / "game_Data").mkdir()
    (tmp_path / "game.runtimeconfig.json").touch()
    monkeypatch.setattr(compatibility.pefile, "PE", lambda *_args, **_kwargs: FakePE())
    monkeypatch.setattr(compatibility, "get_portproton_env", lambda _path: {})
    monkeypatch.setattr(compatibility, "get_prefix_name", lambda _path: "DEFAULT")
    monkeypatch.setattr(compatibility, "get_wine_version", lambda *_args: "Wine")
    monkeypatch.setattr(compatibility, "get_vulkan_use_info", lambda *_args: "DXVK")
    monkeypatch.setattr(
        compatibility,
        "analyze_executable",
        lambda _path: {"highest_directx": "None", "uses_opengl": False},
    )

    report = compatibility.analyze_launch(
        compatibility.CompatibilityLaunch(str(executable), 0, 2.0),
        str(tmp_path),
    )

    assert "Detected Engines: Unity" in report
    assert ".NET Core/5+" in report


def test_json_database_contains_all_bottles_rules() -> None:
    rules = compatibility._load_rules()

    assert len(rules) == 67
    assert {rule["id"] for rule in rules} >= {
        "Unity_Mono",
        "WPF_Framework",
        "SafeDisc_DRM",
        "Node_Kernel_Driver",
        "Stealer_Browser_Credential_Exfil",
    }


def test_json_scanner_preserves_grouped_security_conditions(tmp_path: Path) -> None:
    executable = tmp_path / "suspicious.exe"
    executable.write_bytes(
        b"Login Data cookies.sqlite api.telegram.org/bot"
    )

    findings = compatibility._scan_file(
        str(executable), compatibility._load_rules(), "Main executable"
    )

    assert any(item["name"] == "Browser credential stealer" for item in findings)


def test_json_scanner_does_not_match_partial_security_rule(tmp_path: Path) -> None:
    executable = tmp_path / "clean.exe"
    executable.write_bytes(b"Login Data api.telegram.org/bot")

    findings = compatibility._scan_file(
        str(executable), compatibility._load_rules(), "Main executable"
    )

    assert not any(item["name"] == "Browser credential stealer" for item in findings)


def test_integrated_gpu_recommendation_uses_selected_device(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compatibility,
        "get_selectable_gpu_entries",
        lambda: [
            {"device_name": "Discrete", "device_type": "DISCRETE_GPU"},
            {"device_name": "Integrated", "device_type": "INTEGRATED_GPU"},
        ],
    )

    assert compatibility._uses_integrated_gpu({"PW_GPU_USE": "Integrated"}) is True
    assert compatibility._uses_integrated_gpu({"PW_GPU_USE": "Discrete"}) is False
    assert compatibility._uses_integrated_gpu({"PW_GPU_USE": "disabled"}) is False


def test_suggestions_omit_gamemode_and_discrete_gpu_when_not_integrated() -> None:
    suggestions = compatibility._compatibility_suggestions(
        {"Engines": ["Ren'Py"]}, "None", "", {"PW_GPU_USE": "disabled"}
    )

    assert "Enable GameMode." not in suggestions
    assert "Use the discrete GPU." not in suggestions
    assert "Try Esync." not in suggestions


def test_dotnet_suggestion_uses_dedicated_prefix() -> None:
    default_suggestions = compatibility._compatibility_suggestions(
        {"Runtimes": [".NET Framework"]},
        "None",
        "",
        {"PW_PREFIX_NAME": "DEFAULT"},
    )
    dotnet_suggestions = compatibility._compatibility_suggestions(
        {"Runtimes": [".NET Framework"]},
        "None",
        "",
        {"PW_PREFIX_NAME": "DOTNET"},
    )

    assert "Use the DOTNET prefix." in default_suggestions
    assert "Install the detected .NET runtime in this prefix." not in default_suggestions
    assert "Use the DOTNET prefix." not in dotnet_suggestions


def test_directx_12_does_not_suggest_enabling_vkd3d() -> None:
    suggestions = compatibility._compatibility_suggestions(
        {"Engines": ["Unreal"]},
        "DirectX 12",
        "",
        {"PW_GPU_USE": "disabled"},
    )

    assert "Enable VKD3D-Proton for DirectX 12." not in suggestions


def test_analyze_launch_uses_unreal_shipping_executable_for_graphics(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    launcher = tmp_path / "game.exe"
    shipping = tmp_path / "game-Win64-Shipping.exe"
    launcher.touch()
    shipping.touch()
    analyzed_paths = []
    monkeypatch.setattr(compatibility.pefile, "PE", lambda *_args, **_kwargs: FakePE())
    monkeypatch.setattr(compatibility, "get_portproton_env", lambda _path: {})
    monkeypatch.setattr(compatibility, "get_prefix_name", lambda _path: "DEFAULT")
    monkeypatch.setattr(compatibility, "get_wine_version", lambda *_args: "Wine")
    monkeypatch.setattr(compatibility, "get_vulkan_use_info", lambda *_args: "VKD3D")

    def analyze_graphics(path: str) -> dict[str, object]:
        analyzed_paths.append(path)
        return {
            "highest_directx": "DirectX 12",
            "uses_opengl": False,
            "source": str(shipping),
        }

    monkeypatch.setattr(compatibility, "analyze_executable", analyze_graphics)

    report = compatibility.analyze_launch(
        compatibility.CompatibilityLaunch(str(launcher), 1, 1.0),
        str(tmp_path),
    )

    assert analyzed_paths == [str(launcher)]
    assert "Detected 3D API: DirectX 12" in report
    assert f"3D API source: {shipping}" in report


def test_find_graphics_executable_uses_renpy_runtime(tmp_path: Path) -> None:
    launcher = tmp_path / "game.exe"
    runtime = tmp_path / "lib/py3-windows-x86_64/librenpython.dll"
    launcher.touch()
    runtime.parent.mkdir(parents=True)
    runtime.touch()

    (tmp_path / "renpy").mkdir()
    result = resolve_graphics_executable(str(launcher))

    assert result == runtime


def test_resolve_graphics_executable_uses_unreal_shipping_binary(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "game.exe"
    shipping = tmp_path / "Game/Binaries/Win64/Game-Win64-Shipping.exe"
    launcher.touch()
    shipping.parent.mkdir(parents=True)
    shipping.touch()

    result = resolve_graphics_executable(str(launcher))

    assert result == shipping


def test_dxvk_suggestion_only_appears_for_wined3d() -> None:
    active_dxvk = compatibility._compatibility_suggestions(
        {}, "DirectX 11", "", {"PW_VULKAN_USE": "6"}
    )
    wined3d = compatibility._compatibility_suggestions(
        {}, "DirectX 11", "", {"PW_VULKAN_USE": "0"}
    )

    assert not any("DXVK" in suggestion for suggestion in active_dxvk)
    assert "Switch from WineD3D to DXVK for DirectX 8-11." in wined3d


def test_runtime_suggestions_use_portproton_components() -> None:
    findings = {
        "Runtimes": ["Mono", "Visual C++ 2015-2022"],
        "Physics": ["PhysX"],
    }
    suggestions = compatibility._compatibility_suggestions(
        findings,
        "None",
        "",
        {"PW_PREFIX_NAME": "DEFAULT", "PW_WINETRICKS_LOG": ""},
    )
    installed = compatibility._compatibility_suggestions(
        findings,
        "None",
        "",
        {"PW_PREFIX_NAME": "DEFAULT", "PW_WINETRICKS_LOG": "vcrun2022\nphysx"},
    )

    assert "Install vcrun2022 through Winetricks." in suggestions
    assert "Install physx through Winetricks." in suggestions
    assert not any("Mono" in suggestion for suggestion in suggestions)
    assert not any("vcrun" in suggestion or "physx" in suggestion for suggestion in installed)


def test_wpf_uses_dotnet_prefix_without_generic_wine_advice() -> None:
    suggestions = compatibility._compatibility_suggestions(
        {"Frameworks": ["WPF"]},
        "None",
        "",
        {"PW_PREFIX_NAME": "DEFAULT", "PW_WINETRICKS_LOG": ""},
    )

    assert suggestions == ["Use the DOTNET prefix."]


def test_non_actionable_findings_do_not_create_fixes() -> None:
    suggestions = compatibility._compatibility_suggestions(
        {
            "Warning": ["UWP/Modern API"],
            "Protection": ["Denuvo"],
            "Packers": ["UPX"],
            "Upscaling": ["Upscaling Technology"],
        },
        "None",
        "",
        {"PW_PREFIX_NAME": "DEFAULT", "PW_WINETRICKS_LOG": ""},
    )

    assert suggestions == []
