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

        def set_light_sensitivity(self):
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
