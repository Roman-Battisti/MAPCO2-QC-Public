"""
Test suite for the process of merging pH into the xco2 merge netCDF file.
"""

# standard library imports
import importlib.resources as ir

# 3rd party library imports
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        initial_span_cal=0,
        num_points_eachside=1,
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(self.reduced_path) as p3:
                p3.run()

            with QCChecker(
                self.reduced_path,
                initial_span_cal=initial_span_cal,
                num_points_eachside=1
            ) as p4:
                p4.run()

            with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
                mp.run()

    def test_sami_missing_one_cycle(self):
        """
        SCENARIO:  We perform a merge where SAMI data was present, but there
        was one cycle where the sami section was not present.

        EXPECTED RESULT:  The PH should have a nan in that 3rd cycle.  The QC
        clearly indicates that the data was missing in that 3rd cycle.
        """
        self._processing_chain(
            'tests.data.mapco2.stratus',
            '0156_dp11_20180410_20190424.4.missing_a_sami.txt'
        )

        with xr.open_dataset(self.merge_ncfile) as ds:

            actual = ds['pH_sw'][:]
            expected = np.array([8.10369, 8.06154, np.nan, 8.06095])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['pH_sw_qc'][:]
            expected = np.array([
                core.quality.GOOD, core.quality.GOOD,
                core.quality.MISSING_DATA, core.quality.GOOD
            ])
            np.testing.assert_array_equal(actual, expected)

    def test_smoke(self):
        """
        SCENARIO:  We perform a merge where SAMI data was present.

        EXPECTED RESULT:  The datasets are verified.
        """
        self._processing_chain(
            'tests.data.mapco2.stratus', '0156_dp11_20180410_20190424.4.txt'
        )

        with xr.open_dataset(self.merge_ncfile) as ds:

            actual = ds['pH_sw'][:]
            expected = np.array([8.10338, 8.06123, 8.0587, 8.0606])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['pH_sw_qc'][:]
            expected = np.array([
                core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD, core.quality.GOOD
            ])
            np.testing.assert_array_equal(actual, expected)
