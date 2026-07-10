"""AppImage self-update support."""
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from portprotonqt.downloader import get_requests_session
from portprotonqt.config import CACHE_DIR, ui_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

APPIMAGEUPDATETOOL_URL = (
    "https://github.com/pkgforge-dev/AppImageUpdate/releases/latest/download/"
    "appimageupdate-{arch}-linux"
)
APPIMAGEUPDATETOOL_TIMEOUT = 60
APPIMAGE_UPDATE_CHECK_TIMEOUT = 120
APPIMAGE_UPDATE_TIMEOUT = 900
APPIMAGE_UPDATE_START_DELAY_MS = 5000
EXECUTABLE_MODE = 0o755
FALLBACK_UPDATE_INFO = (
    "gh-releases-zsync|Boria138|PortProtonQt|latest|*x86_64.AppImage.zsync"
)
CHANGELOG_URL = (
    "https://git.linux-gaming.ru/Linux-Gaming/PortProtonQt/raw/branch/main/"
    "CHANGELOG.md"
)
CHANGELOG_TIMEOUT = 10
CHANGELOG_MAX_CHARS = 12000


def _appimage_path() -> str:
    return os.environ.get("APPIMAGE", "")


def _get_appimage_arch() -> str:
    return os.environ.get("APPIMAGE_ARCH") or platform.machine()


def _cached_tool_path() -> Path:
    return CACHE_DIR / "bin" / "appimageupdatetool"


def _get_appimageupdatetool_url() -> str:
    default_url = APPIMAGEUPDATETOOL_URL.format(arch=_get_appimage_arch())
    return os.environ.get("APPIMAGEUPDATETOOL_LINK", default_url)


def _find_appimageupdatetool() -> str | None:
    for tool_name in ("appimageupdatetool", "appimageupdate"):
        tool_path = shutil.which(tool_name)
        if tool_path:
            return tool_path

    cached_tool = _cached_tool_path()
    if cached_tool.exists() and os.access(cached_tool, os.X_OK):
        return str(cached_tool)
    return None


def _download_appimageupdatetool() -> str | None:
    tool_path = _cached_tool_path()
    tmp_path = tool_path.with_suffix(".part")
    try:
        tool_path.parent.mkdir(parents=True, exist_ok=True)
        session = get_requests_session()
        with session.get(
            _get_appimageupdatetool_url(),
            timeout=APPIMAGEUPDATETOOL_TIMEOUT,
        ) as response:
            response.raise_for_status()
            tmp_path.write_bytes(response.content)
        tmp_path.chmod(EXECUTABLE_MODE)
        tmp_path.replace(tool_path)
        return str(tool_path)
    except (OSError, requests.RequestException) as error:
        logger.warning("Failed to download appimageupdatetool: %s", error)
        return None
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _ensure_appimageupdatetool() -> str | None:
    return _find_appimageupdatetool() or _download_appimageupdatetool()


def _run_appimageupdatetool(
    args: list[str],
    timeout: int,
) -> subprocess.CompletedProcess[str] | None:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("Failed to run appimageupdatetool: %s", error)
        return None
    if result.stdout:
        logger.debug("appimageupdatetool stdout: %s", result.stdout.strip())
    if result.stderr:
        logger.debug("appimageupdatetool stderr: %s", result.stderr.strip())
    return result


def _download_changelog() -> str:
    try:
        session = get_requests_session()
        with session.get(CHANGELOG_URL, timeout=CHANGELOG_TIMEOUT) as response:
            response.raise_for_status()
            data = response.content[:CHANGELOG_MAX_CHARS]
    except (OSError, requests.RequestException) as error:
        logger.debug("Failed to download changelog: %s", error)
        return ""
    return data.decode("utf-8", errors="replace")


def _extract_latest_version_changelog(changelog: str) -> str:
    version_header = re.compile(r"^##\s+\[(?!Unreleased\])[^]]+\].*$", re.MULTILINE)
    match = version_header.search(changelog)
    if match is None:
        return changelog

    next_match = re.search(r"^##\s+", changelog[match.end():], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(changelog)
    return changelog[match.start():end].strip()


class AppImageUpdateWorker(QThread):
    """Check and update the running AppImage in a worker thread."""

    update_available = Signal(str, str)
    update_finished = Signal(bool)
    update_output = Signal(str)

    def __init__(self, action: str = "check", update_info: str = "") -> None:
        super().__init__()
        self.action = action
        self.update_info = update_info

    def _tool_args(self, tool_path: str, appimage_path: str, action: str) -> list[str]:
        args = [tool_path, action]
        if self.update_info:
            args.extend(["-u", self.update_info])
        args.append(appimage_path)
        return args

    def _get_changelog(self) -> str:
        return _extract_latest_version_changelog(_download_changelog())

    def _run_tool_with_progress(self, args: list[str]) -> bool:
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as error:
            logger.warning("Failed to run appimageupdatetool: %s", error)
            return False

        start_time = time.monotonic()
        output = process.stdout
        if output is not None:
            for line in output:
                line = line.strip()
                if line:
                    self.update_output.emit(line)
                if time.monotonic() - start_time > APPIMAGE_UPDATE_TIMEOUT:
                    process.kill()
                    logger.warning("AppImage update timed out")
                    return False

        try:
            return process.wait(timeout=1) == 0
        except subprocess.TimeoutExpired:
            process.kill()
            logger.warning("AppImage update timed out")
            return False

    def _run_update(self, tool_path: str, appimage_path: str) -> None:
        success = self._run_tool_with_progress(
            self._tool_args(tool_path, appimage_path, "-Or"),
        )
        self.update_finished.emit(success)

    def _check_for_update(
        self,
        tool_path: str,
        appimage_path: str,
        update_info: str,
    ) -> subprocess.CompletedProcess[str] | None:
        previous_info = self.update_info
        self.update_info = update_info
        result = _run_appimageupdatetool(
            self._tool_args(tool_path, appimage_path, "-j"),
            APPIMAGE_UPDATE_CHECK_TIMEOUT,
        )
        self.update_info = previous_info
        return result

    def _is_check_failure(self, result: subprocess.CompletedProcess[str] | None) -> bool:
        if result is None:
            return True
        if result.returncode not in (0, 1):
            return True
        output = f"{result.stdout}\n{result.stderr}"
        return " Error:" in output or "Failed to fetch" in output

    def run(self) -> None:
        appimage_path = _appimage_path()
        if not ui_config.get_auto_appimage_updates() or not appimage_path:
            return
        if not os.access(appimage_path, os.W_OK):
            logger.info("AppImage is not writable, skipping self-update")
            return

        tool_path = _ensure_appimageupdatetool()
        if not tool_path:
            return

        if self.action == "update":
            self._run_update(tool_path, appimage_path)
            return

        update_infos = ["", FALLBACK_UPDATE_INFO]
        check_code = None
        selected_info = ""
        for update_info in update_infos:
            check_code = self._check_for_update(tool_path, appimage_path, update_info)
            if not self._is_check_failure(check_code):
                selected_info = update_info
                break

        if check_code is None or check_code.returncode != 1:
            return

        logger.info("AppImage update is available")
        self.update_available.emit(self._get_changelog(), selected_info)
