=========================
Python driver for Sphero
=========================

A driver for sphero 2.0 written entirely in python. Currently it provides access to most sphero api calls as described in the `Orbotix Documentation <https://github.com/orbotix/DeveloperResources>`.

**EXAMPLES:**

.. code-block:: python

    from spheropy.Sphero import Sphero
    with Sphero("NAME", "BLUETOOTH ID") as s:
        response = s.ping()
        print(response)
        s.roll(80, 0)
        s.set_heading(90)
        s.set_color(204,153,255)

.. code-block:: python

    import spheropy.Sphero import Sphero
        found = Sphero.find_spheros()
        for name in found:
            print name

**Build Requirements:**

- python 2.6+
- pybluez

**Features:**

- Sphero discovery
- ping
- power state polling and async
- sleep
- level 1 diagnostics
- polling voltage trip points
- heading adjustments
- disable/enable stabilization
- async sensor data
- setting the color
- setting back light instensity
- roll
- stop
- boost
- control raw motor values
- setint permanent options
- set motion timeout
- stop on disconnect

**Future:**

- read and configure locator
- collision detection
- developer commands
- Macro commands
- SSB data

**Not Planned:**

- auto reconnect
- orb basic commands