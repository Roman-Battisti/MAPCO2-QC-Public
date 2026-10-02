# standard library imports
import datetime as dt
import platform
import unittest

# 3rd party library imports
import numpy as np
import pandas as pd

# local imports
from xco2qc.utilities import simple_timezone_offset


@unittest.skipIf(platform.system() == 'Windows', 'windows different dtype')
class TestSuite(unittest.TestCase):

    def test_smoke(self):
        """
        Test the time zone offset

        Expected result:  there is a warning
        """
        longitude = np.array([144, 89.52, 89.52])
        time = np.array([
            dt.datetime(2013, 11, 24, 12, 0, 0),
            dt.datetime(2013, 11, 25, 0, 17, 0),
            dt.datetime(2013, 11, 26, 21, 17, 0),
        ])
        with self.assertWarns(pd.errors.PerformanceWarning):
            actual = simple_timezone_offset(
                time, longitude, adjust_hours_only=True
            )

        expected = np.array([
            np.datetime64('2013-11-24T22:00:00'),
            np.datetime64('2013-11-25T06:17:00'),
            np.datetime64('2013-11-27T03:17:00')
        ])
        np.testing.assert_equal(actual.values, expected)
