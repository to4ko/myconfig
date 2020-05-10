import homeassistant.loader as loader
import os
from distutils.dir_util import copy_tree
from datetime import datetime
from aiohttp import web

# Updated by NG to handle waiting for the MQTT message received. Error checking and more.
# Update Log
# - Error checking
# - Ajax/Timed checking for update mqtt message
# - No need to reload page to get update, as it will come thru the ajax check request

DOMAIN = 'zigbee2mqtt_networkmap'

DEPENDENCIES = ['mqtt']

CONF_TOPIC = 'topic'
DEFAULT_TOPIC = 'zigbee2mqtt'


async def async_setup(hass, config):
    fromDirectory = hass.config.path('custom_components', 'zigbee2mqtt_networkmap', 'www')
    toDirectory = hass.config.path('www', 'community', 'zigbee2mqtt_networkmap')

    copy_tree(fromDirectory, toDirectory)

    """Set up the zigbee2mqtt_networkmap component."""
    mqtt = hass.components.mqtt
    topic = config[DOMAIN].get(CONF_TOPIC, DEFAULT_TOPIC)
    entity_id = 'zigbee2mqtt_networkmap.map_last_update'
    tmpVar = type('', (), {})()  #tmpVar.received_update and update_data

    async def handle_webhook_trigger_update(hass, webhook_id, request):
        """Handle trigger update webhook callback."""
        await update_service(None)
        return web.json_response({"success": "ok"})

    async def handle_webhook_check_update(hass, webhook_id, request):
        """Handle check update webhook callback."""
        return web.json_response({"success": "ok", "update_received": bool(tmpVar.received_update),  "update_received_data": tmpVar.update_data, "last_update": tmpVar.last_update })


    # Register the Webhook for trigger update
    webhook_trigger_update_id = hass.components.webhook.async_generate_id()
    hass.components.webhook.async_register(
        DOMAIN, 'zigbee2mqtt_networkmap-webhook_trigger_update', webhook_trigger_update_id, handle_webhook_trigger_update)
    webhook_trigger_update_url = hass.components.webhook.async_generate_url(webhook_trigger_update_id)

    # Register the Webhook for trigger update
    webhook_check_update_id = hass.components.webhook.async_generate_id()
    hass.components.webhook.async_register(
        DOMAIN, 'zigbee2mqtt_networkmap-webhook_check_update', webhook_check_update_id, handle_webhook_check_update)
    webhook_check_update_url = hass.components.webhook.async_generate_url(webhook_check_update_id)

    f = open(hass.config.path('www', 'community', 'zigbee2mqtt_networkmap', 'settings.js'), "w")
    f.write("var webhook_trigger_update_url = '"+webhook_trigger_update_url+"';")
    f.write("\n")
    f.write("var webhook_check_update_url = '"+webhook_check_update_url+"';")
    f.close()


    # Listener to be called when we receive a message.
    async def message_received(msg):
        """Handle new MQTT messages."""
        # Save Response as JS variable in source.js
        payload = msg.payload.replace('\n', ' ').replace(
            '\r', '').replace("'", r"\'")
        last_update = datetime.now()
        f = open(hass.config.path(
            'www', 'community', 'zigbee2mqtt_networkmap', 'source.js'), "w")
        f.write("var last_update = new Date('" +
                last_update.strftime('%Y/%m/%d %H:%M:%S')+"');\nvar graph = \'"+payload+"\'")
        f.close()
        hass.states.async_set(entity_id, last_update)
        tmpVar.received_update = True
        tmpVar.update_data = payload
        tmpVar.last_update = last_update.strftime('%Y/%m/%d %H:%M:%S')

    # Subscribe our listener to the networkmap topic.
    await mqtt.async_subscribe(topic+'/bridge/networkmap/graphviz', message_received)

    # Set the initial state.
    hass.states.async_set(entity_id, None)
    tmpVar.received_update = False
    tmpVar.update_data = None
    tmpVar.last_update = None

    # Service to publish a message on MQTT.
    async def update_service(call):
        """Service to send a message."""
        tmpVar.received_update = False
        tmpVar.update_data = None
        tmpVar.last_update = None
        mqtt.async_publish(topic+'/bridge/networkmap', 'graphviz')

    hass.services.async_register(DOMAIN, 'update', update_service)
    return True
