"""
Test suite for the importing of external SSTC.
"""

# standard library imports
import io
import pathlib
import tempfile

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.external_met import ImportExternalMET
from . import test_core


class TestSuite(test_core.TestSuite):

    def assertSST(self, met_ncfile):
        with xr.open_dataset(met_ncfile) as ds:

            index = pd.Series(
                pd.to_datetime(['2020-05-23T12:00:00', '2020-05-23T12:30:00']),
                name='time'
            )

            # verify the salinity
            actual = ds['SSS'].to_series()
            expected = pd.Series(
                [33, 35], index=index, dtype=np.float64, name='SSS'
            )
            pd.testing.assert_series_equal(actual, expected)

            # verify the sst
            actual = ds['SST'].to_series()
            expected = pd.Series(
                [22, 23], index=index, dtype=np.float64, name='SST'
            )
            pd.testing.assert_series_equal(actual, expected)

            # verify the data_source.  this is important because the data
            # source should be clear.
            self.assertEqual(ds.data_source, 'external-met')

    def test_smoke(self):
        """
        SCENARIO:  There was no met data.  Import a csv file with the expected
        format(s).

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        texts = [
            (
                "time,salinity,sst\n"
                "2020-05-23T12:00:00,33,22\n"
                "2020-05-23T12:30:00,35,23"
            ),
            (
                "time\tsalinity\tsst\n"
                "2020-05-23T12:00:00\t33\t22\n"
                "2020-05-23T12:30:00\t35\t23"
            ),
        ]

        for text in texts:
            inputfile = io.StringIO(text)

            with ImportExternalMET(inputfile, self.raw_path) as p:
                p.run()

            met_ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
            self.assertSST(met_ncfile)

    def test_one_import_for_sss_and_one_import_for_sst(self):
        """
        SCENARIO:  There was no met data.  Import two csv files for SSS and
        SST.

        EXPECTED RESULTS:  A raw met netCDF file is produced.  Both SSS and
        SST are verified.
        """
        texts = [
            (
                "time,salinity\n"
                "2020-05-23T12:00:00,33\n"
                "2020-05-23T12:30:00,35"
            ),
            (
                "time,sst\n"
                "2020-05-23T12:00:00,22\n"
                "2020-05-23T12:30:00,23"
            ),
        ]

        for text in texts:
            inputfile = io.StringIO(text)

            with ImportExternalMET(inputfile, self.raw_path) as p:
                p.run()

        met_ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
        self.assertSST(met_ncfile)

    def test_temperature(self):
        """
        SCENARIO:  There was no met data.  Import a csv file with the expected
        format, but instead of sst we have temperature name instead.

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        text = (
            "time,salinity,temperature\n"
            "2020-05-23T12:00:00,33,22\n"
            "2020-05-23T12:30:00,35,23"
        )
        inputfile = io.StringIO(text)

        with ImportExternalMET(inputfile, self.raw_path) as p:
            p.run()

        met_ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
        self.assertSST(met_ncfile)

    def test_upper_case(self):
        """
        SCENARIO:  There was no met data.  Import a csv file with the expected
        format, but there are upper case names

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        text = (
            "TIME,SALINITY,TEMPERATURE\n"
            "2020-05-23T12:00:00,33,22\n"
            "2020-05-23T12:30:00,35,23"
        )
        inputfile = io.StringIO(text)

        with ImportExternalMET(inputfile, self.raw_path) as p:
            p.run()

        met_ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
        self.assertSST(met_ncfile)

    def test_reversed(self):
        """
        SCENARIO:  There was no met data.  Import a csv file with the expected
        format, except that the salinity and temperature columns are not in
        order.

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        text = (
            "time,temperature,salinity\n"
            "2020-05-23T12:00:00,22,33\n"
            "2020-05-23T12:30:00,23,35"
        )
        inputfile = io.StringIO(text)

        with ImportExternalMET(inputfile, self.raw_path) as p:
            p.run()

        met_ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
        self.assertSST(met_ncfile)

    def test_time_is_not_iso(self):
        """
        SCENARIO:  There was no met data.  Import a csv file with the expected
        format, but the time is not iso format.

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        text = (
            "time,salinity,temperature\n"
            "2020-05-23 12:00:00,33,22\n"
            "2020-05-23 12:30:00,35,23"
        )
        inputfile = io.StringIO(text)

        with ImportExternalMET(inputfile, self.raw_path) as p:
            p.run()

        met_ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
        self.assertSST(met_ncfile)

    def test_SSS_SST(self):
        """
        SCENARIO:  There was no met data.  Import a csv file with the expected
        format, but the time is not iso format.

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        text = (
            "time,SSS,SST\n"
            "09/18/2018 03:18,35.046,25.474\n"
            "09/18/2018 04:18,35.048,25.466\n"
            "09/18/2018 04:48,35.049,25.432\n"
            "09/18/2018 05:18,35.049,25.429\n"
        )
        inputfile = io.StringIO(text)

        with ImportExternalMET(inputfile, self.raw_path) as p:
            p.run()

        met_ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
        with xr.open_dataset(met_ncfile) as ds:
            self.assertIn('SSS', ds)
            self.assertIn('SST', ds)

    def test_directory_path_instead_of_file(self):
        """
        SCENARIO:  A directory is passed instead of a file.  This will happen
        in the jupyter notebook if the user cancels out of the file dialog.

        EXPECTED RESULTS:  No detectable change, but no error either.
        """
        inputfile = pathlib.Path('.')
        with ImportExternalMET(inputfile, self.raw_path) as p:
            p.run()

    def test_directory_string_instead_of_file(self):
        """
        SCENARIO:  A directory is passed instead of a file.  This will happen
        in the jupyter notebook if the user cancels out of the file dialog.

        EXPECTED RESULTS:  No detectable change, but no error either.
        """
        with tempfile.TemporaryDirectory() as tdir:
            with ImportExternalMET(tdir, self.raw_path) as p:
                p.run()
