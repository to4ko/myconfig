"""Config flow to configure Miio for Yeelink."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import *
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from miio import (
    Device as MiioDevice,
    DeviceException,
)

from . import (
    DOMAIN,
    CONF_MODEL,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

MIIO_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Optional(CONF_MODEL, default=''): str,
    vol.Optional(CONF_MODE, default=''): str,
})


async def check_miio_device(hass, user_input, errors):
    host = user_input.get(CONF_HOST)
    token = user_input.get(CONF_TOKEN)
    try:
        device = MiioDevice(host, token)
        info = await hass.async_add_executor_job(device.info)
    except DeviceException:
        info = None
        errors['base'] = 'cannot_connect'
    _LOGGER.debug('Miio Yeelink config flow: %s', {
        'user_input': user_input,
        'miio_info': info,
        'errors': errors,
    })
    if info is not None:
        if not user_input.get(CONF_MODEL):
            user_input[CONF_MODEL] = str(info.model or '')
        user_input['miio_info'] = dict(info.raw or {})
    return user_input


class MiioYeelinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self.host = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_HOST):
                self.host = user_input[CONF_HOST]
            await check_miio_device(self.hass, user_input, errors)
            info = user_input.get('miio_info')
            if info is not None:
                unique_id = format_mac(info['mac'])
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME),
                    data=user_input,
                )
        return self.async_show_form(
            step_id='user',
            data_schema=MIIO_CONFIG_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        name = discovery_info.get('name')
        self.host = discovery_info.get('host')
        mac_address = discovery_info.get('properties', {}).get('mac')
        if not name or not self.host or not mac_address:
            return self.async_abort(reason='not_xiaomi_miio')
        if not (name.startswith('yeelink') or name.startswith('yeelight')):
            _LOGGER.debug('Device %s discovered with host %s, not yeelink', name, self.host)
            return self.async_abort(reason='not_xiaomi_miio')
        unique_id = format_mac(mac_address)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured({CONF_HOST: self.host})
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update({
            'title_placeholders': {'name': f'{name}({self.host})'}
        })
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        errors = {}
        if isinstance(user_input, dict):
            await check_miio_device(self.hass, user_input, errors)
            cfg = {}
            opt = {}
            for k, v in user_input.items():
                if k in [CONF_HOST, CONF_TOKEN, 'miio_info']:
                    cfg[k] = v
                else:
                    opt[k] = v
            if user_input.get('miio_info'):
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, **cfg}
                )
                return self.async_create_entry(title='', data=opt)
        else:
            user_input = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, vol.UNDEFINED)): str,
                vol.Required(CONF_TOKEN, default=user_input.get(CONF_TOKEN, vol.UNDEFINED)):
                    vol.All(str, vol.Length(min=32, max=32)),
            }),
            errors=errors,
        )
