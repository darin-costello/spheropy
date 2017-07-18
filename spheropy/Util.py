def nothing(self, data):
    print(data)


def outside_range(number, min_range, max_range):
    return number < min_range or number > max_range


def int_to_bytes(number, length):
    number = int(number)
    result = []
    for i in range(0, length):
        result.append((number >> (i * 8)) & 0xff)
    result.reverse()
    return result


def check_sum(data):
    """
    calculates the checksum as The modulo 256 sum of all the bytes bit inverted (1's complement)
    """
    return (sum(data) % 256) ^ 0xff
