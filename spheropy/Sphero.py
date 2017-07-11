"""
Tools for controlling a Sphero 2.0
"""
from __future__ import print_function
import sys

from collections import namedtuple
import threading
from spheropy.BluetoothWrapper import BluetoothWrapper
from spheropy.Constants import *

Response = namedtuple('Response', ['sucess', 'data'])


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class SpheroException(Exception):
    """ Exception class for the Sphero"""
    pass


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

    def __init__(self, name, address, port=1, response_time_out=5):
        super(Sphero, self).__init__()
        self.bluetooth = BluetoothWrapper(address, port)
        self.suppress_exception = False
        self._seq_num = 0

        self._msg_lock = threading.Lock()
        self._msg = bytearray(2048)
        self._msg[SOP1_INDEX] = SOP1

        self._response_lock = threading.Lock()
        self._response_event_lookup = {}
        self._responses = {}
        self._response_time_out = response_time_out

    def __enter__(self):
        self.connect()
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
                pass
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
        array[SEQENCE_INDEX] = seq
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
                self._responses[seq] = Response(False, MSRP[seq])
            event.set()

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

    def __set_data(self, data):
        """ msg lock must be aquired by caller"""
        self._msg[6:6 + len(data)] = data

    def __send(self, data_length, sequence_num=0, response=False):
        """ assumes did, cid, and data have been set
            Msg lock must be aquired by caller"""
        self._msg[SOP2_INDEX] = ANSWER if response else NO_ANSWER
        checksum = Sphero._check_sum(
            self.msg[DATA_START: DATA_START + data_length])
        self._msg[SEQENCE_INDEX] = sequence_num
        self._msg[LENGTH_INDEX] = data_length + 1
        self._msg[DATA_START + data_length] = checksum
        self.bluetooth.send(buffer(self._msg[0: DATA_START + data_length + 1]))
        return

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

    def ping(self, response=True):
        """
        The Ping command is used to verify both a solid data link with the Client and that Sphero is awake and
        dispatching commands.
        returns true if a response is recieved and was requested, false otherwise
        """
        event = None
        seq_number = 0
        if response:
            with self._response_lock:
                seq_number = self._seq
                event = threading.Event()
                self._response_event_lookup[seq_number] = event

        with self._msg_lock:
            self._msg[DID_INDEX] = CORE
            self._msg[CID_INDEX] = CORE_COMMANDS['PING']
            seq_number = self.__send(
                0, sequence_num=seq_number, response=response)

        if response:
            if event.wait(self._response_time_out):
                return self._responses[seq_number].success
        return False

    def run(self):
        self._recieve_loop()
