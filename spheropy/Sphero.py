"""
Tools for controlling a Sphero 2.0. Sphero is the main class, all others define
parameter or return classes.

Most sphero commands return a Response object, that has two data fields. 
`response.success` indicates if the operation was successful, and
`response.data` is any returned data, when appropriate.

"""

from __future__ import print_function
from collections import namedtuple
import struct
import time
import threading

from enum import Enum
from spheropy.BluetoothWrapper import BluetoothWrapper
from spheropy.DataStream import DataStreamManager
from spheropy.Exception import SpheroException
from spheropy.Options import PermanentOptions
from spheropy.Util import nothing, outside_range, int_to_bytes, check_sum, eprint

# Python 3 compatibility
py3 = False
import sys
if sys.version_info > (3,):
    py3 = True
    def buffer(something):
        if isinstance(something,str):
            return bytes(something,encoding="ascii")
        return bytes(something)

_MSRP = {  # taken from sphero api docs
    0x00: "OK",  # succeeded
    0x01: "Error",  # non-specific error
    0x02: "Checksum Error",  # chucksum failure
    0x03: "Fragmented Command",  # FRAG command
    0x04: "Unknown Command",  # unknown command id
    0x05: "Command unsupported",
    0x06: "Bad Message Format",
    0x07: "Invalid Paramter values",
    0x08: "Failed to execute command",
    0x09: "Unknown Device Id",
    0x0A: "Ram access need, but is busy",
    0x0B: "Incorrect Password",
    0x31: "Voltage too low for reflash",
    0x32: "Illegal page number",
    0x33: "Flash Fail: page did not reprogram correctly",
    0x34: "Main application corruptted",
    0x35: "Msg state machine timed out"
}


_SOP1 = 0xff
_ANSWER = 0xff
_NO_ANSWER = 0xfe
_ACKNOWLEDGMENT = 0xff
_ASYNC = 0xfe

_CORE = 0x00
_CORE_COMMANDS = {
    'PING': 0x01,
    'GET VERSIONING': 0x02,
    'SET NAME': 0x10,
    'GET BLUETOOTH INFO': 0x11,
    'GET POWER STATE': 0x20,
    'SET POWER NOTIFICATION': 0x21,
    'SLEEP': 0x22,
    'GET VOLTAGE TRIP': 0x23,
    'SET VOLTAGE TRIP': 0x24,
    'SET INACT TIMEOUT': 0x25,
    'L1': 0x40,
    'L2': 0x41,
    'ASSIGN TIME': 0x50,
    'POLL PACKET TIMES': 0x51

}

_SPHERO = 0x02
_SPHERO_COMMANDS = {
    'SET HEADING': 0x01,
    'SET STABILIZATION': 0x02,
    'SET ROTATION RATE': 0x03,
    'GET CHASSIS ID': 0x07,
    'SET DATA STRM': 0x11,
    'SET COLLISION DETECT': 0x12,
    'SET COLOR': 0x20,
    'SET BACKLIGHT': 0x21,
    'GET COLOR': 0x22,
    'ROLL': 0x30,
    'BOOST': 0x31,
    'SET RAW MOTOR': 0x33,
    'MOTION TIMEOUT': 0x34,
    'SET PERM OPTIONS': 0x35,
    'GET PERM OPTIONS': 0x36,
    'SET TEMP OPTIONS': 0x37,
    'GET TEMP OPTIONS': 0x38,

}

BluetoothInfo = namedtuple("BluetoothInfo", ['name', 'address', 'color'])
Color = namedtuple('Color', ['r', 'g', 'b'])
MotorValue = namedtuple('MotorValue', ['mode', 'power'])
PacketTime = namedtuple('PacketTime', ['offset', 'delay'])
PowerState = namedtuple('PowerState', [
                        'recVer', 'power_state', 'batt_voltage', 'num_charges', 'time_since_chg'])
Response = namedtuple('Response', ['success', 'data'])
CollisionMsg = namedtuple('CollisionMsg', [
                          'x', 'y', 'z', 'axis', 'x_magnitude', 'y_magnitude', 'speed', 'timestamp'])


class MotorState(Enum):
    """
    An enum to represent possible motor states
    """
    off = 0x00
    forward = 0x01
    reverse = 0x02
    brake = 0x03
    ignore = 0x04


