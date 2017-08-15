"""
Miscellaneous functions that used through the project
"""

from __future__ import print_function
import sys


def nothing(data):
    """
    A function that does nothing. Used as the default callback for async events
    """
    pass


def outside_range(number, min_range, max_range):
    """
    Returns True if `number` is between `min_range` and `max_range` exclusive.
    """
    return number < min_range or number > max_range


def int_to_bytes(number, length):
    """
    Returns a list of bytes that repersent `number`. The list is little endian.

    `length` represents the number of bytes.

    `number` is cast to an int before using. If number is larger then `length` 
    the higher order bytes are ignored.
    """
    number = int(number)
    result = []
    for i in range(0, length):
        result.append((number >> (i * 8)) & 0xff)
    result.reverse()
    return result


def check_sum(data):
    """
    Calculates a checksum as the modulo 256 sum then bit inverted (1's complement).

    `data` is an iterable list of bytes or ints < 256
    """
    return (sum(data) % 256) ^ 0xff


def eprint(*args, **kwargs):
    """
    Prints message to std error
    """
    print(*args, file=sys.stderr, **kwargs)
