"""Windows Steam client preparation for PortProton prefixes."""

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from portprotonqt.config.portproton import get_portproton_location, get_portproton_start_command
from portprotonqt.downloader import download_with_cache
from portprotonqt.logger import get_logger
from portprotonqt.steam_api.utils import get_steam_home, get_steam_libs, safe_vdf_load

logger = get_logger(__name__)
ProgressCallback = Callable[[float], None]

WINDOWS_STEAM_DIR = Path("drive_c") / "Program Files (x86)" / "Steam"
WINDOWS_STEAM_EXE = WINDOWS_STEAM_DIR / "steam.exe"
STEAM_LAUNCHER_PREFIX = "portprotonqt_steam_"
STEAM_AUTOINSTALL_URL = "https://ppdb.linux-gaming.ru/static/autoinstall/scripts/138933_Лаунчер_Steam.ppai"
STEAM_CLIENT_CDN_URL = "https://client-update.steamstatic.com"
STEAM_CLIENT_MANIFEST = "steam_client_win64"
STEAM_STEALTH_FLAGS = (
    "-silent -no-browser -noreactlogin -no-dwrite -no-cef-sandbox"
    " -nofriendsui -nobigpicture -noshaders -novid"
    " -noverifyfiles -nointro -skipstreamingdrivers -norepairfiles"
    " -nohltv -nofasthtml -nocrashmonitor -no-shared-textures"
    " -disablehighdpi -cef-single-process -cef-in-process-gpu -single_core"
    " -cef-disable-d3d11 -cef-disable-sandbox -disable-winh264 -vrdisable"
    " -cef-disable-breakpad -cef-disable-gpu -cef-disable-hang-timeouts"
    " -cef-disable-seccomp-sandbox -cef-disable-extensions"
    " -cef-disable-remote-fonts -cef-enable-media-stream"
    " -cef-disable-accelerated-video-decode -cef-disable-gpu-compositing"
)


@dataclass(frozen=True)
class NativeSteamApp:
    appid: str
    name: str
    install_dir: str
    install_path: Path
    manifest_path: Path


def get_windows_steam_prefix(appid: str) -> Path | None:
    """Return the prefix selected in the game's generated settings."""
    if not appid.isdigit():
        return None
    portproton_path = get_portproton_location()
    if portproton_path is None:
        return None

    launcher_path = Path(portproton_path) / "steam_scripts" / f"{STEAM_LAUNCHER_PREFIX}{appid}.bat"
    ppdb_path = launcher_path.with_name(launcher_path.name + ".ppdb")
    if not ppdb_path.is_file():
        return None
    settings = ppdb_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'^export PW_PREFIX_NAME="([^"]+)"', settings, re.MULTILINE)
    if match is None:
        return None
    prefix_dir = Path(portproton_path) / "data" / "prefixes" / match.group(1)
    if prefix_dir.joinpath(WINDOWS_STEAM_EXE).is_file():
        return prefix_dir
    return None


