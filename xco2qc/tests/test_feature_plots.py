# standard library imports
import importlib.resources as ir
import shutil

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.feature_plots import FeaturePlots
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(self, module, filename, calculate_post_xco2=True):

        # Run the processing up until xco2 computations
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

    def test_smoke(self):
        """
        SCENARIO:  Run the feature plots.

        EXPECTED RESULT:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as src:
            dst = self.reduced_path / core.HISTORICAL_NCFILE
            shutil.copyfile(src, dst)

        pairs = (
            (
                (core.licor.APOFF_NCFILE, 'xco2_wet'),
                (core.licor.EPOFF_NCFILE, 'post_xco2_dry')
            ),
            (
                (core.HISTORICAL_NCFILE, 'SSS'),
                (core.MET_NCFILE, 'SSS')
            ),
            (
                (core.MET_NCFILE, 'SST'),
                (core.MET_NCFILE, 'SSS')
            )
        )
        with FeaturePlots(self.reduced_path, pairs) as p:
            p.run()
