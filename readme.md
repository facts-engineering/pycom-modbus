# circuitpython-modbus

CircuitPython Modbus library supporting TCP and RTU protocols as both a client and server.

## Usage

Modbus TCP server using the Wiznet5k.

```python

#Modbus TCP Server

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

```


Modbus RTU client using a RS232 or RS485 interface.

```python
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

```

## License
This library is a fork of the [sfera-labs/pycom-modbus](https://github.com/sfera-labs/pycom-modbus) library.
The source is licensed under GPL v3.0 from the original author Pycom Ltd. Information on the license can be found [here](https://pycom.io/licensing)
