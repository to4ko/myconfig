# to4ko's Home Assistant configuration


First of all - HUGE THANKS to [Alexxit](https://github.com/alexxit), [Omh](https://github.com/omhy/ha), [Vasilchuk](https://github.com/Anonym-tsk), [S_p_i_r_i_t_u_s](https://github.com/Spirituss), [lapatoc](https://github.com/bastshoes), [Vtel](https://github.com/zvldz), [Enzokot](https://github.com/Enzokot), [AVBor](https://github.com/avbor), [Andrew](https://github.com/andrewjswan) for help and support!

**Main Host:** 
  - HP Prodesk 400 G6 Mini
  - Intel i3-10100T
  - 2*8Gb Sk Hynix DDR4 SODIMM
  - 512Gb Samsung 970 Pro NVME

**Main Storage Host:** 
  - Synology DS1621+
  - 2*16Gb Micron DDR4 SODIMM
  - 8TB WD White as Media Storage
  - 2ea WD RED 2Tb (Storage section for critital files) in SHR1
  - 256Gb Adata SX6000 Lite as NVME read cache

**Backup Storage Host:** 
  - Synology DS220J
  - 2ea WD RED 2Tb (Storage section for critital files) in SHR1

**Remote Storage Host:** 
  - Synology DS215J
  - 2ea WD RED 2Tb (Storage section for critital files) in SHR1

**Network(WAN 500mb\s):**
  - Unifi Dream Machine Pro
  - Unifi Switch 16-150W
  - Unifi Switch 8-60W (3ea)
  - Unifi Switch Mini
  - Unifi AC-AP-Lite (2ea)
  - Unifi AC AP Pro (3ea)
  - Unifi NanoHD (not in use)
  - Unifi AP AC Mesh with UMA-D

**UPS**
  - Ippon Smart Power Pro 1200
  - Ippon Back Basic 1050
  - Ippon Back Basic 650
  - CyberPower UT650EG 
  
**Surveillance:** 
  - Unifi Protect on Unifi Dream Machine Pro with 3Tb WD Purple
  - Ubiquiti G3 Flex Cameras (6ea)
  - Digma 100
  - Cheap Aliexpress Pinhole cam via iSpyAgent DVR (Docker on DS1621+)

**Xiaomi\Aqara WiFi Devices:**
  - Xiaomi Gateway v3 (6ea) via [GW3 by AlexxIT](https://github.com/AlexxIT/XiaomiGateway3)
  - Yeelight LED Ceiling Lamp650 (YLXD02YL) (2ea)
  - Yeelight LED Ceiling Lamp Pro White 960mm (YLXD08YL)
  - Yeelight LED Ceiling Light Pro 940mm White (YLXD56YL) 
  - Yeelight LED Ceiling Lamp 480mm White (YLXD05YL)
  - Yeelight LED Light Strip (YLDD01YL)
  - Yeelight LED Light Strip Plus (YLDD04YL) 
  - Yeelight Jiaoyue 260 (YLXD62YI)
  - Xiaomi Yeelight Bedside Lamp 2
  - Yeelight Bedside Lamp D2
  - not in use - Xiaomi Philips Smart LED Bulb E27 White (9290012800) (2ea)
  - Xiaomi Philips Zhirui Downlight (9290012799)
  - Yeelight Xiaomi Led Bulb (Color) (YLDP06YL) (2ea)
  - Yeelight Xiaomi Led Tunable Bulb (White) (YLDP05YL) (2ea)
  - not in use - Xiaomi Smart WiFi Power Strip (2ea)
  - Xiaomi Air Purifier 2s
  - Xiaomi Wifi Plugs v2 (4ea)
  - not in use - Xiaomi Wifi Plugs v2 (3ea)
  - not in use - Xiaomi IR controller

**At the moment, all my Zigbee devices are connected via Xiaomi Gateways, except of DIY Geiger meter (it's sitting on SLS Gateway)**

**Xiaomi\Aqara Zigbee Devices:**
  - Aqara Wall Socket (21ea)
  - Aqara Wall Switch Double (4ea)
  - Aqara D1 Wall Switch Tripple (1ea)
  - not in use - Aqara Wall Switch Single (0ea)
  - Aqara Wireless Switch Double (6ea)
  - Aqara\Xiaomi Door Sensor (25ea)
  - Aqara Water Leak Sensor (3ea)
  - Aqara Vibration Sensor (3ea)
  - Aqara\Xiaomi Motion Sensor (14ea)
  - Aqara\Xiaomi Wireless Button (9ea)
  - Aqara\Xiaomi Temp\Himidity sensor (12ea)
  - Xiaomi Plug (26ea)
  - Xiaomi Smoke Detector (1ea)
  - Xiaomi Natural Gas Detector (1ea)
  - Aqara Zigbee Relay (1ea)
  - Xiaomi Light Sensor (2ea)
  - Aqara Opple Wireless Switch (2ea)
  - not in use - Aqara Opple Wireless Switch (4ea)

**ESPHome devices:**
  - Sonoff Basic (2ea)
  - not in use - Sonoff S26 Plugs (3ea)
  - Sonoff Pow R2 (2ea)
  - Sonoff L1
  - Sonoff Mini (3ea)
  - Sonoff 4ch
  - Blitzwolf SHP2 (10ea) and SHP6 (4ea)
  - Blitzwolf LT11
  - not in use - Blitzwolf SS5 dual gang relay
  - MH-Z19B CO2 sensors on Wemos D1 mini (1ea)
  - ESP32 - Domofon (Intercom helper) with Non-Envasive Power meter
  - ESP32 - Node K - Kitchen MH-Z19B, BME280, BHI1750, Water Filter Counters, IR controller
  - ESP32 - Node B - Bathroom Relays (Water vales, Exhaust Fans), Night LED Strip, Dallas sensors on water pipes (Hot and Cold)
  - ESP32 - Node MB - Master Bedroom MH-Z19B, BME280, BHI1750, Dallas sensors (Heating pipe and Outside)
  - ESP32 - Node V - Vova Room MH-Z19B, BME280, BHI1750, Dallas sensor (Heating pipe)
  - ESP32 - Hood K - Kitchen Hood Fan\Light Control, BME280, Dallas and max6675 
  - ESP32 - BLE Tracker (Nut find 3)
  - ESP32 - BLE Tracker (Xiaomi Scale 2 and Nut find 3)
  - ESP8266 Oven K - Kitchen Oven K-type Thermocouple via max6675
  - ESP32 PZEM HB - Hall Big Breaker Box PZEM-004T
  - Digma IR Remote (3ea)
  - not in use - ESP01 (deepsleep on 14500 LiOn batteries) air freshener (Deerma Aerosol Dispenser DEM-PX830)
  - ESP01 Weight Cell
  - D1 Mini LED Bed light
  - D1 Mini S - Sasha Room MH-Z19B, BME280, BHI1750, WS2812 LES Strip, HA API Watchdog
  - D1 Mini Air Freshener with Figaro air sensor
  - BTF Adressable LED strip Controller (based on esp8265) flashed with ESPHome

**Other Devices:**
  - SLS Gateway
  - DIYRuZ_Geiger Sensor via SLS GW
  - not in use - Google Home Mini (6ea)
  - not in use - Sonoff Micro via [SonoffLan by AlexxIT](https://github.com/AlexxIT/SonoffLAN) (self powering down)
  - Shelly EM - energy monitoring (comparing to PZEM...not shure which one os better)
  - Shelly 1PM
  
**Main Host Software:**
  - Debian 11
  - Home Assistant Core Supervised
  - PostgreSQL

**Add-On's:** 
  - File Editor
  - Custom deps deployment
  - ESPhome
  - Grafana
  - Hass.io Google Drive Backup
  - IDE
  - Log Viewer
  - Portainer
  - RPC shutdown

**DB used:**
  - PostgreSQL
  - InfluxDB

**Scripts:**
  - **ipmi_mqtt.sh**  Publishing IPMI, Temp and other system monitoring info to MQTT broker
  - **ha_log_parser.sh**  Backing up HA log to my home directory and splitting it to Error, Warning, Info message type as well as keeping full log. Logs rotated every 5 days.
  - **ya_weather.sh**  Yandex weather fcst ( thanks to [Ivan](https://t.me/configit)  )
  - **root_dev.sh**  Host root device name for monitoring.
  - **gitignore.sh**  bash script to be used after gitigrone file updated
  - **gitupdate.sh**  git upload


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