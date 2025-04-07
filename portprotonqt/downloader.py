import os
import urllib.request
import threading
import time
from pathlib import Path
from portprotonqt.config_utils import read_proxy_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

# Глобальный блокировщик для вывода прогресса
print_lock = threading.Lock()

def format_size(size_bytes):
    """Форматирует размер в байтах в читаемый вид."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size_bytes >= 1024 and index < len(units)-1:
        size_bytes /= 1024.0
        index += 1
    return f"{size_bytes:.2f} {units[index]}"

def get_opener():
    """Создаёт и возвращает настроенный URL opener с прокси-конфигурацией."""
    proxy_config = read_proxy_config() or {}
    handler = urllib.request.ProxyHandler(proxy_config)
    opener = urllib.request.build_opener(handler)
    return opener

def download_with_cache(url, local_path, timeout=5, downloader_instance=None):
    """Скачивает файл с отображением прогресса."""
    if os.path.exists(local_path):
        return local_path

    opener = get_opener()
    try:
        req = urllib.request.Request(url)
        start_time = time.time()
        with opener.open(req, timeout=timeout) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            downloaded = 0
            chunk_size = 8192

            with open(local_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Расчет скорости и прогресса
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    human_speed = f"{format_size(speed)}/s"

                    if total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        progress = '█' * (percent // 2)
                        status = (
                            f"\rDownloading {Path(local_path).name} |{progress.ljust(50)}| "
                            f"{percent}% ({format_size(downloaded)}/{format_size(total_size)}, {human_speed})"
                        )
                    else:
                        status = f"\rDownloading {Path(local_path).name}: {format_size(downloaded)} ({human_speed})"

                    with print_lock:
                        print(status, end="")

            with print_lock:
                print()
            return local_path
    except Exception as e:
        logger.error(f"Ошибка загрузки {url}: {e}")
        if downloader_instance and hasattr(downloader_instance, '_last_error'):
            downloader_instance._last_error[url] = True
        if os.path.exists(local_path):
            os.remove(local_path)
        return None

def download_with_parallel(url, local_path, timeout=5, workers=4):
    """Параллельная загрузка файла по частям."""
    if os.path.exists(local_path):
        return local_path

    opener = get_opener()

    try:
        # Проверка поддержки частичных загрузок
        head_req = urllib.request.Request(url, method="HEAD")
        with opener.open(head_req, timeout=timeout) as response:
            if response.headers.get('Accept-Ranges', 'none').lower() != 'bytes':
                logger.info(f"Сервер не поддерживает частичные загрузки для {url}, переключаемся на обычную загрузку")
                return download_with_cache(url, local_path, timeout)

            total_size = int(response.headers.get('Content-Length', 0))
            if total_size <= 0:
                logger.info(f"Неизвестный размер файла для {url}, переключаемся на обычную загрузку")
                return download_with_cache(url, local_path, timeout)

            # Создаем директорию, если она не существует
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Если файл маленький, используем обычную загрузку
            if total_size < 1024 * 1024:  # Менее 1 МБ
                logger.info(f"Файл {url} слишком маленький для параллельной загрузки")
                return download_with_cache(url, local_path, timeout)

            # Корректируем количество рабочих потоков в зависимости от размера файла
            effective_workers = min(workers, max(1, total_size // (1024 * 1024)))  # Минимум 1МБ на часть

            part_size = total_size // effective_workers
            parts = [(i * part_size,
                     (i+1)*part_size-1 if i < effective_workers-1 else total_size-1)
                     for i in range(effective_workers)]

            temp_files = [f"{local_path}.part{i}" for i in range(effective_workers)]
            progress = [0] * effective_workers
            progress_lock = threading.Lock()
            threads = []
            errors = []

            def download_part(index, start, end, temp_file):
                """Загрузка части файла."""
                try:
                    req = urllib.request.Request(url)
                    req.headers['Range'] = f"bytes={start}-{end}"

                    with opener.open(req, timeout=timeout) as response:
                        with open(temp_file, "wb") as f:
                            while True:
                                chunk = response.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                                with progress_lock:
                                    progress[index] += len(chunk)
                except Exception as e:
                    with progress_lock:
                        errors.append((index, str(e)))

            # Запуск потоков для каждой части
            for i, (start, end) in enumerate(parts):
                thread = threading.Thread(
                    target=download_part,
                    args=(i, start, end, temp_files[i])
                )
                thread.daemon = True  # Daemon потоки завершаются при выходе из главного потока
                thread.start()
                threads.append(thread)

            # Начальное время для расчета скорости
            start_time = time.time()
            last_total = 0

            # Отображение общего прогресса
            while any(t.is_alive() for t in threads):
                if errors:
                    # Если произошла ошибка, отменяем загрузку
                    logger.error(f"Ошибка при параллельной загрузке {url}: {errors[0][1]}")
                    for t in threads:
                        t.join(0.1)  # Ждем потоки небольшое время
                    # Очищаем временные файлы
                    for part in temp_files:
                        if os.path.exists(part):
                            os.remove(part)
                    return download_with_cache(url, local_path, timeout)  # Попробуем обычную загрузку

                with progress_lock:
                    current = sum(progress)

                # Расчет скорости
                elapsed = time.time() - start_time
                if elapsed > 0.5:  # Обновляем скорость каждые 0.5 секунды
                    speed = (current - last_total) / elapsed
                    human_speed = f"{format_size(speed)}/s"
                    last_total = current
                    start_time = time.time()
                else:
                    human_speed = "plese wait..."

                # Отображение прогресса
                percent = int(current * 100 / total_size) if total_size > 0 else 0
                progress_bar = '█' * (percent // 2)
                status = (
                    f"\rDownloading {Path(local_path).name} |{progress_bar.ljust(50)}| "
                    f"{percent}% ({format_size(current)}/{format_size(total_size)}, {human_speed})"
                )
                with print_lock:
                    print(status, end="")
                time.sleep(0.1)

            with print_lock:
                print()

            # Если есть ошибки после завершения потоков
            if errors:
                logger.error(f"Ошибка при параллельной загрузке {url}: {errors[0][1]}")
                # Очищаем временные файлы
                for part in temp_files:
                    if os.path.exists(part):
                        os.remove(part)
                return None

            # Сборка файла из частей
            with open(local_path, "wb") as f:
                for part in temp_files:
                    if os.path.exists(part):
                        with open(part, "rb") as p:
                            f.write(p.read())
                        os.remove(part)
                    else:
                        logger.error(f"Отсутствует часть файла {part}")
                        if os.path.exists(local_path):
                            os.remove(local_path)
                        return None

            return local_path
    except Exception as e:
        logger.error(f"Ошибка параллельной загрузки {url}: {e}")
        # Очищаем временные файлы
        for part in temp_files if 'temp_files' in locals() else []:
            if os.path.exists(part):
                os.remove(part)

        if os.path.exists(local_path):
            os.remove(local_path)
        return None

class Downloader:
    """Класс для управления загрузками."""
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self._cache = {}
        self._last_error = {}
        self._locks = {}
        self._global_lock = threading.Lock()

    def _get_url_lock(self, url):
        """Возвращает блокировку для конкретного URL."""
        with self._global_lock:
            if url not in self._locks:
                self._locks[url] = threading.Lock()
            return self._locks[url]

    def download(self, url, local_path, timeout=5):
        """Основной метод загрузки с кэшированием."""
        with self._global_lock:
            if url in self._last_error:
                return None
            if url in self._cache:
                return self._cache[url]

        url_lock = self._get_url_lock(url)
        with url_lock:
            # Повторная проверка после получения блокировки
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
        """Параллельная загрузка с кэшированием."""
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
        """Массовая загрузка файлов с возможностью параллелизма."""
        results = {}
        threads = []

        def task(url, path):
            try:
                download_func = self.download_parallel if parallel else self.download
                result = download_func(url, path, timeout)
                results[url] = result
            except Exception as e:
                logger.error(f"Ошибка загрузки {url}: {e}")
                results[url] = None

        for url, path in files:
            thread = threading.Thread(target=task, args=(url, path))
            thread.daemon = True  # Daemon потоки завершаются при выходе из главного потока
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        return results

    def download_async(self, url, local_path, timeout=5, callback=None, parallel=False):
        """Асинхронная загрузка с коллбэком."""
        def wrapper():
            try:
                download_func = self.download_parallel if parallel else self.download
                result = download_func(url, local_path, timeout)
                if callback:
                    callback(result)
            except Exception as e:
                logger.error(f"Ошибка при асинхронной загрузке {url}: {e}")
                if callback:
                    callback(None)

        thread = threading.Thread(target=wrapper)
        thread.daemon = True  # Daemon потоки завершаются при выходе из главного потока
        thread.start()
        return thread

    def clear_cache(self):
        """Очистка кэша загрузок."""
        with self._global_lock:
            self._cache.clear()

    def is_cached(self, url):
        """Проверка, находится ли URL в кэше."""
        with self._global_lock:
            return url in self._cache
