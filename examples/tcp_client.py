"""
    Example Modbus TCP Client

    This example shows how to communicate with a modbus server over TCP.

	Written by FACTS Engineering
	Copyright (c) 2023 FACTS Engineering, LLC
	Licensed under the MIT license.

"""

import time
import board
import busio
import digitalio
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
from uModBus.tcp import TCPClient

def clear_terminal():
    print(chr(27) + "[2J")


cs = digitalio.DigitalInOut(board.D5)
spi_bus = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
eth = WIZNET5K(spi_bus, cs, is_dhcp=True)
socket.set_interface(eth)
print(eth.pretty_ip(eth.ip_address))

client_ip = '192.168.1.177'
unit_id = 255
mb_client = TCPClient(socket, client_ip, default_unit_id=unit_id)

counter = 0
while True:

    counter += 1 # increment counter for register 4
    if counter > 32767:
        counter = 0 # reset counter

    mb_client.write_single_register(4, counter, unit=unit_id)
    current_states = mb_client.read_coils(0, 16, unit=unit_id)
    holding_regs = mb_client.read_holding_registers(0, 3) # when unit is not specified, the default_unit_id is used

    clear_terminal()
    for i in range(len(current_states)):
        print(f"Coil #{i} is {current_states[i]}")
    for i in range(len(holding_regs)):
        print(f"Register #{i} is {holding_regs[i]}")

    time.sleep(1)
