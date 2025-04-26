#!/bin/bash
# setup the python env
source ~/meshtastic/bin/activate
# make sure we are in the correct directory
cd /home/pi/Alligitor/Meshtastic-Scripts
/usr/bin/screen -S splotchplus -d -m /home/pi/meshtastic/bin/python3 BotTastic.py

