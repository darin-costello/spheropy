"""
Tools for controlling a Sphero 2.0
"""
from __future__ import print_function


from collections import namedtuple
import struct
import sys
import time
import threading

from enum import Enum
from spheropy.BluetoothWrapper import BluetoothWrapper
from spheropy.DataStream import DataStreamManager
from spheropy.Options import PermanentOptions
from spheropy.Util import nothing

MSRP = {  # taken from sphero api docs
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


SOP1 = 0xff
ANSWER = 0xff
NO_ANSWER = 0xfe
ACKNOWLEDGMENT = 0xff
ASYNC = 0xfe

CORE = 0x00
CORE_COMMANDS = {
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
    'POLL PACKET TIMES': 0x51

}

SPHERO = 0x02
SPHERO_COMMANDS = {
    'SET HEADING': 0x01,
    'SET STABILIZATION': 0x02,
    'SET ROTATION RATE': 0x03,
    'GET CHASSIS ID': 0x07,
    'SET DATA STRM': 0x11,
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


def eprint(*args, **kwargs):
    """
    Prints message to std error
    """
    print(*args, file=sys.stderr, **kwargs)


BluetoothInfo = namedtuple("BluetoothInfo", ['name', 'address', 'color'])
Color = namedtuple('Color', ['r', 'g', 'b'])
MotorValue = namedtuple('MotorValue', ['mode', 'power'])
PacketTime = namedtuple('PacketTime', ['offset', 'delay'])
PowerState = namedtuple('PowerState', [
                        'recVer', 'power_state', 'batt_voltage', 'num_charges', 'time_since_chg'])
Response = namedtuple('Response', ['success', 'data'])


class MotorState(Enum):
    """
    An enum to represent possible motor states
    """
    off = 0x00
    forward = 0x01
    reverse = 0x02
    brake = 0x03
    ignore = 0x04


class SpheroException(Exception):
    """ Exception class for the Sphero"""
    pass


class Sphero(threading.Thread):
    """ class representing a sphero """
# Static Methods
    @staticmethod
    def _check_sum(data):
        """
        calculates the checksum as The modulo 256 sum of all the bytes bit inverted (1's complement)
        """
        return (sum(data) % 256) ^ 0xff

    @classmethod
    def find_spheros(cls, tries=5):
        """
        Returns a dictionary from names to addresses of all available spheros
        """
        return BluetoothWrapper.find_free_devices(tries=tries, regex="[Ss]phero")

    @staticmethod
    def _int_to_bytes(number, length):
        number = int(number)
        result = []
        for i in range(0, length):
            result.append((number >> (i * 8)) & 0xff)
        result.reverse()
        return result

    @staticmethod
    def _outside_range(number, min_range, max_range):
        return number < min_range or number > max_range

# Working
    def __init__(self, name, address, port=1, response_time_out=1, number_tries=5):
        super(Sphero, self).__init__()
        self.bluetooth = BluetoothWrapper(address, port)
        self.suppress_exception = False
        self._seq_num = 0
        self.number_tries = number_tries

        self._msg_lock = threading.Lock()
        self._msg = bytearray(2048)
        self._msg[0] = SOP1

        self._response_lock = threading.Lock()
        self._response_event_lookup = {}
        self._responses = {}
        self._response_time_out = response_time_out

        self._data_stream = DataStreamManager()
        self._asyn_func = {
            0x01: self._power_notification,
            0x02: self._forward_L1_diag,
            0x03: self._sensor_data,
            # 0x07: self._collision_detect,
            # 0x0B: self._self_level_result,
            # 0x0C: self._gyro_exceeded
        }

        self._sensor_callback = nothing
        self._power_callback = nothing

    def __enter__(self):
        connected = False
        tries = 0
        while not connected and tries < self.number_tries:
            try:
                self.connect()
                connected = True
            except SpheroException:
                tries += 1
        if tries >= self.number_tries:
            raise SpheroException("Unable to connect to sphero")

        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return self.suppress_exception

    def _recieve_loop(self):

        packet = bytearray(2)
        while self.bluetooth.is_connected():
            # state one
            packet[0] = 0
            while packet[0] != SOP1:
                packet[0] = self.bluetooth.receive(1)

            # state two
            packet[1] = self.bluetooth.receive(1)
            packet_type = packet[1]
            if packet_type == ACKNOWLEDGMENT:  # Sync Packet
                self._handle_acknowledge()

            elif packet_type == ASYNC:
                self._handle_async()
            else:
                eprint("Malformed Packet")

    def _handle_acknowledge(self):
        msrp = ord(self.bluetooth.receive(1))
        seq = ord(self.bluetooth.receive(1))
        length = ord(self.bluetooth.receive(1))
        if length == 0xff:
            raise Exception("NOt Implemented")
            # TODO cover oxff cases
        array = self._read(length, offset=3)

        array[0] = msrp
        array[1] = seq
        array[2] = length
        checksum = Sphero._check_sum(array[0:-1])
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
                    False, MSRP.get(msrp, "UNKNOWN ERROR"))
            event.set()

    def _handle_async(self):
        id_code = ord(self.bluetooth.receive(1))
        length_msb = ord(self.bluetooth.receive(1))
        length_lsb = ord(self.bluetooth.receive(1))
        length = (length_msb << 8) + length_lsb

        array = self._read(length, offset=3)

        array[0] = id_code
        array[1] = length_msb
        array[2] = length_lsb
        checksum = Sphero._check_sum(array[0:-1])
        if array[-1] != checksum:
            eprint("Malfromed Packet, recieved: {0} expected: {1}".format(
                array[-1], checksum))
            return
        else:
            data = array[3:-1]
            tocall = self._asyn_func.get(id_code, self._nothing)
            thread = threading.Thread(target=tocall, args=(data,))
            thread.start()
            return

    def _read(self, length, offset=0):
        array = bytearray(offset)
        to_read = length
        while to_read > 0:
            out = self.bluetooth.receive(to_read)
            array += out
            to_read -= len(out)
        return array

    @property
    def _seq(self):
        self._seq_num += 1
        if self._seq_num > 0xff:
            self._seq_num = 1
        return self._seq_num

    def _send(self, did, cid, data, response):
        event = None
        seq_number = 0
        data_length = len(data)
        if response:
            with self._response_lock:
                seq_number = self._seq
                event = threading.Event()
                self._response_event_lookup[seq_number] = event

        with self._msg_lock:
            self._msg[1] = ANSWER if response else NO_ANSWER
            self._msg[2] = did
            self._msg[3] = cid
            self._msg[4] = seq_number
            self._msg[5] = data_length + 1
            self._msg[6:6 + data_length] = data
            checksum = Sphero._check_sum(
                self._msg[2: 6 + data_length])
            self._msg[6 + data_length] = checksum
            self.bluetooth.send(
                buffer(self._msg[0: 6 + data_length + 1]))

        if response:
            if event.wait(self._response_time_out):
                with self._response_lock:
                    return self._responses[seq_number]
        return Response(True, '')

    def connect(self):
        """
        Connects to the sphero with the given address
        """
        self.bluetooth.connect()

    def close(self):
        """
        Closes the connection to the sphero,
        if sphero is not connected call has no effect
        """
        self.bluetooth.close()

    def _stable_send(self, did, cid, data, response):
        tries = 0
        success = False
        reply = None
        while not success and tries < self.number_tries:
            reply = self._send(did, cid, data, response)
            tries += 1
            success = reply.success
        return reply
# CORE COMMANDS

    def ping(self, response=True):
        """
        The Ping command is used to verify both a solid data link with the Client
        and that Sphero is awake and dispatching commands.
        returns true if a response is recieved and was requested, false otherwise
        """
        reply = self._send(CORE, CORE_COMMANDS['PING'], [], response)
        return reply

    def get_versioning(self):
        """
        Returns a tuple of the bytes of the versioning info see Sphero api docs for more info.
        """
        reply = self._send(CORE, CORE_COMMANDS['GET VERSIONING'], [], True)
        if reply.success:
            parsed = struct.unpack_from(">8B", buffer(reply.data))
            return Response(True, parsed)
        else:
            return reply

    def set_device_name(self, name, response=False):
        """
        This assigned name is held internally and produced as part of the Get Bluetooth Info
        service below. Names are clipped at 48 characters in length to support UTF-8 sequences
        you can send something longer but the extra will be discarded.
        This field defaults to the Bluetooth advertising name.
        """
        return self._send(CORE, CORE_COMMANDS['SET NAME'], name, response)

    def get_bluetooth_info(self):
        """
        This returns a structure containing the textual name of the ball (defaults to the Bluetooth
        advertising name but can be changed), the Bluetooth address and
        the ID colors the ball blinks when not connected
        """
        result = self._send(
            CORE, CORE_COMMANDS['GET BLUETOOTH INFO'], [], True)
        if result.success:
            fmt = ">16s12sx3c"
            temp_tup = struct.unpack_from(fmt, buffer(result.data))
            name = temp_tup[0]
            name = name[:name.find('\x00')]
            named_tuple = BluetoothInfo(
                name, temp_tup[1], (temp_tup[2], temp_tup[3], temp_tup[4]))
            return Response(True, named_tuple)
        else:
            return result

    def get_power_state(self):
        """
        If successful returns a PowerState tuple with the following fields in this order.
            recVer: set to 1
            powerState: 1= Charging, 2 = OK, 3 = Low, 4 = Critical
            batt_voltage: current battery voltage in 100ths of a volt
            num_charges: number of recharges in the lilfe of this sphero
            time_since_chg: seconds Awake
        other wise it returns None
        function will try 'number_tries' times to get a response,
        and will wait up to 'response_time_out 'seconds for each response.
        thus it may block for up to 'response_time_out X number_tries' seconds
        """
        reply = self._stable_send(
            CORE, CORE_COMMANDS['GET POWER STATE'], [], True)
        if reply.success:
            parsed_answer = struct.unpack_from('>BBHHH', buffer(reply.data))
            return PowerState._make(parsed_answer)
        else:
            return None

    def set_power_notification(self, setting, response=False):
        """
        Sets Async power notification messages to be sent
        """
        flag = 0x01 if setting else 0x00
        reply = self._send(
            CORE, CORE_COMMANDS['SET POWER NOTIFICATION'], [flag], response)
        return reply

    def sleep(self, wakeup_time, response=False):
        """
        This command puts Sphero to sleep immediately.
        wakeup_time: The number of seconds for Sphero to sleep for and then automatically reawaken.
        Zero does not program a wakeup interval, so he sleeps forever.
        Breaks the connection
        """
        if wakeup_time < 0 or wakeup_time > 0xffff:
            return False
        big = wakeup_time >> 8
        little = (wakeup_time & 0x00ff)
        reply = self._send(CORE, CORE_COMMANDS['SLEEP'], [
            big, little, 0, 0, 0], response)

        return reply

    def get_voltage_trip_points(self):
        """
        This returns the voltage trip points for what Sphero considers Low and Critical battery.
        The values are expressed in 100ths of a volt,
        so the defaults of 7.00V and 6.50V respectively are returned as
        700 and 650.
        """
        reply = self._send(CORE, CORE_COMMANDS['GET VOLTAGE TRIP'], [], True)
        if reply.success:
            parse = struct.unpack_from(">HH", buffer(reply.data))
            return Response(True, parse)
        else:
            return reply

    def set_voltage_trip_points(self, low, critical, response=False):
        """
        not implemented
        This assigns the voltage trip points for Low and Critical battery voltages.
        The values are specified in  100ths of a volt and
        the limitations on adjusting these away from their defaults are:
        Vlow must be in the range 675 to 725 (+=25)
        Vcrit must be in the range 625 to 675 (+=25)
        There must be 0.25V of separation between the two values
        """
        assert False
        low = self._int_to_bytes(low, 2)
        crit = self._int_to_bytes(critical, 2)
        return self._send(CORE, CORE_COMMANDS['SET VOLTAGE TRIP'], low + crit, response)

    def set_inactivity_timeout(self, timeout, response=False):
        """
        Sets inactivity time out. Value must be greater than 60 seconds
        """
        if timeout < 0 or timeout > 0xffff:
            return False

        big = timeout >> 8
        little = (timeout & 0x00ff)
        reply = self._send(CORE, CORE_COMMANDS['SET INACT TIMEOUT'], [
            big, little], response)

        return reply

    def L1_diag(self):
        """
        This is a developer-level command to help diagnose aberrant behavior.
        Most system counters, process flags, and system states are decoded
        into human readable ASCII.
        """
        event = None
        with self._response_lock:
            event = threading.Event()
            self._response_event_lookup['L1'] = event

        self._send(CORE, CORE_COMMANDS['L1'], [], False)

        if event.wait(self._response_time_out * 10):
            response = None
            with self._response_lock:
                response = self._responses['L1']
            return Response(True, response)
        else:
            return Response(False, "no data recieved")

    def L2_diag(self):
        """
        This is a developers-only command to help diagnose aberrant behavior.
        It is much less informative than the Level 1 command
        but it is in binary format and easier to parse
        Command not found
        """

        assert False
        return self._send(CORE, CORE_COMMANDS['L2'], [], True)

    def poll_packet_times(self):
        """
        Command to help profile latencies
        returns a PacketTime tuple with fields:
        offset : the maximum-likelihood time offset of the Client clock to sphero's system clock
        delay: round-trip delay between client a sphero
        """
        # TODO time 1 gets mangled.
        time1 = int(round(time.time() * 1000))
        print(time1 & 0xffffffff)
        bit1 = (time1 & 0xff000000) >> 24
        bit2 = (time1 & 0x00ff0000) >> 16
        bit3 = (time1 & 0x0000ff00) >> 8
        bit4 = (time1 & 0x000000ff)
        reply = self._stable_send(CORE, CORE_COMMANDS['POLL PACKET TIMES'], [
            bit1, bit2, bit3, bit4], True)
        time4 = int(round(time.time() * 1000)) & 0xffffffff
        print(time4)
        print(reply)
        if reply.success:
            sphero_time = struct.unpack_from('>III', buffer(reply.data))
            print(sphero_time[0])
            offset = 0.5 * \
                ((sphero_time[1] - sphero_time[0]) + (sphero_time[2] - time4))
            delay = (time4 - sphero_time[0]) - \
                (sphero_time[2] - sphero_time[1])
            return PacketTime(offset, delay)

# SPHERO COMMANDS

    def set_heading(self, heading, response=False):
        """
        Sets the spheros heading in degrees,
        heading must range between 0 to 359
        """
        if heading < 0 or heading > 359:
            return Response(False, "heading must be between 0 and 359")

        heading_bytes = Sphero._int_to_bytes(heading, 2)
        reply = self._send(
            SPHERO, SPHERO_COMMANDS['SET HEADING'], heading_bytes, response)
        return reply

    def set_stabilization(self, stablize, response=False):
        """
        This turns on or off the internal stabilization of Sphero,
        the IMU is used to match the ball's orientation to its set points.
        An error is returned if the sensor network is dead;
        """
        flag = 0x01 if stablize else 0x00
        return self._send(SPHERO, SPHERO_COMMANDS['SET STABILIZATION'], [flag], response)

    def set_rotation_rate(self, rate, response=False):
        """
        sets teh roation rate sphero will use to meet new heading commands
        Lower value offers better control, with a larger turning radius
        rate should be in degrees/sec, above 199 the maxium value is used(400 degrees/sec)
        """
        # TODO returns unknown command
        if rate < 0:
            return Response(False, "USE POSITIVE RATE ONLY")
        if rate > 199:
            rate = 200
        else:
            rate = int(rate / 0.784)
        to_bytes = self._int_to_bytes(rate, 1)
        return self._send(SPHERO, SPHERO_COMMANDS['SET ROTATION RATE'], to_bytes, response)

    def get_chassis_id(self):
        """
        Returns the Chassis ID,
        """
        response = self._send(
            SPHERO, SPHERO_COMMANDS['GET CHASSIS ID'], [], True)

        if response.success:
            tup = struct.unpack_from('>H', buffer(response.data))
            return Response(True, tup[0])
        else:
            return response

    def set_data_stream(self, stream_settings, frequency, packet_count=0, response=False):
        """
        Sets data stream options
        """
        self._data_stream = stream_settings.copy()
        divisor = self._int_to_bytes(int(400.0 / frequency), 2)
        samples = self._int_to_bytes(self._data_stream.number_frames, 2)
        mask1 = self._int_to_bytes(self._data_stream.mask1, 4)
        mask2 = self._int_to_bytes(self._data_stream_mask2, 4)
        data = divisor + samples + mask1 + [packet_count] + mask2
        return self._send(SPHERO, SPHERO_COMMANDS['SET DATA STRM'], data, response)

    def set_color(self, red, green, blue, default=False, response=False):
        """
        Sets the color of ther sphero given rgb conbonants between 0 and 255,
        if default is true, sphero will default to that color when first connected
        """

        red = self._int_to_bytes(red, 1)
        blue = self._int_to_bytes(blue, 1)
        green = self._int_to_bytes(green, 1)
        flag = [0x01] if default else [0x00]
        return self._send(
            SPHERO, SPHERO_COMMANDS['SET COLOR'], red + green + blue + flag, response)

    def set_back_light(self, brightness, response=False):
        """
        Controls the brightness of the back LED, non persistant
        """
        brightness = self._int_to_bytes(brightness, 1)
        return self._send(
            SPHERO, SPHERO_COMMANDS['SET BACKLIGHT'], brightness, response)

    def get_color(self):
        """
        returns the default sphero color, may not be the current color shown
        """
        response = self._send(SPHERO, SPHERO_COMMANDS['GET COLOR'], [], True)
        if response.success:
            parse = struct.unpack_from('>BBB', buffer(response.data))
            return Response(True, Color._make(parse))
        else:
            return response

    def roll(self, speed, heading, fast_rotate=False, response=False):
        """
        commands the sphero to move
        """
        gobit = [0x02] if fast_rotate else [0x01]
        speed = self._int_to_bytes(speed, 1)
        heading = self._int_to_bytes(heading, 2)
        return self._send(SPHERO, SPHERO_COMMANDS['ROLL'], speed + heading + gobit, response)

    def stop(self, response=False):
        """
        Tells the Shero to stop
        """
        return self._send(SPHERO, SPHERO_COMMANDS['ROLL'], [0, 0, 0, 0], response)

    def boost(self, activate, response=True):
        """
        turns on boost
        """
        activate = 0x01 if activate else 0x00
        return self._send(SPHERO, SPHERO_COMMANDS['BOOST'], [activate], response)

    def set_raw_motor_values(self, left_value, right_value, response=False):
        """
        allows direct controle of the motors
        both motor values hsould be MotorValue tuple
        """
        lmode = left_value.mode.value
        lpower = left_value.power
        rmode = right_value.mode.value
        rpower = right_value.power
        if Sphero._outside_range(lpower, 0, 255) or Sphero._outside_range(rpower, 0, 255):
            raise SpheroException("Values outside of range")
        data = [lmode, lpower, rmode, rpower]
        return self._send(SPHERO, SPHERO_COMMANDS['SET RAW MOTOR'], data, response)

    def set_motion_timeout(self, timeout, response=False):
        """
        This sets the ultimate timeout for the last motion command to keep Sphero from rolling away
        timeout is in miliseconds and defaults to 2000
        must be set in permanent option flags
        """
        if self._outside_range(timeout, 0, 0xFFFF):
            raise SpheroException("Timeout outside of valid range")
        timeout = self._int_to_bytes(timeout, 2)
        return self._send(SPHERO, SPHERO_COMMANDS['MOTION TIMEOUT'], timeout, response)

    def set_permanent_options(self, options, response=False):
        """
        Set Options, for option information see PermanentOptionFlag docs.
        Options persist across power cycles
        @Param a permanentOption Object
        """
        options = self._int_to_bytes(options.bitflags, 8)
        return self._send(SPHERO, SPHERO_COMMANDS['SET PERM OPTIONS'], options, response)

    def get_permanent_options(self):
        """
        returns a teh Permenent Options of teh sphero
        """
        result = self._send(
            SPHERO, SPHERO_COMMANDS['GET PERM OPTIONS'], [], True)
        if result.success:
            settings = struct.unpack_from('>Q', buffer(result.data))
            options = PermanentOptions()
            options.bitflags = settings[0]
            return Response(True, options)
        else:
            return result

    def set_stop_on_disconnect(self, value=True, response=False):
        """
        Sets sphero to stop on disconnect, this is a one_shot, so it must be reset on reconnect
        set value to false to turn off behavior
        """
        value = 1 if value else 0
        return self._send(SPHERO, SPHERO_COMMANDS['SET TEMP OPTIONS'], [
            0, 0, 0, value], response)

    def will_stop_on_disconnect(self):
        """
        returns if the sphero will stop when it is disconnected
        """
        result = self._send(
            SPHERO, SPHERO_COMMANDS['GET TEMP OPTOINS'], [], True)
        if result.success:
            return Response(True, bool(result.data))
        else:
            return result
# ASYNC

    def register_sensor_callback(self, func):
        """
        register a function to call whena sensor message is recieved
        func must be callable
        it will be started in its own thread
        """
        assert callable(func)
        self._sensor_callback = func

    def register_power_callback(self, func):
        """
        register a function to call when an async power notification is recieved
        func must be callable
        it will be started in its own thread
        """
        assert callable(func)
        self._power_callback = func

    def _power_notification(self, notification):
        parsed = struct.unpack_from('b', buffer(notification))
        self._power_callback(parsed[0])

    def _forward_L1_diag(self, data):
        event = None
        with self._response_lock:
            self._responses['L1'] = str(data)
            if 'L1' in self._response_event_lookup:
                event = self._response_event_lookup['L1']
                del self._response_event_lookup['L1']
        event.set()

    def _sensor_data(self, data):
        parsed = self._data_stream.parse(data)
        self._sensor_callback(parsed)

    def run(self):
        self._recieve_loop()
