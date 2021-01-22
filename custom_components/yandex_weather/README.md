# Yandex Weather custom component for Home-assistant
This is custom component for Home-assistant. 
Component work with Home-assistant startinf 0.92 or later.

# Installation

# Step 1

Create a directory called `yandex_weather` in the `<config directory>/custom_components/` directory on your Home Assistant instance.
Install this component by copying the files in [`/custom_components/yandex_weather/`] from this repo into the new `<config directory>/custom_components/yandex_weather/` directory you just created.

# Step 2

Add this to your `configuration.yaml`

```yaml
weather:
  - platform: yandex_weather
    api_key: <yandex_api_key>    
```
