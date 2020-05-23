#  Copyright (c) 2018, Vladimir Maksimenko <vl.maksime@gmail.com>
#  Copyright (c) 2019, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#
# Version 3.0
"""Cache controller."""

import logging
import os
import time

_LOGGER = logging.getLogger(__name__)


class Cache:
    """Data caching class."""

    def __init__(self, params=None):
        """Initialize cache."""
        _LOGGER.debug("Initializing cache")
        params = params or {}

        self._cache_dir = params.get("cache_dir", "")
        self._cache_time = params.get("cache_time", 0)
        self._domain = params.get("domain")

        if self._cache_dir:
            self._cache_dir = os.path.abspath(self._cache_dir)

        if params.get("clean_dir", False):
            self._clean_dir()

    def _clean_dir(self):
        """Clean cache."""
        now_time = time.time()

        if self._cache_dir and os.path.exists(self._cache_dir):
            _LOGGER.debug("Cleaning cache directory %s", self._cache_dir)
            files = os.listdir(self._cache_dir)
            _LOGGER.debug(files)
            for file_name in files:
                file_path = os.path.join(self._cache_dir, file_name)
                try:
                    file_time = os.path.getmtime(file_path)
                    if (file_time + self._cache_time) <= now_time:
                        os.remove(file_path)
                except FileNotFoundError:
                    pass

    def _get_file_path(self, file_name):
        """Get path of cache file."""
        if self._domain:
            file_name = ".".join((self._domain, file_name))
        return os.path.join(self._cache_dir, file_name)

    def is_cached(self, file_name):
        """Return True if cache file is exists."""
        result = False

        file_path = self._get_file_path(file_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            file_time = os.path.getmtime(file_path)
            now_time = time.time()

            result = (file_time + self._cache_time) >= now_time

        return result

    def read_cache(self, file_name):
        """Read cached data."""
        file_path = self._get_file_path(file_name)
        _LOGGER.debug("Read cache file %s", file_path)
        if self.is_cached(file_name):
            file = open(file_path)
            content = file.read()
            file.close()
        else:
            content = None

        return content

    def save_cache(self, file_name, content):
        """Save data to cache."""
        if self._cache_dir:
            if not os.path.exists(self._cache_dir):
                os.makedirs(self._cache_dir)

            file_path = self._get_file_path(file_name)
            _LOGGER.debug("Store cache file %s", file_path)

            file = open(file_path, "w")
            file.write(content.decode("utf-8"))
            file.close()
