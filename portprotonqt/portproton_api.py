import os
import requests
from collections.abc import Callable
from portprotonqt.downloader import Downloader, download_with_cache
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

class PortProtonAPI:
    """API to fetch game assets (cover, metadata) from the PortProtonQt repository."""
    def __init__(self, downloader: Downloader | None = None):
        self.base_url = "https://git.linux-gaming.ru/Boria138/PortProtonQt/raw/branch/main/portprotonqt/custom_data"
        self.downloader = downloader or Downloader(max_workers=4)
        self.xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
        self.custom_data_dir = os.path.join(self.xdg_data_home, "PortProtonQt", "custom_data")
        os.makedirs(self.custom_data_dir, exist_ok=True)

    def _get_game_dir(self, exe_name: str) -> str:
        game_dir = os.path.join(self.custom_data_dir, exe_name)
        os.makedirs(game_dir, exist_ok=True)
        return game_dir

    def _check_file_exists(self, url: str, timeout: int = 5) -> bool:
        try:
            response = requests.head(url, timeout=timeout)
            response.raise_for_status()
            return response.status_code == 200
        except requests.RequestException as e:
            logger.debug(f"Failed to check file at {url}: {e}")
            return False

    def download_game_assets(self, exe_name: str, timeout: int = 5) -> dict[str, str | None]:
        game_dir = self._get_game_dir(exe_name)
        results: dict[str, str | None] = {"cover": None, "metadata": None}
        cover_extensions = [".png", ".jpg", ".jpeg", ".bmp"]
        cover_url_base = f"{self.base_url}/{exe_name}/cover"
        metadata_url = f"{self.base_url}/{exe_name}/metadata.txt"

        for ext in cover_extensions:
            cover_url = f"{cover_url_base}{ext}"
            if self._check_file_exists(cover_url, timeout):
                local_cover_path = os.path.join(game_dir, f"cover{ext}")
                result = download_with_cache(cover_url, local_cover_path, timeout, self.downloader)
                if result:
                    results["cover"] = result
                    logger.info(f"Downloaded cover for {exe_name} to {result}")
                    break
                else:
                    logger.error(f"Failed to download cover for {exe_name} from {cover_url}")
            else:
                logger.debug(f"No cover found for {exe_name} with extension {ext}")

        if self._check_file_exists(metadata_url, timeout):
            local_metadata_path = os.path.join(game_dir, "metadata.txt")
            result = download_with_cache(metadata_url, local_metadata_path, timeout, self.downloader)
            if result:
                results["metadata"] = result
                logger.info(f"Downloaded metadata for {exe_name} to {result}")
            else:
                logger.error(f"Failed to download metadata for {exe_name} from {metadata_url}")
        else:
            logger.debug(f"No metadata found for {exe_name}")

        return results

    def download_game_assets_async(self, exe_name: str, timeout: int = 5, callback: Callable[[dict[str, str | None]], None] | None = None) -> None:
        game_dir = self._get_game_dir(exe_name)
        cover_extensions = [".png", ".jpg", ".jpeg", ".bmp"]
        cover_url_base = f"{self.base_url}/{exe_name}/cover"
        metadata_url = f"{self.base_url}/{exe_name}/metadata.txt"

        results: dict[str, str | None] = {"cover": None, "metadata": None}
        pending_downloads = 0

        def on_cover_downloaded(local_path: str | None, ext: str):
            nonlocal pending_downloads
            if local_path:
                logger.info(f"Async cover downloaded for {exe_name}: {local_path}")
                results["cover"] = local_path
            else:
                logger.debug(f"No cover downloaded for {exe_name} with extension {ext}")
            pending_downloads -= 1
            check_completion()

        def on_metadata_downloaded(local_path: str | None):
            nonlocal pending_downloads
            if local_path:
                logger.info(f"Async metadata downloaded for {exe_name}: {local_path}")
                results["metadata"] = local_path
            else:
                logger.debug(f"No metadata downloaded for {exe_name}")
            pending_downloads -= 1
            check_completion()

        def check_completion():
            if pending_downloads == 0 and callback:
                callback(results)

        for ext in cover_extensions:
            cover_url = f"{cover_url_base}{ext}"
            if self._check_file_exists(cover_url, timeout):
                local_cover_path = os.path.join(game_dir, f"cover{ext}")
                pending_downloads += 1
                self.downloader.download_async(
                    cover_url,
                    local_cover_path,
                    timeout=timeout,
                    callback=lambda path, ext=ext: on_cover_downloaded(path, ext)
                )
                break

        if self._check_file_exists(metadata_url, timeout):
            local_metadata_path = os.path.join(game_dir, "metadata.txt")
            pending_downloads += 1
            self.downloader.download_async(
                metadata_url,
                local_metadata_path,
                timeout=timeout,
                callback=on_metadata_downloaded
            )

        if pending_downloads == 0:
            logger.debug(f"No assets found for {exe_name}")
            if callback:
                callback(results)
