<h1 align="center"><a name="top"></a>
  <a name="logo"><img src="https://raw.githubusercontent.com/to4ko/myconfig/master/images/home.jpg" width="100"></a>
  <br>
  My Smart Home Configuration
</h1>

<div align="center"><a name="menu"></a>
  <h4>
    <a href="https://github.com/to4ko/myconfig#hardware-configuration">
      Hardware Configuration
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#hardware-evolution">
      Hardware Evolution
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#smart-devices">
      Smart Devices
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#networking">
      Networking
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#surveillance">
      Surveillance
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#screenshots">
      Screenshots
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#links">
      Links
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#chats">
      Chats
    </a>
  </h4>
</div>

# Hardware Configuration
**Main Unit - HP Prodesk 600 G6 Mini** 
  - HP Prodesk 600 G6 Mini
  - Intel i5-10600
  - 2*8Gb Samsung DDR4 SODIMM
  - 512Gb ADATA SX8200 Pro 512Gb NVME
  - Buro BU-BT40C
  - Google Coral m.2

**Main Storage Unit - Synology DS1621+** 
  - 2*16Gb Crucial DDR4 SODIMM
  - 8TB WD White as Media Storage
  - 2ea WD Purple 4Tb (Storage section for critical files) in SHR1
  - Adata SX6000 Lite 256Gbas NVME read cache
  - 2ea Samsung 840 Pro 256Gb as Fast "Docker" Storage

**Backup Storage Unit - Synology DS920+**
  - 16Gb Kingston DDR4 SODIMM
  - 2ea WD Purple 4Tb (Storage section for critical files) in SHR1 
  - 2ea Samsung 860 EVO 250Gb in SHR1

**Remote Storage Unit - Synology DS220+** 
  - 2ea Seagate Skyhawk 4Tb in SHR1
  - Upcoming remote HA server

**UPS**
  - Ippon Back Basic 1500
  - Ippon Smart Power Pro 1200
  - Ippon Back Basic 1050
  - Ippon Back Basic 650
  - CyberPower UT650EG 

# Networking
  - Unifi Dream Machine Pro, WAN1 500mb\s + WAN2 500mb\s + LTE Backup
  - Unifi Enterprise Switch 24 PoE
  - Unifi Switch 8-60W (4ea)
  - not in use - Unifi Switch Mini
  - not in use - Unifi Switch Light 8 PoE
  - Unifi AC AP Lite (2ea)
  - Unifi AC AP Pro (3ea)
  - Unifi AP AC Mesh with UMA-D

# Surveillance
  - Unifi Protect on Unifi Dream Machine Pro with 3Tb WD Purple
  - Ubiquiti G3 Flex Cameras (6ea)
  - Digma 100
  - Aliexpress Pinhole camera via Synology Surveillance Station on DS1621+

# Smart Devices
**Lights**
  - Yeelight LED Ceiling Lamp650 (YLXD02YL) (2ea)
  - Yeelight LED Ceiling Lamp Pro White 960mm (YLXD08YL)
  - Yeelight LED Ceiling Light Pro 940mm White (YLXD56YL) 
  - Yeelight LED Ceiling Lamp 480mm White (YLXD05YL)
  - Yeelight LED Light Strip (YLDD01YL)
  - Yeelight LED Light Strip Plus (YLDD04YL)
  - Yeelight LED Light Strip 1S (YLDD05YL) (3ea)
  - Yeelight LED Bulb (Color) (YLDP06YL) (2ea)
  - Yeelight LED Tunable Bulb (White) (YLDP05YL) (2ea)
  - Yeelight LED Bedside Lamp 2
  - Xiaomi Philips Zhirui Downlight (9290012799)
  - not in use - Yeelight Jiaoyue 260 (YLXD62YI)
  - not in use - Xiaomi Philips Smart LED Bulb E27 White (9290012800) (2ea)

