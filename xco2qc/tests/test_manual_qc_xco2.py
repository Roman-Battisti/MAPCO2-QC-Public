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
from xco2qc.o2_concentration import CalcO2Concentration
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
        licor_version='820 v1'
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
            ) as p1:
                p1.run()

            with PreXCO2Calc(
                self.reduced_path, verbosity=verbosity
            ) as p2:
                p2.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path,
                verbosity=verbosity,
                licor_version=licor_version
            ) as p3:
                p3.run()

            with QCChecker(
                self.reduced_path, verbosity=verbosity,
                num_points_eachside=num_points_eachside,
                equil_diff_range_lower=equil_diff_range_lower
            ) as p4:
                p4.run()

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

        # Run the processing chain up until the merge.
        #
        # The EPON/EPOFF pressure difference check will flag everything unless
        # we lower the threshold.
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            licor_version='820 v2',
            equil_diff_range_lower=7
        )

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
        ])
        y = [419, 419, 420, 420, 419]
        verts = list(zip(x, y))

        with XCO2ManualQC(self.merge_ncfile, 'xCO2_air') as p:
            p.run()
            p.onselect(
                verts, 'xCO2_air', 'xCO2_air_qc'
            )

        with xr.open_dataset(self.merge_ncfile) as ds:
            actual = ds['xCO2_air_qc'].data.astype(np.uint32)

        # This finds the *INDICES* of the points that have the appropriate
        # flag.  All four of these points occur between 2018-09-26 and
        # 2018-09-27.
        actual = np.nonzero(
            np.bitwise_and(actual, core.quality.MANUALLY_FLAGGED)
        )
        actual = actual[0]

        expected = np.array([32, 35, 36])

        np.testing.assert_allclose(actual, expected)

        # Now run it again and restrict the time to 2018-09-26T12:00:00 and
        # 2018-09-27T00:00:00.  The first point detected earlier occured at
        # 3am, so it should not be detected here.
        x = mdates.date2num([
            dt.datetime(2018, 9, 26, 12),
            dt.datetime(2018, 9, 27, 0),
            dt.datetime(2018, 9, 27, 0),
            dt.datetime(2018, 9, 26, 12),
            dt.datetime(2018, 9, 26, 12),
        ])
        verts = list(zip(x, y))

        with XCO2ManualQC(self.merge_ncfile, 'xCO2_air') as p:
            p.run()
            p.onselect(
                verts, 'xCO2_air', 'xCO2_air_qc'
            )

        with xr.open_dataset(self.merge_ncfile) as ds:
            actual = ds['xCO2_air_qc'].data.astype(np.uint32)

        actual = np.nonzero(
            np.bitwise_and(actual, core.quality.MANUALLY_FLAGGED)
        )
        actual = actual[0]

        expected = np.array([35, 36])

        np.testing.assert_allclose(actual, expected)

    def test_deselect(self):
        """
        SCENARIO:  the range of data between 403 and 404, and 2018-09-26 and
        2018-09-27 is originally flagged, but then the user changes her mind
        about half of the dates

        EXPECTED RESULT:  There are two datums that are masked.
        """

        # Run the processing chain up until the merge.
        #
        # The EPON/EPOFF pressure difference check will flag everything unless
        # we lower the threshold.
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            licor_version='820 v2',
            equil_diff_range_lower=7
        )

        with XCO2ManualQC(self.merge_ncfile, 'xCO2_air') as p:
            p.run()

            # construct the mouse-click data
            x = mdates.date2num([
                dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
            ])
            y = [419, 419, 420, 420, 419]
            verts = list(zip(x, y))

            p.onselect(verts, 'xCO2_air', 'xCO2_air_qc')

            # construct the mouse-click data for the deselect.  assume the
            # user changes her mind about the time
            x = mdates.date2num([
                dt.datetime(2018, 9, 26, 0),
                dt.datetime(2018, 9, 26, 12),
                dt.datetime(2018, 9, 26, 12),
                dt.datetime(2018, 9, 26, 0),
                dt.datetime(2018, 9, 26, 0),
            ])
            y = [419, 419, 420, 420, 419]
            verts = list(zip(x, y))

            p.onselect(verts, 'xCO2_air', 'xCO2_air_qc')

        with xr.open_dataset(self.merge_ncfile) as ds:
            actual = ds['xCO2_air_qc'].data.astype(np.uint32)

        # This finds the *INDICES* of the points that have the appropriate
        # flag.  Originally, 3 datums were selected, now it's just two.
        actual = np.nonzero(
            np.bitwise_and(actual, core.quality.MANUALLY_FLAGGED)
        )
        actual = actual[0]
        expected = np.array([35, 36])
        np.testing.assert_allclose(actual, expected)
