# My Home Assistant configuration


First of all - HUGE THANKS to [Omh](https://github.com/omhy/ha), [OXOTH1K](https://github.com/OXOTH1K/homeassistant) and [AlexKvazis](https://github.com/kvazis/homeassistant) for cool stuff borrowed from their configs. Special thanks to [@Vasilchuk](https://github.com/Anonym-tsk), [@S_p_i_r_i_t_u_s], [@lapatoc](https://github.com/bastshoes) for help and support! 

And all the rest from [Home Assistant Channel](https://t.me/homassistant) and [ESPHome Channel](https://t.me/esphome)


Main Server: 
  - Xeon E5-2620v3 cooled by Noctua NH-U12DX i4
  - 64gb ECC DDR4 RAM
  - 128Gb Kingston SSD as Boot drive
  - 512Gb ADATA 8200Pro Raid 1 as Root drive
  - 256Gb ADATA 8200Pro NVME for DB
  - 7ea WD RED 2Tb (NAS section) in HW Raid 6 via Adaptec 71605
  - 2ea Samsung 840 Pro 256Gb in HW Raid 0 as temp drive via Adaptec 71605
  - 1Tb WD Purple for cameras
  - 3ea WD Green in HW Raid0 (Torrent heap) via Adaptec 71605
  - Corsair HX1200i
  - Fractal Design XL R2 with be quite Pure Wings 2 140mm PWM fans (6ea)

MQTT\Zigbee2MQTT Server:
  - Celeron j3455
  - 16gb DDR3 RAM
  - 120Gb SSD Crucial BX500
  - CC2538 Zigbee Stick

Backup Server:
  - Celeron j3455
  - 16gb DDR3 RAM
  - 120Gb SSD Crucial BX500

Test Server:
  - Raspberry Pi 3B+
  - 120Gb SSD Crucial BX500

Network(500mb\s):
  - Ubiquiti USG 3
  - Switch 24
  - Switch 8-60W (3ea)
  - UAP-AC-AP-Lite (5ea)
  - Tp-Link "dumb" switch (1ea)
  
Surveillance: 
  - Ubiquiti Video (running as service)
  - Ubiquiti G3 Flex Cameras (4ea)
  - Digma 100
  - Cheap Aliexpress Pinhole cam via Motioneye (motion detection and stream recording)

Smart Home:
  Xiaomi\Aqara:
  - Xiaomi Gateway (7ea) used as alarm devices (audio\visual)
  - Yeelight 650 (2ea)
  - Yeelight Pro 90W
  - Yeelight 480
  - Yeelight LED Strip
  - Philips Xiaomi E27 Bulb (2ea)
  - Yeelight E27 Color Led Bulb v2 (2ea)
  - Aqara Wall Socket (12ea)
  - Aqara Wall Switch 2 Rockers (6ea)
  - Aqara Wireless Switch 2 Rockers (6ea)
  - Aqara Door Sensor (26ea)
  - Aqara Water Leak Sensor (3ea)
  - Aqara Vibration Sensor (3ea)
  - Aqara\Xiaomi Motion Sensor (12ea)
  - Aqara Wireless Switch (7ea)
  - Aqara Temp\Himidity\Pressure sensor (3ea)
  - Xiaomi Zigbee Plug (22ea)
  - Xiaomi Temp\Humidity Sensor (8ea)
  - Xiaomi Wireless switch (6ea)
  - Xiaomi Smart WiFi Power Strip (1ea)
  - Xiaomi Smartmi Humidifier 2
  - Xiaomi Air Purifier 2s
  - Xiaomi Wifi Plugs v2 (7ea) - used to restart Gateways remotely
  - Xiaomi IR controller
  - Xiaomi Smoke Detector (1ea)
  - Xiaomi Natural Gas Detector (1ea)
  - Aqara Zigbee Relay (3ea)
  - Google Home Mini (5ea)
  
  ESPHome devices:
  - Sonoff Basic
  - Sonoff S26 Plugs
  - Blitzwolf SHP2 (2ea) and SHP6 (2ea)
  - MH-Z19B CO2 sensors on Wemos D1 mini, 3ea 
  - ESP32 - Domofon (Intercom helper) with Non-Envasive Power meter
  - ESP32 - Kitchen Air valve, hood fan\light with IR controller
  - ESP32 - Reverse Osmos Water Filter resource counter based on cheap flow meters.
  - Blitzwolf LT11
  - Digma IR Remote (2ea)
      
Software:
  - Ubuntu Server 20.04 LTS
  - Hass.Io in Docker
  - MotionEye
  - Mosquitto

DB used:
  - PostgreSQL
  - InfluxDB

Add-On's: 
  - AirCast
  - File Editor
  - Custom deps deployment
  - Dropbox Sync
  - ESPhome
  - Grafana
  - Hass.io Google Drive Backup
  - IDE
  - Log Viewer
  - Portainer
  - RPC shutdown
  - zigbee2mqtt


  Scripts:
  - **ipmi_mqtt.sh**  Publishing IPMI, Temp and other system monitoring info to MQTT broker
  - **ha_log_parser.sh**  Backing up HA log to my home directory and splitting it to Error, Warning, Info message type as well as keeping full log. Logs rotated every 5 days.
  - **ya_weather.sh** Yandex weather fcst ( thanks to [Ivan](https://t.me/configit)  )
  - **root_dev.sh** Host root device name for monitoring.


[psmqtt](https://github.com/eschava/psmqtt) used to publish host machine status.

# Main page
![Main Page](https://i.ibb.co/BTcVZtt/page1.jpg)
# Security page
![Security page](https://i.ibb.co/vxyRHD3/page2.jpg)
# Devices by room
![Devices by room](https://i.ibb.co/KV7CD01/page3.jpg)
# Sensors by room
![Sensors by room](https://i.ibb.co/vL2M1T1/page4.jpg)
# Utility counters
![Utility counters](https://i.ibb.co/mSYwCjt/page5.jpg)
# Power load
![Power loads](https://i.ibb.co/tsCh1sy/page6.jpg)
# Device trackers
![Device trackers](https://i.ibb.co/XWCCyRY/page7.jpg)
# CCTV
![CCTV](https://i.ibb.co/JnT0sFF/page8.jpg)
# Climate
![Climate](https://i.ibb.co/SvPRtrx/page9.jpg)
# System monitoring
![System monitoring](https://i.ibb.co/sy2KdM0/page10.jpg)
# Main Server Hardware Monitoring
![Main Server Health](https://i.ibb.co/V3rTvPy/page11.jpg)
# Radio
![Radio](https://i.ibb.co/wdNPVvz/page12.jpg)
# Home\Office PCs Telemetry
![Telemetry](https://i.ibb.co/DDnKYWf/page14.jpg)
# Cross Servers Utility Counters
![Utility Counters(cross servers)](https://i.ibb.co/Hx6vrTg/page15.jpg)