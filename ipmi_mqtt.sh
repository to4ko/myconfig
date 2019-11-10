#!/bin/bash

# MQTT Vars
MQTT_SERVER="192.168.1.14"
MQTT_PORT="1883"
MQTT_TOPIC_BASE="ubuntu"

# MQTT User/Pass Vars, only use if needed
MQTT_USER="xxx"
MQTT_PASS="yyy"
MQTT_ID="z9pa"

MQTT_DATA="-h $MQTT_SERVER -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASS -i $MQTT_ID"

##################################################################################################
# Last update
##################################################################################################
VAL=`date '+%d.%m.%Y %H:%M:%S'>/home/dima/echo.txt`
mosquitto_pub $MQTT_DATA -r -t $MQTT_TOPIC_BASE/last_update -f /home/dima/echo.txt

##################################################################################################
# IPMI Stats
##################################################################################################
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'CPU1 Temperature' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/cpu1_temp -m $VAL
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'CPU2 Temperature' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/cpu2_temp -m $VAL

VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'TR1 Temperature' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/tr1_temp -m $VAL
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'TR2 Temperature' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/tr2_temp -m $VAL

VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'CPU_FAN1' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/cpu_fan1 -m $VAL
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'CPU_FAN2' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/cpu_fan2 -m $VAL

VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'FRNT_FAN1' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/frnt_fan1 -m $VAL
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'FRNT_FAN2' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/frnt_fan2 -m $VAL
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'FRNT_FAN3' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/frnt_fan3 -m $VAL
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'FRNT_FAN4' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/frnt_fan4 -m $VAL

VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'REAR_FAN1' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/rear_fan1 -m $VAL
VAL=`ipmitool -I lanplus -H 192.168.1.8 -U admin -P admin sensor | grep -n 'REAR_FAN2' | awk -F'|' '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/ipmi/rear_fan2 -m $VAL

##################################################################################################
# Free RAM
##################################################################################################
# ex Sudo
VAL=`free -h | grep "Mem:" | awk '{print $3}' | rev | cut -c2- | rev `
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/used_memory -m $VAL

##################################################################################################
# NVME TB Written Total
##################################################################################################
VAL=`/usr/sbin/smartctl /dev/nvme0 -x| grep 'Data Units Written:'| awk '{print $4}'|sed 's/\,//g'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/nvme0_lba_written -m $VAL

VAL=`/usr/sbin/smartctl /dev/nvme0 -x| grep 'Power On Hours:'| awk '{print $4}'|sed 's/\,//g'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/nvme0_power_on_hours -m $VAL


VAL=`/usr/sbin/smartctl /dev/nvme1 -x| grep 'Data Units Written:'| awk '{print $4}'|sed 's/\,//g'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/nvme1_lba_written -m $VAL

VAL=`/usr/sbin/smartctl /dev/nvme1 -x| grep 'Power On Hours:'| awk '{print $4}'|sed 's/\,//g'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/nvme1_power_on_hours -m $VAL

VAL=`/usr/sbin/smartctl /dev/nvme2 -x| grep 'Data Units Written:'| awk '{print $4}'|sed 's/\,//g'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/nvme2_lba_written -m $VAL

VAL=`/usr/sbin/smartctl /dev/nvme2 -x| grep 'Power On Hours:'| awk '{print $4}'|sed 's/\,//g'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/nvme2_power_on_hours -m $VAL

VAL=`/usr/sbin/smartctl /dev/sdb -x| grep 'Total_LBAs_Written'| awk '{print $8}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/sdb_lba_written -m $VAL

VAL=`/usr/sbin/smartctl /dev/sdb -x| grep 'Power_On_Hours'| awk '{print $8}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/sdb_power_on_hours -m $VAL

VAL=`/usr/sbin/smartctl /dev/sda -x | grep "Total_LBAs_Written" | awk '{print $8}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/sda_gb_total -m $VAL

VAL=`/usr/sbin/smartctl /dev/sda -x | grep "Power_On_Hours" | awk '{print $8}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/sda_power_on_hours -m $VAL


##################################################################################################
# SSD GB R\W Session
##################################################################################################
VAL=`cat /proc/diskstats |grep "0 sda" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sda_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "0 sda" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sda_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "16 sdb" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdb_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "16 sdb" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdb_gb_write -m $VAL

##################################################################################################
# HDD GB R\W Session
##################################################################################################
VAL=`cat /proc/diskstats |grep "32 sdc" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdc_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "32 sdc" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdc_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "48 sdd" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdd_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "48 sdd" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdd_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "64 sde" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sde_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "64 sde" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sde_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "80 sdf" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdf_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "80 sdf" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdf_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "96 sdg" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdg_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "96 sdg" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdg_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "112 sdh" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdh_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "112 sdh" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdh_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "128 sdi" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdi_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "128 sdi" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdi_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "144 sdj" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdj_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "144 sdj" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdj_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "160 sdk" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdk_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "160 sdk" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdk_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "176 sdl" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdl_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "176 sdl" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdl_gb_write -m $VAL

##################################################################################################
# NVME GB R\W Session
##################################################################################################
VAL=`cat /proc/diskstats |grep "nvme0n1" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/nvme0_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "nvme0n1" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/nvme0_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "nvme2n1p1" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/nvme2_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "nvme2n1p1" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/nvme2_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "nvme1n1" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/nvme1_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "nvme1n1" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/nvme1_gb_read -m $VAL

##################################################################################################
# f20 GB R\W Session
##################################################################################################
VAL=`cat /proc/diskstats |grep "240 sdp" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdp_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "240 sdp" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdp_gb_rear -m $VAL

VAL=`cat /proc/diskstats |grep "0 sdq" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdq_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "0 sdq" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdq_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "16 sdr" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdr_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "16 sdr" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sdr_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "32 sds" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sds_gb_write -m $VAL

