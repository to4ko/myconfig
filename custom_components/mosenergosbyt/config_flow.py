from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from custom_components.mosenergosbyt import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class MosenergosbytFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow for Mosenergosbyt config entries."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow."""
        self._current_type = None
        self._current_config = None
        self._devices_info = None

        import voluptuous as vol
        from collections import OrderedDict

        schema_user = OrderedDict()
        schema_user[vol.Required(CONF_USERNAME)] = str
        schema_user[vol.Required(CONF_PASSWORD)] = str
        self.schema_user = vol.Schema(schema_user)

    async def _check_entry_exists(self, username: str):
        current_entries = self._async_current_entries()

        for config_entry in current_entries:
            if config_entry.data.get(CONF_USERNAME) == username:
                return True

        return False

    # Initial step for user interaction
    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.schema_user)

        username = user_input[CONF_USERNAME]

        if await self._check_entry_exists(username):
            return self.async_abort("already_exists")

        from .mosenergosbyt import API

        try:
            api = API(username=username, password=user_input[CONF_PASSWORD])
            if not await api.login():
                return self.async_abort("invalid_credentials")

        except:  # @TODO: more specific exception handling
            return self.async_abort("authentication_error")

        return self.async_create_entry(title="User: " + username, data=user_input)

    async def async_step_import(self, user_input=None):
        if user_input is None:
            return self.async_abort("unknown_error")

        username = user_input[CONF_USERNAME]

        if await self._check_entry_exists(username):
            return self.async_abort("already_exists")

        return self.async_create_entry(title="User: " + username, data={CONF_USERNAME: username})