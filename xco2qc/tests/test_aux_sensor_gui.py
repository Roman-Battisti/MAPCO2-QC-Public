# standard library imports
import datetime as dt
import importlib.resources as ir

# local imports
import xco2qc.aux_sensor_gui
from . import test_core
from xco2qc.raw_text_conversion import RawTextToRawNC


class TestSuite(test_core.TestSuite):

    def test_ignore(self):
        """
        SCENARIO:  Run the ipython notebook GUI, set the skip checkbox on.
                   This will output a False kwargs output, since a checked
                   checkbox is true but we don't want to process Aux sensors.

        EXPECTED RESULT:  The skip keyword is set.
        """
        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()
            gui.skip_checkbox.children[1].value = True

        kwargs = gui.gather_kwargs()

        self.assertFalse(kwargs['sbe16_mapping'])

    def test_smoke(self):
        """
        SCENARIO:  Run the ipython notebook GUI

        EXPECTED RESULT:  No errors
        """

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

        kwargs = gui.gather_kwargs()

        self.assertTrue(kwargs['sbe16_mapping'])

        self.assertEqual(kwargs['chl_channel'], 0)
        self.assertEqual(kwargs['ntu_channel'], 1)
        self.assertEqual(kwargs['o2_channel'], 2)
        self.assertEqual(kwargs['o2_temp_channel'], 3)

        self.assertIsNone(kwargs['instrument_time_split'])

    def test_set_reasonable_defaults(self):
        """
        SCENARIO:  Run the ipython notebook GUI, set reasonable values

        EXPECTED RESULT:  No errors
        """

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

            # chl scale factor box is the 2nd child
            # the input box is the 2nd child
            # o2_temp box is 4th
            # label and radio are o2_temp box children
            gui.calibration_box.children[1].children[1].value = '10'
            gui.calibration_box.children[2].children[1].value = '0.06'
            gui.calibration_box.children[3].children[1].value = '5'
            gui.calibration_box.children[4].children[1].value = '0.06'
            gui.calibration_box.children[5].children[1].value = True
            gui.calibration_box.children[6].children[1].value = '0'

        kwargs = gui.gather_kwargs()

        self.assertTrue(kwargs['sbe16_mapping'])

        self.assertEqual(kwargs['chl_channel'], 0)
        self.assertEqual(kwargs['ntu_channel'], 1)
        self.assertEqual(kwargs['o2_channel'], 2)
        self.assertEqual(kwargs['o2_temp_channel'], 3)

        self.assertEqual(kwargs['chl_scale_factor'], [10])
        self.assertEqual(kwargs['chl_dark_count'], [0.06])
        self.assertEqual(kwargs['ntu_scale_factor'], [5])
        self.assertEqual(kwargs['ntu_dark_count'], [0.06])
        self.assertEqual(kwargs['chl_global_conversion'], True)
        self.assertEqual(kwargs['o2_salinity_setting'], [0])

    def test_calibration_arrays_have_different_lengths(self):
        """
        SCENARIO:  Run the ipython notebook GUI, set an instrument split
        when this is not indicated by the calbox numbers, i.e. the dark
        count and scale factors indicate a single instrument regime rather than
        two.

        EXPECTED RESULT:  RuntimeError
        """

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

            # chl scale factor box is the 2nd child
            # the input box is the 2nd child
            # o2_temp box is 4th
            # label and radio are o2_temp box children
            gui.calibration_box.children[1].children[1].value = '10'
            gui.calibration_box.children[2].children[1].value = '0.06 0.05'
            gui.calibration_box.children[3].children[1].value = '5'
            gui.calibration_box.children[4].children[1].value = '0.06'
            gui.calibration_box.children[5].children[1].value = True
            gui.calibration_box.children[6].children[1].value = '0'

        with self.assertRaises(RuntimeError):
            gui.gather_kwargs()

    def test_instrument_time_split_but_no_calibration_arrays(self):
        """
        SCENARIO:  Run the ipython notebook GUI, set an instrument split
        when this is not indicated by the calbox numbers, i.e. the dark
        count and scale factors indicate a single instrument regime rather than
        two.

        EXPECTED RESULT:  RuntimeError
        """

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

            # chl scale factor box is the 2nd child
            # the input box is the 2nd child
            # o2_temp box is 4th
            # label and radio are o2_temp box children
            gui.calibration_box.children[1].children[1].value = '10'
            gui.calibration_box.children[2].children[1].value = '0.06'
            gui.calibration_box.children[3].children[1].value = '5'
            gui.calibration_box.children[4].children[1].value = '0.06'
            gui.calibration_box.children[5].children[1].value = True
            gui.calibration_box.children[6].children[1].value = '0'
            gui.calibration_box.children[7].children[1].value = dt.datetime(2020, 1, 1)  # noqa : E501

        with self.assertRaises(RuntimeError):
            gui.gather_kwargs()

    def test_set_array(self):
        """
        SCENARIO:  Run the ipython notebook GUI, set reasonable array values

        EXPECTED RESULT:  No errors
        """

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

            # chl scale factor box is the 2nd child
            # the input box is the 2nd child
            # o2_temp box is 4th
            # label and radio are o2_temp box children
            gui.calibration_box.children[1].children[1].value = '10 9'
            gui.calibration_box.children[2].children[1].value = '0.06, 0.05'
            gui.calibration_box.children[3].children[1].value = '5;4'
            gui.calibration_box.children[4].children[1].value = '0.06,0.05'
            gui.calibration_box.children[5].children[1].value = True
            gui.calibration_box.children[6].children[1].value = '0  0'
            gui.calibration_box.children[7].children[1].value = dt.datetime(2020, 1, 1, 0, 0)  # noqa : E501

        kwargs = gui.gather_kwargs()

        self.assertTrue(kwargs['sbe16_mapping'])

        self.assertEqual(kwargs['chl_channel'], 0)
        self.assertEqual(kwargs['ntu_channel'], 1)
        self.assertEqual(kwargs['o2_channel'], 2)
        self.assertEqual(kwargs['o2_temp_channel'], 3)

        self.assertEqual(kwargs['chl_scale_factor'], [10, 9])
        self.assertEqual(kwargs['chl_dark_count'], [0.06, 0.05])
        self.assertEqual(kwargs['ntu_scale_factor'], [5, 4])
        self.assertEqual(kwargs['ntu_dark_count'], [0.06, 0.05])
        self.assertEqual(kwargs['chl_global_conversion'], True)
        self.assertEqual(kwargs['o2_salinity_setting'], [0, 0])
        self.assertEqual(
            kwargs['instrument_time_split'], dt.datetime(2020, 1, 1, 0, 0)
        )

    def test_set_o2_temp_channel_to_6(self):
        """
        SCENARIO:  Run the ipython notebook GUI, set the o2 temp channel to 6.

        EXPECTED RESULT:  No errors
        """

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

            # radio vbox is 2nd child.
            # o2_temp box is 4th
            # label and radio are o2_temp box children
            gui.mapping_box.children[1].children[3].children[1].value = 5

        kwargs = gui.gather_kwargs()

        self.assertTrue(kwargs['sbe16_mapping'])

        self.assertEqual(kwargs['chl_channel'], 0)
        self.assertEqual(kwargs['ntu_channel'], 1)
        self.assertEqual(kwargs['o2_channel'], 2)
        self.assertEqual(kwargs['o2_temp_channel'], 5)
    
    def test_handle_list(self):
        """
        SCENARIO: handle list of CHL/NTU parameters
        
        EXPECTED RESULT: No errors
        """
        
        test = [1, 2, 3]
        expected = "1, 2, 3"
        
        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            result = gui._handle_list(test)
        
        self.assertEqual(result, expected)


class TestSuiteConfig(test_core.TestSuite):
    """
    Test the propagation of the config file when it's in the source directory
    """

    def _processing_pipeline(
        self, module, filename, deployment_number=None, verbosity='critical',
        historical_file=None
    ):

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity,
                deployment_number=deployment_number
            ) as p0:
                p0.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the ipython notebook GUI, have a config file located
        in the output directory.  config file has a split time.

        EXPECTED RESULT:  The split time is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cheeca.dp04',
            'mapco2_cheeca_dp04_0107_20150325_20160504.txt'
        )

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

            actual = gui.calibration_box.children[7].children[1].value

        expected = dt.datetime(2015, 7, 17, 16)  # noqa : E501
        self.assertEqual(actual, expected)