VAL=`cat /proc/diskstats |grep "32 sds" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/sds_gb_read -m $VAL

##################################################################################################
# md0 R\W Stats
##################################################################################################
VAL=`cat /proc/diskstats |grep "0 md0" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md0_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "0 md0" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md0_gb_write -m $VAL

##################################################################################################
# md1 R\W Stats
##################################################################################################
VAL=`cat /proc/diskstats |grep "1 md1" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md1_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "1 md1" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md1_gb_write -m $VAL

##################################################################################################
# md2 R\W Stats
##################################################################################################
VAL=`cat /proc/diskstats |grep "2 md2" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md2_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "2 md2" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md2_gb_write -m $VAL

##################################################################################################
# md3 R\W Stats
##################################################################################################
VAL=`cat /proc/diskstats |grep "3 md3" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md3_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "3 md3" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md3_gb_write -m $VAL

##################################################################################################
# md4 R\W Stats
##################################################################################################
VAL=`cat /proc/diskstats |grep "4 md4" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md4_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "4 md4" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md4_gb_write -m $VAL

##################################################################################################
# md5 R\W Stats
##################################################################################################
VAL=`cat /proc/diskstats |grep "5 md5" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md5_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "5 md5" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/md5_gb_write -m $VAL


##################################################################################################
# SDM R\W Stats
##################################################################################################
VAL=`cat /proc/diskstats |grep "192 sdm" | awk '{print $6*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/video_gb_read -m $VAL

VAL=`cat /proc/diskstats |grep "192 sdm" | awk '{print $10*512/1024/1024/1024}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_stat/video_gb_write -m $VAL


##################################################################################################
# Drives Temp
##################################################################################################
for VAR_LETTER in c d e f g h i j k l m
do
VAR2="sd$VAR_LETTER"
VAR="/dev/$VAR2"
VAL=`/usr/sbin/hddtemp $VAR | tail -c 6 | rev | cut -c4- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_temp/$VAR2 -m $VAL
done

VAL=`/usr/sbin/smartctl /dev/nvme0 -x | grep "Temperature:" | awk '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_temp/nvme0 -m $VAL

VAL=`/usr/sbin/smartctl /dev/nvme1 -x | grep "Temperature:" | awk '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_temp/nvme1 -m $VAL

VAL=`/usr/sbin/smartctl /dev/nvme2 -x | grep "Temperature:" | awk '{print $2}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_temp/nvme2 -m $VAL

VAL=`/usr/sbin/smartctl /dev/sda -d sat -x | grep "194 Temperature_Celsius" | awk '{print $8}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_temp/sda -m $VAL

VAL=`/usr/sbin/smartctl /dev/sdb -d sat -x | grep "190 Airflow_Temperature_Cel" | awk '{print $8}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_temp/sdb -m $VAL


##################################################################################################
# Disk Usage %
##################################################################################################
VAL=`df -h /dev/md0p1 | grep "/dev/md0p1" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/md0 -m $VAL

VAL=`df -h /dev/md1 | grep "/dev/md1" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/md1 -m $VAL

VAL=`df -h /dev/md2 | grep "/dev/md2" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/md2 -m $VAL

VAL=`df -h /dev/md5 | grep "/dev/md5" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/md5 -m $VAL

VAL=`df -h /dev/sdm1 | grep "/dev/sdm1" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/video -m $VAL

VAL=`df -h /dev/nvme2n1p1 | grep "/dev/nvme2n1p1" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/nvme2 -m $VAL


VAL=`df -h /dev/sdb1 | grep "/dev/sdb1" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/840pro -m $VAL

VAL=`df -h | grep "/mnt/320l" | awk '{print $5}' | rev | cut -c 2- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/disk_usage/320l -m $VAL

##################################################################################################
# CPU Temp
##################################################################################################
VAL=`sensors | grep "Package id 0:" | awk '{print $4}' | rev | cut -c6- | rev | cut -c 2-`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/cpu_temperatures/0 -m $VAL

VAL=`sensors | grep "Package id 1:" | awk '{print $4}' | rev | cut -c6- | rev | cut -c 2-`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/cpu_temperatures/1 -m $VAL

##################################################################################################
# Raid Status
##################################################################################################
VAL=`cat /proc/mdstat | grep "md0 :" | awk '{print $3}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md0 -m $VAL

VAL=`cat /proc/mdstat | grep "md0 :" | awk '{print $5}' | rev | cut -c 6- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md0_disk1 -m $VAL

VAL=`cat /proc/mdstat | grep "md0 :" | awk '{print $6}' | rev | cut -c 6- | rev`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md0_disk2 -m $VAL

VAL=`cat /proc/mdstat | grep "md0 :" >/home/dima/echo.txt`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md0_full -f /home/dima/echo.txt

VAL=`cat /proc/mdstat | grep "md1 :" | awk '{print $3}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md1 -m $VAL

VAL=`cat /proc/mdstat | grep "md1 :" >/home/dima/echo.txt`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md1_full -f /home/dima/echo.txt

VAL=`cat /proc/mdstat | grep "md2 :" | awk '{print $3}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md2 -m $VAL

VAL=`cat /proc/mdstat | grep "md2 :" >/home/dima/echo.txt`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md2_full -f /home/dima/echo.txt


VAL=`cat /proc/mdstat | grep "md3 :" | awk '{print $3}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md3 -m $VAL

VAL=`cat /proc/mdstat | grep "md4 :" | awk '{print $3}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md4 -m $VAL

VAL=`cat /proc/mdstat | grep "md5 :" | awk '{print $3}'`
mosquitto_pub $MQTT_DATA -t $MQTT_TOPIC_BASE/mdstat/md5 -m $VAL
