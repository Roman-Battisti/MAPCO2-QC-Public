# standard library imports
import importlib.resources as ir

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc.external_sami import ImportExternalSAMI
from xco2qc.data_reduction import XCO2Reduce
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def assertPH(self, ph_ncfile):
        with xr.open_dataset(ph_ncfile) as ds:

            index = pd.Series(
                pd.to_datetime([
                    '2018-05-01T12:03:31',
                    '2018-05-01T15:03:31',
                    '2018-05-01T18:03:31',
                ]),
                name='time'
            )

            actual = ds['SSS'].to_series()
            expected = pd.Series(
                [35.6401, 35.6390, 35.6399],
                index=index, dtype=np.float64, name='SSS'
            )
            pd.testing.assert_series_equal(actual, expected)

            actual = ds['temperature'].to_series()
            expected = pd.Series(
                [21.7832, 21.7832, 21.7832],
                index=index, dtype=np.float64, name='temperature'
            )
            pd.testing.assert_series_equal(actual, expected)

            actual = ds['ph'].to_series()
            expected = pd.Series(
                [8.0644, 8.0662, 8.0633],
                index=index, dtype=np.float64, name='ph'
            )
            pd.testing.assert_series_equal(actual, expected)

            actual = ds['ph_err'].to_series()
            expected = pd.Series(
                [0.00354, 0.00486, 0.00230],
                index=index, dtype=np.float64, name='ph_err'
            )
            pd.testing.assert_series_equal(actual, expected)

            actual = ds['external_flag'].to_series()
            expected = pd.Series(
                [0, 1000, 0],
                index=index, dtype=np.float32, name='external_flag'
            )
            pd.testing.assert_series_equal(actual, expected)

            self.assertEqual(ds.data_source, 'external-sami')

    def test_smoke(self):
        """
        SCENARIO:  Read an external sami file.

        EXPECTED RESULTS:  A raw sami netCDF file is produced.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus'
            ).joinpath(
            'sami_stratus_P0042_dp11_20180410_20190410_out.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE
            self.assertPH(ncfile)

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_sami()

            ncfile = self.reduced_path / core.EXTERNAL_SAMI_NCFILE
            self.assertPH(ncfile)

    def test_iceland(self):
        """
        SCENARIO:  external sami file has seven columns instead of six

        Expected Result:  No errors
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.iceland.dp08'
            ).joinpath(
            'sami_iceland_P245_dp08_20200814_20210813.txt_out.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

    def test_temperature(self):
        """
        SCENARIO:  Read an external sami file.

        EXPECTED RESULTS:  A raw sami netCDF file is produced.  Verify the
        temperature and salinity.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus.depl09'
            ).joinpath(
            'dp09_20160620_20161022_Temperature_Corrected.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

        ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE
        with xr.open_dataset(ncfile) as ds:
            temp = ds['temperature'].to_series()
            sal = ds['SSS'].to_series()

        index_data = [
            '2016-06-20 23:05:01', '2016-06-21 02:05:00',
            '2016-06-21 05:05:00', '2016-06-21 08:05:00'
        ]
        index = pd.DatetimeIndex(index_data, name='time')

        data = [np.nan, 21.5590, 21.5703, 21.5458]
        expected = pd.Series(data, index=index, name='temperature')
        pd.testing.assert_series_equal(temp, expected)

        data = [np.nan, 35.7688, 35.7925, 35.7761]
        expected = pd.Series(data, index=index, name='SSS')
        pd.testing.assert_series_equal(sal, expected)
