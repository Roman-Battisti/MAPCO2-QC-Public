"""
This module tests the process of exporting a netCDF mapco2 file to CSV.
"""
# standard library imports
import importlib.resources as ir

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.export_to_csv import ExportToCSV
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(self, module, filename):

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

    def test_cycle_header(self):
        """
        SCENARIO:  Export the cycle header netCDF file to CSV.

        EXPECTED RESULT:  The CSV file is verified against the netCDF file.
        """
        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        csv_file = self.root / 'cycle_header.csv'
        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with ExportToCSV(ncfile, csv_file) as p:
            p.run()

        parse_dates = ['gps_dtime', 'sys_dtime2', 'gps_dtime_ck']
        actual = pd.read_csv(
            csv_file, index_col='time', parse_dates=parse_dates
        )
        actual.index = pd.to_datetime(actual.index)

        expected = xr.open_dataset(ncfile).to_dataframe()
        dtypes = {
            colname: np.float64
            for colname in [
                'mode', 'rand1', 'rand2', 'gps_aqtime', 'gps_qf',
                'valve_pulse', 'span_flag', 'zero_flag', 'in_out_flag'
            ]
        }
        expected = expected.astype(dtypes)

        pd.testing.assert_frame_equal(actual, expected)
