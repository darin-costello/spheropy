"""
Tools for configuring and parsing sphero async data stream
"""

from collections import namedtuple
import struct
from math import pi

ACC_RAW_MASK = 0xE0000000
GYRO_RAW_MASK = 0x1C000000
MOTOR_EMF_RAW_MASK = 0x00600000
MOTOR_PWM_RAW_MASK = 0x00180000
IMU_ANGLE_MASK = 0x00070000
ACC_MASK = 0x0000E000
GYRO_MASK = 0x00001C00
MOTOR_EMF_MASK = 0x00000060
QUATERNION_MASK = 0xF0000000
ODOM_MASK = 0x0C000000
ACCEL_ONE_MASK = 0x02000000
VEL_MASK = 0x01800000

ThreeD = namedtuple('ThreeD', ['x', 'y', 'z'])
RandL = namedtuple('RandL', ['right', 'left'])
LandR = namedtuple('LandR', ['left', 'right'])
Angle = namedtuple('Angle', ['pitch', 'roll', 'yaw'])
TwoD = namedtuple('TwoD', ['x', 'y'])
Value = namedtuple('Value', ['value'])
Quat = namedtuple('Quat', ['x', 'y', 'z', 'w'])
DataInfo = namedtuple(
    'DataInfo', ['name', 'tuple', 'size', 'mask', 'conversion'])

ACC_RAW_CONV = 4 * 1e-3  # 4mg -> g
GYRO_RAW_CONV = 0.068 * (pi / 180.0)  # 0.068 degrees -> degrees
MOTOR_EMF_RAW_CONV = 22.5 * 1e-2  # 22.5cm -> m
MOTOR_PMW_CONV = 1
IMU_ANGE_CONV = pi / 180.0
ACC_CONV = 1.0 / 4096.0  # 1 /4096 G -> G
GYRO_CONV = 0.1  # 0.1 dps -> dps
MOTOR_EMF_CONV = 22.5 * 1e-2
QUATERNION_CONV = 1e-4  # 1/ 10000Q -> Q
ODOM_CONV = 1e-2  # cm -> m
ACCELONE_CONV = 1e-3  # mG -> G
VELOCITY_CONV = 1e-3  # mm/s -> m/s
ORDER1 = [
    DataInfo('acc_raw', ThreeD, 3, ACC_RAW_MASK, ACC_CONV),
    DataInfo('gyro_raw', ThreeD, 3, GYRO_RAW_MASK, GYRO_RAW_CONV),
    DataInfo('motor_emf_raw', RandL, 2,
             MOTOR_EMF_RAW_MASK, MOTOR_EMF_RAW_CONV),
    DataInfo('motor_pwm_raw', LandR, 2,
             MOTOR_PWM_RAW_MASK, MOTOR_EMF_RAW_CONV),
    DataInfo('imu_ange', Angle, 3, IMU_ANGLE_MASK, IMU_ANGE_CONV),
    DataInfo('acc', ThreeD, 3, ACC_MASK, ACC_CONV),
    DataInfo('gyro', ThreeD, 3, GYRO_MASK, GYRO_CONV),
    DataInfo('motor_emf', RandL, 2, MOTOR_EMF_MASK, MOTOR_EMF_CONV),
]
ORDER2 = [
    DataInfo('quaternion', Quat, 4, QUATERNION_MASK, QUATERNION_CONV),
    DataInfo('odom', TwoD, 2, ODOM_MASK, ODOM_CONV),
    DataInfo('accel_one', Value, 1, ACCEL_ONE_MASK, ACCELONE_CONV),
    DataInfo('velocity', TwoD, 2, VEL_MASK, VELOCITY_CONV)
]


