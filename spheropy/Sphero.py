"""
Tools for controlling a Sphero 2.0
"""
import threading
from spheropy.BluetoothWrapper import BluetoothWrapper


class SpheroException(Exception):
    """ Exception class for the Sphero"""
    pass


class Sphero(threading.Thread):
    """ class representing a sphero """

    def __init__(self):
        self.bluetooth = BluetoothWrapper()
