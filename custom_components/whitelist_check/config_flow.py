import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, CONF_CUSTOM_HOSTS, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL

class WhitelistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="White List Check",
                data={},
                options={CONF_CUSTOM_HOSTS: {}}
            )
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WhitelistOptionsFlow()


class WhitelistOptionsFlow(config_entries.OptionsFlow):
    def __init__(self):
        self.selected_host = None

    async def async_step_init(self, user_input=None):
        current_options = self.config_entry.options or {}
        custom_hosts = dict(current_options.get(CONF_CUSTOM_HOSTS, {}))

        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                return await self.async_step_add_host()
            elif action == "edit":
                return await self.async_step_select_edit_host()
            elif action == "remove":
                return await self.async_step_remove_host()
            elif action == "settings":
                return await self.async_step_settings()

        # Добавили новый пункт настроек
        actions = {"add": "Добавить новый хост", "settings": "Настройки интервала опроса"}
        if custom_hosts:
            actions["edit"] = "Изменить существующий хост"
            actions["remove"] = "Удалить существующий хост"

        schema = vol.Schema({
            vol.Required("action", default="add"): vol.In(actions)
        })

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_settings(self, user_input=None):
        """Новое окно: Настройка глобального интервала."""
        current_options = dict(self.config_entry.options)

        if user_input is not None:
            current_options[CONF_UPDATE_INTERVAL] = user_input[CONF_UPDATE_INTERVAL]
            return self.async_create_entry(title="", data=current_options)

        current_interval = current_options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        
        schema = vol.Schema({
            vol.Required(CONF_UPDATE_INTERVAL, default=current_interval): vol.All(int, vol.Range(min=10, max=86400))
        })
        
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_add_host(self, user_input=None):
        current_options = dict(self.config_entry.options)
        custom_hosts = dict(current_options.get(CONF_CUSTOM_HOSTS, {}))

        if user_input is not None:
            host = user_input["host"].strip()
            custom_hosts[host] = {
                "name": user_input["name"].strip(),
                "method": user_input["method"],
                "description": user_input.get("description", "")
            }
            current_options[CONF_CUSTOM_HOSTS] = custom_hosts
            return self.async_create_entry(title="", data=current_options)

        schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("name"): str,
            vol.Optional("method", default="GET"): vol.In(["GET", "POST", "HEAD", "PUT", "PING"]),
            vol.Optional("description", default=""): str,
        })
        return self.async_show_form(step_id="add_host", data_schema=schema)

    async def async_step_select_edit_host(self, user_input=None):
        current_options = self.config_entry.options or {}
        custom_hosts = dict(current_options.get(CONF_CUSTOM_HOSTS, {}))

        if user_input is not None:
            self.selected_host = user_input["host"]
            return await self.async_step_edit_host_details()

        hosts_list = {k: f"{v.get('name', 'Без имени')} ({k})" for k, v in custom_hosts.items()}
        schema = vol.Schema({
            vol.Required("host"): vol.In(hosts_list)
        })
        return self.async_show_form(step_id="select_edit_host", data_schema=schema)

    async def async_step_edit_host_details(self, user_input=None):
        current_options = dict(self.config_entry.options)
        custom_hosts = dict(current_options.get(CONF_CUSTOM_HOSTS, {}))
        
        current_data = custom_hosts.get(self.selected_host, {})

        if user_input is not None:
            custom_hosts[self.selected_host] = {
                "name": user_input["name"].strip(),
                "method": user_input["method"],
                "description": user_input.get("description", "")
            }
            current_options[CONF_CUSTOM_HOSTS] = custom_hosts
            return self.async_create_entry(title="", data=current_options)

        schema = vol.Schema({
            vol.Required("name", default=current_data.get("name", "")): str,
            vol.Required("method", default=current_data.get("method", "GET")): vol.In(["GET", "POST", "HEAD", "PUT", "PING"]),
            vol.Optional("description", default=current_data.get("description", "")): str,
        })
        
        return self.async_show_form(
            step_id="edit_host_details", 
            data_schema=schema,
            description_placeholders={"host_name": self.selected_host}
        )

    async def async_step_remove_host(self, user_input=None):
        current_options = dict(self.config_entry.options)
        custom_hosts = dict(current_options.get(CONF_CUSTOM_HOSTS, {}))

        if user_input is not None:
            host_to_remove = user_input["host"]
            if host_to_remove in custom_hosts:
                del custom_hosts[host_to_remove]
            current_options[CONF_CUSTOM_HOSTS] = custom_hosts
            return self.async_create_entry(title="", data=current_options)

        hosts_list = {k: f"{v.get('name', 'Без имени')} ({k})" for k, v in custom_hosts.items()}
        schema = vol.Schema({
            vol.Required("host"): vol.In(hosts_list)
        })
        return self.async_show_form(step_id="remove_host", data_schema=schema)
