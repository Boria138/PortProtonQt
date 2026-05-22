"""Cache configuration and management."""
import json
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
import orjson
from portprotonqt.config.base import BaseConfig, CACHE_DIR
from portprotonqt.logger import get_logger

logger = get_logger(__name__)
_CACHE_FILE_LOCK = threading.RLock()


class CacheConfig(BaseConfig):
    """Cache configuration and management."""

    _section = "Cache"

    def __init__(self):
        super().__init__()
        self._cache_dir = CACHE_DIR

    def get_cache_dir(self) -> Path:
        """Get cache directory path."""
        return self._cache_dir

    def clear_cache(self):
        """Clear the cache directory."""
        if self._cache_dir.exists():
            try:
                shutil.rmtree(self._cache_dir)
                logger.info("Cache directory deleted: %s", self._cache_dir)
            except Exception as e:
                logger.warning("Failed to delete cache: %s", e)
        self._invalidate_cache()


class CacheManager:
    """Unified cache manager for PortProtonQt with disk and memory caching."""

    def __init__(self, cache_dir: Path | None = None, name: str | None = None):
        """Initialize cache manager.

        Args:
            cache_dir: Cache directory path. Uses default CACHE_DIR if None.
            name: Optional name for in-memory cache instance.
        """
        self._cache_dir = cache_dir or CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._name = name
        self._memory_cache: dict[str, Any] = {
            'data': None,
            'index': None,
            'timestamp': 0
        }
        self._lock = threading.RLock() if threading else None
        self._loading = False
        self._pending_callbacks: list[Callable] = []

    @property
    def cache_dir(self) -> Path:
        """Get cache directory path."""
        return self._cache_dir

    def _get_cache_file_path(self, name: str, extension: str = ".json") -> Path:
        """Get cache file path for given name.

        Args:
            name: File name (will be sanitized).
            extension: File extension (default: .json).

        Returns:
            Full path to cache file.
        """
        safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip().replace(" ", "_").lower()
        return self._cache_dir / f"{safe_name}{extension}"

    def load_json(self, name: str) -> Any | None:
        """Load JSON data from disk cache.

        Args:
            name: Cache file name.

        Returns:
            Parsed JSON data or None if not found/invalid.
        """
        cache_file = self._get_cache_file_path(name)
        try:
            with _CACHE_FILE_LOCK:
                if cache_file.exists():
                    with open(cache_file, "rb") as f:
                        return orjson.loads(f.read())
        except orjson.JSONDecodeError as e:
            logger.warning("Failed to load cache %s: %s", cache_file, e)
            try:
                cache_file.unlink()
            except OSError as unlink_error:
                logger.debug("Failed to remove invalid cache %s: %s", cache_file, unlink_error)
        except OSError as e:
            logger.warning("Failed to load cache %s: %s", cache_file, e)
        return None

    def save_json(self, name: str, data: Any, pretty: bool = False) -> bool:
        """Save JSON data to disk cache.

        Args:
            name: Cache file name.
            data: Data to cache (will be JSON-serialized).
            pretty: Use pretty-printing (default: False).

        Returns:
            True if saved successfully, False otherwise.
        """
        cache_file = self._get_cache_file_path(name)
        temp_file = cache_file.with_name(f".{cache_file.name}.{time.time_ns()}.tmp")
        try:
            if pretty:
                content = json.dumps(data, indent=2).encode("utf-8")
            else:
                content = orjson.dumps(data)
            with _CACHE_FILE_LOCK:
                with open(temp_file, "wb") as f:
                    f.write(content)
                temp_file.replace(cache_file)
            return True
        except (OSError, TypeError) as e:
            logger.warning("Failed to save cache %s: %s", cache_file, e)
            try:
                temp_file.unlink()
            except OSError:
                pass
            return False

    def load_text(self, name: str) -> str | None:
        """Load text data from disk cache.

        Args:
            name: Cache file name.

        Returns:
            Text content or None if not found/invalid.
        """
        cache_file = self._get_cache_file_path(name)
        try:
            if cache_file.exists():
                with open(cache_file, encoding="utf-8") as f:
                    return f.read()
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to load text cache %s: %s", cache_file, e)
        return None

    def save_text(self, name: str, content: str) -> bool:
        """Save text data to disk cache.

        Args:
            name: Cache file name.
            content: Text content to cache.

        Returns:
            True if saved successfully, False otherwise.
        """
        cache_file = self._get_cache_file_path(name)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except (OSError, TypeError) as e:
            logger.warning("Failed to save text cache %s: %s", cache_file, e)
            return False

    def load_binary(self, name: str) -> bytes | None:
        """Load binary data from disk cache.

        Args:
            name: Cache file name.

        Returns:
            Binary content or None if not found.
        """
        cache_file = self._get_cache_file_path(name, extension=".dat")
        try:
            if cache_file.exists():
                with open(cache_file, "rb") as f:
                    return f.read()
        except OSError as e:
            logger.warning("Failed to load binary cache %s: %s", cache_file, e)
        return None

    def save_binary(self, name: str, content: bytes) -> bool:
        """Save binary data to disk cache.

        Args:
            name: Cache file name.
            content: Binary content to cache.

        Returns:
            True if saved successfully, False otherwise.
        """
        cache_file = self._get_cache_file_path(name, extension=".dat")
        try:
            with open(cache_file, "wb") as f:
                f.write(content)
            return True
        except OSError as e:
            logger.warning("Failed to save binary cache %s: %s", cache_file, e)
            return False

    def exists(self, name: str, extension: str = ".json") -> bool:
        """Check if cache file exists.

        Args:
            name: Cache file name.
            extension: File extension to check.

        Returns:
            True if cache file exists, False otherwise.
        """
        cache_file = self._get_cache_file_path(name, extension)
        return cache_file.exists()

    def remove(self, name: str, extension: str = ".json") -> bool:
        """Remove cache file.

        Args:
            name: Cache file name.
            extension: File extension.

        Returns:
            True if removed successfully, False otherwise.
        """
        cache_file = self._get_cache_file_path(name, extension)
        try:
            if cache_file.exists():
                cache_file.unlink()
                logger.debug("Cache file removed: %s", cache_file)
                return True
        except OSError as e:
            logger.warning("Failed to remove cache %s: %s", cache_file, e)
        return False

    def clear(self):
        """Clear all cache files in the cache directory."""
        if self._cache_dir.exists():
            try:
                shutil.rmtree(self._cache_dir)
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Cache directory cleared: %s", self._cache_dir)
            except Exception as e:
                logger.warning("Failed to clear cache: %s", e)

    def get_file_age(self, name: str, extension: str = ".json") -> float | None:
        """Get age of cache file in seconds.

        Args:
            name: Cache file name.
            extension: File extension.

        Returns:
            File age in seconds, or None if file doesn't exist.
        """
        cache_file = self._get_cache_file_path(name, extension)
        try:
            if cache_file.exists():
                mtime = cache_file.stat().st_mtime
                return time.time() - mtime
        except OSError:
            pass
        return None

    def is_fresh(self, name: str, max_age: int, extension: str = ".json") -> bool:
        """Check if cache file is fresh (not older than max_age seconds).

        Args:
            name: Cache file name.
            max_age: Maximum age in seconds.
            extension: File extension.

        Returns:
            True if cache is fresh, False otherwise.
        """
        age = self.get_file_age(name, extension)
        return age is not None and age < max_age

    def get_data_and_index_async(
        self,
        load_func: Callable[[Callable[[list], None]], None],
        build_index_func: Callable[[list], dict],
        callback: Callable[[tuple[list | None, dict | None]], None],
        cache_duration: float = 30 * 24 * 60 * 60
    ) -> None:
        """Asynchronously load and cache data with index (in-memory caching).

        Args:
            load_func: Function to load data asynchronously.
            build_index_func: Function to build index from data.
            callback: Callback with (data, index) tuple.
            cache_duration: Cache TTL in seconds.
        """
        import threading as threading_module
        current_time = time.time()

        if self._lock is None:
            self._lock = threading_module.RLock()

        with self._lock:
            if (self._memory_cache['data'] is not None and
                self._memory_cache['index'] is not None and
                current_time - self._memory_cache['timestamp'] < cache_duration):
                callback((self._memory_cache['data'], self._memory_cache['index']))
                return

            if self._loading:
                self._pending_callbacks.append(callback)
                return

            self._loading = True
            self._pending_callbacks = []

        def on_data(data: list) -> None:
            current_time = time.time()
            if self._lock:
                with self._lock:
                    if data:
                        self._memory_cache['data'] = data
                        self._memory_cache['index'] = build_index_func(data)
                        self._memory_cache['timestamp'] = current_time
                        cached_data = (self._memory_cache['data'], self._memory_cache['index'])
                    else:
                        self._memory_cache['data'] = None
                        self._memory_cache['index'] = None
                        self._memory_cache['timestamp'] = 0
                        cached_data = (None, None)

                    self._loading = False
                    pending_callbacks = self._pending_callbacks
                    self._pending_callbacks = []

                callback(cached_data)
                for pending_callback in pending_callbacks:
                    pending_callback(cached_data)

        load_func(on_data)

    def clear_memory_cache(self) -> None:
        """Clear in-memory cache."""
        if self._lock:
            with self._lock:
                self._memory_cache = {
                    'data': None,
                    'index': None,
                    'timestamp': 0
                }
        if self._name:
            logger.info("Cleared %s in-memory cache", self._name)
