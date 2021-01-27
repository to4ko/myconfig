#!/bin/bash

cd /usr/share/hassio/homeassistant
echo "-----> cd done"
git add .
echo "-----> git add done"
git status
echo "-----> git status done"
#echo -n "Enter the Description for the Change: "
#read CHANGE_MSG
VAL=`date '+%d.%m.%Y_%H:%M:%S'`
git commit -m "${VAL}"
echo "-----> git commit done"
git push origin master
echo "-----> git push dene"
echo "-----> all done"

exit
