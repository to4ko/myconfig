#!/usr/bin/env python3
# DeftDawg's script for converting ESP NEC IR Remote commands and addresses in place
# 
# In the 2021.12 release of ESPHome the order of bits used in NEC commands was reversed
# https://esphome.io/changelog/2021.12.0.html#nec-remote-protocol
# 
# This script takes your yaml file and applies the coversion automatically while attempting to preserve formatting as much as possible
#
# pip3 install ruamel.yaml pathlib

# chmod +x esphome-yaml-nec-converter.py # make this script executable
# cd esphome
# mkdir new
# for f in $(grep transmit_nec *.yaml | cut -d: -f1 | sort -u); do ../esphome-yaml-nec-converter.py $f > new/$f; done
# 
# These steps will install the required deps, create a new directory and convert each yaml saving them to the new directory.
# Next compare the exsting yaml files with new and replace if everything looks good (apt install colordiff wdiff; wdiff esp.yaml new/esp.yaml | colordiff)
# Finally if everything looks okay, using ESPHome run validate on the changed config and then install it

import sys
from ruamel.yaml import YAML
from pathlib import Path

# @petergebruers method for converting from old to new format
def reverse_mask(x):
    x = ((x & 0x5555) << 1) | ((x & 0xAAAA) >> 1)
    x = ((x & 0x3333) << 2) | ((x & 0xCCCC) >> 2)
    x = ((x & 0x0F0F) << 4) | ((x & 0xF0F0) >> 4)
    x = ((x & 0x00FF) << 8) | ((x & 0xFF00) >> 8)
    return x

# For example, address: 0x84ED , command: 0x13EC becomes 0xB721 and 0x37C8 respectively.
# print(f"0x{reverse_mask(0x84ED):04X} should be 0xB721")
# print(f"0x{reverse_mask(0x13EC):04X} should be 0x37C8")

def convert_file(file_name):
    path = Path(file_name)
    yaml = YAML()
    doc = yaml.load(path)

    for switch in doc['switch']:
        if 'turn_on_action' in switch:
            for action in switch['turn_on_action']:
                if 'remote_transmitter.transmit_nec' in action:
                    action['remote_transmitter.transmit_nec']['address'] = f"0x{reverse_mask(action['remote_transmitter.transmit_nec']['address']):04X}"
                    action['remote_transmitter.transmit_nec']['command'] = f"0x{reverse_mask(action['remote_transmitter.transmit_nec']['command']):04X}"
    yaml.dump(doc, sys.stdout)

convert_file(sys.argv[1])