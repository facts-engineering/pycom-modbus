# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#
# Modified by FACTS Engineering 2023

import time
import struct
import uModBus.const as Const
from uModBus.common import ModbusException
from uModBus.common import Server, Client

def _t35chars_time(baudrate, data_bits, stop_bits):
    if baudrate <= 19200:
        return (3.5 * (data_bits + stop_bits + 2)) / baudrate
    else:
        return .001750

def _rtu_send(ctx, modbus_pdu, slave_addr):
    serial_pdu = bytearray()
    serial_pdu.append(slave_addr)
    serial_pdu.extend(modbus_pdu)

    crc = _calculate_crc16(serial_pdu)
    serial_pdu.extend(crc)
    ctx._uart.write(serial_pdu)
    time.sleep(ctx._t35chars)

def _calculate_crc16(data):
    crc = 0xFFFF

    for char in data:
        crc = (crc >> 8) ^ Const.CRC16_TABLE[((crc) ^ char) & 0xFF]

    return struct.pack('<H',crc)

def _uart_read_frame(ctx, timeout=None):
    frame = bytearray()

    start_ms = time.monotonic()
    while timeout == None or time.monotonic() - start_ms <= timeout:
        last_byte_ts = time.monotonic()
        while time.monotonic() - last_byte_ts <= ctx._t35chars:
            waiting = ctx._uart.in_waiting
            if waiting:
                r = ctx._uart.read(waiting)
                frame.extend(r)
                last_byte_ts = time.monotonic()
        if len(frame) >= 8:
            return frame

    return None

def _validate_resp_hdr(response, slave_addr, function_code, count):

    if len(response) == 0:
        raise OSError('no data received from slave')

    resp_crc = response[-Const.CRC_LENGTH:]
    expected_crc = _calculate_crc16(response[:-Const.CRC_LENGTH])

    if resp_crc != expected_crc:        
        print(f"Bad CRC - \n\tReceived - {hex(resp_crc[0]) + hex(resp_crc[1])[-2:]} \n\t Expected - {hex(expected_crc[0]) + hex(expected_crc[1])[-2:]}")
        raise OSError(f"Response was: {[hex(i) for i in response]}")

    if (response[0] != slave_addr):
        raise ValueError('wrong slave address')

    if (response[1] == (function_code + Const.ERROR_BIAS)):
        raise ValueError('slave returned exception code: {:d}'.format(response[2]))

    hdr_length = Const.RESPONSE_HDR_LENGTH + int(count)
    return response[hdr_length:-Const.CRC_LENGTH]

class RTUClient(Client):
    def __init__(self, uart, *, default_unit_id=0x00, timeout=None, data_bits=8, stop_bits=1):
        super().__init__(default_unit_id)
        self._uart = uart
        self.timeout = timeout
        self._t35chars = _t35chars_time(self._uart.baudrate, data_bits, stop_bits)

    def _exit_read(self, response):
        if response[1] >= Const.ERROR_BIAS:
            if len(response) < Const.ERROR_RESP_LEN:
                return False
        elif (Const.READ_COILS <= response[1] <= Const.READ_INPUT_REGISTER):
            expected_len = Const.RESPONSE_HDR_LENGTH + 1 + response[2] + Const.CRC_LENGTH
            if len(response) < expected_len:
                return False
        elif len(response) < Const.FIXED_RESP_LEN:
            return False

        return True

    def _uart_read(self):
        response = bytearray()
        start = time.monotonic()
        while True:
            waiting = self._uart.in_waiting
            time.sleep(self._t35chars)
            if waiting > 0:
                while waiting != self._uart.in_waiting: # give timeout period
                    time.sleep(self._t35chars)
                    waiting = self._uart.in_waiting
                response.extend(self._uart.read(waiting))
                start = time.monotonic() # reset timeout on new data

            if len(response) >= Const.ERROR_RESP_LEN and self._exit_read(response):
                return response

            if self.timeout is not None:
                if time.monotonic() - start > self.timeout:
                    return response
                    

    def _send(self, slave_addr, modbus_pdu):
        _rtu_send(self, modbus_pdu, slave_addr)

    def _send_receive(self, slave_addr, modbus_pdu, count):
        try:
            self._uart.reset_input_buffer()
            self._send(slave_addr, modbus_pdu)
            resp = self._uart_read()
            return _validate_resp_hdr(resp, slave_addr, modbus_pdu[0], count)
        except (OSError, ValueError): # retry to help with devices with lax timing
            time.sleep(self._t35chars * 2)
            self._uart.reset_input_buffer()
            self._send(slave_addr, modbus_pdu)
            resp = self._uart_read()
            return _validate_resp_hdr(resp, slave_addr, modbus_pdu[0], count)

class RTUServer(Server):
    def __init__(self, uart, data_bits=8, stop_bits=1, *, unit_addr=1, number_coils=None, number_discrete_inputs=None,
    number_input_registers=None, number_holding_registers=None):
        super().__init__(
            unit_addr, 
            number_coils=number_coils, 
            number_discrete_inputs=number_discrete_inputs, 
            number_input_registers=number_input_registers,
            number_holding_registers=number_holding_registers
            )
        
        self._uart = uart
        self._t35chars = _t35chars_time(self._uart.baudrate, data_bits, stop_bits)

    def _send(self, modbus_pdu, slave_addr):
        _rtu_send(self, modbus_pdu, slave_addr)

    def poll(self, timeout=None):
        req = _uart_read_frame(self, timeout)
        if req is None or len(req) < 8:
            return None
        req_crc = req[-Const.CRC_LENGTH:]
        req_no_crc = req[:-Const.CRC_LENGTH]
        expected_crc = _calculate_crc16(req_no_crc)
        if (req_crc[0] != expected_crc[0]) or (req_crc[1] != expected_crc[1]):
            print(f"Bad CRC - \n\tReceived - {hex(req_crc[0]) + hex(req_crc[1])[-2:]} \n\t Expected - {hex(expected_crc[0]) + hex(expected_crc[1])[-2:]}")
            return None

        try:
            return self.handle_request(req_no_crc)
        except ModbusException as e:
            self.send_exception_response(req[0], e.function_code, e.exception_code)
            print(f"Modbus Exception - {e.function_code} - {e.exception_code}")
            return None

