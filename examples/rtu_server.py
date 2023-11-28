"""
    Example Modbus RTU Server

    This example shows how to configure a Modbus RTU server.

	Written by FACTS Engineering
	Copyright (c) 2023 FACTS Engineering, LLC
	Licensed under the MIT license.

"""

import board
import digitalio
from uModBus.serial import RTUServer
import p1am_200_helpers as helpers # For P1AM-SERIAL
from rs485_wrapper import RS485 # If using an RS485 transceiver
    

led = digitalio.DigitalInOut(board.LED)
led.switch_to_output()
switch = digitalio.DigitalInOut(board.SWITCH)

# For P1AM-SERIAL using RS232
comm = helpers.get_serial(1, mode=232, baudrate=115200) 

# For P1AM-SERIAL using RS485
# uart, de = helpers.get_serial(1, mode=485, baudrate=115200) # For P1AM-SERIAL
# comm = RS485(uart, de, auto_idle_time=.05) # If using an RS485 transceiver

# For generic RS232
# comm = busio.UART(board.TX1, board.RX1, baudrate=115200)

mb_server = RTUServer(
    comm,
    unit_addr=1,
    number_coils=32,
    number_input_registers=255,
    number_discrete_inputs=16,
    number_holding_registers=10,
)

mb_server.input_registers = list(range(255))  # set input register value to their address
mb_server.discrete_inputs[5] = True  # set input register 5 to True
count = 0

while True:

    mb_server.poll(timeout=.5) # Regularly poll the modbus server to handle incoming requests
    mb_server.discrete_inputs[0] = switch.value  # set discrete input 0 to switch value
    mb_server.holding_registers[0] = count  # set holding register 0 to count value
    led.value = mb_server.coils[0]  # set led to output value
    
    count += 1
    if count > 32767:
        count = 0 # reset count