"""
Tools for configuring and parsing sphero async data stream
"""

from collections import namedtuple
import struct
import math

_ACC_RAW_MASK = 0xE0000000
_GYRO_RAW_MASK = 0x1C000000
_MOTOR_EMF_RAW_MASK = 0x00600000
_MOTOR_PWM_RAW_MASK = 0x00180000
_IMU_ANGLE_MASK = 0x00070000
_ACC_MASK = 0x0000E000
_GYRO_MASK = 0x00001C00
_MOTOR_EMF_MASK = 0x00000060
_QUATERNION_MASK = 0xF0000000
_ODOM_MASK = 0x0C000000
_ACCEL_ONE_MASK = 0x02000000
_VEL_MASK = 0x01800000

_ThreeDimCoord = namedtuple('ThreeDimCoord', ['x', 'y', 'z'])
_RightAndLeft = namedtuple('RightAndLeft', ['right', 'left'])
_LeftAndRight = namedtuple('LeftAndRight', ['left', 'right'])
_Angle = namedtuple('Angle', ['pitch', 'roll', 'yaw'])

_TwoDimCoord = namedtuple('TwoDimCoord', ['x', 'y'])
_Value = namedtuple('Value', ['value'])
_Quaternion = namedtuple('Quaternion', ['x', 'y', 'z', 'w'])
_DataInfo = namedtuple(
    'DataInfo', ['name', 'tuple', 'size', 'mask', 'conversion'])

_ACC_RAW_CONV = 4 * 1e-3  # 4mg -> g
_GYRO_RAW_CONV = 0.068 * (math.pi / 180.0)  # 0.068 degrees -> radians
_MOTOR_EMF_RAW_CONV = 22.5 * 1e-2  # 22.5cm -> m
_MOTOR_PMW_CONV = 1
_IMU_ANGE_CONV = math.pi / 180.0  # degress -> radians
_ACC_CONV = (1.0 / 4096.0) * 9.80665  # 1 /4096 G -> m/s^2
_GYRO_CONV = 0.1 * math.pi / 180.0  # 0.1 dps -> dps
_MOTOR_EMF_CONV = 22.5 * 1e-2
_QUATERNION_CONV = 1e-4  # 1/ 10000Q -> Q
_ODOM_CONV = 1e-2  # cm -> m
_ACCELONE_CONV = 1e-3 * 9.80665  # mG -> m/s^2
_VELOCITY_CONV = 1e-3  # mm/s -> m/s
_ORDER1 = [
    _DataInfo('acc_raw', _ThreeDimCoord, 3, _ACC_RAW_MASK, _ACC_CONV),
    _DataInfo('gyro_raw', _ThreeDimCoord, 3, _GYRO_RAW_MASK, _GYRO_RAW_CONV),
    _DataInfo('motor_emf_raw', _RightAndLeft, 2,
              _MOTOR_EMF_RAW_MASK, _MOTOR_EMF_RAW_CONV),
    _DataInfo('motor_pwm_raw', _LeftAndRight, 2,
              _MOTOR_PWM_RAW_MASK, _MOTOR_EMF_RAW_CONV),
    _DataInfo('imu_ange', _Angle, 3, _IMU_ANGLE_MASK, _IMU_ANGE_CONV),
    _DataInfo('acc', _ThreeDimCoord, 3, _ACC_MASK, _ACC_CONV),
    _DataInfo('gyro', _ThreeDimCoord, 3, _GYRO_MASK, _GYRO_CONV),
    _DataInfo('motor_emf', _RightAndLeft, 2, _MOTOR_EMF_MASK, _MOTOR_EMF_CONV),
]
_ORDER2 = [
    _DataInfo('quaternion', _Quaternion, 4,
              _QUATERNION_MASK, _QUATERNION_CONV),
    _DataInfo('odom', _TwoDimCoord, 2, _ODOM_MASK, _ODOM_CONV),
    _DataInfo('accel_one', _Value, 1, _ACCEL_ONE_MASK, _ACCELONE_CONV),
    _DataInfo('velocity', _TwoDimCoord, 2, _VEL_MASK, _VELOCITY_CONV)
]


