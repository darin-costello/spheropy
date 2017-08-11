"""
Tools for working with Sphero Options
"""

_BIT0 = 0x00000001
_BIT1 = 0x00000002
_BIT2 = 0x00000004
_BIT3 = 0x00000008
_BIT4 = 0x00000010
_BIT5 = 0x00000020
_BIT6 = 0x00000040
_BIT7 = 0x00000080
_BIT8 = 0x00000100


class PermanentOptions(object):
    """
    Used to set Permanent Options on the spheros.
    Each property represents an option

    Data members should be set to a bool.
    """

    def __init__(self):
        self.bitflags = 0x00000000
        """ Bitflags representing which Options are set."""

    def set_light_wakeup_sensitivity(self):
        """
        Sets sphero's wakeup sensitivity to light.
        """
        self.bitflags &= (~ _BIT7)
        self.bitflags |= _BIT6

    def set_heavy_wakeup_sensitivity(self):
        """
        Sets sphero's wakeup sensitivity to heavy.
        """
        self.bitflags &= (~ _BIT6)
        self.bitflags |= _BIT7

    @property
    def sleep_on_charge_connected(self):
        """
        Prevents the sphero from immediatly sleeping when
        placed on the charger and connected over bluetooth.
        """
        return bool(self.bitflags & _BIT0)

    @sleep_on_charge_connected.setter
    def sleep_on_charge_connected(self, value):
        if value:
            self.bitflags |= _BIT0
        else:
            self.bitflags &= (~ _BIT0)

    @property
    def vector_drive(self):
        """
        When Sphero is stopped and is given a new roll command
        it achieves the heading before moving along it.
        """
        return bool(self.bitflags & _BIT1)

    @vector_drive.setter
    def vector_drive(self, value):
        if value:
            self.bitflags |= _BIT1
        else:
            self.bitflags &= (~ _BIT1)

    @property
    def level_on_charge(self):
        """
        Set to diable self_leveling when sphero is palced on the charger.
        """
        return bool(self.bitflags & _BIT2)

    @level_on_charge.setter
    def level_on_charge(self, value):
        if value:
            self.bitflags |= _BIT2
        else:
            self.bitflags &= (~ _BIT2)

    @property
    def tail_always_on(self):
        """
        Set to force the tail led always on.
        """
        return bool(self.bitflags & _BIT3)

    @tail_always_on.setter
    def tail_always_on(self, value):
        if value:
            self.bitflags |= _BIT3
        else:
            self.bitflags &= (~ _BIT3)

    @property
    def enable_motion_timeout(self):
        """
        Set to enable motion timeout.
        """
        return bool(self.bitflags & _BIT4)

    @enable_motion_timeout.setter
    def enable_motion_timeout(self, value):
        if value:
            self.bitflags |= _BIT4
        else:
            self.bitflags &= (~ _BIT4)

    @property
    def demo_mode(self):
        """
        Set to enable demo retail mode, where
        sphero runs a slow rainbow for 60 minutes when palced in charger.
        """
        return bool(self.bitflags & _BIT5)

    @demo_mode.setter
    def demo_mode(self, value):
        if value:
            self.bitflags |= _BIT5
        else:
            self.bitflags &= (~ _BIT5)

    @property
    def enable_gyro_max_async_msg(self):
        """
        Enables the gyro max async message.
        """
        return bool(self.bitflags & _BIT8)

    @enable_gyro_max_async_msg.setter
    def enable_gyro_max_async_msg(self, value):
        if value:
            self.bitflags |= _BIT8
        else:
            self.bitflags &= (~ _BIT8)
