"""
Test suite for the importing of external SSTC.
"""

# standard library imports
import importlib.resources as ir
import io

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.external_met import ImportExternalMET
from xco2qc.data_reduction import XCO2Reduce
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO:  There was no met data.  Import a csv file with the expected
        format.

        EXPECTED RESULTS:  A reduced met netCDF file is produced, meaning that
        quality variables should be there, specifically the salinity and
        temperature qc variables.
        """

        # run the raw data conversion
        with ir.as_file(ir.files(
            'tests.data.mapco2.nh'
            ).joinpath(
            'dp09_0014_20131105_20140802.met.txt'
        )) as path:
            with RawTextToRawNC(path, dst_dir=self.raw_path) as p0:
                p0.run()

        # import the external met data
        text = (
            "time,salinity,sst\n"
            "2013-11-05T18:59:00,33,22\n"
            "2013-11-05T19:31:00,35,23\n"
            "2013-11-05T20:01:00,35,23\n"
        )
        inputfile = io.StringIO(text)

        with ImportExternalMET(inputfile, self.raw_path) as p:
            p.run()

        # reduce the data, introduce QC variables.
        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        met_ncfile = self.reduced_path / core.EXTERNAL_MET_NCFILE

        with xr.open_dataset(met_ncfile) as ds:

            index = pd.Series(
                pd.to_datetime([
                    '2013-11-05T18:59:00',
                    '2013-11-05T19:31:00',
                    '2013-11-05T20:01:00',
                ]),
                name='time'
            )

            # verify the salinity QC
            actual = ds['SSS_qc'].to_series()
            expected = pd.Series(
                np.full((3,), core.quality.GOOD),
                index=index,
                dtype=np.float64,
                name='SSS_qc'
            )
            pd.testing.assert_series_equal(actual, expected)

            # verify the sst QC
            actual = ds['SST_qc'].to_series()
            expected = pd.Series(
                np.full((3,), core.quality.GOOD),
                index=index,
                dtype=np.float64,
                name='SST_qc'
            )
            pd.testing.assert_series_equal(actual, expected)

            # verify the data_source.  this is important because the data
            # source should be clear.
            self.assertEqual(ds.data_source, 'external-met')
