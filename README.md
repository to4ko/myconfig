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
    <a href="https://github.com/to4ko/myconfig#small-tips">
      Small tips
    </a>
    <span> | </span>
    <a href="https://github.com/to4ko/myconfig#chats">
      Chats
    </a>
  </h4>
</div>

# Hardware Configuration
**Proxmox Node 1**
  - [Minisforum MS01](https://store.minisforum.com/products/minisforum-ms-01)
  - Intel i9-13900H
  - 2*48Gb Crucial DDR5 SODIMM
  - 512Gb Samsung PM9A1 M.2
  - 2Tb Samsung PM9A3 U.2

**Proxmox Node 2**
  - [Minisforum MS01](https://store.minisforum.com/products/minisforum-ms-01)
  - Intel i9-12900H
  - 2*32Gb DDR5 SODIMM
  - 512Gb Samsung PM9A1 M.2
  - 2Tb Micron 7400 Pro U.3

**Proxmox backup server**
  - [ZXIPC R5-4500U Mini PC](https://aliexpress.ru/item/1005007007752583.html)
  - AMD Ryzen 5 4500U
  - 16Gb Micron DDR4 SODIMM
  - 512Gb Samsung PM9A1 M.2
  - 2Tb Samsung 870 EVO

**KVM setup**
  - [BLIKVM v3 HAT running PiKVM](https://aliexpress.ru/item/1005004377930400.html)
  - [Raspberry Pi4 4Gb](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/)
  - XH-HK4401 4-port HDMI USB KVM Switch

**KVM2 "light"setup**
  - [CSI-2](https://aliexpress.ru/item/1005005499573640.html)
  - [Raspberry Pi Zero 2W](https://aliexpress.ru/item/1005005792181612.html)


**Main Storage Unit** 
  - [Synology DS1621+](https://www.synology.com/en-uk/products/DS1621+)
  - 2*16Gb Crucial DDR4 SODIMM
  - Mellanox ConnectX-3
  - 6ea WD HC550 16Tb as Main Storage
  - 2ea SP A38 1Tb as NVME read\write cache

**Backup Storage Unit**
  - [Synology DS920+](https://global.synologydownload.com/download/Document/Hardware/DataSheet/DiskStation/20-year/DS920+/enu/Synology_DS920_Plus_Data_Sheet_enu.pdf)
  - 4Gb onboard + 16Gb Kingston DDR4 SODIMM
  - 2ea WD Purple 4Tb in SHR1 as Main Storage section 
  - 2ea Adata SX6000 Lite 256Gb as NVME read\write cache

**Remote Backup Storage Unit**
  - [Synology DS220+](https://global.synologydownload.com/download/Document/Hardware/DataSheet/DiskStation/20-year/DS220+/enu/Synology_DS220_Plus_Data_Sheet_enu.pdf)
  - 2ea Seagate Skyhawk 4Tb in SHR1 as Main Storage section

**UPS**
  - Ippon Back Basic 1500
  - Ippon Smart Power Pro 1200
  - Ippon Back Basic 1050
  - Ippon Back Basic 650
  - CyberPower UT650EG 

# Networking
  - [Ubiquiti U-fiber Loco](https://store.ui.com/us/en/pro/category/all-fiber/products/ufiber-loco)
  - [Ubiquiti Unifi Dream Machine Pro Max, WAN1 1Gb\s + WAN2 500Mb\s](https://store.ui.com/us/en/pro/category/all-unifi-cloud-gateways/products/udm-pro-max)
  - [Ubiquiti Unifi Hi-Capacity Aggregation Switch](https://store.ui.com/us/en/pro/category/all-switching/products/usw-pro-aggregation)
  - [Ubiquiti Unifi Aggregation Switch](https://store.ui.com/us/en/pro/category/all-switching/products/usw-aggregation)
  - [Ubiquiti Unifi Enterprise Switch 24 PoE](https://store.ui.com/us/en/pro/category/all-switching/products/usw-enterprise-24-poe)
  - [Ubiquiti Unifi Switch 10Gbe XG](https://store.ui.com/us/en/pro/category/all-switching/products/usw-flex-xg)
  - [Ubiquiti Unifi Enterprise Switch 8 PoE (3ea)](https://store.ui.com/us/en/pro/category/all-switching/products/switch-enterprise-8-poe)
  - [Ubiquiti Unifi Switch Flex (3ea)](https://store.ui.com/us/en/pro/category/all-switching/products/usw-flex)
  - [Ubiquiti Unifi Switch Flex Mini (1ea)](https://store.ui.com/us/en/pro/category/all-switching/products/usw-flex-mini)
  - [Ubiquiti Unifi U6 Pro (4ea)](https://store.ui.com/us/en/pro/category/all-wifi/products/u6-pro)
  - [Ubiquiti Unifi AP AC Mesh with UMA-D (yard WiFi)](https://store.ui.com/us/en/pro/category/all-wifi/products/uap-ac-mesh)
  - [Ubiquiti Unifi Switch Flex Mini 2.5G (2ea)](https://eu.store.ui.com/eu/en/category/switching-utility/products/usw-flex-2-5g-5)

# Surveillance
  - Ubiquiti Unifi Dream Machine Pro Max with 6Tb Toshibe Drive
  - [Ubiquiti Unifi G3 Instant](https://store.ui.com/us/en/pro/category/all-cameras-nvrs/products/unifi-protect-g3-instant-camera)
  - [Ubiquiti Unifi G4 Instant](https://store.ui.com/us/en/pro/category/all-cameras-nvrs/products/camera-g4-instant)
  - [Ubiquiti Unifi G5 Dome](https://store.ui.com/us/en/category/all-cameras-nvrs/products/uvc-g5-dome)
  - [Ubiquiti Unifi G5 Turret Ultra (2ea)](https://store.ui.com/us/en/category/all-cameras-nvrs/products/uvc-g5-turret-ultra)
  - [Ubiquiti Unifi G5 Bullet (2ea)](https://store.ui.com/us/en/category/all-cameras-nvrs/products/uvc-g5-bullet)
  - [Ubiquiti Unifi G5 Flex](https://store.ui.com/us/en/category/all-cameras-nvrs/products/uvc-g5-flex)
  - [Ubiquiti Unifi G4 Doorbell Pro POE Kit](https://store.ui.com/us/en/pro/category/cameras-doorbells/collections/pro-store-doorbells-chimes/products/uvc-g4-doorbell-pro-poe-kit?variant=UVC-G4+Doorbell+Pro+PoE+Kit)

# Network map
<details><summary>Click me...</summary>

![map](images/networkmap.jpg)

</details>


# Smart Devices
**Lights**
  - Yeelight LED Ceiling Lamp650 (YLXD02YL) (2ea)
  - Yeelight LED Ceiling Lamp Pro White 960mm (YLXD08YL)
  - Yeelight LED Ceiling Light Pro 940mm White (YLXD56YL) 
  - Yeelight LED Ceiling Lamp 480mm White (YLXD05YL)
  - not in use - Yeelight LED Light Strip (YLDD01YL)
  - not in use - Yeelight LED Light Strip Plus (YLDD04YL)
  - not in use - Yeelight LED Light Strip 1S (YLDD05YL) (3ea)
  - not in use - Yeelight LED Bulb (Color) (YLDP06YL) (2ea)
  - not in use - Yeelight Smart LED Bubl W3 (YLDP005) (1ea)
  - not in use - Yeelight LED Tunable Bulb (White) (YLDP05YL) (2ea)
  - Yeelight Display Light Lamp Pro (YLTD003) (1ea)
  - Xiaomi Philips Zhirui Downlight (9290012799) (1ea)
  - not in use - Yeelight Jiaoyue 260 (YLXD62YI)
  - not in use - Xiaomi Philips Smart LED Bulb E27 White (9290012800) (2ea)

**Xiaomi\Aqara WiFi Devices:**
  - Xiaomi Multimode Gateway 2 CN (6ea)
  - Xiaomi Air Purifier 2s
  - Xiaomi Wifi Plugs v2 (4ea)
  - Viomi Water Purifier 1200g
  - not in use - Xiaomi Wifi Plugs v2 (3ea)
  - not in use - Xiaomi IR controller
  - not in use - Qingping Air Monitor Lite (2ea)
  - not in use - Xiaomi Smart WiFi Power Strip (2ea)

**Xiaomi\Aqara Zigbee Devices:**
  - Aqara Vibration sensor DJT11LM (4ea)
  - Xiaomi Light Detection Sensor GZCGQ01LM (4ea)
  - Xiaomi Honeywell Natural Gas Sensor JTQJ-BF-01LM/BW (1ea)
  - Xiaomi Honeywell Smoke JTYJ-GD-01LM/BW (1ea)
  - Aqara Relay LLKZMK11LM (1ea)
  - Xiaomi Door Sensor MCCGQ01LM (15ea)
  - Aqara Door Sensor MCCGQ11LM (11ea)
  - Aqara Wall Outlet QBCZ11LM (14ea)
  - Aqara Wall Switch (No Neutral, Double Rocker) QBKG03LM (4ea)
  - Aqara E1 Wall Switch (With Neutral, Double Rocker) QBKG41LM (1ea)
  - Xiaomi Motion Sensor RTCGQ01LM (4ea)
  - Aqara Motion Sensor RTCGQ11LM (13ea)
  - Aqara Water Leak Sensor SJCGQ11LM (4ea)
  - Xiaomi Temperature Humidity sensor WSDCGQ01LM (8ea)
  - Aqara Temperature Humidity Pressure Sensor WSDCGQ11LM (4ea)
  - Aqara Opple Wireless Scene Switch 2 Button WXCJKG11LM (2ea)
  - Aqara Opple Wireless Scene Switch 4 Button WXCJKG12LM (1ea)
  - Xiaomi Mijia Wireless Switch WXKG01LM (2ea)
  - Aqara Wireless Remote Switch (Double Rocker) (2016 version) WXKG02LM (3ea)
  - Aqara Wireless Mini Switch WXKG11LM (2ea)
  - Aqara Wireless Mini Switch with Gyroscope WXKG12LM (2ea)
  - Aqara E1 Wireless Remote Switch (Double Rocker) WXKG17LM (1ea)
  - Xiaomi Mi Power Plug ZigBee ZNCZ02LM (24ea)
  - Aqara T1 E27 Bulb ZNLDP14LM (4ea)

**Xiaomi BT\BLE Devices:**
  - XMOSB01XS Xiaomi Mijia People Presence Sensor (2ea)
  - CGD1 Cleargrass alarm clock
  - LYWSD02 Temperature and Humidity sensor
  - LYWSD03MMC Hygro thermometer
  - MCCGQ02HL Mijia Window/Door Sensor 2
  - MJYD02YL Motion Activated Night Light
  - Mi Body Composition Scale 2
  - MMC-T201-1 Digital Baby Thermometer
  - YLAI003 Smart Wireless Switch
  - HB01 Linptech ES1 Presence Sensor (4ea)
  - RTCGQ02LM Mi Motion Sensor 2
  - CGPR1 Qingping Motion Sensor
  - Mijia curtain companion MJSGCLBL01LM Rod-type (6ea)

**ESPHome devices:**
  - Sonoff Pow R2 (2ea)
  - Sonoff Mini (3ea)
  - not in use - Sonoff 4ch
  - not in use - Sonoff L1
  - not in use - Sonoff S26 Plugs (3ea)
  - not in use - Sonoff Micro via (self powering down)
  - not in use - Blitzwolf SHP2 (10ea) and SHP6 (4ea)
  - Blitzwolf LT11
  - not in use - Blitzwolf SS5 dual gang relay
  - Digma IR Remote (4ea)
  - Yeelight 1s Led Strip ESPHome firmware (4ea)

**ESPHome DIY devices:**
  - ESP32 - Node K - Kitchen SensAir S8, BME280, BHI1750, Water Filter Counters, IR controller
  - ESP32 - Node B - Bathroom Relays (Water valves, Exhaust Fans), Night LED Strip, Dallas sensors on water pipes (Hot and Cold)
  - ESP32 - Node MB - Master Bedroom SensAir S8B, BME280, BHI1750, Dallas sensors (Heating pipe and Outside)
  - ESP32 - Node V - Vova Room SensAir S8, BME280, BHI1750, Dallas sensor (Heating pipe)
  - ESP32 - Node S - Sasha Room SensAir S8, BME280, BHI1750, WS2812 LES Strip, HA API Watchdog
  - ESP32 - Hood K - Kitchen Hood Fan\Light Control, BME280, Dallas and max6675
  - ESP32 - Node HS - Hall Small adressable LED controller with BME280 and ClimateGuard Geiger sensor 
  - ESP32 - BLE Gateway HB
  - ESP32 - GL.iNET GL-S10 POE powered BLE Gateway (3ea)
  - ESP32 - Hall Big Breaker Box PZEM-004T
  - ESP8266 Oven K - Kitchen Oven K-type Thermocouple via max6675
  - ESP01 Weight Cell for RO water filter tank
  - D1 Mini LED Bed light
  - D1 Mini Air Freshener with Figaro air sensor
  - D1 Mini TOF Distance and LD2410 Radar
  - BTF Adressable LED strip Controller (based on esp8265) flashed with ESPHome
  - not in use - ESP01 (deepsleep on 14500 LiOn batteries) air freshener (Deerma Aerosol Dispenser DEM-PX830)
  - not in use - Tuya USB Micro Switch (2ea) - ESPHome firmware

**Smart Speakers:**
  - not in use - Google Home Mini (5ea)
  - Yandex Station Lite (4ea)
  - Yandex Station Mini 2 (1ea)
  - Yandex Station 2 (1ea)
  - Yandex Ststion Midi (2ea)

**Other Devices:**
  - Lenovo Xiaoxin Pad 2024 8/128 with Fully Kiosk Browser
  - not in use - Digma z801 Tablet
  - not in use - SLS Gateway
  - not in use - DIYRuZ_Geiger Sensor
  - Shelly EM
  - Shelly 1PM (2ea)
  - Shelly 1 (2ea)
  - Shelly Plug S (2ea)
  - not in use - Xiaomi Kettle

# Software configuration
**Proxmox Node Software:**
  - Proxmox VE 8
      * Debian 12 with HA Supervised (main instance)
      * Debian 12 with HA Supervised (backup instance)
      * Plex
      * Zabbix Server
      * NGINX Proxy Manager
      * Bitwarden
      * MariaDB
      * EMQX

**Main Storage Unit Software**
  - DSM 7.2
  - Proxmox Backup Server VM
  - Docker containers:
    * InfluxDB
    * Transmission
    * qBitTorrent
    * Adguard home (not in use)

**Backup Storage Unit Software**
  - DSM 7.2

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

# Small Tips
<details>
  <summary>List of integrations in use</summary>

  ```yaml
  {% set devices = states | map(attribute='entity_id') | map('device_id') | unique | reject('eq',None) | list %}
  {%- set ns = namespace(integrations = []) %}
  {%- for device in devices %}
    {%- set ids = device_attr(device, 'identifiers') | list | first | default('unknown') %}
    {%- if ids and ids | length == 2 %}
      {%- set integration, something_unique = ids %}
      {%- if integration not in ns.integrations %}
        {%- set ns.integrations = ns.integrations + [ integration ] %}
      {%- endif %}
    {%- endif %}
  {%- endfor %}
  {{ ns.integrations }}
  ```
</details>

<!--<details>-->
<!--  <summary>some usefull SQL tips</summary>-->

<!--  ```-->
<!--  SELECT m.entity_id, COUNT(*) as count FROM states as s JOIN states_meta AS m ON s.metadata_id = m.metadata_id GROUP BY m.metadata_id ORDER BY count DESC LIMIT 100;-->
<!--  ```-->
<!--  ```-->
<!--  SELECT SUM(pgsize) bytes, name FROM dbstat GROUP BY name ORDER BY bytes DESC;-->
<!--  ```-->
<!--  ```-->
<!--  SELECT m.statistic_id, COUNT(*) as count FROM statistics as s JOIN statistics_meta AS m ON s.metadata_id = m.id GROUP BY m.statistic_id ORDER BY count DESC LIMIT 100;-->
<!--  ```-->
<!--  ```-->
<!--  DELETE FROM states WHERE metadata_id IN (SELECT metadata_id FROM states_meta WHERE entity_id = 'sensor.your_sensor');-->
<!--  ```-->
<!--</details>-->

<details>
  <summary>List of all used domains</summary>

  ```yaml
  {%- for d in states | groupby('domain') %}
    {{ d[0] }}
  {%- endfor %}
  ```
</details>

<details>
  <summary>List of all devices(IDs) per integration</summary>

  ```yaml
  {{ integration_entities('yeelight') |  map('device_id') | unique | list }}
  ```
</details>

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
<td>512GB NVME SSD</td>
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
<td>512GB NVME SSD</td>
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
<td>512GB NVME SSD</td>
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
<td>512GB NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>16Tb HDD + 2*4Tb HDD + 2*2Tb SSD + 2*512Gb NVME (read\write cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">14</td>
<td rowspan="2">2023</td>
<td>Minisforum NPB7</td>
<td>i7-13700H</td>
<td>2 * 8Gb DDR5</td>
<td>250Gb SATA SSD + 1Tb NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>16Tb HDD + 2*4Tb HDD + 2*2Tb SSD + 2*512Gb NVME (read\write cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">15</td>
<td rowspan="2">2023</td>
<td>Intel NUC 12 Pro</td>
<td>i3-1220p</td>
<td>2 * 8Gb DDR4</td>
<td>500Gb SATA SSD + 1Tb NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>3*16Tb HDD + 2*2Tb SSD + 2*512Gb NVME (read\write cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">16</td>
<td rowspan="2">2023</td>
<td>Intel NUC 13 Pro</td>
<td>i5-1340p</td>
<td>2 * 32Gb DDR4</td>
<td>500Gb SATA SSD + 1Tb NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>3*16Tb HDD + 2*2Tb SSD + 2*512Gb NVME (read\write cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="3">16</td>
<td rowspan="3">2023</td>
<td>Intel NUC 13 Pro</td>
<td>i5-1340p</td>
<td>2 * 32Gb DDR4</td>
<td>500Gb SATA SSD + 1Tb NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Intel NUC 12 Pro</td>
<td>i3-1220p</td>
<td>2 * 8Gb DDR4</td>
<td>500Gb SATA SSD + 1Tb NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>4*16Tb HDD + 2*2Tb SSD + 2*512Gb NVME (read\write cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="3">17</td>
<td rowspan="3">2024</td>
<td>Intel NUC 13 Pro</td>
<td>i5-1340p</td>
<td>2 * 32Gb DDR4</td>
<td>500Gb SATA SSD + 1Tb NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Minisforum MS01</td>
<td>i9-13900H</td>
<td>2 * 48Gb DDR5</td>
<td>512Gb M.2 NVME SSD + 2Tb U.2 NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>4*16Tb HDD + 2*2Tb SSD + 2*1Tb NVME (read\write cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="2">18</td>
<td rowspan="2">2024</td>
<td>Minisforum MS01</td>
<td>i9-13900H</td>
<td>2 * 48Gb DDR5</td>
<td>512Gb M.2 NVME SSD + 2Tb U.2 NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>6*16Tb HDD + 2*1Tb NVME (read\write cache)</td>
<td>-</td>
</tr>
<tr>
<td rowspan="3">19</td>
<td rowspan="3">2024</td>
<td>Minisforum MS01</td>
<td>i9-13900H</td>
<td>2 * 48Gb DDR5</td>
<td>512Gb M.2 NVME SSD + 2Tb U.2 NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Minisforum MS01</td>
<td>i9-12900H</td>
<td>2 * 32Gb DDR5</td>
<td>512Gb M.2 NVME SSD + 2Tb U.2 NVME SSD</td>
<td>-</td>
</tr>
<tr>
<td>Synology DS1621+</td>
<td>Ryzen V1500B</td>
<td>2 * 16Gb DDR4</td>
<td>6*16Tb HDD + 2*1Tb NVME (read\write cache)</td>
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