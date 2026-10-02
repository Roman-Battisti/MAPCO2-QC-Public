# standard library imports
import collections
import pathlib
import tempfile
import unittest

# 3rd party library imports
import yaml

# local imports
from xco2qc.qc import KEYWORDS
from xco2qc.qc_gui import (
    QCGui, APON_APOFF_MIN_PRESSURE_DIFFERENCE,
    EPON_EPOFF_MIN_PRESSURE_DIFFERENCE, SPON_SPOFF_MIN_PRESSURE_DIFFERENCE
)
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO:  Run the ipython notebook GUI

        EXPECTED RESULT:  No errors
        """

        with QCGui() as qc:
            qc.run()
            self.assertIsNotNone(qc.gui)

    def test_epon_epoff_min_slider_change_too_close_to_max_slider(self):
        """
        SCENARIO:  The EPON/EPOFF pressure difference sliders are set to
        conflicting values.

        EXPECTED RESULT:  The callbacks reset the values so they do not
        conflict.
        """
        with QCGui() as qc:
            qc.run()

            Change = collections.namedtuple('Change', ['new'])

            # the min slider is made consistent with the max slider value
            c = Change(new=qc.epon_epoff_max_slider.value)
            qc.validate_epon_epoff_min_slider_change(c)
            self.assertTrue(
                qc.epon_epoff_min_slider.value < qc.epon_epoff_max_slider.value
            )

            # the max slider is made consistent with the min slider value
            c = Change(new=qc.epon_epoff_min_slider.value)
            qc.validate_epon_epoff_max_slider_change(c)
            self.assertTrue(
                qc.epon_epoff_max_slider.value > qc.epon_epoff_min_slider.value
            )

    def test_initial_span_cal(self):
        """
        Scenario:  the config file is found in the current directory

        Expected result:  no errors
        """
        root_dir = tempfile.TemporaryDirectory()
        root_path = pathlib.Path(root_dir.name)
        new_dst_dir = tempfile.TemporaryDirectory(dir=root_dir.name)
        new_dst_path = pathlib.Path(new_dst_dir.name)

        # change a config file setting from the default value so that we
        # can verify it, then write it into the source directory
        self.config['QC']['initial_span_cal'] = 405

        new_config_file = root_path / 'config.yml'
        with new_config_file.open('wt') as f:
            yaml.dump(self.config, f)

        with test_core.chdir(new_dst_path):

            # now run the conversion, the new config file should be read
            with QCGui(dst_dir=new_dst_path) as qc:
                qc.run()

                self.assertEqual(qc.config['QC']['initial_span_cal'], 405)

    def test_apon_apoff_min_slider_change_too_close_to_max_slider(self):
        """
        SCENARIO:  The APON/APOFF pressure difference sliders are set to
        conflicting values.

        EXPECTED RESULT:  The callbacks reset the values so they do not
        conflict.
        """
        with QCGui() as qc:
            qc.run()

            Change = collections.namedtuple('Change', ['new'])

            # the min slider is made consistent with the max slider value
            c = Change(new=qc.apon_apoff_max_slider.value)
            qc.validate_apon_apoff_min_slider_change(c)
            self.assertTrue(
                qc.apon_apoff_min_slider.value < qc.apon_apoff_max_slider.value
            )

            # the max slider is made consistent with the min slider value
            c = Change(new=qc.apon_apoff_min_slider.value)
            qc.validate_apon_apoff_max_slider_change(c)
            self.assertTrue(
                qc.apon_apoff_max_slider.value > qc.apon_apoff_min_slider.value
            )

    def test_apon_apoff_min_slider_change_ok(self):
        """
        SCENARIO:  The APON/APOFF min slider is changed to an ok value.

        EXPECTED RESULT:  The callback does not complain, the value is verified
        """
        with QCGui() as qc:
            qc.run()

            expected = qc.apon_apoff_min_slider.value - APON_APOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501
            qc.apon_apoff_min_slider.value = expected
            actual = qc.apon_apoff_min_slider.value

            self.assertEqual(actual, expected)

    def test_apon_apoff_max_slider_change_ok(self):
        """
        SCENARIO:  The APON/APOFF max slider is changed to an ok value.

        EXPECTED RESULT:  The callback does not complain, the value is verified
        """
        with QCGui() as qc:
            qc.run()

            expected = qc.apon_apoff_max_slider.value + APON_APOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501
            qc.apon_apoff_max_slider.value = expected
            actual = qc.apon_apoff_max_slider.value

            self.assertEqual(actual, expected)

    def test_epon_epoff_min_slider_change_ok(self):
        """
        SCENARIO:  The EPON/EPOFF min slider is changed to an ok value.

        EXPECTED RESULT:  The callback does not complain, the value is verified
        """
        with QCGui() as qc:
            qc.run()

            expected = qc.epon_epoff_min_slider.value - EPON_EPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501
            qc.epon_epoff_min_slider.value = expected
            actual = qc.epon_epoff_min_slider.value

            self.assertEqual(actual, expected)

    def test_epon_epoff_max_slider_change_ok(self):
        """
        SCENARIO:  The EPON/EPOFF max slider is changed to an ok value.

        EXPECTED RESULT:  The callback does not complain, the value is verified
        """
        with QCGui() as qc:
            qc.run()

            expected = qc.epon_epoff_max_slider.value + EPON_EPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501
            qc.epon_epoff_max_slider.value = expected
            actual = qc.epon_epoff_max_slider.value

            self.assertEqual(actual, expected)

    def test_spon_spoff_min_slider_change_ok(self):
        """
        SCENARIO:  The SPON/SPOFF min slider is changed to an ok value.

        EXPECTED RESULT:  The callback does not complain.
        """
        with QCGui() as qc:
            qc.run()

            new_value = qc.spon_spoff_min_slider.value - SPON_SPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501
            qc.spon_spoff_min_slider.value = new_value
            self.assertEqual(qc.spon_spoff_min_slider.value, new_value)

    def test_spon_spoff_max_slider_change_ok(self):
        """
        SCENARIO:  The SPON/SPOFF max slider is changed to an ok value.

        EXPECTED RESULT:  The callback does not complain.
        """
        with QCGui() as qc:
            qc.run()

            new_value = qc.spon_spoff_max_slider.value + SPON_SPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501
            qc.spon_spoff_max_slider.value = new_value
            self.assertEqual(qc.spon_spoff_max_slider.value, new_value)

    def test_spon_spoff_min_slider_change_too_close_to_max_slider(self):
        """
        SCENARIO:  The SPON/SPOFF pressure difference sliders are set to
        conflicting values.

        EXPECTED RESULT:  The callbacks reset the values so they do not
        conflict.
        """
        with QCGui() as qc:
            qc.run()

            Change = collections.namedtuple('Change', ['new'])

            # the min slider is made consistent with the max slider value
            c = Change(new=qc.spon_spoff_max_slider.value)
            qc.validate_spon_spoff_min_slider_change(c)
            self.assertTrue(
                qc.spon_spoff_min_slider.value < qc.spon_spoff_max_slider.value
            )

            # the max slider is made consistent with the min slider value
            c = Change(new=qc.spon_spoff_min_slider.value)
            qc.validate_spon_spoff_max_slider_change(c)
            self.assertTrue(
                qc.spon_spoff_max_slider.value > qc.spon_spoff_min_slider.value
            )

    @unittest.skip('linked via javascript, not python')
    def test_apon_apoff_min_text_change(self):
        """
        SCENARIO:  The APON/APOFF pressure difference min text label is
        changed.

        EXPECTED RESULT:  The minimum slider value should change to match.
        """
        with QCGui() as qc:
            qc.run()

            Change = collections.namedtuple('Change', ['new'])

            expected = qc.apon_apoff['min_text'].value * 0.9
            qc.apon_apoff['min_text'].value = expected
            c = Change(new=expected)
            qc.validate_apon_apoff_min_slider_change(c)
            self.assertEqual(
                qc.apon_apoff_min_slider.value, qc.apon_apoff['min_text'].value
            )

    @unittest.skip('linked via javascript, not python')
    def test_apon_apoff_max_text_change(self):
        """
        SCENARIO:  The APON/APOFF pressure difference max text label is
        changed.

        EXPECTED RESULT:  The maximum slider value should change to match.
        """
        with QCGui() as qc:
            qc.run()

            Change = collections.namedtuple('Change', ['new'])

            expected = qc.apon_apoff['max_text'].value * 1.1
            qc.apon_apoff['max_text'].value = expected
            c = Change(new=expected)
            qc.validate_apon_apoff_max_slider_change(c)
            self.assertEqual(
                qc.apon_apoff_max_slider.value, qc.apon_apoff['max_text'].value
            )

    def test_spon_spoff_min_text_change_too_close_to_max_slider(self):
        """
        SCENARIO:  The SPON/SPOFF pressure difference text is set to
        conflicting values.

        EXPECTED RESULT:  The callbacks reset the values so they do not
        conflict.
        """
        return
        with QCGui() as qc:
            qc.run()

            Change = collections.namedtuple('Change', ['new'])

            Change(new=qc.spon_spoff_max_slider.value)
            qc.spon_spoff['min_text'].value = qc.spon_spoff_max_slider.value
            self.assertTrue(
                qc.spon_spoff_min_slider.value < qc.spon_spoff_max_slider.value
            )
            self.assertTrue(
                qc.spon_spoff['min_text'].value < qc.spon_spoff_max_slider.value  # noqa : E501
            )

    def test_span_cal_change_too_small(self):
        """
        SCENARIO:  The span cal slider is changed to something out of range

        EXPECTED RESULT:  The callback resets the value to either the min or
        the max, whichever is closer.
        """
        with QCGui() as qc:
            qc.run()

            Change = collections.namedtuple('Change', ['new'])

            # check for too small
            c = Change(new=qc.initial_span_cal_slider.min - 1)
            qc.validate_initial_span_cal_slider_value(c)
            self.assertEqual(
                qc.initial_span_cal_slider.value,
                qc.initial_span_cal_slider.min
            )

            # check for too large
            c = Change(new=qc.initial_span_cal_slider.max + 1)
            qc.validate_initial_span_cal_slider_value(c)
            self.assertEqual(
                qc.initial_span_cal_slider.value,
                qc.initial_span_cal_slider.max
            )

    def test_parameters(self):
        """
        SCENARIO:  Attempt to retrieve the settings from the GUI.

        EXPECTED RESULT:  No errors
        """

        with QCGui() as qc:
            qc.run()

            kwargs = qc.gather_kwargs()

        self.assertTrue(isinstance(kwargs, dict))

        for keyword in KEYWORDS:
            self.assertIn(keyword, kwargs)

    def test_spike_detection_parameter(self):
        """
        SCENARIO:  Attempt to retrieve the settings from the GUI.  Spike
        detection is a new GUI control.

        EXPECTED RESULT:  spike_detection is a boolean value
        """

        with QCGui() as qc:
            qc.run()

            kwargs = qc.gather_kwargs()

        self.assertTrue(isinstance(kwargs, dict))

        self.assertIn(kwargs['spike_detection'], [False, True])
