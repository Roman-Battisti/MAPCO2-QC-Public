# standard library imports
import datetime as dt
import importlib.resources as ir

# 3rd party library imports
import matplotlib.dates as mdates
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.manual_qc_xco2 import XCO2ManualQC
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        verbosity='CRITICAL',
        num_points_eachside=1,
        equil_diff_range_lower=8,
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity
            ) as p0:
                p0.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
                verbosity=verbosity
            ) as p:
                p.run()

            with PreXCO2Calc(
                self.reduced_path, verbosity=verbosity
            ) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path, verbosity=verbosity
            ) as p:
                p.run()

            with QCChecker(
                self.reduced_path, verbosity=verbosity,
                num_points_eachside=num_points_eachside,
                equil_diff_range_lower=equil_diff_range_lower
            ) as p:
                p.run()

            with XCO2Merge(
                self.reduced_path, self.merge_ncfile,
                verbosity=verbosity
            ) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  the range of data between 403 and 404, and 2018-09-26 and
        2018-09-27 is desired to be flagged

        EXPECTED RESULT:  There are four datums that are masked.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            equil_diff_range_lower=7
        )

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
        ])
        y = [8.050, 8.050, 8.056, 8.056, 8.050]
        verts = list(zip(x, y))

        with XCO2ManualQC(self.merge_ncfile, 'pH_sw') as p:
            p.run()
            p.onselect(verts, 'pH_sw', 'pH_sw_qc')

        with xr.open_dataset(self.merge_ncfile) as ds:
            actual = ds['pH_sw_qc'].data.astype(np.uint32)

        # This finds the *INDICES* of the points that have the appropriate
        # flag.  All four of these points occur between 2018-09-26 and
        # 2018-09-27.
        actual = np.nonzero(
            np.bitwise_and(actual, core.quality.MANUALLY_FLAGGED)
        )
        actual = actual[0]

        expected = np.array([32, 34, 35, 37, 38])

        np.testing.assert_allclose(actual, expected)
