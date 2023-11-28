"""
    Example Modbus RTU Client

    This example shows how to communicate with a modbus server over RTU.

	Written by FACTS Engineering
	Copyright (c) 2023 FACTS Engineering, LLC
	Licensed under the MIT license.

"""

import time
import board
import busio
from uModBus.serial import RTUClient
import p1am_200_helpers as helpers # For P1AM-SERIAL
from rs485_wrapper import RS485 # If using an RS485 transceiver

def clear_terminal():
    print(chr(27) + "[2J")


# For P1AM-SERIAL using RS232
comm = helpers.get_serial(1, mode=232, baudrate=115200) 

# For P1AM-SERIAL using RS485
# uart, de = helpers.get_serial(1, mode=485, baudrate=115200) # For P1AM-SERIAL
# comm = RS485(uart, de, auto_idle_time=.05) # If using an RS485 transceiver

# For generic RS232
# comm = busio.UART(board.TX1, board.RX1, baudrate=115200)

unit_id = 1 # ID of modbus unit
mb_client = RTUClient(comm, default_unit_id=unit_id) # Optionally specify a unit ID

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
