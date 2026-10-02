# standard library imports
import importlib.resources as ir

# local imports
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.post_xco2_plots import PostXCO2Plots
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(self, module, filename, calculate_post_xco2=True):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p:
                p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path, calculate_post_xco2=calculate_post_xco2
            ) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Create post xco2 plots

        EXPECTED RESULT:  Should not error out.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with PostXCO2Plots(self.reduced_path) as p:
            p.run()

    def test_no_post_xco2(self):
        """
        SCENARIO:  Create post xco2 plots, but there's no post xco2

        EXPECTED RESULT:  Should not error out.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            calculate_post_xco2=False
        )

        with PostXCO2Plots(self.reduced_path) as p:
            p.run()
