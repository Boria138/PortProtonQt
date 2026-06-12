from PySide6.QtCore import QObject, Signal, QThread
import threading
import os
import requests
from pathlib import Path
from tqdm import tqdm
from collections.abc import Callable
from portprotonqt.config import proxy_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)


def get_default_user_agent() -> str:
    from portprotonqt.app import __app_version__

    return f"PortProtonQt/{__app_version__}"

def get_requests_session():
    session = requests.Session()
    proxy = proxy_config.get_proxy() or {}
    if proxy:
        session.proxies.update(proxy)
    session.headers.update({"User-Agent": get_default_user_agent()})
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
    callback_requested = Signal(object, object)

    def __init__(self, max_workers=4):
        super().__init__()
        self.max_workers = max_workers
        self._cache = {}
        self._last_error = {}
        self._locks = {}
        self._active_threads: list[QThread] = []
        self._global_lock = threading.Lock()
        self.callback_requested.connect(self._run_callback)

    def _run_callback(self, callback, result):
        if callback:
            callback(result)

    def _get_url_lock(self, url):
        with self._global_lock:
            if url not in self._locks:
                self._locks[url] = threading.Lock()
            return self._locks[url]

    def _download_with_parallel(
        self,
        urls,
        local_paths,
        timeout=5,
        throttle_delay=0.2,
        max_workers=4,
        on_result: Callable[[str, str | None], None] | None = None,
    ):
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
                if e.response is not None and e.response.status_code == 429:
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
                    if on_result:
                        on_result(url, res)
                except Exception as e:
                    logger.error(f"Download error {url}: {e}")
                    results[url] = None
                    if on_result:
                        on_result(url, None)
        return results

    def download(self, url, local_path, timeout=5):
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

    def download_parallel(
        self,
        urls,
        local_paths,
        timeout=5,
        throttle_delay=0.2,
        max_workers=None,
        on_result: Callable[[str, str | None], None] | None = None,
    ):
        filtered_urls = []
        filtered_paths = []
        emitted_urls = set()
        with self._global_lock:
            for url, path in zip(urls, local_paths, strict=False):
                if url in self._last_error:
                    logger.warning(f"Previous download error for {url}, skipping")
                    if on_result and url not in emitted_urls:
                        on_result(url, None)
                        emitted_urls.add(url)
                    continue
                if url in self._cache:
                    if on_result and url not in emitted_urls:
                        on_result(url, self._cache[url])
                        emitted_urls.add(url)
                    continue
                filtered_urls.append(url)
                filtered_paths.append(path)

        def emit_result(url: str, result: str | None):
            if on_result:
                on_result(url, result)
            emitted_urls.add(url)

        workers = max_workers if max_workers is not None else self.max_workers
        results = self._download_with_parallel(
            filtered_urls,
            filtered_paths,
            timeout,
            throttle_delay,
            workers,
            on_result=emit_result,
        )

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
        if on_result:
            for url in urls:
                if url not in emitted_urls:
                    on_result(url, final_results[url])
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
                    self.downloader.callback_requested.emit(callback, result)
                except Exception as e:
                    logger.error(f"Async download error {self.url}: {e}")
                    self.downloader.download_completed.emit(self.url, "", False)
                    self.downloader.callback_requested.emit(callback, None)

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

    def cache_config(self):
        with self._global_lock:
            self._cache.clear()