class Sphero(object):
    """
    Class representing a sphero. Can be used in a `with` block or managed explicitly.

    All direct sphero commands will return a `Response` object. where `response.success`
    indicates if the command ran successfully, and `response.data` will contain the
    data of the response or what went wrong. Other returns will be specified

    ### Usage:

        #!python
        from spheropy.Sphero import Sphero
        # explicit managment
        s = Sphero("Sphero-YWY", "68:86:E7:07:59:71")
        s.connect()
        s.start() # starts receiving data from sphero
        s.roll(50, 0)
        s.exit()

        # context manager
        with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
            s.roll(50, 0)
    """
# Static Methods

    @classmethod
    def find_spheros(cls, tries=5):
        """
        Returns a dictionary from names to addresses of all available spheros
        `tries` indicates the number of scans to perform before returning results.

        ### Usage:

            #!python
            from spheropy.Sphero import Sphero

            found_spheros = Sphero.find_spheros()
            for key, value in found_sphero.iteritems():
                print("Name: {}\tAddress: {}".format(key, value))
        """
        return BluetoothWrapper.find_free_devices(tries=tries, regex="[Ss]phero")


# Working
    def __init__(self, name, address, port=1, response_time_out=1, number_tries=5):
        """
        `name` is mostly used in printing error and information messages, usefull when working with
        more then one sphero.

        `address` is the bluetooth address and `port` is the RFCOMM port to use every sphero I've used
        uses port 1 so you unless you have trouble connectng it shouldn't need to change.

        `response_time_out` indicates how long to wait in seconds for a response after a message
        that expects a response is sent ,it does not include sendng time.

        Any command will be sent up to `number_tries` untill it is successful. This only happens
        if a response is expected, otherwise it's sent once.  A single command
        with a response may block for up to `response_time_out` X `number_tries` seconds
        """
        super(Sphero, self).__init__()
        self.bluetooth = BluetoothWrapper(address, port)
        """ access to bluetooth wrapper, avoid using """
        self.suppress_exception = False
        """ suppress_exceptions when used in `with` block """
        self._seq_num = 0
        self.number_tries = number_tries
        """ number of times to try to send a command to sphero """

        self._msg_lock = threading.Lock()
        self._msg = bytearray(2048)
        self._msg[0] = _SOP1

        self._response_lock = threading.Lock()
        self._response_event_lookup = {}
        self._responses = {}
        self._response_time_out = response_time_out

        # self._recieve_thread = threading.Thread(target=self._recieve_loop) # should only be available after connect

        self._data_stream = None
        self._asyn_func = {
            0x01: self._power_notification,
            0x02: self._forward_L1_diag,
            0x03: self._sensor_data,
            0x07: self._collision_detect,
            # 0x0B: self._self_level_result,
            # 0x0C: self._gyro_exceeded
        }

        self._sensor_callback = nothing
        self._power_callback = nothing
        self._collision_callback = nothing

    def __enter__(self):
        """ for use in contex manager """
        connected = False
        tries = 0
        while not connected and tries < self.number_tries:
            try:
                connected = self.bluetooth.connect(suppress_exceptions=True)
            except SpheroException:
                pass
            tries += 1
        if tries >= self.number_tries:
            raise SpheroException("Unable to connect to sphero")

        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ for use in context manager """
        self.disconnect()
        return self.suppress_exception

    def _recieve_loop(self):
        """ recieves data from sphero and parses it"""
        packet = bytearray(2)
        while self.bluetooth.is_connected():
            # state one
            try:
                # bytearray needs ord
                packet[0] = 0
                while packet[0] != _SOP1:
                    packet[0] = ord(self.bluetooth.receive(1))

                # state two
                packet[1] = ord(self.bluetooth.receive(1))
                packet_type = packet[1]
                if packet_type == _ACKNOWLEDGMENT:  # Sync Packet
                    self._handle_acknowledge()

                elif packet_type == _ASYNC:
                    self._handle_async()
                else:
                    eprint("Malformed Packet")
            except SpheroException:
                return

    def _handle_acknowledge(self):
        """
        Parses response packets from sphero. Response added to a response dictionary
        as a Response tuple where tuple[0] indicates success and tuple[1] is the data,
        the thread waiting on the response is alerted to it via an event registered
        in the response_event_lookup dictionary, and is responsible for parsing the data.
        all access should be done with the response_lock.
        """
        msrp = ord(self.bluetooth.receive(1))
        seq = ord(self.bluetooth.receive(1))
        length = ord(self.bluetooth.receive(1))
        if length == 0xff:
            pass
            # raise Exception("NOt Implemented _MSRP: {0}".format(_msrp))
            # TODO cover oxff cases
        array = self._read(length, offset=3)

        array[0] = msrp
        array[1] = seq
        array[2] = length
        checksum = check_sum(array[0:-1])
        if array[-1] != checksum:
            eprint("Malfromed Packet, recieved: {0} expected: {1}".format(
                array[-1], checksum))
            return
        else:
            event = None
            with self._response_lock:
                if seq in self._response_event_lookup:
                    event = self._response_event_lookup[seq]
                    del self._response_event_lookup[seq]
                else:
                    return
            if msrp == 0:
                self._responses[seq] = Response(True, array[3: length + 3 - 1])
            else:
                self._responses[seq] = Response(
                    False, _MSRP.get(msrp, "UNKNOWN ERROR"))
            event.set()

    def _handle_async(self):
        """
        Handles async (usually sensor) messages form sphero,
        It calls the a parser function which will call any regstered
        callback for each type of data
        """
        id_code = ord(self.bluetooth.receive(1))
        length_msb = ord(self.bluetooth.receive(1))
        length_lsb = ord(self.bluetooth.receive(1))
        length = (length_msb << 8) + length_lsb

        array = self._read(length, offset=3)

        array[0] = id_code
        array[1] = length_msb
        array[2] = length_lsb
        checksum = check_sum(array[0:-1])
        if array[-1] != checksum:
            eprint("Malfromed Packet, recieved: {0} expected: {1}".format(
                array[-1], checksum))
            return
        else:
            data = array[3:-1]
            tocall = self._asyn_func.get(id_code, nothing)
            thread = threading.Thread(target=tocall, args=(data,))
            thread.start()
            return

    def _read(self, length, offset=0):
        """
        reads a given length from the bluetooth, into a buffer, starting at a given offset
        """
        array = bytearray(offset)
        to_read = length
        while to_read > 0:
            out = self.bluetooth.receive(to_read)
            array += out
            to_read -= len(out)
        return array

    @property
    def _seq(self):
        """
        used for assigning unique seq numbers
        """
        self._seq_num += 1
        if self._seq_num > 0xff:
            self._seq_num = 1
        return self._seq_num

    def _send(self, did, cid, data, response):
        """
        sends data to sphero `did` is the device id, `cid` is the virtual core id
        for more information view sphero Docs.

        `data` is the data to send

        `response` indicates if a response is expected or not if it is it handles
        working with the event system, and blocks until response is recieved,
        or `self.response_time_out` elapses
        """
        event = None
        seq_number = 0
        data_length = len(data)
        if response:
            with self._response_lock:
                seq_number = self._seq
                event = threading.Event()
                self._response_event_lookup[seq_number] = event

        with self._msg_lock:
            self._msg[1] = _ANSWER if response else _NO_ANSWER
            self._msg[2] = did
            self._msg[3] = cid
            self._msg[4] = seq_number
            self._msg[5] = data_length + 1
            self._msg[6:6 + data_length] = data
            checksum = check_sum(
                self._msg[2: 6 + data_length])
            self._msg[6 + data_length] = checksum
            self.bluetooth.send(
                buffer(self._msg[0: 6 + data_length + 1]))

        if response:
            if event.wait(self._response_time_out):
                with self._response_lock:
                    return self._responses[seq_number]
        return Response(True, '')

    def connect(self, retries = 5):
        """
        Establishes a connection and
        returns a boolean indicating if the connection was successful.
        Retries: how often it should be tried before raising an error
        """
        while retries > 0:
            res = None
            try:
                res = self.bluetooth.connect()
            except:
                res = None
            if not res:
                retries -= 1
            else:
                break
        if not res:
            raise ValueError("Could not connect to device.")
        self._recieve_thread = threading.Thread(target=self._recieve_loop)
        return res

    def disconnect(self):
        """
        Closes the connection to the sphero.
        If sphero is not connected the call has no effect.
        """
        self.bluetooth.close()

    def _stable_send(self, did, cid, data, response):
        """
        A version of send that tries untill successful
        if response is false it will only try once
        """
        tries = 0
        success = False
        reply = None
        while not success and tries < self.number_tries:
            reply = self._send(did, cid, data, response)
            tries += 1
            success = reply.success
        return reply

    def is_alive(self):
        return self._recieve_thread.is_alive() & self.bluetooth.is_connected()

# CORE COMMANDS

    def ping(self):
        """
        The Ping command is used to verify both a solid data link with the caller
        and that Sphero is awake and dispatching commands.

        A Response tuple is returned with response.success indicating if a response
        is received back from the sphero, there is no accompanying data.

        # Usage

            #!python
            from spheropy.Sphero import Sphero

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                response = s.ping()
                print(response.success)
        """
        reply = self._stable_send(_CORE, _CORE_COMMANDS['PING'], [], True)
        return reply

    def get_versioning(self):
        """
        A Response tuple is returned, if `response.success == True`, then
        `response.data` will contain a tuple of the bytes of the versioning info.

        see Sphero api docs for more info.
        """
        reply = self._stable_send(
            _CORE, _CORE_COMMANDS['GET VERSIONING'], [], True)
        if reply.success:
            parsed = struct.unpack_from(">8B", buffer(reply.data))
            return Response(True, parsed)
        else:
            return reply

    def set_device_name(self, name, response=False):
        """
        This assigned name is held internally and produced as part of the Get Bluetooth Info
        service below. Names are clipped at 48 characters in length to support UTF - 8 sequences
        you can send something longer but the extra will be discarded.
        This field defaults to the Bluetooth advertising name.

        The returned Response objects data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        return self._stable_send(_CORE, _CORE_COMMANDS['SET NAME'], name, response)

    def get_bluetooth_info(self):
        """
        If successful the returned Response Object's data field
        is a BluetoothInfo object containing the textual
        name of the ball (defaults to the Bluetooth
        advertising name but can be changed), the Bluetooth address and
        the ID colors the ball blinks when not connected.
        """
        result = self._stable_send(
            _CORE, _CORE_COMMANDS['GET BLUETOOTH INFO'], [], True)
        if result.success:
            fmt = ">16s12sx3c"
            temp_tup = struct.unpack_from(fmt, buffer(result.data))
            name = temp_tup[0]
            name = name[:name.find('\x00' if not py3 else b'\x00')] # python3 needs byte object
            named_tuple = BluetoothInfo(
                name, temp_tup[1], (temp_tup[2], temp_tup[3], temp_tup[4]))
            return Response(True, named_tuple)
        else:
            return result

    def get_power_state(self):
        """
        If successful the response.data will contains a
        PowerState tuple with the following fields in this order.

            `recVer`: set to 1

            `powerState`: 1 = Charging, 2 = OK, 3 = Low, 4 = Critical

            `batt_voltage`: current battery voltage in 100ths of a volt

            `num_charges`: number of recharges in the lilfe of this sphero

            `time_since_chg`: seconds Awake
        `

        ### Usage:

            #!python
            from spheropy.Sphero import Sphero

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                response = s.get_power_state()
                if response.success:
                    power = response.data
                    print("power_state: {}".format(power.power_state))
                    print("Voltage: {}".format(power.batt_voltage))
                    print("Number Charges: {}".format(power.num_charges))
                    print("Time Since Charge: {}".format(power.time_since_chg))

        """
        reply = self._stable_send(
            _CORE, _CORE_COMMANDS['GET POWER STATE'], [], True)
        if reply.success:
            parsed_answer = struct.unpack_from('>BBHHH', buffer(reply.data))
            return Response(True, PowerState._make(parsed_answer))
        else:
            return reply

    def set_power_notification(self, setting, response=False):
        """
        Sets Async power notification messages to be sent. To access the notifications register a power_notfiation callback. Notifications
        are sent every 10 seconds

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        flag = 0x01 if setting else 0x00
        reply = self._stable_send(
            _CORE, _CORE_COMMANDS['SET POWER NOTIFICATION'], [flag], response)
        return reply

    def sleep(self, wakeup_time, response=False):
        """
        This command puts Sphero to sleep immediately.
        The sphero will automaticall reawaken after `wakeup_time` seconds.
        Zero does not program a wakeup interval, so it sleeps forever.

        The Sphero must be reconnected after this function is called. However,
        most settings are preserved.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        if wakeup_time < 0 or wakeup_time > 0xffff:
            return Response(False, None)
        big = wakeup_time >> 8
        little = (wakeup_time & 0x00ff)
        reply = self._stable_send(_CORE, _CORE_COMMANDS['SLEEP'], [
            big, little, 0, 0, 0], response)
        self.close()
        return reply

    def get_voltage_trip_points(self):
        """
        If successful the Response Object's data field contains a tuple of the
        voltage trip points for what Sphero considers Low and Critical battery.
        The values are expressed in 100ths of a volt,
        so the defaults of 7.00V and 6.50V respectively are returned as
        700 and 650.
        """
        reply = self._stable_send(
            _CORE, _CORE_COMMANDS['GET VOLTAGE TRIP'], [], True)
        if reply.success:
            parse = struct.unpack_from(">HH", buffer(reply.data))
            return Response(True, parse)
        else:
            return reply

    def set_voltage_trip_points(self, low, critical, response=False):
        """
        DOES NOT WORK
        not implemented
        This assigns the voltage trip points for Low and Critical battery voltages.
        The values are specified in 100ths of a volt and
        the limitations on adjusting these away from their defaults are:
        Vlow must be in the range 675 to 725 ( += 25)
        Vcrit must be in the range 625 to 675 ( += 25)
        There must be 0.25V of separation between the two values
        """
        assert False
        low = int_to_bytes(low, 2)
        crit = int_to_bytes(critical, 2)
        return self._stable_send(_CORE, _CORE_COMMANDS['SET VOLTAGE TRIP'], low + crit, response)

    def set_inactivity_timeout(self, timeout, response=False):
        """
        Sets inactivity time out. Value must be greater than 60 seconds,
        is preserved across power cycles.

       The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        if timeout < 0 or timeout > 0xffff:
            return False

        big = timeout >> 8
        little = (timeout & 0x00ff)
        reply = self._send(_CORE, _CORE_COMMANDS['SET INACT TIMEOUT'], [
            big, little], response)

        return reply

    def L1_diag(self):
        """
        This is a developer - level command to help diagnose aberrant behavior.
        Most system counters, process flags, and system states are decoded
        into human readable ASCII.

        If successful the Response Object's data field will contain an ASCII message.
        """
        event = None
        with self._response_lock:
            event = threading.Event()
            self._response_event_lookup['L1'] = event

        self._stable_send(_CORE, _CORE_COMMANDS['L1'], [], False)

        if event.wait(self._response_time_out * 10):
            response = None
            with self._response_lock:
                response = self._responses['L1']
            return Response(True, response)
        else:
            return Response(False, "no data recieved")

    def L2_diag(self):
        """
        DOES NOT WORK
        This is a developers - only command to help diagnose aberrant behavior.
        It is much less informative than the Level 1 command
        but it is in binary format and easier to parse
        Command not found
        """

        assert False
        return self._stable_send(_CORE, _CORE_COMMANDS['L2'], [], True)

    def assign_time(self, time_value, response=False):
        """
        Sets the internal timer to `time_value`. 
        This is the time that shows up in a collision message.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        return self._stable_send(_CORE, _CORE_COMMANDS['ASSIGN TIME'], int_to_bytes(time_value, 4), response)

    def poll_packet_times(self):
        """
        Command to help profile latencies
        returns a PacketTime tuple with fields:
        offset: the maximum - likelihood time offset of the Client clock to sphero's system clock
        delay: round - trip delay between client a sphero

        DOESN"T REALLY WORK YET....
        """
        # TODO time 1 gets mangled.
        time1 = int(round(time.time() * 1000))
        bit1 = (time1 & 0xff000000) >> 24
        bit2 = (time1 & 0x00ff0000) >> 16
        bit3 = (time1 & 0x0000ff00) >> 8
        bit4 = (time1 & 0x000000ff)
        reply = self._stable_send(_CORE, _CORE_COMMANDS['POLL PACKET TIMES'], [
            bit1, bit2, bit3, bit4], True)
        time4 = int(round(time.time() * 1000)) & 0xffffffff
        if reply.success:
            sphero_time = struct.unpack_from('>III', buffer(reply.data))
            offset = 0.5 * \
                ((sphero_time[1] - sphero_time[0]) + (sphero_time[2] - time4))
            delay = (time4 - sphero_time[0]) - \
                (sphero_time[2] - sphero_time[1])
            return PacketTime(offset, delay)