**Xiaomi\Aqara WiFi Devices:**
  - Xiaomi Gateway v3 (6ea) 
  - Xiaomi Air Purifier 2s
  - Xiaomi Wifi Plugs v2 (4ea)
  - not in use - Xiaomi Wifi Plugs v2 (3ea)
  - not in use - Xiaomi IR controller
  - not in use - Qingping Air Monitor Lite (2ea)
  - not in use - Xiaomi Smart WiFi Power Strip (2ea)

**Xiaomi\Aqara Zigbee Devices:**
  - Aqara Wall Socket (14ea)
  - Aqara Wall Switch Double (4ea)
  - not in use - Aqara D1 Wall Switch Tripple (1ea)
  - Aqara Wall Switch Single (1ea)
  - Aqara Wireless Switch Double (6ea)
  - Aqara\Xiaomi Door Sensor (26ea)
  - Aqara Water Leak Sensor (4ea)
  - Aqara Vibration Sensor (3ea)
  - Aqara\Xiaomi Motion Sensor (18ea)
  - Aqara\Xiaomi Wireless Button (9ea)
  - Aqara\Xiaomi Temp\Himidity sensor (11ea)
  - Aqara Zigbee Relay (1ea)
  - Aqara Opple Wireless Switch (2ea)
  - Xiaomi Plug (26ea)
  - Xiaomi Smoke Detector (1ea)
  - Xiaomi Natural Gas Detector (1ea)
  - Xiaomi Light Sensor (4ea)
  - not in use - Aqara Opple Wireless Switch (4ea)

**ESPHome devices:**
  - Sonoff Basic (2ea)
  - Sonoff Pow R2 (2ea)
  - Sonoff Mini (3ea)
  - not in use - Sonoff 4ch
  - not in use - Sonoff L1
  - not in use - Sonoff S26 Plugs (3ea)
  - not in use - Sonoff Micro via (self powering down)
  - not in use - Blitzwolf SHP2 (10ea) and SHP6 (4ea)
  - Blitzwolf LT11
  - not in use - Blitzwolf SS5 dual gang relay
  - Digma IR Remote (3ea)

**ESPHome DIY devices:**
  - ESP32 - Node K - Kitchen SensAir S8, BME280, BHI1750, Water Filter Counters, IR controller
  - ESP32 - Node B - Bathroom Relays (Water valves, Exhaust Fans), Night LED Strip, Dallas sensors on water pipes (Hot and Cold)
  - ESP32 - Node MB - Master Bedroom SensAir S8B, BME280, BHI1750, Dallas sensors (Heating pipe and Outside)
  - ESP32 - Node V - Vova Room SensAir S8, BME280, BHI1750, Dallas sensor (Heating pipe)
  - ESP32 - Hood K - Kitchen Hood Fan\Light Control, BME280, Dallas and max6675 
  - not in use - ESP32 - BLE Tracker HB
  - not in use - ESP32 - BLE Tracker HS
  - not in use - ESP32 - M5 Stack Pico BLE Tracker S
  - not in use - ESP32 - M5 Stack Pico BLE Tracker MB
  - ESP32 - Hall Big Breaker Box PZEM-004T
  - ESP8266 Oven K - Kitchen Oven K-type Thermocouple via max6675
  - ESP01 Weight Cell for RO water filter tank
  - D1 Mini LED Bed light
  - D1 Mini S - Sasha Room SensAir S8, BME280, BHI1750, WS2812 LES Strip, HA API Watchdog
  - D1 Mini Air Freshener with Figaro air sensor
  - D1 Mini TOF Distance Sensor
  - BTF Adressable LED strip Controller (based on esp8265) flashed with ESPHome
  - not in use - ESP01 (deepsleep on 14500 LiOn batteries) air freshener (Deerma Aerosol Dispenser DEM-PX830)

**BT\BLE Devices:**
  - CGD1 Cleargrass alarm clock
  - LYWSD02 Temperature and Humidity sensor
  - LYWSD03MMC Hygro thermometer
  - MCCGQ02HL Mijia Window/Door Sensor 2
  - MJYD02YL Motion Activated Night Light
  - Mi Body Composition Scale 2
  - MMC-T201-1 Digital Baby Thermometer
  - YLAI003 Smart Wireless Switch

