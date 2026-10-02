"""
The purpose of this module is to test the xco2 QC plots.
"""

# standard library imports
import importlib.resources as ir

# local imports
from tests import test_core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.qc_plots import QCPlots


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, num_points_eachside=1,
        calculate_post_xco2=True
    ):

        # Run the processing up until qc plots
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p:
                p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path, calculate_post_xco2=calculate_post_xco2
            ) as p:
                p.run()

            with QCChecker(
                self.reduced_path, num_points_eachside=num_points_eachside
            ) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the automatic QC plots for a basic case

        EXPECTED RESULTS:  No errors.
        """

        num_points_eachside = 1

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            num_points_eachside=num_points_eachside
        )

        with QCPlots(
            self.reduced_path, num_points_eachside=num_points_eachside
        ) as p:
            p.run()

    def test_no_post_xco2(self):
        """
        SCENARIO:  Run the automatic QC plots when there was no post xco2
        calculated.

        EXPECTED RESULTS:  No errors.
        """

        num_points_eachside = 1

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            num_points_eachside=num_points_eachside,
            calculate_post_xco2=False
        )

        with QCPlots(
            self.reduced_path, num_points_eachside=num_points_eachside
        ) as p:
            p.run()
