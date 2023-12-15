import struct
import uModBus.const as Const
import uModBus.functions as functions

class Client:
    def __init__(self, default_unit_id):
        self._default_unit_id = default_unit_id
        pass

    def read_coils(self, starting_addr, coil_qty, *, unit=None):
        modbus_pdu = functions.read_coils(starting_addr, coil_qty)
        if unit is None:
            unit = self._default_unit_id

        response = self._send_receive(unit, modbus_pdu, True)
        status_pdu = self._bytes_to_bool(response)

        return status_pdu[:coil_qty]

    def read_discrete_inputs(self, starting_addr, input_qty, *, unit=None):
        modbus_pdu = functions.read_discrete_inputs(starting_addr, input_qty)
        if unit is None:
            unit = self._default_unit_id

        response = self._send_receive(unit, modbus_pdu, True)
        status_pdu = self._bytes_to_bool(response)

        return status_pdu[:input_qty]

    def read_holding_registers(self, starting_addr, register_qty, *, unit=None, signed = True):
        modbus_pdu = functions.read_holding_registers(starting_addr, register_qty)
        if unit is None:
            unit = self._default_unit_id

        response = self._send_receive(unit, modbus_pdu, True)
        register_value = self._to_short(response, signed)

        return register_value

    def read_input_registers(self, starting_address, register_quantity, *, unit=None, signed = True):
        modbus_pdu = functions.read_input_registers(starting_address, register_quantity)
        if unit is None:
            unit = self._default_unit_id
            
        response = self._send_receive(unit, modbus_pdu, True)
        register_value = self._to_short(response, signed)

        return register_value

    def write_single_coil(self, output_address, output_value, *, unit=None):
        modbus_pdu = functions.write_single_coil(output_address, output_value)
        if unit is None:
            unit = self._default_unit_id
            
        response = self._send_receive(unit, modbus_pdu, False)
        operation_status = functions.validate_resp_data(response, Const.WRITE_SINGLE_COIL,
                                                        output_address, value=output_value, signed=False)

        return operation_status

    def write_single_register(self, register_address, register_value, *, unit=None, signed=True):
        modbus_pdu = functions.write_single_register(register_address, register_value, signed)
        if unit is None:
            unit = self._default_unit_id


        response = self._send_receive(unit, modbus_pdu, False)
        operation_status = functions.validate_resp_data(response, Const.WRITE_SINGLE_REGISTER,
                                                        register_address, value=register_value, signed=signed)

        return operation_status

    def write_multiple_coils(self, starting_address, output_values, *, unit=None):
        modbus_pdu = functions.write_multiple_coils(starting_address, output_values)
        if unit is None:
            unit = self._default_unit_id

        response = self._send_receive(unit, modbus_pdu, False)
        operation_status = functions.validate_resp_data(response, Const.WRITE_MULTIPLE_COILS,
                                                        starting_address, quantity=len(output_values))

        return operation_status

    def write_multiple_registers(self, starting_address, register_values, *, unit=None, signed=True):
        modbus_pdu = functions.write_multiple_registers(starting_address, register_values, signed)
        if unit is None:
            unit = self._default_unit_id

        response = self._send_receive(unit, modbus_pdu, False)
        operation_status = functions.validate_resp_data(response, Const.WRITE_MULTIPLE_REGISTERS,
                                                        starting_address, quantity=len(register_values))

        return operation_status

    def _bytes_to_bool(self, byte_list):
        bool_list = []
        for index, byte in enumerate(byte_list):
            bool_list.extend([bool(byte & (1 << n)) for n in range(8)])

        return bool_list

    def _to_short(self, byte_array, signed=True):
        response_quantity = int(len(byte_array) / 2)
        fmt = '>' + (('h' if signed else 'H') * response_quantity)

        return struct.unpack(fmt, byte_array)