**Smart Speakers:**
  - not in use - Google Home Mini (6ea)
  - Yandex Station Lite (4ea)
  - Yandex Station Mini 2 (1ea)

**Other Devices:**
  - Digma z801 Tablet
  - SLS Gateway
  - DIYRuZ_Geiger Sensor
  - Shelly EM
  - Shelly 1PM (2ea)
  - Shelly Plug S (3ea)
  - not in use - Xiaomi Kettle

# Software configuration
**Main Unit Software:**
  - Debian 11 (backports)
  - Home Assistant Core Supervised
  - PostgreSQL
  - Add-On's: 
    * File Editor
    * ESPhome
    * Grafana
    * Hass.io Google Drive Backup
    * IDE
    * Log Viewer
    * Portainer
    * RPC shutdown

**Main Storage Unit Software**
  - DSM 7.1
  - HA OS instance in VM
  - Docker containers:
    * Mosquitto
    * InfluxDB
    * Transmission

<!-- **Scripts:**
  - **ipmi_mqtt.sh**  Publishing IPMI, Temp and other system monitoring info to MQTT broker
  - **ha_log_parser.sh**  Backing up HA log to my home directory and splitting it to Error, Warning, Info message type as well as keeping full log. Logs rotated every 5 days.
  - **ya_weather.sh**  Yandex weather fcst ( thanks to [Ivan](https://t.me/configit)  )
  - **root_dev.sh**  Host root device name for monitoring.
  - **gitignore.sh**  bash script to be used after gitigrone file updated
  - **gitupdate.sh**  git upload -->

# Links
  - [Alexxit](https://github.com/alexxit)
  - [Omh](https://github.com/omhy)
  - [Vasilchuk](https://github.com/Anonym-tsk)
  - [S_p_i_r_i_t_u_s](https://github.com/Spirituss)
  - [lapatoc](https://github.com/bastshoes)
  - [Vtel](https://github.com/zvldz)
  - [Enzokot](https://github.com/Enzokot)
  - [AVBor](https://github.com/avbor)
  - [Andrew](https://github.com/andrewjswan)

# Chats
  - [Home Assistant RU](https://t.me/homassistant)
  - [Home Assistant - Hardware](https://t.me/homeassistant_hardware)
  - [ESPhome RU](https://t.me/esphome)

# Hardware Evolution
<!-- ![Hardwarez](images/hardware_evolution.jpg) -->
<details><summary>Click me...</summary>
<table max-width:100%;
white-space:nowrap;>
<tbody>
<tr>
<td>#</td>
<td>Year</td>
<td>Motherboard</td>
<td>CPU</td>
<td>RAM</td>
<td>Storage</td>
<td>Raid card</td>
</tr>
<tr>
<td rowspan="2">1</td>
<td rowspan="2">2018</td>
<td>Asrock H77M-ITX</td>
<td>i7-3770s</td>
<td>16gb DDR3</td>
<td>256GB SSD</td>
<td>-</td>
</tr>
<tr>
<td>Asrock J3455-ITX</td>
<td>Celeron j3455</td>
<td>16gb DDR3</td>
<td>4 * 2Tb HDD</td>
<td>&nbsp;</td>
</tr>
<tr>
<td>2</td>
<td>2019</td>
<td>Asus P8H77-M PRO</td>
<td>i7-3770s</td>
<td>16gb DDR3</td>
<td>256GB SSD + 7*2Tb HDD</td>
<td>-</td>
</tr>
<tr>
<td>3</td>
<td>2019</td>
<td>Asus Z9PA-D8</td>
<td>2 * E5-2620 V2</td>
<td>64gb ECC DDR3</td>
<td>128GB SSD + 7*2Tb HDD + 256Gb NVME</td>
<td>Asus Pike 2008</td>
</tr>
<tr>
<td>4</td>
<td>2019</td>
<td>Asus Z9PA-D8</td>
<td>2 * E5-2630L V2</td>
<td>64gb ECC DDR3</td>
<td>128GB SSD + 7*2Tb HDD + 3 *2Tb HDD + 1*256Gb NVME</td>
<td>Asus Pike 2008</td>
</tr>
<tr>
<td>5</td>
<td>2019</td>
<td>Asus Z9PA-D8</td>
<td>E5-1660</td>
<td>64gb ECC DDR3</td>
<td>128GB SSD + 7*2Tb HDD + 3 *2Tb HDD + 1*512Gb NVME</td>
<td>Adaptec 71605</td>
</tr>
<tr>
<td>6</td>
<td>2020</td>
<td>Supermicro X10SRL-F</td>
<td>E5-2620 V3</td>
<td>64gb ECC DDR4</td>
<td>128GB SSD + 7*2Tb HDD + 3 *2Tb HDD + 2*512Gb NVME</td>
<td>Adaptec 71605</td>
</tr>
<tr>
<td>7</td>
<td>2020</td>
<td>Supermicro X10SRL-F</td>
<td>E5-2630L V3</td>
<td>64gb ECC DDR4</td>
<td>128GB SSD + 7*2Tb HDD + 3 *2Tb HDD + 2*512Gb NVME</td>
<td>Adaptec 71605</td>
</tr>
<tr>
<td>8</td>
<td>2020</td>
<td>Supermicro X10SRL-F</td>
<td>E5-2628L V3</td>
<td>64gb ECC DDR4</td>
<td>128GB SSD + 7*2Tb HDD + 3 *2Tb HDD + 2*512Gb NVME + 1*256Gb NVME</td>
<td>Adaptec 71605</td>
</tr>
<tr>
<td>9</td>
<td>2021</td>
<td>Asrock Rack x470d4u</td>
<td>Ryzen 5 3600</td>
<td>32gb ECC DDR4</td>
<td>128GB SSD + 3*2Tb HDD + 1*8Tb HDD + 3*512Gb NVME + 1*256Gb NVME</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">10</td>
<td rowspan="2">2022</td>
<td>HP Prodesk 400 G6 mini</td>
<td>i3-10100t</td>
<td>2 * 8Gb DDR4</td>
<td>512GB NVME</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>8Tb HDD + 3*2Tb HDD + 256Gb SSD + 256Gb NVME (read cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">11</td>
<td rowspan="2">2022</td>
<td>HP Prodesk 600 G6 mini</td>
<td>i3-10100</td>
<td>2 * 8Gb DDR4</td>
<td>512GB NVME</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>8Tb HDD + 3*2Tb HDD + 256Gb SSD + 256Gb NVME (read cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">12</td>
<td rowspan="2">2022</td>
<td>HP Prodesk 600 G6 mini</td>
<td>i5-10600</td>
<td>2 * 8Gb DDR4</td>
<td>512GB NVME</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>8Tb HDD + 3*2Tb HDD + 256Gb SSD + 256Gb NVME (read cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">13</td>
<td rowspan="2">2022</td>
<td>HP Prodesk 600 G6 mini</td>
<td>i5-10600</td>
<td>2 * 8Gb DDR4</td>
<td>512GB NVME</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>8Tb HDD + 2*4Tb HDD + 2*256Gb SSD + 256Gb NVME (read cache)</td>
<td>-</td>
</tr>

</tbody>
</table>
</details>

# Screenshots
<details><summary>Click me...</summary>

![main1](images/main_1.jpg)
![main2](images/main_2.jpg)
![security](images/security.jpg)
![devices by room](images/devices_by_room.jpg)
![sensors by room](images/sensors_by_room.jpg)
![utility counters](images/utility_counters.jpg)
![ro filter](images/ro_filter.jpg)
![power details](images/power_details.jpg)
![cctv](images/cctv.jpg)
![air details](images/air_details.jpg)
![system stats](images/system_stats.jpg)
![system health](images/system_health.jpg)
![esp stats](images/esp_stats.jpg)
![wifi devices](images/wifi_devices.jpg)
![temperature detials](images/temperature_details.jpg)
![z switches](images/z_switches.jpg)
![z sensors](images/z_sensors.jpg)
![gw3 stats](images/gw3_stats.jpg)
![zigbee stats](images/zigbee_stats.jpg)
![testing](images/testing_page.jpg)


</details>