# _SPHERO COMMANDS

    def set_heading(self, heading, response=False):
        """
        Sets the spheros heading in degrees,
        heading must range between 0 to 359. This should move the
        back tail light.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        if heading < 0 or heading > 359:
            return Response(False, "heading must be between 0 and 359")

        heading_bytes = int_to_bytes(heading, 2)
        reply = self._stable_send(
            _SPHERO, _SPHERO_COMMANDS['SET HEADING'], heading_bytes, response)
        return reply

    def set_stabilization(self, stablize, response=False):
        """
        This turns on or off the internal stabilization of Sphero,
        the IMU is used to match the ball's orientation to its set points.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        flag = 0x01 if stablize else 0x00
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET STABILIZATION'], [flag], response)

    def set_rotation_rate(self, rate, response=False):
        """
        DOESN't WORK
        This sets the roation rate sphero will use to meet new heading commands
        Lower value offers better control, with a larger turning radius.
        The rate should be in degrees / sec,
        anythin above 199 the maxium value is used(400 degrees / sec)
        """
        # TODO returns unknown command
        if rate < 0:
            return Response(False, "USE POSITIVE RATE ONLY")
        if rate > 199:
            rate = 200
        else:
            rate = int(rate / 0.784)
        to_bytes = int_to_bytes(rate, 1)
        return self._send(_SPHERO, _SPHERO_COMMANDS['SET ROTATION RATE'], to_bytes, response)

    def get_chassis_id(self):
        """
        Returns the Chassis ID as an int.
        """
        response = self._stable_send(
            _SPHERO, _SPHERO_COMMANDS['GET CHASSIS ID'], [], True)

        if response.success:
            tup = struct.unpack_from('>H', buffer(response.data))
            return Response(True, tup[0])
        else:
            return response

    def set_data_stream(self, stream_settings, frequency, packet_count=0, response=False):
        """
        Sets data stream options, where `stream_settings` is a DataStreamManager object,
        and `frequency` how often you want to recieve data and `packet_count` indicates
        the number of packets you want to recieve, set to zero for unlimited streaming.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.

        ### Usage:

            #!python
            from spheropy.Sphero import Sphero
            from spheropy.DataStream import DataStreamManager

            dsm = DataStreamManager()
            dsm.acc = True

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                s.set_data_stream(dsm, 10 packet_count=2)
        """
        self._data_stream = stream_settings.copy()
        divisor = int_to_bytes(int(400.0 / frequency), 2)
        samples = int_to_bytes(self._data_stream.number_frames, 2)
        mask1 = int_to_bytes(self._data_stream._mask1, 4)
        mask2 = int_to_bytes(self._data_stream._mask2, 4)
        data = divisor + samples + mask1 + [packet_count] + mask2
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET DATA STRM'], data, response)

    def stop_data_stream(self):
        """
        stops data streaming
        """
        result = self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET DATA STRM'], [
                                   0xff, 0, 0, 0, 0, 0, 0, 0, 1], True)
        if result.success:
            self._data_stream = None
        return result

    def start_collision_detection(self, x_threshold, x_speed, y_threshold, y_speed, dead=1000, response=False):
        """
        Starts collision detection. `Threshold` values represent the max threshold,
        and `speed` is added to the thresholds to rang detection by the spheros speed,
        `dead` is the minimum time between detections
        in ms. all data must be in the range 0...255

        For more infomation see Collision Detection pdf

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        method = 0x01
        dead = int(dead / 10)
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET COLLISION DETECT'], [method, x_threshold, x_speed, y_threshold, y_speed, dead], response)

    def stop_collision_detection(self, response=False):
        """
        Stops collision detection
        """
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET COLLISION DETECT'], [0, 0, 0, 0, 0, 0], response)

    def set_color(self, red, green, blue, default=False, response=False):
        """
        Sets the color of the sphero given rgb components between 0 and 255,
        if `default` is true, sphero will default to that color when first connected

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.

        ### Usage:

            #!python
            from time import sleep
            from spheropy.Sphero import Sphero

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                s.set_color(255, 0, 0)
                sleep(1)
                s.set_color(0, 255, 0)
                sleep(1)
                s.set_color(0, 0, 255)

        """
        red = int_to_bytes(red, 1)
        blue = int_to_bytes(blue, 1)
        green = int_to_bytes(green, 1)
        flag = [0x01] if default else [0x00]
        return self._stable_send(
            _SPHERO, _SPHERO_COMMANDS['SET COLOR'], red + green + blue + flag, response)

    def set_back_light(self, brightness, response=False):
        """
        Controls the brightness of the back LED, non persistent

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        brightness = int_to_bytes(brightness, 1)
        return self._stable_send(
            _SPHERO, _SPHERO_COMMANDS['SET BACKLIGHT'], brightness, response)

    def get_color(self):
        """
        If sucessful `response.data` contains the sphero default
        Color, may not be the current color shown.

        ### Usage:

            #!python
            from spheropy.Sphero import Sphero

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                response = s.get_color()
                if response.success:
                    color = response.data
                    print("r: {}  b: {}  g: {}".format(color.r, color.b, color.g))

        """
        response = self._stable_send(
            _SPHERO, _SPHERO_COMMANDS['GET COLOR'], [], True)
        if response.success:
            parse = struct.unpack_from('>BBB', buffer(response.data))
            return Response(True, Color._make(parse))
        else:
            return response

    def roll(self, speed, heading, fast_rotate=False, response=False):
        """
        Commands the sphero to move. `speed` ranges from 0..255, while `heading` is
        in degrees from 0..359, 0 is strait, 90 is to the right, 180 is back and
        270 is to the left. When `fast_rotate` is set to True sphero will rotate as
        quickly as possible to given heading regardless of speed.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        gobit = [0x02] if fast_rotate else [0x01]
        speed = int_to_bytes(speed, 1)
        heading = int_to_bytes(heading, 2)
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['ROLL'], speed + heading + gobit, response)

    def stop(self, response=False):
        """
        Commands the Shero to stop.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['ROLL'], [0, 0, 0, 0], response)

    def boost(self, activate, response=True):
        """
        Activates or deactivates boost, depending on the truth value of `activate`.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        activate = 0x01 if activate else 0x00
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['BOOST'], [activate], response)

    def set_raw_motor_values(self, left_value, right_value, response=False):
        """
        Allows direct controle of the motors
        both motor values should be MotorValue tuple

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        lmode = left_value.mode.value
        lpower = left_value.power
        rmode = right_value.mode.value
        rpower = right_value.power
        if outside_range(lpower, 0, 255) or outside_range(rpower, 0, 255):
            raise SpheroException("Values outside of range")
        data = [lmode, lpower, rmode, rpower]
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET RAW MOTOR'], data, response)

    def set_motion_timeout(self, timeout, response=False):
        """
        This sets the ultimate timeout for the last motion command
        to keep Sphero from rolling away
        timeout is in miliseconds and defaults to 2000
        for this to be in effect motion timeout must be
        in must be set in permanent options

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        if self._outside_range(timeout, 0, 0xFFFF):
            raise SpheroException("Timeout outside of valid range")
        timeout = int_to_bytes(timeout, 2)
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['MOTION TIMEOUT'], timeout, response)

    def set_permanent_options(self, options, response=False):
        """
        Set Options, for option information see PermanentOptionFlag docs.
        Options persist across power cycles. `options` is a Permanent Option Object

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.

        ### Usage:

            #!python
            from spheropy.Sphero import Sphero
            from spheropy.Options import PermanentOptions

            po = PermanentOptions()
            po.set_light_wakeup_sensitivity= True
            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                s.set_permanent_options(po)

        """
        options = int_to_bytes(options.bitflags, 8)
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET PERM OPTIONS'], options, response)

    def get_permanent_options(self):
        """
        If successful `result.data` contains the Permenent Options of the sphero
        """
        result = self._stable_send(
            _SPHERO, _SPHERO_COMMANDS['GET PERM OPTIONS'], [], True)
        if result.success:
            settings = struct.unpack_from('>Q', buffer(result.data))
            options = PermanentOptions()
            options.bitflags = settings[0]
            return Response(True, options)
        else:
            return result

    def set_stop_on_disconnect(self, value=True, response=False):
        """
        Sets sphero to stop on disconnect, this is a one_shot, so it must be reset on reconnect.

        Set `value` to false to turn off behavior.

        The returned Response object's data field will be empty,
        but if `response` is set to `True`, it's success field
        will indicate if the command was successful.
        """
        value = 1 if value else 0
        return self._stable_send(_SPHERO, _SPHERO_COMMANDS['SET TEMP OPTIONS'], [
            0, 0, 0, value], response)

    def will_stop_on_disconnect(self):
        """
        Returns if the sphero will stop when it is disconnected.
        """
        result = self._stable_send(
            _SPHERO, _SPHERO_COMMANDS['GET TEMP OPTOINS'], [], True)
        if result.success:
            return Response(True, bool(result.data))
        else:
            return result
# ASYNC

    def register_sensor_callback(self, func):
        """
        Register a function to call when a sensor message is recieved.
        `func` must be callable and it will be started in its own thread
        as not to block the recieve loop.

        ### Usage:

            #!python
            from time import sleep
            from spheropy.Sphero import Sphero

            dsm = DataStreamManager()
            dsm.acc = True
            dsm.odom = True

            #assume acc and odom sensor messages have be requested
            def callback(sensor_data):
                #sensor_data will be an array of dictionaries where
                #each item is a frame sent by the sphero
                for  frames in sensor_data:
                    print(frames['acc'])
                    print(frames['odom'])

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                s.register_sensor_callback(callback)
                s.set_data_stream(dsm, 10 packet_count=2)
                # callback will be called twice
                sleep(1) # so data will be recieved before exit

        """
        assert callable(func)
        self._sensor_callback = func

    def register_power_callback(self, func):
        """
        Register a function to call when an async power notification is recieved. `func` must be callable and it will be started in it's own thread. The call back will recieve an integer with:

        1 = charging

        2 = OK

        3 = Low

        4 = Critical 

        ### Usage:

            #!python
            import time
            from sphropy.Sphero import Sphero

            def callback(notification):
                print(notification)

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                s.register_power_callback(callback)
                s.set_power_notification(True)
                time.sleep(20)

        """
        assert callable(func)
        self._power_callback = func

    def register_collision_callback(self, func):
        """
        Registers a callback function for asyn collision notifications.
        `func` must be callable and it is started in it's own thread

        ### Usage:

            #!python
            import time
            from spheropy.Sphero import Sphero

            def callback(data):
                #data will be a CollisionMsg
                print(data.x)
                print(data.y)
                print(data.axis)
                print(data.speed)
                print(data.timestamp)

            with Sphero("Sphero-YWY", "68:86:E7:07:59:71") as s:
                s.register_collision_callback(callback)
                s.start_collision_detection(100, 50, 100, 50)
                time.sleep(10)
                s.stop_collision_detection()

        """
        assert callable(func)
        self._collision_callback = func

    def _power_notification(self, notification):
        """
        Parses a power notification and calls the callback
        """
        parsed = struct.unpack_from('B', buffer(notification))
        self._power_callback(parsed[0])

    def _forward_L1_diag(self, data):
        """
        This is used to forwrard the L1 diagnostic call. It
        is treated differently becuase it is sent as an async message
        even though it is in response to a system call
        """
        event = None
        with self._response_lock:
            self._responses['L1'] = str(data)
            if 'L1' in self._response_event_lookup:
                event = self._response_event_lookup['L1']
                del self._response_event_lookup['L1']
        event.set()

    def _sensor_data(self, data):
        """
        parses sensor data and forwards it to registered callback
        """
        if self._data_stream is None:
            self.stop_data_stream()
            return
        parsed = self._data_stream.parse(data)
        self._sensor_callback(parsed)

    def _collision_detect(self, data):
        """
        Parses collision events and calls teh callback
        """

        fmt = ">3hB2HbI"
        unpacked = struct.unpack_from(fmt, buffer(data))

        x_list = ['x'] if unpacked[3] & 0x01 else []
        y_list = ['y'] if unpacked[3] & 0x02 else []
        parsed = CollisionMsg(unpacked[0], unpacked[1], unpacked[2], x_list +
                              y_list, unpacked[4], unpacked[5], unpacked[6], unpacked[7])
        self._collision_callback(parsed)

    def start(self):
        self._recieve_thread.start()