class DataStreamManager(object):
    """
    To be used to manage what data the sphero streams back.
    Currently it only supports setting all of a group at once,
    so it isn't possible to request only z accelerometer.
    Anything not marked raw has been filtered by the sphero.

    All data members should be set to a boolean values, with
    True indicating the data should be sent.

    Data will be sent, (to the callback function registered with the sphero)
    as a array of dictionary from strings to named tuples.
    The tuple fields are described below, keys to the dictionary
    are a string version of the name of its corresponding data memeber

    ie. acc_raw data is  accessed by `dic["acc_raw"]` and so forth

    ### Usage:

        #!python

        dsm = DataStreamManager()
        dsm.acc = True
        dsm.gyro = True
        # dsm should then be be haned to a Sphero Object
        sphero.set_data_stream(dsm, 10)
    """

    def __init__(self, number_frames=1, convert=True):
        self._mask1 = 0x00000000
        self._mask2 = 0x00000000
        self._format = ""
        self._tuples = []
        self.number_frames = number_frames
        """
         The number of dataframes to store before the sphero sends data,
         only important when setting the datastream
        """
        self.convert = convert
        """
        If convert is True the data is converted into standard measurments

        acceleration => m/s^2

        angles => radians

        length => meters

        otherwise the units on the data can be found in the orbotix documentation
        """

    def _update_mask1(self, value, bitmask):
        if value:
            self._mask1 |= bitmask
        else:
            self._mask1 &= (~ bitmask)
        self.update()

    def _update_mask2(self, value, bitmask):
        if value:
            self._mask2 |= bitmask
        else:
            self._mask2 &= (~ bitmask)
        self.update()

    def copy(self):
        """
        Creates a deep copy of this object,
        update is called to ensure object is in value state
        """
        stream = DataStreamManager()
        stream._mask1 = self._mask1
        stream._mask2 = self._mask2
        stream.convert = self.convert
        stream.number_frames = self.number_frames
        stream.update()
        return stream

    @property
    def acc_raw(self):
        """
        Raw accelerator data

        Data tuple has x,y, z and values
        """
        return bool(self._mask1 & _ACC_RAW_MASK)

    @acc_raw.setter
    def acc_raw(self, value):
        self._update_mask1(value, _ACC_RAW_MASK)

    @property
    def gyro_raw(self):
        """
        Raw Gyroscope data

        Data tuple has x,y, and z values
        """
        return bool(self._mask1 & _GYRO_RAW_MASK)

    @gyro_raw.setter
    def gyro_raw(self, value):
        self._update_mask1(value, _GYRO_RAW_MASK)

    @property
    def motor_emf_raw(self):
        """
        Raw motor EMF data

        Data tuple has right and left values
        """

        return bool(self._mask1 & _MOTOR_EMF_RAW_MASK)

    @motor_emf_raw.setter
    def motor_emf_raw(self, value):
        self._update_mask1(value, _MOTOR_EMF_RAW_MASK)

    @property
    def motor_pwm_raw(self):
        """
        Raw Motor pwm data

        Data tuple has right and left values
        """
        return bool(self._mask1 & _MOTOR_PWM_RAW_MASK)

    @motor_pwm_raw.setter
    def motor_pwm_raw(self, value):
        self._update_mask1(value, _MOTOR_PWM_RAW_MASK)

    @property
    def imu_angle(self):
        """
        Imu data, filtered

        Data tuple has pitch, roll, and yaw values
        """
        return bool(self._mask1 & _IMU_ANGLE_MASK)

    @imu_angle.setter
    def imu_angle(self, value):
        self._update_mask1(value, _IMU_ANGLE_MASK)

    @property
    def acc(self):
        """
        Accelerometer, filtered

        Data tuple has x y and z values
        """
        return bool(self._mask1 & _ACC_MASK)

    @acc.setter
    def acc(self, value):
        self._update_mask1(value, _ACC_MASK)

    @property
    def gyro(self):
        """
        Gyroscope, filtered

        Data tuple has x y and z values
        """
        return bool(self._mask1 & _GYRO_MASK)

    @gyro.setter
    def gyro(self, value):
        self._update_mask1(value, _GYRO_MASK)

    @property
    def motor_emf(self):
        """
        Motor EMF, filtered

        Data tuple has left and right vlaues
        """
        return bool(self._mask1 & _MOTOR_EMF_MASK)

    @motor_emf.setter
    def motor_emf(self, value):
        self._update_mask1(value, _MOTOR_EMF_MASK)

    @property
    def quaternion(self):
        """
        Orientation in Quaternion

        Data tuple has x, y, z, and w values
        """
        return bool(self._mask2 & _QUATERNION_MASK)

    @quaternion.setter
    def quaternion(self, value):
        self._update_mask2(value, _QUATERNION_MASK)

    @property
    def odom(self):
        """
        Odomoter

        Data tuple has x and y values
        """
        return bool(self._mask2 & _ODOM_MASK)

    @odom.setter
    def odom(self, value):
        self._update_mask2(value, _ODOM_MASK)

    @property
    def accel_one(self):
        """
        Data tuple has a single value between 0 and 8000
        """
        return bool(self._mask2 & _ACCEL_ONE_MASK)

    @accel_one.setter
    def accel_one(self, value):
        self._update_mask2(value, _ACCEL_ONE_MASK)

    @property
    def velocity(self):
        """
        Velocity

        Data tuple has x and y values"""
        return bool(self._mask2 & _VEL_MASK)

    @velocity.setter
    def velocity(self, value):
        self._update_mask2(value, _VEL_MASK)

    def parse(self, data):
        """
        Parses the data stream given from the sphero and
        returns the result as an array of dictionarys.

        Each dictionary is a differnt data frame as sent from the sphero.
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
        updates internals variables to ensure data integrety.
        This is called after each property is set.

        """
        self._update_format()
        self._update_list()

    def _update_format(self):
        num_ones = self._num_ones(self._mask1) + self._num_ones(self._mask2)
        self._format = ">" + "h" * num_ones

    def _update_list(self):
        tuples = []
        for i in _ORDER1:
            if i.mask & self._mask1:
                tuples.append(i)

        for i in _ORDER2:
            if i.mask & self._mask2:
                tuples.append(i)
        self._tuples = tuples

    @staticmethod
    def _num_ones(number):
        count = 0
        while number != 0:
            number = number & (number - 1)
            count += 1
        return count
