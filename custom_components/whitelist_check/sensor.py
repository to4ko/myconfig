from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    hosts = coordinator.get_all_hosts()
    
    entities = []
    for host, config in hosts.items():
        entities.append(WhitelistUnifiedSensor(coordinator, host, config))
        
    async_add_entities(entities)

class WhitelistUnifiedSensor(CoordinatorEntity, SensorEntity):
    """Единый датчик статуса сетевого узла."""

    def __init__(self, coordinator, host, config):
        super().__init__(coordinator)
        self.host = host
        self._name = config.get("name", host)
        
    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self.host}"

    @property
    def device_info(self) -> DeviceInfo:
        """Привязываем датчик к главному устройству White List Check."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="White List Check",
            manufacturer="Eugen417",
            model="Network & VPN Monitor",
        )

    @property
    def native_value(self):
        """Главный статус на дашборде."""
        host_data = self.coordinator.data.get(self.host) or {}
        is_online = host_data.get("is_online", False)
        status_text = host_data.get("status_text", "Ожидание...")
        config = host_data.get("config") or {}
        
        # Если это статус платформы GitHub — выводим ответ API без изменений
        if config.get("type") == "github_status":
            return status_text
        
        if is_online:
            return "Подключено" 
        return status_text

    @property
    def icon(self):
        """Динамическая иконка."""
        host_data = self.coordinator.data.get(self.host) or {}
        is_online = host_data.get("is_online", False)
        status_text = host_data.get("status_text", "").lower()
        config = host_data.get("config") or {}
        
        # Исправленная логика иконок для статуса GitHub
        if config.get("type") == "github_status":
            if not is_online and status_text in ["timeout / offline", "unknown"]:
                return "mdi:cloud-off-outline"      # Полностью оффлайн
            if "all systems operational" in status_text:
                return "mdi:github"                 # Всё отлично работает
            if "minor" in status_text or "degraded" in status_text:
                return "mdi:cloud-alert"            # Частичные проблемы (Actions/Webhooks)
            return "mdi:alert-octagon-outline"      # Крупный глобальный сбой (Major Outage)

        # Стандартные иконки для сетевых узлов
        if is_online:
            return "mdi:check-network-outline"
        return "mdi:network-off-outline"

    @property
    def extra_state_attributes(self):
        """Детальная информация при клике."""
        host_data = self.coordinator.data.get(self.host) or {}
        config = host_data.get("config") or {}
        return {
            "target_host": self.host,
            "method": config.get("method", "GET"),
            "description": config.get("description", "Нет описания"),
            "raw_status": host_data.get("status_text", "Unknown")
        }
