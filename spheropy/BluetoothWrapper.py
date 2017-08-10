#!/usr/bin/python
"""
Wrapper for pybluez.
"""
import re

import bluetooth
from spheropy.Exception import BluetoothException
from spheropy.Util import eprint


class BluetoothWrapper(object):
    """
    A class used to wrap the bluetooth connection, for a RFCOMM connection.
    """

    @classmethod
    def find_free_devices(cls, tries=5, regex=".*?"):
        """
        class method that returns a dictionary from names to address of available bluetotoh devices

        `tries` indicates the number of times to scan for bluetooth devices

        `regex` is used to filter bluetooth devices names
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
        """
        `address` is the bluetooth address to connect to

        `port` is the RFCOMM port to use
        """
        self.address = address
        self.port = port
        self._socket = None

    def is_connected(self):
        """
        Returns if the bluetooth has a connection

        Even if this returns true, the connections is not guaranteed to be in a valid state.
        """
        return self._socket is not None

    def connect(self, address=None, suppress_exceptions=False):
        """
        Returns True if a connection is successfully made, False otherwise

        `address` is bluetooth address, that must be set or given as a keyword argument.

        If `suppress_exceptions` is set to `True` exceptions thrown by the bluetooth library will be suppressed, and the function will return false

        If there is a current connection it is closed before an attempt to connect is made.
        """
        if address is not None:
            self.address = address

        self.close()

        try:
            self._socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self._socket.connect((self.address, self.port))
            return True
        except bluetooth.BluetoothError as error:
            if self._socket is not None:
                self._socket.close()
                self._socket = None
            if suppress_exceptions:
                eprint(error.message)
                return False
            else:
                raise BluetoothException(error.message)
        return False

    def send(self, msg):
        """
        Sends data to the connected bluetooth device. Will block until all the data is sent.

        `msg` is a byte string
        """
        if self._socket is None:
            raise BluetoothException("Device is not connected")

        try:
            message_len = len(msg)
            while message_len > 0:
                sent_amount = self._socket.send(msg)
                message_len -= sent_amount
                msg = msg[sent_amount:]

        except bluetooth.BluetoothError as error:
            self.close()
            raise BluetoothException(error.message)

    def receive(self, num_bytes):
        """
        Returns data received data from bluetoth deviced as a byte string. If no device is connected an exception is thrown.

        `num_bytes` refers to the number of bytes to request the amount returned may be less

        When sphero is disconnected, and all data is read, the empty string is returned.
        Blocks until at least one byte is available.
        """
        if self._socket is None:
            raise BluetoothException("Device is not connected")
        try:
            data = self._socket.recv(num_bytes)
            if data == "":
                self.close()
            return data
        except bluetooth.BluetoothError as error:
            self.close()
            raise BluetoothException(
                "Unable to receive data due to bluetooth error: " + error.message)

    def close(self):
        """
        Closes the connection to sphero
        """
        if self._socket is not None:
            self._socket.close()
            self._socket = None
