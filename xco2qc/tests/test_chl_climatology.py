"""
Test suite for functionality related to the Chlorophyll climatology
"""

# standard library imports
import datetime as dt

# 3rd party library imports
import pandas as pd

# local imports
from xco2qc.chl_climatology import CHLClimatology
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        Scenario:  Try to access the O2 climatology for alawai

        Expected Result:  no errors
        """
        c = CHLClimatology('alawai', verbosity='debug')
        c.get_climatology()

    def test_interpolate(self):
        """
        Scenario:  Get a time series of an O2 climatology

        Expected Result:  no errors
        """
        t1 = dt.datetime(1992, 1, 1)
        t2 = dt.datetime(1993, 7, 1)
        nperiods = 50
        ts = pd.date_range(t1, t2, nperiods)

        clim = CHLClimatology('alawai').get_climatology()
        df = CHLClimatology('alawai').interpolate(ts)
        self.assertEqual(len(df), 50)

        # the last value is for july.  It should be equal to the 7th value in
        # the series
        self.assertEqual(df['Chl'].values[-1], clim[7])

    def test_failure(self):
        """
        Scenario:  Try to access the O2 climatology for a site that does not
        have an O2 climatology

        Expected Result:  KeyError

        As of the time of writing this test, failures are expected for any of

        cb-06, chuuk_k1, cola, coastalmS, crimp1, dabob, graysff, jkeo,
        enrique, mosean, peggy, sofs, southeast_ak, tao110w_0n, 110w0,
        tao125w_0n, 125w0, tao140w_0n, 140w0, tao155w_0n, 155w0, tao165e_0n,
        165e0, tao165e_8s, 165e8s, tao170w_0n, 170w0, twanoh
        """
        c = CHLClimatology('cb-06', verbosity='debug')
        with self.assertRaises(KeyError):
            c.get_climatology()
