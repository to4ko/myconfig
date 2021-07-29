brightness = data.get("brightness")
screen_time = data.get("screen_time")
fully_command = data.get("cmd")
motion_sen = data.get("motion_sen")
motion_on = data.get("motion_on")
acoustic_sen = data.get("acoustic_sen")
acoustic_on = data.get("acoustic_on")
dark_off = data.get("dark_off")
dark_threshold = data.get("dark_threshold")
new_url = data.get("new_url")

start_url = True
# Screen Brightness
if brightness is not None:
    service_data = {"cmd": "setStringSetting", "key": "screenBrightness", "value": brightness}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
#Screen Time On
if screen_time is not None:
    service_data = {"cmd": "setStringSetting", "key": "timeToScreenOffV2", "value": screen_time}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
#Send a command to fully
if fully_command is not None:
    service_data = {"cmd": fully_command}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# Motion Sensitivity
if motion_sen is not None:
    service_data = {"cmd": "setStringSetting", "key": "motionSensitivity", "value": motion_sen}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# Motion Activate
if motion_on is not None:
    service_data = {"cmd": "setBooleanSetting", "key": "motionDetection", "value": motion_on}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# Acoustic Activate
if acoustic_on is not None:
    service_data = {"cmd": "setBooleanSetting", "key": "motionDetectionAcoustic", "value": acoustic_on}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# Acoustic Sensitivity
if acoustic_sen is not None:
    service_data = {"cmd": "setStringSetting", "key": "motionSensitivityAcoustic", "value": acoustic_sen}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# Screen turns off with darkness
if dark_off is not None:
    service_data = {"cmd": "setBooleanSetting", "key": "screenOffInDarkness", "value": dark_off}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# Darkness threshold
if dark_threshold is not None:
    service_data = {"cmd": "setStringSetting", "key": "darknessLevel", "value": dark_threshold}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# Load new URL
if new_url is not None:
    service_data = {"cmd": "loadUrl", "url": new_url}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    start_url = False
# If no data is entered at all the the start URL is loaded
if start_url is True:
    service_data = {"cmd": "loadStartUrl"}
    hass.services.call("rest_command", "kiosk_command", service_data, False)
    logger.info("Fully Kiosk Test Variable")