"""
Test suite for the importing of validation data.
"""

# standard library imports
import importlib.resources as ir
import io
import pathlib
import tempfile

# 3rd party library imports
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.validation_data import ValidationData
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke_o2(self):
        """
        SCENARIO:  There is a CSV file with o2 data.

        EXPECTED RESULTS:  A netCDF file is produced.  The dissolved_oxygen
        variable does NOT have an ancillary_variables attribute because there
        are no associated QC variables.
        """
        expected = (
                "time,dissolved_oxygen\n"
                "1950-02-10 09:18:00,232.1794\n"
                "1950-02-10 12:30:00,235.0\n"
        )
        expected_df = pd.read_csv(io.StringIO(expected))

        inputfile = io.StringIO(expected)

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / core.VALIDATION_NCFILE

        with xr.open_dataset(ncfile) as ds:
            df = ds.to_dataframe()
            s = io.StringIO()
            df.to_csv(s)
            s.seek(0)
            actual = s.getvalue()

        actual_df = pd.read_csv(io.StringIO(actual))
        pd.testing.assert_frame_equal(actual_df, expected_df)

        # ancillary variables
        with xr.open_dataset(ncfile) as ds:
            self.assertFalse(
                hasattr(ds['dissolved_oxygen'], 'ancillary_variables')
            )

    def test_nan(self):
        """
        SCENARIO:  There is a CSV file with o2 data.  The o2 data has a NaN

        EXPECTED RESULTS:  A netCDF file is produced.
        """
        text = (
                "time,dissolved_oxygen\n"
                "1950-02-10 09:18:00,232.1794\n"
                "1950-02-10 12:30:00,NaN\n"
        )

        inputfile = io.StringIO(text)

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / core.VALIDATION_NCFILE

        with xr.open_dataset(ncfile) as ds:
            actual = ds.to_dataframe()

        expected = pd.read_csv(
            io.StringIO(text), index_col='time', parse_dates=['time']
        )
        pd.testing.assert_frame_equal(actual, expected)

    def test_two_usable_columns(self):
        """
        SCENARIO:  There is a CSV file with SSS and SST data.

        EXPECTED RESULTS:  A netCDF file is produced.
        """
        text = (
                "time,SSS,SST\n"
                "1950-02-10 09:18:00,30.0,20.0\n"
                "1950-02-10 12:30:00,31.0,21.0\n"
        )

        inputfile = io.StringIO(text)

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / core.VALIDATION_NCFILE

        with xr.open_dataset(ncfile) as ds:
            actual = ds.to_dataframe()

        expected = pd.read_csv(
            io.StringIO(text), index_col='time', parse_dates=['time']
        )
        pd.testing.assert_frame_equal(actual, expected)

    def test_two_usable_columns_and_one_that_is_not(self):
        """
        SCENARIO:  There is a CSV file with SSS and SST columns.  In addition
        there is a column of pH_pco2sys.  Since pH_pco2sys is not QC'd, we
        exclude that.

        EXPECTED RESULTS:  A netCDF file is produced.
        """
        text = (
                "time,SSS,SST,pH_pco2sys\n"
                "1950-02-10 09:18:00,30.0,20.0,5\n"
                "1950-02-10 12:30:00,31.0,21.0,6\n"
        )

        inputfile = io.StringIO(text)

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / core.VALIDATION_NCFILE

        with xr.open_dataset(ncfile) as ds:
            actual = ds.to_dataframe()
            s = io.StringIO(text)
            expected = pd.read_csv(s, index_col='time', parse_dates=['time'])
            expected = expected[['SSS', 'SST']]

        pd.testing.assert_frame_equal(actual, expected)

    def test_no_candidates(self):
        """
        SCENARIO:  There is a CSV file, but it does not contain a column that
        we recognize.

        EXPECTED RESULTS:  RuntimeError
        """
        expected = (
                "time,stuff\n"
                "1950-02-10 09:18:00,232.1794\n"
                "1950-02-10 12:30:00,235.0\n"
        )

        inputfile = io.StringIO(expected)

        with ValidationData(inputfile, self.raw_path, verbosity='DEBUG') as p:
            with self.assertRaises(RuntimeError):
                p.run()

    def test_no_time(self):
        """
        SCENARIO:  There is a CSV file, but it does not contain a time column.

        EXPECTED RESULTS:  ValueError
        """
        expected = (
                "stuff,o2\n"
                "1950-02-10 09:18:00,232.1794\n"
                "1950-02-10 12:30:00,235.0\n"
        )

        inputfile = io.StringIO(expected)

        with ValidationData(inputfile, self.raw_path) as p:
            with self.assertRaises(ValueError):
                p.run()

    def test_time(self):
        """
        SCENARIO:  CSV file

        EXPECTED RESULTS: no errors
        """
        inputfile = ir.files('tests.data.external').joinpath('time.csv')

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / 'validation.nc'
        with xr.open_dataset(ncfile) as ds:
            ds.to_dataframe()

    def test_directory(self):
        """
        SCENARIO:  input file is a directory

        EXPECTED RESULTS: no errors
        """
        tdir = tempfile.mkdtemp()
        tpath = pathlib.Path(tdir)

        with ValidationData(tpath, self.raw_path) as p:
            p.run()

        ncfile = self.raw_path / 'validation.nc'
        self.assertFalse(ncfile.exists())
