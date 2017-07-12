"""
Tools for controlling a Sphero 2.0
"""
from __future__ import print_function
import sys

import time
import threading
import struct
from spheropy.BluetoothWrapper import BluetoothWrapper
from spheropy.Constants import *


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class Sphero(threading.Thread):
    """ class representing a sphero """
    @staticmethod
    def _check_sum(data):
        """ calculates the checksum as The modulo 256 sum of all the bytes bit inverted (1's complement)
        """
        return (sum(data) % 256) ^ 0xff

    @classmethod
    def find_spheros(cls, tries=5):
        """
        Returns a dictionary from names to addresses of all available spheros
        """
        return BluetoothWrapper.find_free_devices(tries=tries, regex="[Ss]phero")

    def __init__(self, name, address, port=1, response_time_out=1, number_tries=5):
        super(Sphero, self).__init__()
        self.bluetooth = BluetoothWrapper(address, port)
        self.suppress_exception = False
        self._seq_num = 0
        self.number_tries = number_tries

        self._msg_lock = threading.Lock()
        self._msg = bytearray(2048)
        self._msg[SOP1_INDEX] = SOP1

        self._response_lock = threading.Lock()
        self._response_event_lookup = {}
        self._responses = {}
        self._response_time_out = response_time_out

    def __enter__(self):
        connected = False
        tries = 0
        while not connected and tries < self.number_tries:
            try:
                self.connect()
                connected = True
            except:
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
            packet[SOP2_INDEX] = self.bluetooth.receive(1)
            packet_type = packet[SOP2_INDEX]
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

        array[MSRP_INDEX] = msrp
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
        # TODO, this is a stup, actual parsing will be needed
        self.bluetooth.receive(1)
        length_msb = ord(self.bluetooth.receive(1))
        length_lsb = ord(self.bluetooth.receive(1))
        length = length_msb << 8 + length_lsb
        self._read(length)

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
            self._msg[SOP2_INDEX] = ANSWER if response else NO_ANSWER
            self._msg[SEQENCE_INDEX] = seq_number
            self._msg[DID_INDEX] = did
            self._msg[CID_INDEX] = cid
            self._msg[LENGTH_INDEX] = data_length + 1
            self._msg[6:6 + data_length] = data
            checksum = Sphero._check_sum(
                self._msg[DID_INDEX: DATA_START + data_length])
            self._msg[DATA_START + data_length] = checksum
            self.bluetooth.send(
                buffer(self._msg[0: DATA_START + data_length + 1]))

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

    def ping(self, response=True):
        """
        The Ping command is used to verify both a solid data link with the Client
        and that Sphero is awake and dispatching commands.
        returns true if a response is recieved and was requested, false otherwise
        """
        reply = self._send(CORE, CORE_COMMANDS['PING'], [], response)
        return reply

    def get_power_state(self):
        """
        If successful returns a PowerState tuple with the following fields in this order.
            recVer: set to 1
            powerState: 1= Charging, 2 = OK, 3 = Low, 4 = Critical
            batt_voltage: current battery voltage in 100ths of a volt
            num_charges: number of recharges in the lilfe of this sphero
            time_since_chg: seconds Awake
        other wise it returns None
        function will try 'number_tries' times to get a response, and will wait up to 'response_time_out 'seconds for each response. thus it may block for up to 'response_time_out X number_tries' seconds
        """
        reply = self._stable_send(
            CORE, CORE_COMMANDS['GET POWER STATE'], [], True)
        if reply.success:
            parsed_answer = struct.unpack_from('>BBHHH', buffer(reply.data))
            return PowerState._make(parsed_answer)
        else:
            return None

    def set_power_notification(self, setting, response=False):
        """ WARNING asnyc messages not implemetned"""
        assert(False)
        flag = 0x01 if setting else 0x00
        reply = self._send(
            CORE, CORE_COMMANDS['SET POWER NOTIFICATION'], [flag], response)
        return reply

    def sleep(self, wakeup_time, response=False):
        """
        This command puts Sphero to sleep immediately.
        wakeup_time: The number of seconds for Sphero to sleep for and then automatically reawaken. Zero does not program a wakeup interval, so he sleeps forever. FFFFh attempts to put him into deep sleep (if supported in hardware) and returns an error if the hardware does not support it.

        Breaks the connection
        """
        if wakeup_time < 0 or wakeup_time > 0xffff:
            return False
        big = wakeup_time >> 8
        little = (wakeup_time & 0x00ff)
        reply = self._send(CORE, CORE_COMMANDS['SLEEP'], [
                           big, little, 0, 0, 0], response)

        return reply

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

    def poll_packet_times(self):
        """
        Command to help profile latencies
        returns a PacketTime tuple with fields:
        offset : the maximum-likelihood time offset of the Client clock to sphero's system clock
        delay: round-trip delay between client a sphero
        """
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

    def run(self):
        self._recieve_loop()
