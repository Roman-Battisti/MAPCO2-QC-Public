# Standard library imports
import importlib.resources as ir
import unittest

# 3rd party library imports
import numpy as np
import pandas as pd

# Local imports
from xco2qc.science_algorithms import (
    calc_xco2, calc_fugacity, Licorv830, calc_salinity
)


class TestSuite(unittest.TestCase):

    def test_salinity(self):
        """
        Scenario:  Have conductivity (S/m), temperature (C), pressure (kPa)

        Expected:  salinity is verified
        """
        temperature = np.array([20.08125, 20.13532, 20.14853])
        conductivity = np.array([4.07338, 4.077169, 4.079117])
        pressure = np.array([0.57, 0.57, 0.57])

        expected = np.array([29.1365381, 29.1294232, 29.1358154])

        actual = calc_salinity(conductivity, temperature, pressure * 0.1)
        np.testing.assert_almost_equal(actual, expected)

    def test_salinity_but_cond_has_nans(self):
        """
        Scenario:  Have conductivity (S/m), temperature (C), pressure (kPa).
        Some of the conductivity is Nan.

        Expected:  salinity is verified
        """
        temperature = np.array([20.08125, 20.13532, 20.14853])
        conductivity = np.array([np.nan, 4.077169, 4.079117])
        pressure = np.array([0.57, 0.57, 0.57])

        expected = np.array([np.nan, 29.1294232, 29.1358154])

        actual = calc_salinity(conductivity, temperature, pressure * 0.1)
        np.testing.assert_almost_equal(actual, expected)

    def test_salinity_with_masked_arrays(self):
        """
        Scenario:  Have conductivity (S/m), temperature (C), pressure (kPa).
        Some of the data is masked.

        Expected:  salinity is verified
        """
        x = np.array([20.08125, 20.13532, 20.14853])
        temperature = np.ma.masked_array(x, mask=[1, 0, 0])

        x = np.array([20.08125, 20.13532, 20.14853])
        temperature = np.ma.masked_array(x, mask=[1, 0, 0])

        x = np.array([4.07338, 4.077169, 4.079117])
        conductivity = np.ma.masked_array(x, mask=[1, 0, 0])

        pressure = np.array([0.57, 0.57, 0.57])

        expected = np.array([np.nan, 29.1294232, 29.1358154])

        actual = calc_salinity(conductivity, temperature, pressure * 0.1)
        np.testing.assert_almost_equal(actual, expected)

    def test_fugacity(self):
        """
        SCENARIO:  calculate fugacity from a known measurement

        EXPECTED RESULTS:  no errors, result verifies.
        """
        hPa = np.full((2, 3), 1013.2)
        hPa = np.ma.MaskedArray(data=hPa, mask=False)

        sst = np.full((2, 3), 15.98)
        sst = np.ma.MaskedArray(data=sst, mask=False)

        salinity = np.full((2, 3), 33.482)
        salinity = np.ma.MaskedArray(data=salinity, mask=False)

        xco2_sw = np.full((2, 3), 375.136)
        xco2_sw = np.ma.MaskedArray(data=xco2_sw, mask=False)

        actual = calc_fugacity(hPa, sst, salinity, xco2_sw)

        expected = np.full((2, 3), 367.207)
        expected = np.ma.MaskedArray(data=expected, mask=False)

        np.testing.assert_array_almost_equal(actual, expected, decimal=3)

    def test_pressure_less_than_atmos_standard(self):
        """
        SCENARIO:  The measured pressure is less than the standard pressure.

        EXPECTED RESULT:  The calculated xCO2 is verified against existing
        data.
        """
        T = 13.424310
        p1 = 96.598276
        v = 2658964
        vo = 2041035
        zerocoeff = 0.710275
        spancoeff = 0.907211
        actual = calc_xco2(T, p1, v, vo, zerocoeff, spancoeff)
        expected = 379.989481
        self.assertTrue(np.abs(actual - expected) < 1e-5)

    def test_scalar(self):
        """
        SCENARIO:  The input parameters are provided as scalars (normally we
        would operate on numpy arrays).

        EXPECTED RESULT:  A scalar result is verified against existing data.
        """
        T = 13.850862
        p1 = 102.861724
        v = 2634568
        vo = 2040271
        zerocoeff = 0.710275
        spancoeff = 0.907211
        actual = calc_xco2(T, p1, v, vo, zerocoeff, spancoeff)
        expected = 402.225693
        self.assertTrue(np.abs(actual - expected) < 1e-6)

    def test_licor_830(self):
        """
        SCENARIO:  The input parameters are provided for the LICOR 830 case.

        EXPECTED RESULT:  A scalar result is verified against existing data.
        """
        zero_coeff = 1.0505443

        # middle span and high span
        S0 = 0.77243495
        S1 = 0.0267004325

        with ir.as_file(ir.files('tests.data.licor830').joinpath('20210317_173000.csv')) as path:
            df = pd.read_csv(path)

        v830 = Licorv830()
        xco2 = v830.calc_xco2(
            zero_coeff, S0, S1, df['Li_Raw'].mean(), df['Li_ref'].mean(),
            df['Pres'].mean(), df['Temp'].mean()
        )

        np.testing.assert_almost_equal(xco2, 463.859, decimal=3)
