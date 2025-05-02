import os
import threading
import time
import socket
from pathlib import Path
import requests
from tqdm import tqdm
from portprotonqt.config_utils import read_proxy_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
print_lock = threading.Lock()

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
            with tqdm(
                total=total_size if total_size > 0 else None,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=f"Downloading {desc}",
                ascii=True
            ) as pbar:
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

def download_with_parallel(url, local_path, timeout=5, workers=4):
    if os.path.exists(local_path):
        return local_path

    session = get_requests_session()
    temp_files = []
    try:
        head = session.head(url, timeout=timeout)
        head.raise_for_status()
        if head.headers.get('Accept-Ranges', 'none').lower() != 'bytes':
            return download_with_cache(url, local_path, timeout)

        total_size = int(head.headers.get('Content-Length', 0))
        if total_size <= 0:
            return download_with_cache(url, local_path, timeout)

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        part_size = total_size // workers
        ranges = [(i * part_size, total_size - 1 if i == workers - 1 else (i + 1) * part_size - 1)
                  for i in range(workers)]

        temp_files = [f"{local_path}.part{i}" for i in range(workers)]
        progress = [0] * workers
        threads = []
        errors = []
        lock = threading.Lock()

        def download_part(i, start, end):
            try:
                headers = {"Range": f"bytes={start}-{end}"}
                with session.get(url, headers=headers, stream=True, timeout=timeout) as r:
                    r.raise_for_status()
                    with open(temp_files[i], 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                with lock:
                                    progress[i] += len(chunk)
            except Exception as e:
                with lock:
                    error_msg = f"Ошибка загрузки части {i} (байты {start}-{end}): {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        for i, (start, end) in enumerate(ranges):
            t = threading.Thread(target=download_part, args=(i, start, end))
            t.start()
            threads.append(t)

        with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024,
                  desc=f"Downloading {Path(local_path).name}", ascii=True) as pbar:
            last = 0
            while any(t.is_alive() for t in threads):
                current = sum(progress)
                pbar.update(current - last)
                last = current
                time.sleep(0.1)

        for t in threads:
            t.join()

        if errors:
            for tf in temp_files:
                if os.path.exists(tf):
                    os.remove(tf)
            return download_with_cache(url, local_path, timeout)

        with open(local_path, 'wb') as out:
            for tf in temp_files:
                with open(tf, 'rb') as f:
                    out.write(f.read())
                os.remove(tf)

        return local_path

    except Exception as e:
        logger.error(f"Ошибка параллельной загрузки {url}: {e}")
        for tf in temp_files:
            if os.path.exists(tf):
                os.remove(tf)
        return None

class Downloader:
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self._cache = {}
        self._last_error = {}
        self._locks = {}
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
            return None

        with self._global_lock:
            if url in self._last_error:
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

    def download_parallel(self, url, local_path, timeout=5):
        if not self.has_internet():
            return None

        with self._global_lock:
            if url in self._cache:
                return self._cache[url]

        url_lock = self._get_url_lock(url)
        with url_lock:
            with self._global_lock:
                if url in self._cache:
                    return self._cache[url]

            result = download_with_parallel(url, local_path, timeout, self.max_workers)

            with self._global_lock:
                if result:
                    self._cache[url] = result
                if url in self._locks:
                    del self._locks[url]

            return result

    def download_many(self, files, timeout=5, parallel=False):
        if not self.has_internet():
            return {url: None for url, _ in files}

        results = {}
        threads = []

        def task(url, path):
            try:
                func = self.download_parallel if parallel else self.download
                results[url] = func(url, path, timeout)
            except Exception as e:
                logger.error(f"Ошибка загрузки {url}: {e}")
                results[url] = None

        for url, path in files:
            t = threading.Thread(target=task, args=(url, path))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        return results

    def download_async(self, url, local_path, timeout=5, callback=None, parallel=False):
        def wrapper():
            try:
                func = self.download_parallel if parallel else self.download
                result = func(url, local_path, timeout)
                if callback:
                    callback(result)
            except Exception as e:
                logger.error(f"Ошибка при асинхронной загрузке {url}: {e}")
                if callback:
                    callback(None)

        t = threading.Thread(target=wrapper)
        t.start()
        return t

    def clear_cache(self):
        with self._global_lock:
            self._cache.clear()

    def is_cached(self, url):
        with self._global_lock:
            return url in self._cache
