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
from random import getrandbits
import uModBus.const as Const
from uModBus.common import Server, Client
from uModBus.common import ModbusException


class TCPClient(Client):

    def __init__(self, socket, server_ip, *, server_port=502, default_unit_id=255, timeout=5):
        super().__init__(default_unit_id)
        self._sock = socket.socket()
        self._addrinfo = socket.getaddrinfo(server_ip, server_port)[0][-1]
        self.connect()
        self._sock.settimeout(timeout)

    def connect(self):
        """Connect to Server"""
        self._sock.connect(self._addrinfo)
    
    def disconnect(self):
        """Disconnect from server"""
        self._sock.disconnect()

    @property
    def connected(self):
        """Return if socket is connected to the server"""
        return self._sock._connected

    def _create_mbap_hdr(self, slave_id, modbus_pdu):
        trans_id = getrandbits(16) & 0xFFFF
        mbap_hdr = struct.pack('>HHHB', trans_id, 0, len(modbus_pdu) + 1, slave_id)

        return mbap_hdr, trans_id

    def _validate_resp_hdr(self, response, trans_id, slave_id, function_code, count=False):
        rec_tid, rec_pid, rec_len, rec_uid, rec_fc, rec_ec = struct.unpack('>HHHBBB', response[:Const.MBAP_HDR_LENGTH + 2])
        if (trans_id != rec_tid):
            raise ValueError('wrong transaction Id')

        if (rec_pid != 0):
            raise ValueError('invalid protocol Id')

        if (slave_id != rec_uid):
            raise ValueError('wrong slave Id')

        if (rec_fc == (function_code + Const.ERROR_BIAS)):
            raise ValueError('slave returned exception code: {:d}'.format(rec_ec))

        hdr_length = (Const.MBAP_HDR_LENGTH + 2) if count else (Const.MBAP_HDR_LENGTH + 1)

        return response[hdr_length:]

    def _send_receive(self, slave_id, modbus_pdu, count):
        mbap_hdr, trans_id = self._create_mbap_hdr(slave_id, modbus_pdu)
        self._sock.send(mbap_hdr + modbus_pdu)

        timeout = self._sock.gettimeout()
        stamp = time.monotonic()

        while self._sock._available() < Const.MBAP_HDR_LENGTH and time.monotonic() - stamp < timeout:
            pass

        response = self._sock.recv(Const.MAX_MSG_LENGTH)
        if len(response) == 0:
            raise TimeoutError("No response received")
        modbus_data = self._validate_resp_hdr(response, trans_id, slave_id, modbus_pdu[0], count)

        return modbus_data


class TCPServer(Server):

    def __init__(self, socket, local_ip, *, local_port=502, unit_addr=None, number_coils=None, number_discrete_inputs=None,
    number_input_registers=None, number_holding_registers=None):
        super().__init__(
            unit_addr, 
            number_coils=number_coils, 
            number_discrete_inputs=number_discrete_inputs, 
            number_input_registers=number_input_registers,
            number_holding_registers=number_holding_registers
            )
        self._sock = None
        self._client_sock = None
        self._socket_source = socket
        self._local_ip = local_ip
        self._local_port = local_port


    def _listen(self):
        self._sock.bind((self._local_ip, self._local_port))
        self._sock.listen()

        
    def _send(self, modbus_pdu, slave_addr):
        size = len(modbus_pdu)
        fmt = 'B' * size
        adu = struct.pack('>HHHB', self._req_tid, 0, size + 1, slave_addr) + modbus_pdu
        try:
            self._client_sock.send(adu)
        except Exception as e:
            self._client_sock.close()
            self._client_sock = None
            raise e


    def _accept_request(self, accept_timeout):

        start = time.monotonic()
        self._sock.settimeout(accept_timeout)
        while time.monotonic() - start < accept_timeout and (self._client_sock == None or self._client_sock._socket_closed == True):
            try: 
                self._client_sock, addr = self._sock.accept()
            except TimeoutError:
                pass
        if self._client_sock == None:
            return None
        self._client_sock.settimeout(.000001)
        while time.monotonic() - start < accept_timeout:
            try: 
                if self._client_sock._available() >= Const.MBAP_HDR_LENGTH:
                    break
            except TimeoutError:
                pass
        if self._client_sock._available() < Const.MBAP_HDR_LENGTH:
            return None
        req = self._client_sock.recv(Const.MAX_MSG_LENGTH)

        req_header_no_uid = req[:Const.MBAP_HDR_LENGTH - 1]
        self._req_tid, req_pid, req_len = struct.unpack('>HHH', req_header_no_uid)
        req_uid_and_pdu = req[Const.MBAP_HDR_LENGTH - 1:Const.MBAP_HDR_LENGTH + req_len - 1]
        if (req_pid != 0):
            self._client_sock.close()
            self._client_sock = None
            return None
        try:
            r = self.handle_request(req_uid_and_pdu)
            return r
        except ModbusException as e:
            # print("Modbus request error:", e)
            self.send_exception_response(req[0], e.function_code, e.exception_code)
            return None

    def poll(self, timeout=.000001):
        if self._sock == None or self._sock._socket_closed == True:
            self._sock = self._socket_source.socket()
            self._listen()
            self._sock.settimeout(.1)

        return self._accept_request(timeout)
