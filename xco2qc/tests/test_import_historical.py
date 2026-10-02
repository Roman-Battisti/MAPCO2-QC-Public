# standard library imports
import importlib.resources as ir
import logging

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc.external_historical import ImportHistorical
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO:  Import historical data

        EXPECTED RESULTS:  A raw netCDF file is produced.
        """
        with ir.as_file(ir.files(
            'tests.data.external.stratus'
            ).joinpath(
            'historical.4.txt'
        )) as ifile:
            with ImportHistorical(ifile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.HISTORICAL_NCFILE

        with xr.open_dataset(ncfile) as ds:

            time = [
                '2006-10-16 21:00:00', '2006-10-16 21:30:00',
                '2006-10-16 22:00:00', '2006-10-16 22:30:00',
            ]
            index = pd.DatetimeIndex(time, name='time')

            data = [19.872, 19.876, 19.742, 19.701]
            expected = pd.Series(data, index=index, name='SST')
            actual = ds['SST'].to_series()
            pd.testing.assert_series_equal(actual, expected)

            data = [35.435, 35.433, 35.433, 35.432]
            expected = pd.Series(data, index=index, name='SSS')
            actual = ds['SSS'].to_series()
            pd.testing.assert_series_equal(actual, expected)

            data = [373.1, 373.0, 371.4, 370.0]
            expected = pd.Series(data, index=index, name='pCO2_sw')
            actual = ds['pCO2_sw'].to_series()
            pd.testing.assert_series_equal(actual, expected)

            data = [369.8, 370.3, 370.3, 370.8]
            expected = pd.Series(data, index=index, name='pCO2_air')
            actual = ds['pCO2_air'].to_series()
            pd.testing.assert_series_equal(actual, expected)

            data = [379.6, 380.1, 380.0, 380.4]
            expected = pd.Series(data, index=index, name='xCO2_air')
            actual = ds['xCO2_air'].to_series()
            pd.testing.assert_series_equal(actual, expected)

            data = [np.nan, np.nan, np.nan, np.nan]
            expected = pd.Series(data, index=index, name='pH_sw')
            actual = ds['pH_sw'].to_series()
            pd.testing.assert_series_equal(actual, expected)

    def test_multiple_separate_imports(self):
        """
        SCENARIO:  Import SSS and SST separately.  The SSS and SST share some
        but not all timestamps.

        EXPECTED RESULTS:  A raw netCDF file is produced.
        """
        with ir.as_file(ir.files(
            'tests.data.external.stratus'
            ).joinpath(
            'historical.123.sss.txt'
        )) as ifile:
            with ImportHistorical(ifile, self.raw_path) as p:
                p.run()

        with ir.as_file(ir.files(
            'tests.data.external.stratus'
            ).joinpath(
            'historical.234.sst.txt'
        )) as ifile:
            with ImportHistorical(ifile, self.raw_path) as p:
                p.run()

        ncfile = self.raw_path / core.HISTORICAL_NCFILE

        with xr.open_dataset(ncfile) as ds:

            time = [
                '2006-10-16 21:00:00', '2006-10-16 21:30:00',
                '2006-10-16 22:00:00', '2006-10-16 22:30:00',
            ]
            index = pd.DatetimeIndex(time, name='time')

            data = [np.nan, 19.876, 19.742, 19.701]
            expected = pd.Series(data, index=index, name='SST')
            actual = ds['SST'].to_series()
            pd.testing.assert_series_equal(actual, expected)

            data = [35.435, 35.433, 35.433, np.nan]
            expected = pd.Series(data, index=index, name='SSS')
            actual = ds['SSS'].to_series()
            pd.testing.assert_series_equal(actual, expected)

    def test_multiple_separate_imports__no_shared_timestamps(self):
        """
        SCENARIO:  Import SSS and SST separately.  The SSS and SST do not share
        any timestamps (interleaved).

        EXPECTED RESULTS:  A raw netCDF file is produced.
        """
        with ir.as_file(ir.files(
            'tests.data.external.stratus'
            ).joinpath(
            'historical.sss.interleaved.txt'
        )) as ifile:
            with ImportHistorical(ifile, self.raw_path) as p:
                p.run()

        with ir.as_file(ir.files(
            'tests.data.external.stratus'
            ).joinpath(
            'historical.sst.interleaved.txt'
        )) as ifile:
            with ImportHistorical(ifile, self.raw_path) as p:
                p.run()

        ncfile = self.raw_path / core.HISTORICAL_NCFILE

        with xr.open_dataset(ncfile) as ds:

            time = [
                '2006-10-16 21:00:00',
                '2006-10-16 21:15:00',
                '2006-10-16 21:30:00',
                '2006-10-16 21:45:00',
                '2006-10-16 22:00:00',
                '2006-10-16 22:15:00',
                '2006-10-16 22:30:00',
                '2006-10-16 22:45:00',
            ]
            index = pd.DatetimeIndex(time, name='time')

            data = [
                19.872, np.nan, 19.876, np.nan, 19.742, np.nan, 19.701, np.nan
            ]
            expected = pd.Series(data, index=index, name='SST')
            actual = ds['SST'].to_series()
            pd.testing.assert_series_equal(actual, expected)

            data = [
                np.nan, 35.435, np.nan, 35.433, np.nan, 35.433, np.nan, 35.432
            ]
            expected = pd.Series(data, index=index, name='SSS')
            actual = ds['SSS'].to_series()
            pd.testing.assert_series_equal(actual, expected)

    def test_opt_out(self):
        """
        SCENARIO:  The user cancels out of the import.

        EXPECTED RESULTS:  no error
        """
        with ImportHistorical('.', self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / core.HISTORICAL_NCFILE
        self.assertFalse(ncfile.exists())

    def test_excel_file(self):
        """
        SCENARIO:  The generic CSV import tool is given an historical data
        file but it's in excel format.

        EXPECTED RESULTS:  RuntimeError
        """

        # take a file that we know works and convert it to excel
        with ir.as_file(ir.files(
            'tests.data.external.stratus'
            ).joinpath(
            'historical.4.txt'
        )) as ifile:
            with ImportHistorical(ifile, self.raw_path) as p:
                df = p.read_data()

            excel_file = self.root / 'historical.4.xlsx'
            df.to_excel(excel_file)

            with self.assertRaises(RuntimeError):
                with ImportHistorical(excel_file, self.raw_path) as p:
                    p.run()


class TestErddap(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, deployment_number=None, verbosity='critical'
    ):
        """
        Shortcut for running just raw processing.
        """

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity
            ) as p0:
                p0.run()

    def test_smoke(self):
        """
        SCENARIO:  The historical module is invoked with no local file, which
        means to try to contact the PMEL ERDDAP server.

        EXPECTED RESULT:  The historical netCDF file is produced from the
        ERDDAP server.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1',
            '0108_dp11_20181113_20190509.txt'
        )

        with ImportHistorical(None, self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / core.HISTORICAL_NCFILE
        self.assertTrue(ncfile.exists())

    def test_bad_site_id(self):
        """
        SCENARIO:  The historical module is invoked with no local file, which
        means to try to contact the PMEL ERDDAP server.  However, the site
        ID in the mapco2 file is bad, meaning we need to provide it ourselves.
        In this case the site ID should be 'cce1', but it is instead 'cce1_11'.

        EXPECTED RESULT:  The historical netCDF file is produced from the
        ERDDAP server.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1',
            '0108_dp11_20181113_20190509.bad_site_id.txt'
        )

        with ImportHistorical(None, self.raw_path, site_id='cce1') as p:
            p.run()

        ncfile = self.raw_path / core.HISTORICAL_NCFILE
        self.assertTrue(ncfile.exists())


class SailDrone(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, verbosity='critical'
    ):
        """
        Shortcut for running just raw processing.
        """

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            input_dir = inputfile.parents[0]
            with RawTextToRawNC(
                input_dir,
                dst_dir=self.raw_path,
                verbosity=verbosity
            ) as p0:
                p0.run()

    def test_smoke(self):
        """
        SCENARIO:  The historical module is invoked with no local file, which
        means to try to contact the PMEL ERDDAP server.  But this is saildrone
        data, so we actually don't want to contact anyone.

        EXPECTED RESULT:  No historical file is produced.  But there is some
        logging.
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        with ImportHistorical(None, self.raw_path, verbosity='info') as p:
            with self.assertLogs(p.logger, level=logging.INFO):
                p.run()

        ncfile = self.raw_path / core.HISTORICAL_NCFILE
        self.assertFalse(ncfile.exists())
