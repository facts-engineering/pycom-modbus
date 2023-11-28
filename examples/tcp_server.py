"""
    Example Modbus TCP Server

    This example shows how to configure a Modbus TCP server.

	Written by FACTS Engineering
	Copyright (c) 2021 FACTS Engineering, LLC
	Licensed under the MIT license.

"""

import board
import busio
import digitalio
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
from uModBus.tcp import TCPServer


led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()
switch = digitalio.DigitalInOut(board.SWITCH)

cs = digitalio.DigitalInOut(board.D5)
spi_bus = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
eth = WIZNET5K(spi_bus, cs, is_dhcp=False)

IP_ADDRESS = (192, 168, 1, 177)
SUBNET_MASK = (255, 255, 248, 0)
GATEWAY_ADDRESS = (192, 168, 0, 1)
DNS_SERVER = (8, 8, 8, 8)
eth.ifconfig = (IP_ADDRESS, SUBNET_MASK, GATEWAY_ADDRESS, DNS_SERVER)

socket.set_interface(eth)
server_ip = eth.pretty_ip(eth.ip_address)
mb_server = TCPServer(
    socket,
    server_ip,
    number_coils=0x20,
    number_input_registers=0xFF,
    number_discrete_inputs=0x10,
    number_holding_registers=10,
)

mb_server.input_registers = list(range(0xFF))
mb_server.discrete_inputs[5] = True
count = 0

while True:

    try:
        mb_server.poll(timeout=.1) # Regularly poll the modbus server to handle incoming requests
    except RuntimeError as e:
        pass # Ignore errors in case the client disconnects mid-poll
    mb_server.discrete_inputs[0] = switch.value  # set discrete input 0 to switch value
    mb_server.holding_registers[0] = count  # set holding register 0 to count value
    led.value = mb_server.coils[0]  # set led to output value

    count += 1
    if count > 32767:
        count = 0 # reset count
