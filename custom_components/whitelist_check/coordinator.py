import asyncio
import logging
import async_timeout
from datetime import timedelta
from urllib.parse import urlparse

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, DEFAULT_HOSTS, CONF_CUSTOM_HOSTS, CONF_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

class WhitelistUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        interval_seconds = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval_seconds),
        )
        self.entry = entry
        self.session = async_get_clientsession(hass)

    def get_all_hosts(self):
        hosts = DEFAULT_HOSTS.copy()
        custom = self.entry.options.get(CONF_CUSTOM_HOSTS, {})
        if isinstance(custom, dict):
            hosts.update(custom)
        return hosts

    async def _async_update_data(self):
        hosts = self.get_all_hosts()
        results = {}

        tasks = [self._check_host(host, config) for host, config in hosts.items()]
        responses = await asyncio.gather(*tasks)

        for host, data in responses:
            results[host] = data
        
        return results

    async def _check_host(self, host: str, config: dict):
        method = config.get("method", "GET")
        is_online = False
        status_text = "Unknown"

        # Перехват специального API статуса GitHub
        if config.get("type") == "github_status":
            is_online, status_text = await self._check_github_status_api()
        
        # Если выбран строгий PING
        elif method == "PING":
            clean_host = host
            if "://" in host:
                try:
                    parsed = urlparse(host)
                    clean_host = parsed.hostname or host
                except Exception:
                    pass
            is_online = await self._check_ping(clean_host)
            status_text = "PING OK" if is_online else "PING Failed"
            
        # Стандартные веб-запросы
        else:
            url = host if host.startswith("http") else f"https://{host}"
            is_online, status_text = await self._check_http(url, method)

        return host, {
            "is_online": is_online,
            "status_text": status_text,
            "config": config
        }

    async def _check_github_status_api(self) -> tuple[bool, str]:
        """Запрос к официальному API статуса компонентов GitHub."""
        url = "https://www.githubstatus.com/api/v2/summary.json"
        try:
            async with async_timeout.timeout(5):
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        desc = data.get("status", {}).get("description", "Unknown")
                        # Считаем систему условно онлайн, если получили ответ. 
                        # Аптайм конкретных сервисов отработает через текст и иконку.
                        return "all systems operational" in desc.lower(), desc
                    return False, f"HTTP {response.status}"
        except Exception:
            pass
        return False, "Timeout / Offline"

    async def _check_http(self, url: str, method: str) -> tuple[bool, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        try:
            async with async_timeout.timeout(5):
                async with self.session.request(method, url, allow_redirects=True, headers=headers) as response:
                    status = response.status
                    
                    if status in [403, 451]:
                        return False, f"HTTP {status} (Blocked)"
                    
                    return True, f"HTTP {status}"
        except Exception:
            pass
        
        # Фолбек на системный пинг
        try:
            parsed_url = urlparse(url)
            host = parsed_url.hostname or url
            clean_host = host.replace("https://", "").replace("http://", "").split("/")[0]
            if await self._check_ping(clean_host):
                return True, "PING OK (HTTP Failed)"
        except Exception:
            pass
            
        return False, "Timeout / Offline"

    async def _check_ping(self, host: str) -> bool:
        try:
            clean_host = host.replace("https://", "").replace("http://", "").split("/")[0]
            process = await asyncio.create_subprocess_shell(
                f"ping -c 1 -W 2 {clean_host}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False
