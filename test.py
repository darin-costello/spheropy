# pylint: disable=c0111
import unittest
from spheropy.BluetoothWrapper import BluetoothWrapper
from spheropy.Sphero import SpheroException
import bluetooth


class OverrideDiscover(object):
    def __init__(self, tuples):
        self.tuples = tuples
        self.calls = 0

    def call(self, lookup_names=True):
        self.calls += 1
        return self.tuples


class FindSpheroTest(unittest.TestCase):
    def tearDown(self):
        reload(bluetooth)

    def test_find_one(self):
        override = OverrideDiscover([(33, "Sphero-YBO")])
        bluetooth.discover_devices = override.call
        answer = BluetoothWrapper.find_free_devices(regex="[Ss]phero")
        self.assertEqual(answer["Sphero-YBO"], 33)

    def test_multi_calls(self):
        override = OverrideDiscover([])
        bluetooth.discover_devices = override.call
        BluetoothWrapper.find_free_devices(regex="[Ss]phero", tries=10)
        self.assertEqual(override.calls, 10)

    def test_no_match(self):
        override = OverrideDiscover([(1234, "NOT_A_MATCH")])
        bluetooth.discover_devices = override.call
        answer = BluetoothWrapper.find_free_devices(regex="[Ss]phero")
        self.assertEqual(len(answer), 0)


class SocketStub(object):
    def __init__(self, connection_t):
        self.connection_t = connection_t
        self.address = None
        self.port = 0

    def connect(self, address_t):
        if address_t[0] == "fail":
            raise bluetooth.BluetoothError("TestFail")

        address, port = address_t
        self.address = address
        self.port = port

    def close(self):
        pass


class BlueToothWrapperConnectTest(unittest.TestCase):
    def setUp(self):
        bluetooth.BluetoothSocket = SocketStub
        self.wrapper = BluetoothWrapper("t", 1)

    def tearDown(self):
        reload(bluetooth)

    def test_sucess(self):
        result = self.wrapper.connect(address="some_address")
        self.assertTrue(True)

    def test_error(self):
        with self.assertRaises(SpheroException):
            self.wrapper.connect(address="fail")
