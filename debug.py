from spheropy.Sphero import Sphero
import time
from contextlib import contextmanager


@contextmanager
def timeit_context(name):
    startTime = time.time()
    yield
    elapsedTime = time.time() - startTime
    print('[{}] finished in {} ms'.format(name, int(elapsedTime * 1000)))


with Sphero("TESTER", '68:86:E7:07:89:37', response_time_out=1, number_tries=5) as s:
    r = s.get_power_state()
    print(r)
    t = s.poll_packet_times()
    print(t)
