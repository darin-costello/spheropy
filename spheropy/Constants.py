from collections import namedtuple
from enum import Enum

SOP1_INDEX = 0
SOP2_INDEX = 1
DID_INDEX = 2
MSRP_INDEX = 0
CID_INDEX = 3
SEQENCE_INDEX = 4
LENGTH_INDEX = 5
DATA_START = 6

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


Response = namedtuple('Response', ['success', 'data'])
PowerState = namedtuple('PowerState', [
                        'recVer', 'power_state', 'batt_voltage', 'num_charges', 'time_since_chg'])
PacketTime = namedtuple('PacketTime', ['offset', 'delay'])
Color = namedtuple('Color', ['r', 'g', 'b'])

MotorValue = namedtuple('MotorValue', ['mode', 'power'])


BIT0 = 0x00000001
BIT1 = 0x00000002
BIT2 = 0x00000004
BIT3 = 0x00000008
BIT4 = 0x00000010
BIT5 = 0x00000020
BIT6 = 0x00000040
BIT7 = 0x00000080
BIT8 = 0x00000100


class PermanentOptions(object):
    """
    Used to set Permanent Options on the spheros.
    Each propoerty represents an option, to set a property to true to set it
    """

    def __init__(self):
        self.bitflags = 0x00000000

        @property
        def sleep_on_charge_connected(self):
            """
            Prevents the sphero from immediatly sleeping when placed on the charged and connected over bluetooth
            """
            return bool(self.bitflags & BIT0)

        @sleep_on_charge_connected.setter
        def sleep_on_charge_connected(self, value):
            if value:
                self.bitflags |= BIT0
            else:
                self.bitflags &= (~ BIT0)

        @property
        def vector_drive(self):
            """
            Set to enable when Sphero  is stopped and ais given a new roll command, ti achieves teh heading before moving along it.
            """
            return bool(self.bitflags & BIT1)

        @vector_drive.setter
        def vector_drive(self, value):
            if value:
                self.bitflags |= BIT1
            else:
                self.bitflags &= (~ BIT1)

        @property
        def level_on_charge(self):
            """
            set to diable self_leveling when sphero is palced on the charger
            """
            return bool(self.bitflags & BIT2)

        @level_on_charge.setter
        def level_on_charge(self, value):
            if value:
                self.bitflags |= BIT2
            else:
                self.bitflags &= (~ BIT2)

        @property
        def tail_always_on(self):
            """
            set to force the tail led always on
            """
            return bool(self.bitflags & BIT3)

        @tail_always_on.setter
        def tail_always_on(self, value):
            if value:
                self.bitflags |= BIT3
            else:
                self.bitflags &= (~ BIT3)

        @property
        def enable_motion_timeout(self):
            """
            set to enable motion timeout
            """
            return bool(self.bitflags & BIT4)

        @enable_motion_timeout.setter
        def enable_motion_timeout(self, value):
            if value:
                self.bitflags |= BIT4
            else:
                self.bitflags &= (~ BIT4)

        @property
        def demo_mode(self):
            """
            set to enable demo retail mode, ball runs a slow rainbow for 60 minutes when palced in charger
            """
            return bool(self.bitflags & BIT5)

        @demo_mode.setter
        def demo_mode(self, value):
            if value:
                self.bitflags |= BIT5
            else:
                self.bitflags &= (~ BIT5)

        def set_ligt_sensitivity(self):
            self._bitflag &= (~ BIT7)
            self._bitflag |= BIT6

        def set_heavy_awake_sensitivity(self):
            self._bitflag &= (~ BIT6)
            self._bigflag |= BIT7

        @property
        def enable_gyro_max_async_msg(self):
            """
            enables the gyro max async message
            """
            return bool(self.bitflag & BIT8)

        @enable_gyro_max_async_msg.setter
        def enable_gyuro_max_async_msg(self, value):
            if value:
                self.bitfalgs |= BIT8
            else:
                self.bitflags &= (~ BIT8)


class MotorState(Enum):
    """
    An enum to represent possible motor states
    """
    off = 0x00
    forward = 0x01
    reverse = 0x02
    brake = 0x03
    ignore = 0x04


class VoltageTripPoints(object):

    def __init__(self):
        self._low = 700
        self._crit = 650

    @property
    def low(self):
        return self._low

    @low.setter
    def low(self, value):
        if value < 675 or value > 725:
            raise SpheroException(
                "Low voltage trip point must be between 675 and 725")

        if abs(value - self._crit) > 25:
            raise SpheroException(
                "Low and Critical trip points must have a seperation larger then 25")

        self._low = value

    @property
    def crit(self):
        return self._crit

    @crit.setter
    def crit(self, value):
        if value < 625 or value > 675:
            raise SpheroException(
                "Critical voltage trip point must be between 625 and 675")

        if abs(value - self._low) > 25:
            raise SpheroException(
                "Low and Critical trip points must have a seperation larger then 25")
        self._crit = value


class SpheroException(Exception):
    """ Exception class for the Sphero"""
    pass
