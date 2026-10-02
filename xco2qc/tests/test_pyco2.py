# standard library imports
import platform
import unittest

# 3rd party library imports
import numpy as np
import pandas as pd
from PyCO2SYS.api import CO2SYS_wrap as co2sys


class TestSuite(unittest.TestCase):

    def test_smoke(self):
        """
        Scenario:  test basic usage of pyco2sys

        Expected Result:  profit
        """
        alk = np.array([2360, 2400])
        pco2 = np.array([420, 425])
        sal = np.array([35, 34])
        temp_in = np.array([25, 24])

        # pressure is set to a specific value, and total phosphate and
        # silicate are set to defaults (0)?

        df1 = co2sys(alk=alk, pco2=pco2, sal=sal, temp_in=temp_in, pres_in=0.5)

        actual = df1['pHin']
        # if platform.system() == 'Windows':
        #     index = pd.Index([0, 1], dtype=np.int32)
        # else:
        index = pd.Index([0, 1], dtype=np.int64)
        
        expected = pd.Series(
            data=[8.035087, 8.041012], index=index, name='pHin'
        )
        pd.testing.assert_series_equal(actual, expected)
