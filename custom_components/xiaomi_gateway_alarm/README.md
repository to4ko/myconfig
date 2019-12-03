# Xiaomi Gateway Alarm

This custom component is based on [Xiaomi Raw](https://github.com/syssi/xiaomi_raw)

Credits: Thanks to [Rytilahti](https://github.com/rytilahti/python-miio) and [syssi](https://github.com/syssi/xiaomi_raw)

<img src="https://github.com/hekm77/homeassistant-config/blob/master/screenshots/switch_xiaomi_gateway_alarm.png" alt="Home Assistant Lovelace UI" 
/>
### Installation

Copy this folder to `<config_dir>/custom_components/xiaomi_gateway_alarm/`

Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
switch:
  - platform: xiaomi_gateway_alarm
    name: Xiaomi Gateway Alarm
    host: 192.168.1.x
    token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # Gateway token
```
[Retrieving the Access Token](https://www.home-assistant.io/integrations/vacuum.xiaomi_miio/#retrieving-the-access-token)
