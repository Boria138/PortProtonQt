import os
import shutil
import tarfile
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from PySide6.QtCore import QThread, Signal

from portprotonqt.config.base import THEMES_DIRS
from portprotonqt.downloader import get_requests_session
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
THEME_STORE_API_URL = "https://ppdb.linux-gaming.ru/api/ppqt/themes"
THEME_STORE_TIMEOUT = 20
THEME_STORE_DOWNLOAD_TIMEOUT = 60
THEME_STORE_IMAGE_WORKERS = 8
THEME_STORE_CARD_BATCH_SIZE = 20
THEME_STORE_VOTES_ICON = "★"
THEME_STORE_DOWNLOADS_ICON = "⇩"


def _theme_store_download_url(theme_id: int) -> str:
    return f"{THEME_STORE_API_URL}/{theme_id}/download"


def _theme_store_preview_urls(theme_data: dict) -> list[str]:
    raw_urls = (
        theme_data.get("dark_screenshot_urls")
        or theme_data.get("screenshot_urls")
        or theme_data.get("light_screenshot_urls")
        or []
    )
    return [_theme_store_absolute_url(url) for url in raw_urls if isinstance(url, str)]


def _theme_store_variant_urls(theme_data: dict, variant: str) -> list[str]:
    if variant == "light":
        raw_urls = theme_data.get("light_screenshot_urls") or []
    else:
        raw_urls = theme_data.get("dark_screenshot_urls") or []
    if not raw_urls:
        raw_urls = theme_data.get("screenshot_urls") or []
    return [_theme_store_absolute_url(url) for url in raw_urls if isinstance(url, str)]


def _theme_store_absolute_url(url: str) -> str:
    if url.startswith("http"):
        return url
    return f"https://ppdb.linux-gaming.ru/{url.lstrip('/')}"


def _safe_theme_entry_name(name: str) -> bool:
    if not name or os.path.isabs(name):
        return False
    if os.sep in name or (os.altsep and os.altsep in name):
        return False
    return os.path.normpath(name) == name and name not in (".", "..")


def _is_safe_archive_path(target_dir: str, member_name: str) -> bool:
    target_root = os.path.realpath(target_dir)
    member_path = os.path.realpath(os.path.join(target_dir, member_name))
    return member_path.startswith(target_root + os.sep)


def _safe_extract_zip(zip_path: str, target_dir: str) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if not _is_safe_archive_path(target_dir, member.filename):
                raise ValueError("Theme archive contains unsafe paths")
        archive.extractall(target_dir)


def _safe_extract_tar(tar_path: str, target_dir: str) -> None:
    with tarfile.open(tar_path) as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise ValueError("Theme archive contains links")
            if not _is_safe_archive_path(target_dir, member.name):
                raise ValueError("Theme archive contains unsafe paths")
        archive.extractall(target_dir)


def _safe_extract_archive(archive_path: str, target_dir: str) -> None:
    if zipfile.is_zipfile(archive_path):
        _safe_extract_zip(archive_path, target_dir)
        return
    if tarfile.is_tarfile(archive_path):
        _safe_extract_tar(archive_path, target_dir)
        return
    raise ValueError("Unsupported theme archive format")


def _find_theme_dirs(root_dir: str) -> list[str]:
    if os.path.exists(os.path.join(root_dir, "styles.py")):
        return [root_dir]

    theme_dirs = []
    for entry in os.listdir(root_dir):
        entry_path = os.path.join(root_dir, entry)
        if os.path.isdir(entry_path) and os.path.exists(os.path.join(entry_path, "styles.py")):
            theme_dirs.append(entry_path)
    return theme_dirs


def _install_theme_archive(archive_path: str) -> list[str]:
    user_themes_dir = str(THEMES_DIRS[0])
    installed_names = []
    os.makedirs(user_themes_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ppqt-theme-") as temp_dir:
        _safe_extract_archive(archive_path, temp_dir)
        for source_dir in _find_theme_dirs(temp_dir):
            theme_name = os.path.basename(source_dir)
            if not _safe_theme_entry_name(theme_name):
                logger.warning("Skipping unsafe theme name: %s", theme_name)
                continue
            target_dir = os.path.join(user_themes_dir, theme_name)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.move(source_dir, target_dir)
            installed_names.append(theme_name)
    return installed_names


class ThemeStoreListWorker(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, sort_key: str = "votes", order_key: str = "desc"):
        super().__init__()
        self.sort_key = sort_key
        self.order_key = order_key

    def run(self) -> None:
        session = get_requests_session()
        try:
            response = session.get(
                THEME_STORE_API_URL,
                params={"sort": self.sort_key, "order": self.order_key},
                timeout=THEME_STORE_TIMEOUT,
            )
            response.raise_for_status()
            self.loaded.emit(response.json().get("themes", []))
        except (ValueError, requests.RequestException) as error:
            self.failed.emit(str(error))
        finally:
            session.close()


class ThemeStoreImageWorker(QThread):
    loaded = Signal(str, bytes)

    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        session = get_requests_session()
        try:
            with ThreadPoolExecutor(max_workers=THEME_STORE_IMAGE_WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_image, session, url): url
                    for url in self.urls
                }
                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    url = futures[future]
                    data = future.result()
                    if data:
                        self.loaded.emit(url, data)
        finally:
            session.close()

    def _fetch_image(self, session: requests.Session, url: str) -> bytes | None:
        try:
            response = session.get(url, timeout=THEME_STORE_TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            logger.warning("Failed to load theme preview %s: %s", url, error)
            return None


class ThemeStoreDetailImageWorker(QThread):
    image_loaded = Signal(int, bytes)

    def __init__(self, urls: list[str]):
        super().__init__()
        self.urls = urls
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        session = get_requests_session()
        try:
            with ThreadPoolExecutor(max_workers=THEME_STORE_IMAGE_WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_image, session, url): index
                    for index, url in enumerate(self.urls)
                }
                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    index = futures[future]
                    image = future.result()
                    if image:
                        self.image_loaded.emit(index, image)
        finally:
            session.close()

    def _fetch_image(self, session: requests.Session, url: str) -> bytes | None:
        try:
            response = session.get(url, timeout=THEME_STORE_TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            logger.warning("Failed to load theme screenshot %s: %s", url, error)
            return None


class ThemeStoreDownloadWorker(QThread):
    installed = Signal(list)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, theme_id: int):
        super().__init__()
        self.theme_id = theme_id
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        archive_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as archive:
                archive_path = archive.name
            self._download_archive(archive_path)
            if not self._cancelled:
                self.installed.emit(_install_theme_archive(archive_path))
        except (
            OSError,
            ValueError,
            tarfile.TarError,
            zipfile.BadZipFile,
            requests.RequestException,
        ) as error:
            if not self._cancelled:
                self.failed.emit(str(error))
        finally:
            if archive_path and os.path.exists(archive_path):
                os.remove(archive_path)

    def _download_archive(self, archive_path: str) -> None:
        session = get_requests_session()
        url = _theme_store_download_url(self.theme_id)
        with session.get(url, stream=True, timeout=THEME_STORE_DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with open(archive_path, "wb") as archive:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._cancelled:
                        break
                    if chunk:
                        archive.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))
