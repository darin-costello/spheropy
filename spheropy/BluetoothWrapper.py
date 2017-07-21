#!/usr/bin/python
"""
Wraps the bluetooth library for easy of use in sphero.
"""
import re
import sys

import bluetooth
from spheropy.Exception import SpheroException


class BluetoothWrapper(object):
    """
    A class used to wrap the bluetooth connection to the sphero
    """

    @classmethod
    def find_free_devices(cls, tries=5, regex=".*?"):
        """
        Finds a list of all available devices that match the given regex
        @param tries: indicates the number of times to scan for bluetooth devices
        @param regex: A regex used to match bluetooth device names,
        @return: A dictionary from names to addresses
        """
        re_prog = re.compile(regex)
        result = {}
        for _ in range(0, tries):
            devices_in_range = bluetooth.discover_devices(lookup_names=True)
            for addr, name in devices_in_range:
                if re.match(re_prog, name):
                    result[name] = addr

        return result

    def __init__(self, address, port):
        self.address = address
        self.port = port
        self._socket = None

    def is_connected(self):
        """ returns if the bluetooth has a connection """
        return self._socket is not None

    def connect(self, address=None):
        """
        Connects, attempts to connect to a sphero, address must be set,
        or given as a keyword argument.
        If a connection is all ready made it is closed, and a new one is started.
        """
        if address is not None:
            self.address = address

        if self._socket is not None:
            self._socket.close()
            self._socket = None

        try:
            self._socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self._socket.connect((self.address, self.port))
            return True
        except bluetooth.BluetoothError as error:
            if self._socket is not None:
                self._socket.close()
            self._socket = None
            raise SpheroException(error.message)
        return False

    def send(self, msg):
        """
        sends a message to the sphero
        @param msg: a byte string
        Blocks until message is sent.
        """
        if self._socket is None:
            raise SpheroException("Sphero is not connected")

        message_len = len(msg)
        while message_len > 0:
            sent_amount = self._socket.send(msg)
            message_len -= sent_amount
            msg = msg[sent_amount:]

    def receive(self, num_bytes):
        """
        recieves data from Sphero, and returns it as a byte string
        @param num_bytes, the number of bytes to request
        @return a byte string with length less than num_bytes,
        when sphero is disconnected, and all data is read, the empty string is returned.
        Blocks until atleast one byte is available.
        """
        if self._socket is None:
            raise SpheroException("Sphero is not connected")
        try:
            return self._socket.recv(num_bytes)
        except bluetooth.BluetoothError as error:
            raise SpheroException(
                "Unable to receive data due to bluetooth error: " + error.message)

    def close(self):
        """
        Closes the connection to sphero
        """
        if self._socket is not None:
            self._socket.close()
            self._socket = None
