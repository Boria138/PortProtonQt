from PySide6.QtCore import QObject, Signal, QThread
import threading
import os
import requests
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
        logger.error(f"Ошибка загрузки {url}: {e}")
        if downloader_instance and hasattr(downloader_instance, '_last_error'):
            downloader_instance._last_error[url] = True
        if os.path.exists(local_path):
            os.remove(local_path)
        return None

def download_with_parallel(urls, local_paths, max_workers=4, timeout=5, downloader_instance=None):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    session = get_requests_session()

    def _download_one(url, local_path):
        if os.path.exists(local_path):
            return local_path
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
            logger.error(f"Ошибка загрузки {url}: {e}")
            if downloader_instance and hasattr(downloader_instance, '_last_error'):
                downloader_instance._last_error[url] = True
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
                logger.error(f"Ошибка при загрузке {url}: {e}")
                results[url] = None
    return results

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
                logger.warning("Интернет недоступен:\n" + "\n".join(errors))
                self._has_internet = False
            else:
                self._has_internet = True
        return self._has_internet

    def reset_internet_check(self):
        self._has_internet = None

    def _get_url_lock(self, url):
        with self._global_lock:
            if url not in self._locks:
                self._locks[url] = threading.Lock()
            return self._locks[url]

    def download(self, url, local_path, timeout=5):
        if not self.has_internet():
            logger.warning(f"Нет интернета, пропускаем загрузку {url}")
            return None
        with self._global_lock:
            if url in self._last_error:
                logger.warning(f"Предыдущая ошибка загрузки для {url}, пропускаем")
                return None
            if url in self._cache:
                return self._cache[url]
        url_lock = self._get_url_lock(url)
        with url_lock:
            with self._global_lock:
                if url in self._last_error:
                    return None
                if url in self._cache:
                    return self._cache[url]
            result = download_with_cache(url, local_path, timeout, self)
            with self._global_lock:
                if result:
                    self._cache[url] = result
                if url in self._locks:
                    del self._locks[url]
            return result

    def download_parallel(self, urls, local_paths, timeout=5):
        if not self.has_internet():
            logger.warning("Нет интернета, пропускаем параллельную загрузку")
            return dict.fromkeys(urls)

        filtered_urls = []
        filtered_paths = []
        with self._global_lock:
            for url, path in zip(urls, local_paths, strict=False):
                if url in self._last_error:
                    logger.warning(f"Предыдущая ошибка загрузки для {url}, пропускаем")
                    continue
                if url in self._cache:
                    continue
                filtered_urls.append(url)
                filtered_paths.append(path)

        results = download_with_parallel(filtered_urls, filtered_paths, max_workers=self.max_workers, timeout=timeout, downloader_instance=self)

        with self._global_lock:
            for url, path in results.items():
                if path:
                    self._cache[url] = path
        # Для URL которые были пропущены, добавляем их из кэша или None
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
                    logger.error(f"Ошибка при асинхронной загрузке {self.url}: {e}")
                    self.downloader.download_completed.emit(self.url, "", False)
                    if callback:
                        callback(None)

        thread = DownloadThread(self, url, local_path, timeout, parallel)
        thread.finished.connect(thread.deleteLater)

        # Удалить из списка после завершения
        def cleanup():
            self._active_threads.remove(thread)

        thread.finished.connect(cleanup)

        self._active_threads.append(thread)  # Сохраняем поток, чтобы не уничтожился досрочно
        logger.debug(f"Запуск потока для асинхронной загрузки {url}")
        thread.start()
        return thread

    def clear_cache(self):
        with self._global_lock:
            self._cache.clear()

    def is_cached(self, url):
        with self._global_lock:
            return url in self._cache