def _download_file(
    url: str,
    target_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    """Download file using project downloader with caching."""
    result = download_with_cache(
        url,
        str(target_path),
        timeout=30,
        progress_callback=progress_callback,
    )
    return result is not None


def _download_steam_seed(
    steam_dir: Path,
    progress_callback: ProgressCallback | None = None,
) -> bool:
    """Download and extract all official Windows Steam client packages."""
    package_dir = steam_dir / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = package_dir / f"{STEAM_CLIENT_MANIFEST}.manifest"
    quiet_progress = (lambda _current, _total: None) if progress_callback else None
    if not _download_file(
        f"{STEAM_CLIENT_CDN_URL}/{STEAM_CLIENT_MANIFEST}",
        manifest_path,
        quiet_progress,
    ):
        return False

    manifest = manifest_path.read_text(encoding="utf-8", errors="ignore")
    packages = _get_manifest_packages(manifest)
    if not any(name.startswith("steam_win64.zip.") for name, _size in packages):
        logger.warning("Windows Steam bootstrap package is missing from the manifest")
        return False

    downloaded = 0
    total_size = sum(size for _name, size in packages)
    for package_name, package_size in packages:
        report = _package_progress(progress_callback, downloaded, total_size)
        if not _download_steam_package(package_dir, steam_dir, package_name, report):
            return False
        downloaded += package_size
        if progress_callback and total_size:
            progress_callback(downloaded * 100 / total_size)
    shutil.copy2(manifest_path, package_dir / f"{STEAM_CLIENT_MANIFEST}.installed")
    return steam_dir.joinpath("steam.exe").is_file() and steam_dir.joinpath("SteamUI.dll").is_file()


def _get_manifest_packages(manifest: str) -> list[tuple[str, int]]:
    matches = re.findall(
        r'"file"\s+"([^"\s]+\.zip\.[0-9a-f]+)"\s+"size"\s+"([0-9]+)"',
        manifest,
    )
    packages = {}
    for name, size in matches:
        if "_steamchina.zip." not in name and "_steamrow.zip." not in name:
            packages.setdefault(name, int(size))
    return list(packages.items())


def _package_progress(
    callback: ProgressCallback | None,
    downloaded: int,
    total_size: int,
) -> Callable[[int, int], None] | None:
    if callback is None or not total_size:
        return None
    return lambda current, _size: callback((downloaded + current) * 100 / total_size)


def _download_steam_package(
    package_dir: Path,
    steam_dir: Path,
    name: str,
    progress_callback: Callable[[int, int], None] | None,
) -> bool:
    archive_path = package_dir / name
    if not _download_file(f"{STEAM_CLIENT_CDN_URL}/{name}", archive_path, progress_callback):
        return False
    try:
        shutil.unpack_archive(archive_path, steam_dir, format="zip")
    except (OSError, shutil.ReadError) as e:
        logger.warning("Failed to extract Windows Steam package %s: %s", name, e)
        return False
    return True


def _get_shared_steam_dir(progress_callback: ProgressCallback | None = None) -> Path | None:
    """Return the shared Steam directory, downloading the seed if needed."""
    portproton_path = get_portproton_location()
    if portproton_path is None:
        return None
    shared_dir = Path(portproton_path) / "data" / "tmp" / "steam"
    try:
        shared_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("Failed to create shared Steam directory: %s", e)
        return None
    installed = shared_dir / "package" / f"{STEAM_CLIENT_MANIFEST}.installed"
    if shared_dir.joinpath("SteamUI.dll").is_file() and installed.is_file():
        return shared_dir
    if _download_steam_seed(shared_dir, progress_callback):
        return shared_dir
    return None


def get_windows_steam_launch_commands(
    appid: str,
    progress_callback: ProgressCallback | None = None,
) -> list[list[str]]:
    """Return PortProton commands for Windows Steam app launch."""
    if not appid.isdigit():
        return []

    steam_home = get_steam_home()
    if steam_home is None:
        return []

    app = find_native_steam_app(steam_home, appid)
    if app is None:
        return []

    start_command = get_portproton_start_command()
    if not start_command:
        return []

    steam_dir = _get_shared_steam_dir(progress_callback)
    if steam_dir is None:
        return []

    _mirror_app_manifest(steam_dir, app)

    launcher_path = get_windows_steam_app_launcher(appid)
    if launcher_path is None:
        return []
    return [start_command + [str(launcher_path)]]


def get_windows_steam_app_launcher(appid: str) -> Path | None:
    """Return per-app Windows Steam launcher for editable ppdb settings."""
    if not appid.isdigit():
        return None

    launcher_dir = _get_steam_launcher_dir()
    if launcher_dir is None:
        return None

    launcher_path = _write_steam_launcher(launcher_dir, appid)
    return launcher_path


def _get_steam_launcher_dir() -> Path | None:
    portproton_path = get_portproton_location()
    if portproton_path is None:
        return None

    launcher_dir = Path(portproton_path) / "steam_scripts"
    try:
        launcher_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("Failed to create Steam launcher directory %s: %s", launcher_dir, e)
        return None
    return launcher_dir


def _write_steam_launcher(steam_dir: Path, appid: str) -> Path:
    launcher_path = steam_dir / f"{STEAM_LAUNCHER_PREFIX}{appid}.bat"
    game_exe = get_native_steam_app_executable(appid)
    game_exe_line = str(game_exe).replace("\r", "").replace("\n", "") if game_exe else ""
    launcher_path.write_text(
        "@echo off\r\n"
        f"rem PORTPROTON_GAME_EXE={game_exe_line}\r\n"
        "cd /d \"C:\\Program Files (x86)\\Steam\"\r\n"
        f"start \"\" \"steam.exe\" {STEAM_STEALTH_FLAGS} -applaunch {appid}\r\n",
        encoding="utf-8",
    )
    return launcher_path


def find_native_steam_app(steam_home: Path, appid: str) -> NativeSteamApp | None:
    """Return native Steam app install data."""
    for lib in get_steam_libs(steam_home):
        manifest_path = lib / "steamapps" / f"appmanifest_{appid}.acf"
        if not manifest_path.is_file():
            continue
        app_state = safe_vdf_load(manifest_path).get("AppState", {})
        install_dir = str(app_state.get("installdir", "")).strip()
        if not install_dir:
            return None
        install_path = lib / "steamapps" / "common" / install_dir
        if not install_path.exists():
            return None
        return NativeSteamApp(
            appid=appid,
            name=str(app_state.get("name", install_dir)),
            install_dir=install_dir,
            install_path=install_path,
            manifest_path=manifest_path,
        )
    return None


def get_native_steam_app_executable(appid: str) -> Path | None:
    """Return a likely Windows executable for a native Steam app."""
    steam_home = get_steam_home()
    if steam_home is None:
        return None

    app = find_native_steam_app(steam_home, appid)
    if app is None:
        return None

    return _find_best_game_executable(app)


def _find_best_game_executable(app: NativeSteamApp) -> Path | None:
    candidates = [
        path for path in app.install_path.rglob("*.exe")
        if _is_game_executable_candidate(path)
    ]
    if not candidates:
        return None

    name_tokens = _normalize_executable_name(app.name)
    install_tokens = _normalize_executable_name(app.install_dir)
    return sorted(
        candidates,
        key=lambda path: _score_executable(path, name_tokens, install_tokens),
        reverse=True,
    )[0]


def _is_game_executable_candidate(path: Path) -> bool:
    lower_name = path.name.lower()
    blocked_tokens = (
        "crash", "helper", "installer", "redist", "setup", "unins",
        "unitycrashhandler", "vcredist", "webview",
    )
    if any(token in lower_name for token in blocked_tokens):
        return False
    return "steamworks shared" not in str(path).lower()


def _normalize_executable_name(value: str) -> set[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in value)
    return {token for token in normalized.split() if len(token) > 2}


def _score_executable(
    path: Path,
    name_tokens: set[str],
    install_tokens: set[str],
) -> tuple[int, int]:
    stem_tokens = _normalize_executable_name(path.stem)
    score = len(stem_tokens & name_tokens) * 3 + len(stem_tokens & install_tokens) * 2
    if path.parent.name.lower() in ("bin", "binaries", "win64", "win32"):
        score += 1
    return score, -len(path.parts)


def _mirror_app_manifest(steam_dir: Path, app: NativeSteamApp) -> None:
    steamapps_dir = steam_dir / "steamapps"
    common_dir = steamapps_dir / "common"
    steamapps_dir.mkdir(parents=True, exist_ok=True)
    common_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(app.manifest_path, steamapps_dir / f"appmanifest_{app.appid}.acf")
    link_path = common_dir / app.install_dir
    if link_path.exists() or link_path.is_symlink():
        return
    try:
        os.symlink(app.install_path, link_path, target_is_directory=True)
    except OSError as e:
        logger.warning("Failed to link Steam app %s into Windows Steam: %s", app.appid, e)
