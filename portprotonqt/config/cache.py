"""Cache configuration and management."""
import shutil
from pathlib import Path
from portprotonqt.config.base import BaseConfig, CACHE_DIR
from portprotonqt.logger import get_logger

logger = get_logger(__name__)


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
