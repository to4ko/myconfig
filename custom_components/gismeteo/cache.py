#  Copyright (c) 2018, Vladimir Maksimenko <vl.maksime@gmail.com>
#  Copyright (c) 2019-2022, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#
# Version 3.1.0
"""Cache controller."""

import logging
import os
import time
from pathlib import Path
from typing import Any

import aiofiles

_LOGGER = logging.getLogger(__name__)


class Cache:
    """Data caching class."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        """Initialize cache."""
        _LOGGER.debug("Initializing cache")
        params = params or {}

        cache_dir = params.get("cache_dir")
        #
        self._cache_time = params.get("cache_time", 0)
        self._domain = params.get("domain")

        if cache_dir:
            self._cache_dir = Path(cache_dir).resolve()

        if params.get("clean_dir", False):
            self._clean_dir()

    def _clean_dir(self, cache_time: int = 0) -> None:
        """Clean cache."""
        now_time = time.time()
        cache_time = max(cache_time, self._cache_time)

        if self._cache_dir and self._cache_dir.exists():
            _LOGGER.debug("Cleaning cache directory %s", self._cache_dir)
            files = os.listdir(self._cache_dir)
            _LOGGER.debug(files)
            for file_name in files:
                file_path = self._cache_dir / file_name
                try:
                    file_time = file_path.stat().st_mtime
                    if (file_time + cache_time) <= now_time:
                        file_path.unlink()
                except FileNotFoundError:  # pragma: no cover
                    pass

    def _get_file_path(self, file_name: str) -> Path:
        """Get path of cache file."""
        if self._domain:
            file_name = f"{self._domain}.{file_name}"
        return self._cache_dir / file_name

    def cached_for(self, file_name: str) -> float | None:
        """Return caching time of file if exists. Otherwise, None."""
        file_path = self._get_file_path(file_name)
        if not file_path.exists() or not file_path.is_file():
            return None

        file_time = file_path.stat().st_mtime
        return time.time() - file_time

    def is_cached(self, file_name: str, cache_time: int = 0) -> bool:
        """Return True if cache file is exists."""
        file_path = self._get_file_path(file_name)
        if not file_path.exists() or not file_path.is_file():
            return False

        file_time = file_path.stat().st_mtime
        cache_time = max(cache_time, self._cache_time)
        return (file_time + cache_time) > time.time()

    async def async_read_cache(self, file_name: str, cache_time: int = 0) -> Any | None:
        """Read cached data."""
        file_path = self._get_file_path(file_name)
        _LOGGER.debug("Read cache file %s", file_path)
        if not self.is_cached(file_name, cache_time):
            return None

        async with aiofiles.open(file_path, encoding="utf-8") as fp:
            return await fp.read()

    async def async_save_cache(self, file_name: str, content: Any) -> None:
        """Save data to cache."""
        if self._cache_dir:
            if not self._cache_dir.exists():
                self._cache_dir.mkdir(parents=True)

            file_path = self._get_file_path(file_name)
            _LOGGER.debug("Store cache file %s", file_path)

            async with aiofiles.open(file_path, "w", encoding="utf-8") as fp:
                await fp.write(content)
