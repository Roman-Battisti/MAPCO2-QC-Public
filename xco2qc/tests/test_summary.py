# standard library imports
import importlib.resources as ir
import shutil

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.trim_netcdf import TrimXCO2netCDF
from xco2qc.socat_qc import SocatQC
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.summary import XCO2Summary
import tests.test_core


class TestSuite(tests.test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename,
        historical_ncfile=None,
        initial_span_cal=490,
        num_points_eachside=1,
        calculate_post_xco2=True
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
                p.run()

            if historical_ncfile is not None:
                dst = self.raw_path / core.HISTORICAL_NCFILE
                shutil.copyfile(historical_ncfile, dst)

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
            ) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with TrimXCO2netCDF(self.reduced_path, self.trimmed_path) as m:
                m.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.trimmed_path) as p:
                p.run()

            with PostXCO2Calc(
                self.trimmed_path, calculate_post_xco2=calculate_post_xco2
            ) as p:
                p.run()

            with QCChecker(
                self.trimmed_path,
                initial_span_cal=initial_span_cal,
                num_points_eachside=num_points_eachside
            ) as p:
                p.run()

            with XCO2Merge(self.trimmed_path, self.merge_ncfile) as m:
                m.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

            with MetadataWriter(self.merge_ncfile) as m:
                m.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the notebook summary.

        EXPECTED RESULTS:  no errors
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_ncfile=historical_ncfile
            )

            with XCO2Summary(
                self.merge_ncfile, historical_ncfile=historical_ncfile
            ) as p:
                p.run()

    def test_no_post_xco2(self):
        """
        SCENARIO:  Run the notebook summary if no post xco2 has been
        calculated.

        EXPECTED RESULTS:  no errors
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_ncfile=historical_ncfile,
                calculate_post_xco2=False
            )

            with XCO2Summary(
                self.merge_ncfile, historical_ncfile=historical_ncfile
            ) as p:
                p.run()

    def test_no_sami(self):
        """
        SCENARIO:  Run the notebook summary when there is no sami

        EXPECTED RESULTS:  no errors
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.alawai',
                'dp3_0027_20101207_20120206.txt',
                historical_ncfile=historical_ncfile
            )

            with XCO2Summary(
                self.merge_ncfile, historical_ncfile=historical_ncfile
            ) as p:
                p.run()

    def test_no_historical(self):
        """
        SCENARIO:  Run the notebook summary when there is historical data

        EXPECTED RESULTS:  no errors
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.alawai',
                'dp3_0027_20101207_20120206.txt'
            )

            with XCO2Summary(
                self.merge_ncfile, historical_ncfile=historical_ncfile
            ) as p:
                p.run()
