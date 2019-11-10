#!/bin/bash

HA_LOG=/usr/share/hassio/homeassistant/home-assistant.log
LOG_PATH=/home/dima/hassio_log/

while inotifywait -e modify $HA_LOG; do
  ACTUAL_DATE=`date '+%d.%m.%Y'`
  LAST_MESSAGE=`tail -n1 $HA_LOG`

  echo $LAST_MESSAGE >> $LOG_PATH"full_"$ACTUAL_DATE".log"

  LAST_STATUS=`echo $LAST_MESSAGE | awk {'print $3'}`
  echo $LAST_STATUS

  if [ $LAST_STATUS = "ERROR" ]; then
    echo $LAST_MESSAGE >> $LOG_PATH"error_"$ACTUAL_DATE".log"
  elif [ $LAST_STATUS = "WARNING" ]; then
    echo $LAST_MESSAGE >> $LOG_PATH"warning_"$ACTUAL_DATE".log"
  else
    echo $LAST_MESSAGE >> $LOG_PATH"info_"$ACTUAL_DATE".log"
  fi

  find $LOG_PATH -type f -ctime +5 -exec rm {} \;

done
