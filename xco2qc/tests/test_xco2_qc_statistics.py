# standard library imports
import importlib.resources as ir

# local imports
from xco2qc.qc_statistics import XCO2QCStatistics
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, num_points_eachside=1,
        merge=True, calculate_post_xco2=True
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
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

            with QCChecker(
                self.reduced_path,
                num_points_eachside=num_points_eachside
            ) as qc:
                qc.run()

            if merge:
                with XCO2Merge(self.reduced_path, self.merge_ncfile) as p:
                    p.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the display of QC statistics

        EXPECTED RESULTS:  no errors, the length of the time series is
        verified, the number of columns in the dataframe is four, for all the
        xCO2 variables.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with XCO2QCStatistics(ncfiles=self.merge_ncfile) as p:
            p.run()

            self.assertEqual(p.tslen, 6)
            self.assertEqual(len(p.df.columns), 4)

    def test_inputs_are_list_of_dicts(self):
        """
        SCENARIO:  Run the display of QC statistics.  The input argument is
        a dictionary

        EXPECTED RESULTS:  no errors, the length of the time series is
        verified, and the column names are suitably shortened
        """

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        lst = [
            {
                'ncfile': self.reduced_path / core.licor.APOFF_NCFILE,
                'variable': 'xco2_wet_qc',
            },
            {
                'ncfile': self.reduced_path / core.licor.APON_NCFILE,
                'variable': 'xco2_dry_qc',
            },
        ]

        with XCO2QCStatistics(ncfiles=lst) as p:
            p.run()

            actual = list(p.df.columns)
            expected = ['AIR PUMP OFF xco2_wet_qc', 'AIR PUMP ON xco2_dry_qc']
            self.assertEqual(actual, expected)

    def test_inputs_are_directory(self):
        """
        SCENARIO:  Run the display of QC statistics when given a directory.

        EXPECTED RESULTS:  There are 13 variables to look at, including a sami
        ph variable, so the dataframe has 13 columns.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with XCO2QCStatistics(ncfiles=self.reduced_path) as p:
            p.run()

            self.assertEqual(p.df.shape[1], 13)

    def test_inputs_are_directory_but_no_post_xco2(self):
        """
        SCENARIO:  Run the display of QC statistics when given a directory.
        No post xco2 is calculated.

        EXPECTED RESULTS:  There are 13 variables to look at, including a sami
        ph variable, so the dataframe has 13 columns.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            merge=False,
            calculate_post_xco2=False
        )

        with XCO2QCStatistics(ncfiles=self.reduced_path) as p:
            p.run()

            self.assertEqual(p.df.shape[1], 13)

    def test_inputs_are_directory_but_no_sami(self):
        """
        SCENARIO:  Run the display of QC statistics when given a directory.

        EXPECTED RESULTS:  There are 12 variables to look at, including a sami
        ph variable, so the dataframe has 12 columns.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp3_0027_20101207_20120206.txt'
        )

        with XCO2QCStatistics(ncfiles=self.reduced_path) as p:
            p.run()

            self.assertEqual(p.df.shape[1], 12)
