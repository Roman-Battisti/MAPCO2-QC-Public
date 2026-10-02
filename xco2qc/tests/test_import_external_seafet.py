# standard library imports
import importlib.resources as ir
import unittest

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc.external_seafet import ImportExternalSeafet
from xco2qc.data_reduction import XCO2Reduce
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def assertPH(self, ph_ncfile):
        with xr.open_dataset(ph_ncfile) as ds:

            index = pd.Series(
                pd.to_datetime([
                    '2017-06-10T04:36:39',
                    '2017-06-10T05:06:32',
                    '2017-06-10T05:36:33',
                    '2017-06-10T06:06:32',
                    '2017-06-10T06:36:33',
                ]),
                name='time'
            )

            actual = ds['SSS'].to_series()
            expected = pd.Series(
                [35, 35, 35, 35, 35],
                index=index, dtype=np.float64, name='SSS'
            )
            pd.testing.assert_series_equal(actual, expected)

            actual = ds['temperature'].to_series()
            expected = pd.Series(
                [13.33, 13.32, 13.24, 13.22, 13.2],
                index=index, dtype=np.float64, name='temperature'
            )
            pd.testing.assert_series_equal(actual, expected)

            actual = ds['ph_int'].to_series()
            expected = pd.Series(
                [8.1568, 8.1539, 8.1531, 8.1515, 8.1526],
                index=index, dtype=np.float64, name='ph_int'
            )
            pd.testing.assert_series_equal(actual, expected)

            actual = ds['ph_ext'].to_series()
            expected = pd.Series(
                [8.0738, 8.0836, 8.0950, 8.1037, 8.1137],
                index=index, dtype=np.float64, name='ph_ext'
            )
            pd.testing.assert_series_equal(actual, expected)

            self.assertEqual(ds.data_source, 'external-seafet')

    @unittest.skip('excel format is wrong')
    def test_smoke(self):
        """
        SCENARIO:  Read an external seafet file.

        EXPECTED RESULTS:  A raw seafet netCDF file is produced.
        """
        with ir.as_file(ir.files('tests.data.external').joinpath('capearago.xlsx')) as inputfile:
            with ImportExternalSeafet(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SEAFET_NCFILE
            self.assertPH(ncfile)

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_seafet()

            ncfile = self.reduced_path / core.EXTERNAL_SEAFET_NCFILE
            self.assertPH(ncfile)

    def test_smoke_chuuk(self):
        """
        SCENARIO:  Read an external seafet file.

        EXPECTED RESULTS:  A raw seafet netCDF file is produced.
        """
        with ir.as_file(ir.files(
            'tests.data.external.chuuk'
            ).joinpath(
            'seafet.satphp0094.txt'
        )) as inputfile:
            with ImportExternalSeafet(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SEAFET_NCFILE

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_seafet()

            ncfile = self.reduced_path / core.EXTERNAL_SEAFET_NCFILE
            with xr.open_dataset(ncfile) as ds:

                index = pd.Series(
                    pd.to_datetime([
                        '2015-08-12T15:41:25',
                        '2015-08-12T15:41:29',
                        '2015-08-12T15:41:33',
                    ]),
                    name='time'
                )

                actual = ds['SSS'].to_series()
                expected = pd.Series(
                    [33.937, 33.937, 33.937],
                    index=index, dtype=np.float64, name='SSS'
                )
                pd.testing.assert_series_equal(actual, expected)

                actual = ds['temperature'].to_series()
                expected = pd.Series(
                    [29.38, 29.38, 29.38],
                    index=index, dtype=np.float64, name='temperature'
                )
                pd.testing.assert_series_equal(actual, expected)

                actual = ds['ph_int'].to_series()
                expected = pd.Series(
                    [6.6933, 6.6938, 6.6943],
                    index=index, dtype=np.float64, name='ph_int'
                )
                pd.testing.assert_series_equal(actual, expected)

                actual = ds['ph'].to_series()
                expected = pd.Series(
                    [6.5474, 6.5478, 6.5485],
                    index=index, dtype=np.float64, name='ph'
                )
                pd.testing.assert_series_equal(actual, expected)

                self.assertEqual(ds.data_source, 'external-seafet')

    def test_smoke_cce1(self):
        """
        SCENARIO:  Read an external seafet file from CCE1.  The data is not
        in chronological order.

        EXPECTED RESULTS:  A raw seafet netCDF file is produced.  The seafet
        data IS in chronological order.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.cce1.depl_11'
            ).joinpath(
            'seafet.csv'
        )) as inputfile:
            with ImportExternalSeafet(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SEAFET_NCFILE

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_seafet()

            ncfile = self.reduced_path / core.EXTERNAL_SEAFET_NCFILE
            with xr.open_dataset(ncfile) as ds:

                index = pd.Series(
                    pd.to_datetime([
                        '2019-03-05T03:05:57',
                        '2019-03-05T03:05:58',
                        '2019-03-05T03:05:59',
                        '2019-03-05T06:05:54',
                    ]),
                    name='time'
                )

                actual = ds['SSS'].to_series()
                expected = pd.Series(
                    [33.409, 33.409, 33.409, 33.413],
                    index=index, dtype=np.float64, name='SSS'
                )
                pd.testing.assert_series_equal(actual, expected)

                self.assertEqual(ds.data_source, 'external-seafet')