class Server:
    def __init__(self, unit_addr=None, *, number_coils=None, number_discrete_inputs=None,
    number_input_registers=None, number_holding_registers=None):
        self.unit_addr = unit_addr 

        if number_coils is not None:
            self.coils = [0] * number_coils

        if number_discrete_inputs is not None:
            self.discrete_inputs = [0] * number_discrete_inputs
      
        if number_input_registers is not None:
            self.input_registers = _ValueRegisters(number_input_registers)

        if number_holding_registers is not None:
            self.holding_registers = _ValueRegisters(number_holding_registers)

       
    def handle_request(self, data):
        unit_addr = data[0]
        if self.unit_addr is not None and self.unit_addr != unit_addr:
            print(f"Unit address {unit_addr} does not match {self.unit_addr}")
            return

        function_code, address = struct.unpack_from('>BH', data, 1)

        if function_code in [Const.READ_COILS, Const.READ_DISCRETE_INPUTS]:
            quantity = struct.unpack_from('>H', data, 4)[0]
            if not self._within_limits(function_code, quantity, address):
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                return
            if function_code == Const.READ_COILS:
                data = self.coils[address:address+quantity]
            else:
                data = self.discrete_inputs[address:address+quantity]

        elif function_code in [Const.READ_HOLDING_REGISTERS, Const.READ_INPUT_REGISTER]:
            quantity = struct.unpack_from('>H', data, 4)[0]
            if not self._within_limits(function_code, quantity, address):
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                return

            if function_code == Const.READ_HOLDING_REGISTERS:
                data = self.holding_registers.raw[address:address+quantity]
            else:
                data = self.input_registers.raw[address:address+quantity]
            data = b''.join(data)

        elif function_code == Const.WRITE_SINGLE_COIL:
            quantity = None
            data = data[4:6]
            if not self._within_limits(function_code, quantity, address):
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                return
            # allowed values: 0x0000 or 0xFF00
            if (data[0] not in [0x00, 0xFF]) or data[1] != 0x00:
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                return
            self.coils[address] = data[0] & 1

        elif function_code == Const.WRITE_SINGLE_REGISTER:
            quantity = None
            data = data[4:6]
            if not self._within_limits(function_code, quantity, address):
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                return
            self.holding_registers.raw[address] = data
            # all values allowed

        elif function_code == Const.WRITE_MULTIPLE_COILS:
            quantity = struct.unpack_from('>H', data, 4)[0]
            if not self._within_limits(function_code, quantity, address):
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                raise ModbusException(function_code, Const.ILLEGAL_DATA_VALUE, self)
            data = data[7:]
            if len(data) != ((quantity - 1) // 8) + 1:
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                raise ModbusException(function_code, Const.ILLEGAL_DATA_VALUE, self)
            self.coils[address:address+quantity] = self.data_as_bits(data, quantity)

        elif function_code == Const.WRITE_MULTIPLE_REGISTERS:
            quantity = struct.unpack_from('>H', data, 4)[0]
            if not self._within_limits(function_code, quantity, address):
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                return
            data = data[7:]
            if len(data) != quantity * 2:
                self.send_exception(function_code, Const.ILLEGAL_DATA_ADDRESS)
                raise ModbusException(function_code, Const.ILLEGAL_DATA_VALUE, self)
            self.holding_registers.raw[address:address+quantity] = [data[i:i+2] for i in range(0, quantity*2, 2)]

        else:
            # Not implemented functions
            quantity = None
            data = data[4:]
            self.send_exception(function_code, Const.ILLEGAL_FUNCTION)
            return
 
        self.send_response(unit_addr, function_code, address, quantity, data, data)

        return (function_code, address, quantity)

    def send_response(self, slave_addr, function_code, request_register_addr, request_register_qty, request_data, values=None, signed=False):
        modbus_pdu = functions.response(function_code, request_register_addr, request_register_qty, request_data, values, signed)
        self._send(modbus_pdu, slave_addr)

    def send_exception_response(self, slave_addr, function_code, exception_code):
        modbus_pdu = functions.exception_response(function_code, exception_code)
        self._send(modbus_pdu, slave_addr)

    def send_exception(self, function_code, exception_code):
        addr = self.unit_addr
        if addr is None:
            addr = 255
        self.send_exception_response(addr, function_code, exception_code)


    def data_as_bits(self, data, quantity):
        bits = []
        for byte in data:
            for i in range(0, 8):
                bits.append((byte >> i) & 1)
                if len(bits) == quantity:
                    return bits

    def _within_limits(self, function_code, quantity, address):
       
        if function_code == Const.READ_DISCRETE_INPUTS:
            object_count = len(self.discrete_inputs)
            quantity_max = 0x07D0
        elif function_code in [Const.READ_COILS, Const.WRITE_SINGLE_COIL, Const.WRITE_MULTIPLE_COILS]:
            object_count = len(self.coils)
            quantity_max = 0x07D0
        elif function_code == Const.READ_INPUT_REGISTER:
            object_count = len(self.input_registers)
            quantity_max = 0x007D
        else: # Holding register
            object_count = len(self.holding_registers)
            quantity_max = 0x007D
        
        if quantity is not None and (quantity < 1 or quantity > quantity_max):
            return False

        if quantity == None:
            quantity = 0

        if quantity + address > object_count:
            return False
        else: 
            return True


class ModbusException(Exception):
    def __init__(self, function_code, exception_code, instance):
        instance.send_exception_response(instance.unit_addr, function_code, exception_code)
        self.function_code = function_code
        self.exception_code = exception_code


class _ValueRegisters():
    def __init__(self, length):
        self.raw = [bytes(2)] * length
        self.signed = [False] * length
        self.byteswap = [False] * length

    def __len__(self):
        return len(self.raw)

    def __setitem__(self, index, value):
        if isinstance(index, int):
            self._set_value(index, value)
        elif isinstance(index, slice):
            start = index.start
            if start is None:
                start = 0
            end = index.stop
            if end is None:
                end = len(self)
            end = min(end, start + len(value))

            for i in range(start, end):
                self._set_value(i, value[i-start])

        else:
            raise TypeError('Index must be an integer or slice')
            

    def __getitem__(self, index):
        if isinstance(index, int):
            return self._get_value(index)
        elif isinstance(index, slice):
            start = index.start
            if start is None:
                start = 0
            end = index.stop
            if end is None:
                end = len(self)

            return [self._get_value(i) for i in range(start, end)]
        else:
            raise TypeError('Index must be an integer or slice')

    def _set_value(self, index, value):
        format = '<' if self.byteswap[index] else '>'
        format += 'h' if self.signed[index] else 'H'

        try:
            self.raw[index] = struct.pack(format, value)
        except OverflowError:
            raise OverflowError(f'Address {index} value {value} must be between {((-32768 if self.signed[index] else 0))} and {(32767 if self.signed[index] else 65535)}')


    def _get_value(self, index):
        format = '<' if self.byteswap[index] else '>'
        format += 'h' if self.signed[index] else 'H'

        return struct.unpack(format, self.raw[index])[0]
