import logging

from homeassistant.core import ServiceCall
from paramiko import SSHClient, AutoAddPolicy

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'ssh_command'


def setup(hass, hass_config):
    async def exec_command(call: ServiceCall):
        host = call.data.get('host', '172.17.0.1')
        port = call.data.get('port', 22)
        username = call.data.get('user', 'pi')
        password = call.data.get('pass', 'raspberry')
        command = call.data.get('command')

        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(host, port, username, password)
        stdin, stdout, stderr = client.exec_command(command)
        data = stdout.read()
        stderr.read()
        client.close()

        _LOGGER.info(data)

    hass.services.register(DOMAIN, 'exec_command', exec_command)

    return True
