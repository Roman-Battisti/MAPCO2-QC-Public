# standard library imports
import importlib.resources as ir

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.external_sbe63 import ImportExternalSBE63
from xco2qc.qc import QCChecker
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        with ir.as_file(ir.files('tests.data.mapco2.whots.depl08').joinpath('sbe63.txt')) as path:
            with ImportExternalSBE63(path, self.raw_path) as p:
                p.run()

        with XCO2Reduce(self.raw_path, self.reduced_path) as p:
            p.process_external_sbe63()

        time = [
            '2014-07-17 03:00:01', '2014-07-17 05:30:00',
            '2014-07-17 06:00:00', '2014-07-17 06:30:00',
        ]
        index = pd.DatetimeIndex(time, name='time')
        data = np.array([
            np.nan, 206.082115407291, 205.869220684994, 205.644511829777
        ])
        expected = pd.DataFrame({'o2': data}, index=index)

        # test the raw netCDF file
        ncfile = self.raw_path / core.EXTERNAL_SBE63_NCFILE
        with xr.open_dataset(ncfile) as ds:
            actual = ds.to_dataframe()
            pd.testing.assert_frame_equal(actual, expected)

        # test the "reduced".  The o2 should be the same, but in addition we
        # now have the QC data.
        ncfile = self.reduced_path / core.EXTERNAL_SBE63_NCFILE
        with xr.open_dataset(ncfile) as ds:
            actual = ds.to_dataframe()

            expected['o2_qc'] = np.array([1, 1, 1, 1], dtype=np.float64)
            pd.testing.assert_frame_equal(actual, expected)

        # Test the QC part
        with QCChecker(self.reduced_path) as o:
            o.check_valid_range()

        with xr.open_dataset(ncfile) as ds:
            actual = ds.to_dataframe()

            expected['o2_qc'] = np.array([
                core.quality.OUT_OF_RANGE,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
            ], dtype=np.float64)
            pd.testing.assert_frame_equal(actual, expected)
