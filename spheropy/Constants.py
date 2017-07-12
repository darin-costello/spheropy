from collections import namedtuple

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
    'GET POWER STATE': 0x20,
    'SET POWER NOTIFICATION': 0x21,
    'SLEEP': 0x22,
    'SET INACT TIMEOUT': 0x25,
    'POLL PACKET TIMES': 0x51
}


Response = namedtuple('Response', ['success', 'data'])
PowerState = namedtuple('PowerState', [
                        'recVer', 'power_state', 'batt_voltage', 'num_charges', 'time_since_chg'])
PacketTime = namedtuple('PacketTime', ['offset', 'delay'])


class SpheroException(Exception):
    """ Exception class for the Sphero"""
    pass
