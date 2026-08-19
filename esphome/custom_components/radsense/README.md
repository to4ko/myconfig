
## Description

ESPHome custom component sensor for Climateguard RadSens 1v2

## Deployment

First of all get the code:
```bash
git clone https://github.com/maaad/RadSens1v2 /usr/share/hassio/homeassistant/esphome/RadSens1v2
```
Add to device config for climateguard/RadSens
```yaml
esphome:
  ...
 libraries:
   - Wire
   - "climateguard/ClimateGuard RadSens"
 includes:
   - RadSens1v2/_CG_RadSens.h

 i2c:

...

sensor:
  - platform: custom
    lambda: |-
      auto rad_sens = new MyRadSens();
      App.register_component(rad_sens);
      return {rad_sens->IntensityDynamic_Sensor,rad_sens->IntensityStatic_Sensor, rad_sens->CurrentCPM_Sensor, rad_sens->MaxCPM_Sensor,rad_sens->Sensivity_Sensor};
    sensors:
      - name: "Dynamic intensity"
        id: dynamic_intensity
        accuracy_decimals: 1
        unit_of_measurement: μR/h
        state_class: measurement
      - name: "Static intensity"
        accuracy_decimals: 1
        unit_of_measurement: μR/h
        state_class: measurement
      - name: "Current CPM"
        accuracy_decimals: 1
        unit_of_measurement: CPM
        state_class: measurement
      - name: "Max CPM"
        accuracy_decimals: 1
        unit_of_measurement: CPM
        state_class: measurement
      - name: "Device Sensivity"
        id: sensivity
        state_class: measurement
        entity_category: diagnostic
```

HA service call to set device sensivity:
```yaml
service: esphome.radsens_set_sensivity 
data:
  sensivity: "105"
```


## Known issues

#### RadSens 1v5
[1v5 boards workaround](https://github.com/maaad/RadSens1v2/issues/3#issuecomment-1289578773)



## References

[Official RadSens library by ClimateGuard](https://github.com/climateguard/RadSens)

[ESPHome Documentation](https://esphome.io/index.html)


