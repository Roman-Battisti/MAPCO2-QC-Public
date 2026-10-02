# standard library imports
import importlib.resources as ir
import io
import logging

# 3rd party library imports
import netCDF4
import xarray as xr

# local imports
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.external_historical import ImportHistorical
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.trim_netcdf import TrimXCO2netCDF
from xco2qc import core
from xco2qc.validation_data import ValidationData
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, deployment_number=None, historical_file=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                deployment_number=deployment_number
            ) as p0:
                p0.run()

            if historical_file is not None:
                with ImportHistorical(historical_file, self.raw_path) as p:
                    p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Don't actually trim anything.

        EXPECTED RESULT:  The time series are the same length before and after.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        for ncfile in [
            self.reduced_path / core.CYCLE_HEADER_NCFILE,
            self.reduced_path / core.licor.APOFF_NCFILE,
            self.reduced_path / core.licor.APOFF_NCFILE,
        ]:
            with xr.open_dataset(ncfile) as ds:
                ts = ds['time'].to_series()
                self.assertEqual(len(ts), 6)

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
        ) as p:
            p.run()

        for ncfile in [
            self.trimmed_path / core.CYCLE_HEADER_NCFILE,
            self.trimmed_path / core.licor.APOFF_NCFILE,
            self.trimmed_path / core.licor.APOFF_NCFILE,
        ]:
            with xr.open_dataset(ncfile) as ds:
                ts = ds['time'].to_series()
                self.assertEqual(len(ts), 6)

    def test_validation_data(self):
        """
        SCENARIO:  Validation data was present before trimming is done.

        EXPECTED RESULT:  Validation data is confirmed in the trimming area.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
        )

        text = (
                "time,dissolved_oxygen\n"
                "2013-11-05 15:00:00,100\n"
                "2013-11-05 16:00:00,100\n"
        )
        inputfile = io.StringIO(text)

        with ValidationData(inputfile, self.reduced_path) as p:
            p.run()

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            start="2013-11-05T00:00:00", stop="2013-11-05T21:57:45"
        ) as p:
            p.run()

        ncfile = self.reduced_path / 'validation.nc'
        self.assertTrue(ncfile.exists())

    def test_trim(self):
        """
        SCENARIO:  Trim off the first 50% the time extent and the last 25%.
        Because the time series has more values in the latter half of the
        deployment, we still has 2 values left out of the 6.

        EXPECTED RESULT:  Two values are left.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 6)

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            start="2013-11-05T17:38:30", stop="2013-11-05T18:57:45"
        ) as p:
            p.run()

        ncfile = self.trimmed_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 2)

    def test_historical(self):
        """
        SCENARIO:  Trim off the first 50% the time extent and the last 25%.
        Because the time series has more values in the latter half of the
        deployment, we still has 2 values left out of the 6.  Add a historical
        file into the fix.

        EXPECTED RESULT:  No errors. Two values are left.
        """
        with ir.as_file(ir.files(
            'tests.data.external.stratus'
            ).joinpath(
            'historical.4.txt'
        )) as historical_file:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                historical_file=historical_file
            )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 6)

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            start="2013-11-05T17:38:30", stop="2013-11-05T18:57:45"
        ) as p:
            p.run()

        ncfile = self.trimmed_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 2)

    def test_deployment_number(self):
        """
        SCENARIO:  The deployment number were set at the beginning
        of the processing.

        EXPECTED RESULT:  They are verified as global attributes in the
        finished file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            deployment_number=9
        )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 6)

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            start="2013-11-05T17:38:30", stop="2013-11-05T18:57:45"
        ) as p:
            p.run()

        ncfile = self.trimmed_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.site_id, 'nh')
            self.assertEqual(nc.deployment_number, 9)

    def test_date_selection_does_not_capture_any_points(self):
        """
        SCENARIO:  The choice of starting and stopping dates is such that not
        even a single data point is captured.

        EXPECTED RESULT:  RuntimeError
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with self.assertRaises(RuntimeError):
            with TrimXCO2netCDF(
                self.reduced_path, self.trimmed_path,
                start="2013-11-05T17:38:30", stop="2013-11-05T17:38:31"
            ) as p:
                p.run()

    def test_start_date_is_past_the_stop_date(self):
        """
        SCENARIO:  The start date is later than the stop date.

        EXPECTED RESULT:  RuntimeError
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with self.assertRaises(RuntimeError):
            with TrimXCO2netCDF(
                self.reduced_path, self.trimmed_path,
                start="2013-11-07T17:39:30", stop="2013-11-05T17:38:31"
            ) as p:
                p.run()

    def test_start_date_is_none(self):
        """
        SCENARIO:  The start date is None.

        EXPECTED RESULT:  The start date is interpreted as being intended to
        be the first point in the netCDF time series.  With the end point
        chosen to be past the end of the time series, the result is that the
        entire time series is chosen.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 6)

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            start=None, stop="2020-01-01"
        ) as p:
            p.run()

        ncfile = self.trimmed_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 6)

    def test_stop_date_is_none(self):
        """
        SCENARIO:  The stop date is None.

        EXPECTED RESULT:  The stop date is interpreted as being intended to
        be the last point in the netCDF time series.  With the start point
        chosen to be before the beginning of the time series, the result is
        that the entire time series is chosen.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 6)

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            start="2000-01-01", stop=None
        ) as p:
            p.run()

        ncfile = self.trimmed_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 6)

    def test_parent_directory_of_output_ncfile_does_not_exist(self):
        """
        SCENARIO:  The parent directory of the output netCDF file does not
        exist.

        EXPECTED RESULT:  We do not error out.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        trimmed_path = self.root / 'i_do_not_exist'

        with TrimXCO2netCDF(
            self.reduced_path, trimmed_path,
            start="2000-01-01", stop=None
        ) as p:
            p.run()

    def test_logging(self):
        """
        SCENARIO:  The trimming is invoked normally.

        EXPECTED RESULT:  logging is verified
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            verbosity='INFO',
            start="2013-11-05T17:38:30", stop="2013-11-05T18:57:45"
        ) as p:
            with self.assertLogs(p.logger, level=logging.INFO):
                p.run()


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, deployment_number=None, historical_file=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                deployment_number=deployment_number
            ) as p0:
                p0.run()

            if historical_file is not None:
                with ImportHistorical(historical_file, self.raw_path) as p:
                    p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  trim with saildrone data

        EXPECTED RESULT:  no errors
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 3)

        with TrimXCO2netCDF(
            self.reduced_path, self.trimmed_path,
            start="2021-08-16T00:12:00", stop="2021-08-16T00:25:000"
        ) as p:
            p.run()

        ncfile = self.trimmed_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ts = ds['time'].to_series()
            self.assertEqual(len(ts), 1)
