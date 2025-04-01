import os
import urllib.request
import threading
import time
from portprotonqt.config_utils import read_proxy_config
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

def download_with_cache(url, local_path, timeout=5):
    """
    Загружает данные по URL и сохраняет в local_path.
    Отображает процент загрузки, размер файла и скорость загрузки
    :param url: URL для загрузки.
    :param local_path: Путь для сохранения файла.
    :param timeout: Таймаут запроса.
    :return: local_path, если загрузка успешна, иначе None.
    """
    if os.path.exists(local_path):
        return local_path
    proxy_config = read_proxy_config()
    try:
        if proxy_config:
            proxy_handler = urllib.request.ProxyHandler(proxy_config)
            opener = urllib.request.build_opener(proxy_handler)
        else:
            opener = urllib.request.build_opener()
        req = urllib.request.Request(url)

        start_time = time.time()
        response = opener.open(req, timeout=timeout)
        total_size = response.headers.get('Content-Length')
        if total_size:
            total_size = int(total_size)
        else:
            total_size = 0

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        downloaded = 0
        chunk_size = 8192  # 8 КБ

        with open(local_path, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                elapsed_time = time.time() - start_time
                if elapsed_time > 0:
                    speed = downloaded / elapsed_time
                    human_speed = format_size(speed) + "/s"
                else:
                    human_speed = "? B/s"

                if total_size > 0:
                    percent = int(downloaded * 100 / total_size)
                    progress_bar = '█' * (percent // 2)
                    human_downloaded = format_size(downloaded)
                    human_total_size = format_size(int(total_size))

                    # Индикатор прогресса с процентами, размером и скоростью
                    print(f"\r{('Downloading')} {os.path.basename(local_path)} |{progress_bar.ljust(50)}| {percent}% ({human_downloaded} of {human_total_size}, {human_speed})", end="")
                else:
                    human_downloaded = format_size(downloaded)
                    print(f"\r{'Downloading'} {os.path.basename(local_path)}: {human_downloaded} ({human_speed})", end="")

            print()  # Перевод строки после завершения загрузки

        return local_path
    except Exception as e:
        logger.error(f"Downloading error {url}: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
    return None

def format_size(size_bytes):
    """
    Преобразует размер в байтах в человекочитаемый формат.
    """
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names)-1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {size_names[i]}"

class Downloader:
    """
    Класс для оптимизированной загрузки файлов.

    Поддерживает:
      - Кэширование: если файл уже существует локально, повторная загрузка не выполняется.
      - Прокси: настройки прокси получаются через read_proxy_config.
      - Асинхронная загрузка: загрузка файлов в отдельных потоках.
      - Прогресс загрузки
    """
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self._cache = {}
        self._lock = threading.Lock()

    def download(self, url, local_path, timeout=5):
        """
        Синхронно загружает файл по указанному URL с кэшированием.
        Если файл уже есть в кэше, возвращает его путь.
        """
        with self._lock:
            if url in self._cache:
                return self._cache[url]
        result = download_with_cache(url, local_path, timeout)
        with self._lock:
            self._cache[url] = result
        return result

    def download_async(self, url, local_path, timeout=5, callback=None):
        """
        Асинхронно загружает файл в отдельном потоке.

        :param url: URL для загрузки.
        :param local_path: Путь для сохранения файла.
        :param timeout: Время ожидания запроса.
        :param callback: Функция обратного вызова, которая будет вызвана с результатом (local_path или None).
        :return: Объект потока.
        """
        def task():
            result = self.download(url, local_path, timeout)
            if callback:
                callback(result)

        thread = threading.Thread(target=task)
        thread.daemon = True
        thread.start()
        return thread
