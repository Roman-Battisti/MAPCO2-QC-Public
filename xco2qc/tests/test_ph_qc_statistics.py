# standard library imports
import importlib.resources as ir

# local imports
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.qc_statistics import PH_QCStatistics
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(self, module, filename, num_points_eachside=1):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p:
                p.run()

            with XCO2Reduce(
                self.raw_path, self.reduced_path
            ) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(self.reduced_path) as p:
                p.run()

            with QCChecker(
                self.reduced_path,
                num_points_eachside=num_points_eachside
            ) as qc:
                qc.run()

            with XCO2Merge(self.reduced_path, self.merge_ncfile) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the display of QC statistics

        EXPECTED RESULTS:  no errors, the length of the time series is
        verified, the number of columns in the dataframe is just one, for the
        single PH variable.
        """
        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with PH_QCStatistics(self.merge_ncfile) as p:
            p.run()

            self.assertEqual(p.tslen, 6)
            self.assertEqual(len(p.df.columns), 1)
