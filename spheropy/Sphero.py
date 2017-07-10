"""
Tools for controlling a Sphero 2.0
"""
import threading
from spheropy.BluetoothWrapper import BluetoothWrapper


SOP1 = 0xff
ANSWER = 0xff
NO_ANSWER = 0xfe


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

    def __init__(self, name, address, port=1):
        super(Sphero, self).__init__()
        self.bluetooth = BluetoothWrapper(address, port)
        self.suppress_exception = False
        self._seq_num = 0
        self._msg = bytearray(2048)
        self._msg_lock = threading.Lock()
        self._msg[0] = SOP1

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return self.suppress_exception

    @property
    def _seq(self):
        self._seq_num += 1
        if self._seq_num > 0xff:
            self._seq_num = 0
        return self._seq_num

    def _set_data(self, data):
        """ msg lock must be aquired"""
        assert(self._msg_lock.locked())
        self._msg[6:6 + len(data)] = data

    def _send(self, data_length, response=False):
        """ assumes did, cid, and data have been set
            Msg lock must be aquired """
        assert(self._msg_lock.locked())
        self._msg[1] = ANSWER if response else NO_ANSWER
        checksum = Sphero._check_sum(self.msg[6:6 + data_length])
        self._msg[4] = self._seq
        self._msg[5] = data_length + 1
        self._msg[6 + data_length] = checksum
        self.bluetooth.send(buffer(self._msg[0: 7 + data_length]))

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

    def run(self):
        self.recieve_loop()
