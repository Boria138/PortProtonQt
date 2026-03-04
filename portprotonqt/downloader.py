from PySide6.QtCore import QObject, Signal, QThread
import threading
import os
import requests
import orjson
import socket
from pathlib import Path
from tqdm import tqdm
from collections.abc import Callable
from portprotonqt.config_utils import read_proxy_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

def get_requests_session():
    session = requests.Session()
    proxy = read_proxy_config() or {}
    if proxy:
        session.proxies.update(proxy)
    session.verify = True
    return session

def download_with_cache(url, local_path, timeout=5, downloader_instance=None):
    if os.path.exists(local_path):
        return local_path
    session = get_requests_session()
    try:
        with session.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('Content-Length', 0))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            desc = Path(local_path).name
            with tqdm(total=total_size if total_size > 0 else None,
                      unit='B', unit_scale=True, unit_divisor=1024,
                      desc=f"Downloading {desc}", ascii=True) as pbar:
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
        return local_path
    except Exception as e:
        logger.error(f"Download error {url}: {e}")
        if downloader_instance and hasattr(downloader_instance, '_last_error'):
            downloader_instance._last_error[url] = True
        if os.path.exists(local_path):
            os.remove(local_path)
        return None

class Downloader(QObject):
    download_completed = Signal(str, str, bool)  # url, local_path, success

    def __init__(self, max_workers=4):
        super().__init__()
        self.max_workers = max_workers
        self._cache = {}
        self._last_error = {}
        self._locks = {}
        self._active_threads: list[QThread] = []
        self._global_lock = threading.Lock()
        self._has_internet = None

    def has_internet(self, timeout=3):
        if self._has_internet is None:
            errors = []
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            except Exception as e:
                errors.append(f"8.8.8.8: {e}")
            try:
                socket.create_connection(("8.8.4.4", 53), timeout=timeout)
            except Exception as e:
                errors.append(f"8.8.4.4: {e}")
            try:
                requests.get("https://www.google.com", timeout=timeout)
            except Exception as e:
                errors.append(f"google.com: {e}")
            if errors:
                logger.warning("Internet unavailable:\n" + "\n".join(errors))
                self._has_internet = False
            else:
                self._has_internet = True
        return self._has_internet


    def _get_url_lock(self, url):
        with self._global_lock:
            if url not in self._locks:
                self._locks[url] = threading.Lock()
            return self._locks[url]

    def _download_with_parallel(self, urls, local_paths, timeout=5, throttle_delay=0.2, max_workers=4):
        """Internal parallel download with rate limiting and 429 retry."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time

        results = {}
        session = get_requests_session()
        rate_limit_lock = threading.Lock()
        last_request_time = [0.0]

        def _download_one(url, local_path):
            if os.path.exists(local_path):
                return local_path
            try:
                with rate_limit_lock:
                    elapsed = time.time() - last_request_time[0]
                    if elapsed < throttle_delay:
                        time.sleep(throttle_delay - elapsed)
                    last_request_time[0] = time.time()

                with session.get(url, stream=True, timeout=timeout) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get('Content-Length', 0))
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    desc = Path(local_path).name
                    with tqdm(total=total_size if total_size > 0 else None,
                              unit='B', unit_scale=True, unit_divisor=1024,
                              desc=f"Downloading {desc}", ascii=True) as pbar:
                        with open(local_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                return local_path
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logger.warning(f"Rate limited (429) for {url}, retrying after delay")
                    time.sleep(2.0)
                    try:
                        with session.get(url, stream=True, timeout=timeout) as response:
                            response.raise_for_status()
                            total_size = int(response.headers.get('Content-Length', 0))
                            os.makedirs(os.path.dirname(local_path), exist_ok=True)
                            desc = Path(local_path).name
                            with tqdm(total=total_size if total_size > 0 else None,
                                      unit='B', unit_scale=True, unit_divisor=1024,
                                      desc=f"Downloading {desc}", ascii=True) as pbar:
                                with open(local_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                            pbar.update(len(chunk))
                        return local_path
                    except Exception as retry_e:
                        logger.error(f"Retry download error {url}: {retry_e}")
                        with self._global_lock:
                            self._last_error[url] = True
                        if os.path.exists(local_path):
                            os.remove(local_path)
                        return None
                else:
                    logger.error(f"Download error {url}: {e}")
                    with self._global_lock:
                        self._last_error[url] = True
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    return None
            except Exception as e:
                logger.error(f"Download error {url}: {e}")
                with self._global_lock:
                    self._last_error[url] = True
                if os.path.exists(local_path):
                    os.remove(local_path)
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(_download_one, url, local_path): url for url, local_path in zip(urls, local_paths, strict=False)}
            for future in tqdm(as_completed(future_to_url), total=len(urls), desc="Downloading in parallel", ascii=True):
                url = future_to_url[future]
                try:
                    res = future.result()
                    results[url] = res
                except Exception as e:
                    logger.error(f"Download error {url}: {e}")
                    results[url] = None
        return results

    def download(self, url, local_path, timeout=5):
        if not self.has_internet():
            logger.warning(f"No internet, skipping download {url}")
            return None
        with self._global_lock:
            if url in self._last_error:
                logger.warning(f"Previous download error for {url}, skipping")
                return None
            if url in self._cache:
                cached_path = self._cache[url]
                if os.path.exists(cached_path):
                    if os.path.abspath(cached_path) == os.path.abspath(local_path):
                        return cached_path
                else:
                    del self._cache[url]
        url_lock = self._get_url_lock(url)
        with url_lock:
            with self._global_lock:
                if url in self._last_error:
                    return None
                if url in self._cache:
                    cached_path = self._cache[url]
                    if os.path.exists(cached_path) and os.path.abspath(cached_path) == os.path.abspath(local_path):
                        return cached_path
            result = download_with_cache(url, local_path, timeout, self)
            with self._global_lock:
                if result:
                    self._cache[url] = result
                if url in self._locks:
                    del self._locks[url]
            return result

    def download_parallel(self, urls, local_paths, timeout=5, throttle_delay=0.2, max_workers=None):
        if not self.has_internet():
            logger.warning("No internet, skipping parallel download")
            return dict.fromkeys(urls)

        filtered_urls = []
        filtered_paths = []
        with self._global_lock:
            for url, path in zip(urls, local_paths, strict=False):
                if url in self._last_error:
                    logger.warning(f"Previous download error for {url}, skipping")
                    continue
                if url in self._cache:
                    continue
                filtered_urls.append(url)
                filtered_paths.append(path)

        workers = max_workers if max_workers is not None else self.max_workers
        results = self._download_with_parallel(filtered_urls, filtered_paths, timeout, throttle_delay, workers)

        with self._global_lock:
            for url, path in results.items():
                if path:
                    self._cache[url] = path
        final_results = {}
        with self._global_lock:
            for url in urls:
                if url in self._cache:
                    final_results[url] = self._cache[url]
                else:
                    final_results[url] = None
        return final_results


    def download_async(self, url: str, local_path: str, timeout: int = 5, callback: Callable[[str | None], None] | None = None, parallel: bool = False) -> QThread:
        class DownloadThread(QThread):
            def __init__(self, downloader: 'Downloader', url: str, local_path: str, timeout: int, parallel: bool):
                super().__init__()
                self.downloader = downloader
                self.url = url
                self.local_path = local_path
                self.timeout = timeout
                self.parallel = parallel

            def run(self):
                try:
                    if self.parallel:
                        results = self.downloader.download_parallel([self.url], [self.local_path], timeout=self.timeout)
                        result = results.get(self.url, None)
                    else:
                        result = self.downloader.download(self.url, self.local_path, self.timeout)
                    success = result is not None
                    logger.debug(f"Async download completed {self.url}: success={success}, path={result or ''}")
                    self.downloader.download_completed.emit(self.url, result or "", success)
                    if callback:
                        callback(result)
                except Exception as e:
                    logger.error(f"Async download error {self.url}: {e}")
                    self.downloader.download_completed.emit(self.url, "", False)
                    if callback:
                        callback(None)

        thread = DownloadThread(self, url, local_path, timeout, parallel)
        thread.finished.connect(thread.deleteLater)

        # Remove from list after completion
        def cleanup():
            self._active_threads.remove(thread)

        thread.finished.connect(cleanup)

        self._active_threads.append(thread)  # Keep thread to prevent premature destruction
        logger.debug(f"Starting thread for async download {url}")
        thread.start()
        return thread

    def clear_cache(self):
        with self._global_lock:
            self._cache.clear()


    def get_latest_legendary_release(self):
        """Get the latest legendary release info from GitHub API."""
        try:
            api_url = "https://api.github.com/repos/derrod/legendary/releases/latest"
            session = get_requests_session()
            response = session.get(api_url, timeout=10)
            response.raise_for_status()

            release_data = orjson.loads(response.content)

            # Find the Linux binary asset
            for asset in release_data.get('assets', []):
                if asset['name'] == 'legendary' and 'linux' in asset.get('content_type', '').lower():
                    return {
                        'version': release_data['tag_name'],
                        'download_url': asset['browser_download_url'],
                        'size': asset['size']
                    }

            # Fallback: look for asset named just "legendary"
            for asset in release_data.get('assets', []):
                if asset['name'] == 'legendary':
                    return {
                        'version': release_data['tag_name'],
                        'download_url': asset['browser_download_url'],
                        'size': asset['size']
                    }

            logger.warning("Could not find legendary binary in latest release assets")
            return None

        except requests.RequestException as e:
            logger.error(f"Failed to fetch latest legendary release info: {e}")
            return None
        except (KeyError, orjson.JSONDecodeError) as e:
            logger.error(f"Failed to parse legendary release info: {e}")
            return None

    def download_legendary_binary(self, callback: Callable[[str | None], None] | None = None):
        """Download the latest legendary binary for Linux from GitHub releases."""
        if not self.has_internet():
            logger.warning("No internet connection, skipping legendary binary download")
            if callback:
                callback(None)
            return None

        # Get latest release info
        latest_release = self.get_latest_legendary_release()
        if not latest_release:
            logger.error("Could not determine latest legendary version, falling back to hardcoded version")
            # Fallback to hardcoded version
            binary_url = "https://github.com/derrod/legendary/releases/download/0.20.34/legendary"
            version = "0.20.34"
        else:
            binary_url = latest_release['download_url']
            version = latest_release['version']
            logger.info(f"Found latest legendary version: {version}")

        local_path = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "PortProtonQt", "legendary_cache", "legendary"
        )

        logger.info(f"Downloading legendary binary version {version} from {binary_url} to {local_path}")
        return self.download_async(binary_url, local_path, timeout=5, callback=callback)