class DataStreamManager(object):
    """
    To be used to manage what data ther sphero streams back.
    Currently it only supports setting all of a group at once,
    so it isn't possible to request only z accelrometer, you get
    all accelerometer values, so x, y, z. Anyting not marked raw,
    has been filtered by the sphero.
    With convert set to true, all measurements are converted to standard form,
     Ie. meters g, and degrees,
    otherwise they are left in the 'raw' form sent, which can be find in the api docs.

    Data will be sent, (to the callback function) as an arraydictionary of named tuples.
    the tuple fields are described below
    """

    def __init__(self, number_frames=1, convert=True):
        self.mask1 = 0x00000000
        self.mask2 = 0x00000000
        self._format = ""
        self._tuples = []
        self.number_frames = number_frames
        self.convert = convert

    def _update_mask1(self, value, bitmask):
        if value:
            self.mask1 |= bitmask
        else:
            self.mask1 &= (~ bitmask)
        self.update()

    def _update_mask2(self, value, bitmask):
        if value:
            self.mask2 |= bitmask
        else:
            self.mask2 &= (~ bitmask)
        self.update()

    def copy(self):
        """
        Creats a deep copy of this object,
        update is called to ensure object is in valud state
        """
        stream = DataStreamManager()
        stream.mask1 = self.mask1
        stream.mask2 = self.mask2
        stream.convert = self.convert
        stream.number_frames = self.number_frames
        stream.update()
        return stream

    @property
    def acc_raw(self):
        """
        Has x,y,z, values
        """
        return bool(self.mask1 & ACC_RAW_MASK)

    @acc_raw.setter
    def acc_raw(self, value):
        self._update_mask1(value, ACC_RAW_MASK)

    @property
    def gyro_raw(self):
        """
        Has x,y,z, values
        """
        return bool(self.mask1 & GYRO_RAW_MASK)

    @gyro_raw.setter
    def gyro_raw(self, value):
        self._update_mask1(value, GYRO_RAW_MASK)

    @property
    def motor_emf_raw(self):
        """
        Has right and left values
        """

        return bool(self.mask1 & MOTOR_EMF_RAW_MASK)

    @motor_emf_raw.setter
    def motor_emf_raw(self, value):
        self._update_mask1(value, MOTOR_EMF_RAW_MASK)

    @property
    def motor_pwm_raw(self):
        """
        Has right and left values
        """
        return bool(self.mask1 & MOTOR_PWM_RAW_MASK)

    @motor_pwm_raw.setter
    def motor_pwm_raw(self, value):
        self._update_mask1(value, MOTOR_PWM_RAW_MASK)

    @property
    def imu_angle(self):
        """
        has pitch roll and ya values
        """
        return bool(self.mask1 & IMU_ANGLE_MASK)

    @imu_angle.setter
    def imu_angle(self, value):
        self._update_mask1(value, IMU_ANGLE_MASK)

    @property
    def acc(self):
        """
        Filtered
        Has x y and z values
        """
        return bool(self.mask1 & ACC_MASK)

    @acc.setter
    def acc(self, value):
        self._update_mask1(value, ACC_MASK)

    @property
    def gyro(self):
        """
        filtered
        Has x y and z values
        """
        return bool(self.mask1 & GYRO_MASK)

    @gyro.setter
    def gyro(self, value):
        self._update_mask1(value, GYRO_MASK)

    @property
    def motor_emf(self):
        """
        filtered
        has left and right vlaues
        """
        return bool(self.mask1 & MOTOR_EMF_MASK)

    @motor_emf.setter
    def motor_emf(self, value):
        self._update_mask1(value, MOTOR_EMF_MASK)

    @property
    def quaternion(self):
        """
        has x y z and w values
        """
        return bool(self.mask2 & QUATERNION_MASK)

    @quaternion.setter
    def quaternion(self, value):
        self._update_mask2(value, QUATERNION_MASK)

    @property
    def odom(self):
        """
        has x y values
        """
        return bool(self.mask2 & ODOM_MASK)

    @odom.setter
    def odom(self, value):
        self._update_mask2(value, ODOM_MASK)

    @property
    def accel_one(self):
        """ has a single values between 0 and 8000
        """
        return bool(self.mask2 & ACCEL_ONE_MASK)

    @accel_one.setter
    def accel_one(self, value):
        self._update_mask2(value, ACCEL_ONE_MASK)

    @property
    def velocity(self):
        """ has x and y values"""
        return bool(self.mask2 & VEL_MASK)

    @velocity.setter
    def velocity(self, value):
        self._update_mask2(value, VEL_MASK)

    def parse(self, data):
        """
        Parses the given data stream and returns the result of an array of dictionarys
        """
        expected_items = (len(self._format) - 1) * 2
        assert len(data) == expected_items * self.number_frames
        buff = buffer(data)
        result = []
        for frame in range(0, self.number_frames):

            data = struct.unpack_from(
                self._format, buff, offset=frame * expected_items)
            offset = 0
            dic = {}
            for i in self._tuples:
                temp_list = []
                for j in range(0, i.size):
                    to_add = i.conversion * \
                        data[offset + j] if self.convert else data[offset + j]
                    temp_list.append(to_add)
                offset += i.size
                dic[i.name] = i.tuple._make(temp_list)
            result.append(dic)
        return result

    def update(self):
        """
        updates internals. This is called after each property is set.
        If masks are eddited by hand the format string and the tuples list will need to be updated,
        this can be done  But if you grab only part of a group you'll need to do it by hand.
        """
        self._update_format()
        self._update_list()

    def _update_format(self):
        num_ones = self._num_ones(self.mask1) + self._num_ones(self.mask2)
        self._format = ">" + "h" * num_ones

    def _update_list(self):
        tuples = []
        for i in ORDER1:
            if i.mask & self.mask1:
                tuples.append(i)

        for i in ORDER2:
            if i.mask & self.mask2:
                tuples.append(i)
        self._tuples = tuples

    @staticmethod
    def _num_ones(number):
        count = 0
        while number != 0:
            number = number & (number - 1)
            count += 1
        return count
