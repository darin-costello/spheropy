from collections import namedtuple

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

AccRaw = namedtuple('AccRaw', ['x', 'y', 'z'])
GyroRaw = namedtuple('GyroRaw', ['x', 'y', 'z'])
MotorEMFRaw = namedtuple('MotorEMFRaw', ['right', 'left'])
MotorPWMRaw = namedtuple('MotorPWMRaw', ['left, right'])
IMUAngle = namedtuple('IMUAngle', ['pitch', 'roll', 'yaw'])
Acc = namedtuple('Acc', ['x', 'y', 'z'])
Gyro = namedtuple('Gyro', ['x', 'y', 'z'])
MotorEMF = namedtuple('MotorEMF', ['right', 'left'])
Quaternion = namedtuple('Quaternion', ['x', 'y', 'z', 'w'])
Odom = namedtuple('Odom', ['x', 'y'])
AccelOne = namedtuple('AccelOne', ['value'])
Velocity = namedtuple('Velocity', ['x', 'y'])

ACC_RAW_CONV = 4 * 1e-3  # 4mg -> g
GYRO_RAW_CONV = 0.068  # 0.068 degrees -> degrees
MOTOR_EMF_RAW_CONV = 22.5 * 1e-2  # 22.5cm -> m
MOTOR_PMW_CONV = 1
IMU_ANGE_CONV = 1
ACC_CONV = 1.0 / 4096.0  # 1 /4096 G -> G
GYRO_CONV = 0.1  # 0.1 dps -> dps
MOTOR_EMF_CONV = 22.5 * 1e-2
QUATERNION_CONV = 1e-4  # 1/ 10000Q -> Q
ODOM_CONV = 1e-2  # cm -> m
ACCELONE_CONV = 1e-3  # mG -> G
VELOCITY_CONV = 1e-3  # mm/s -> m/s


class DataStreamManager(object):

    def __init__(self):
        self.mask1 = 0x00000000
        self.mask2 = 0x00000000
        self._format = ""

    def _update_mask1(self, value, bitmask):
        if value:
            self.mask1 |= bitmask
        else:
            self.mask1 &= (~ bitmask)
        self._format = self.update_format()

    def _update_mask2(self, value, bitmask):
        if value:
            self.mask2 |= bitmask
        else:
            self.mask2 &= (~ bitmask)
        self._format = self.update_format()

    @property
    def acc_raw(self):
        return bool(self.mask1 & ACC_RAW_MASK)

    @acc_raw.setter
    def acc_raw(self, value):
        self._update_mask1(value, ACC_RAW_MASK)

    @property
    def gyro_raw(self):
        return bool(self.mask1 & GYRO_RAW_MASK)

    @gyro_raw.setter
    def gyro_raw(self, value):
        self._update_mask1(value, GYRO_RAW_MASK)

    @property
    def motor_emf_raw(self):
        return bool(self.mask1 & MOTOR_EMF_RAW_MASK)

    @motor_emf_raw.setter
    def motor_emf_raw(self, value):
        self._update_mask1(value, MOTOR_EMF_RAW_MASK)

    @property
    def motor_pwm_raw(self):
        return bool(self.mask1 & MOTOR_PWM_RAW_MASK)

    @motor_pwm_raw.setter
    def motor_pwm_raw(self, value):
        self._update_mask1(value, MOTOR_PWM_RAW_MASK)

    @property
    def imu_angle(self):
        return bool(self.mask1 & IMU_ANGLE_MASK)

    @imu_angle.setter
    def imu_angle(self, value):
        self._update_mask1(value, IMU_ANGLE_MASK)

    @property
    def acc(self):
        return bool(self.mask1 & ACC_MASK)

    @acc.setter
    def acc(self, value):
        self._update_mask1(value, ACC_MASK)

    @property
    def gyro(self):
        return bool(self.mask1 & GYRO_MASK)

    @gyro.setter
    def gyro(self, value):
        self._update_mask1(value, GYRO_MASK)

    @property
    def motor_emf(self):
        return bool(self.mask1 & MOTOR_EMF_MASK)

    @motor_emf.setter
    def motor_emf(self, value):
        self._update_mask1(value, MOTOR_EMF_MASK)

    @property
    def quaternion(self):
        return bool(self.mask2 & QUATERNION_MASK)

    @quaternion.setter
    def quaternion(self, value):
        self._update_mask2(value, QUATERNION_MASK)

    @property
    def odom(self):
        return bool(self.mask2 & ODOM_MASK)

    @odom.setter
    def odom(self, value):
        self._update_mask2(value, ODOM_MASK)

    @property
    def accel_one(self):
        return bool(self.mask2 & ACCEL_ONE_MASK)

    @accel_one.setter
    def accel_one(self, value):
        self._update_mask2(value, ACCEL_ONE_MASK)

    @property
    def velocity(self):
        return bool(self.mask2 & VEL_MASK)

    @velocity.setter
    def velocity(self, value):
        self._update_mask2(value, VEL_MASK)

    def update_format(self):
        num_ones = self._num_ones(self.mask1) + self._num_ones(self.mask2)
        return ">" + "h" * num_ones

    def _num_ones(self, number):
        count = 0
        while number != 0:
            number = number & (number - 1)
            count += 1
        return count
