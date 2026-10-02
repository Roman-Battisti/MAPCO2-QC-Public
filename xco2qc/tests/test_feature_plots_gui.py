# standard library imports
import importlib.resources as ir
import shutil

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.feature_plots_gui import FeaturePlotsGUI
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(self, module, filename, historical_ncfile=None):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
                p.run()

            if historical_ncfile is not None:
                dest = self.raw_path / core.HISTORICAL_NCFILE
                shutil.copyfile(historical_ncfile, dest)

            with XCO2Reduce(self.raw_path, self.reduced_path) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the feature plots GUI.

        EXPECTED RESULT:  Without doing anything, the file type selectors
        are populated for us.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh', 'dp09_0014_20131105_20140802.met.txt'
        )

        expected = [
            'APOFF', 'APON', 'EPOFF', 'EPON', 'SPON', 'SPOFF', 'SPOSTCAL',
            'ZPON', 'ZPOFF', 'ZPOSTCAL', 'MET', 'MAPCO2', 'SAMI'
        ]
        expected = set(expected)

        path = self.reduced_path

        with FeaturePlotsGUI(path) as gui:
            gui.run()

            for rownum in range(gui.nrows):
                for feature_num in range(2):
                    feature_box = gui.window[rownum].children[feature_num]
                    filetype_box = feature_box.children[0]
                    actual = set(filetype_box.options)

                    self.assertEqual(actual, expected)

                    # what feature has been chosen?
                    feature_widget = feature_box.children[1]
                    # we should have more than one now
                    self.assertTrue(len(feature_widget.options) > 1)

            # and finally, launch the plot
            gui.plot_features(None)

    def test_set_epoff_file_type(self):
        """
        SCENARIO:  Run the feature plots GUI.  Set the 1st file type to
        'EPOFF'.

        EXPECTED RESULT:  The 1st feature list includes EPOFF data variables
        except for time.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh', 'dp09_0014_20131105_20140802.met.txt'
        )

        path = self.reduced_path

        with FeaturePlotsGUI(path) as gui:
            gui.run()

            feature_box = gui.window[0].children[0]
            filetype_box = feature_box.children[0]
            filetype_box.value = 'EPOFF'

        feature_type_selector = feature_box.children[1]

        actual = set(feature_type_selector.options)

        expected = [
            'dissolved_oxygen', 'pressure', 'rh_stddev',
            'rh_temp_stddev', 'temperature',
            'o2', 'rh_temp', 'rh', 'xco2_wet', 'xco2_wet_stddev',
            'raw_reference', 'raw_sample', 'xco2_dry', 'post_xco2_dry',
            'post_xco2_wet', 'post_xco2_wet_v1', 'post_xco2_wet_v2',
            'vapor_pressure'
        ]
        expected = set(expected)

        self.assertEqual(actual, expected)

    def test_historical_set_file_type(self):
        """
        SCENARIO:  Run the feature plots GUI.  Set the 2nd file type to
        'historical'.

        EXPECTED RESULT:  The 2nd feature list includes EPOFF data variables,
        but not coordinate variables.
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                historical_ncfile=historical_ncfile
            )

        path = self.reduced_path

        with FeaturePlotsGUI(path) as gui:
            gui.run()

            feature_box = gui.window[0].children[0]
            filetype_box = feature_box.children[0]
            filetype_box.value = 'historical'

        feature_type_selector = feature_box.children[1]

        actual = set(feature_type_selector.options)

        expected = [
            'SSS', 'SST', 'pCO2_air', 'pCO2_sw', 'pH_sw', 'xCO2_air',
            'latitude', 'longitude'
        ]
        expected = set(expected)

        self.assertEqual(actual, expected)
