# standard library imports
import datetime as dt
import importlib.resources as ir

# local imports
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.trim_time_gui import TimeGUI
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(self, module, filename):

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the time GUI

        EXPECTED RESULT:  No errors
        """
        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with TimeGUI(self.reduced_path) as tgui:
            tgui.run()

        # In the netCDF file, the time series endpoints are
        #
        # [2013-11-05 15:00:00, 2013-11-05 20:17:00]
        #
        # So the GUI should be set at
        #
        # [2013-11-05 00:00:00, 2013-11-06 00:00:00]
        #
        # Moving the ending date picker to 2013-11-04 should be illegal because
        # it is before the start time.
        # The old value should be restored.
        tgui.ending_datetime_picker.value = dt.datetime(2013, 11, 4)
        self.assertEqual(
            tgui.ending_datetime_picker.value, dt.datetime(2013, 11, 6, 20, 19)
        )

        # Moving the beginning date picker to 2017-11-04 should be illegal
        # because it is after the ending time.
        # The old value should be restored.
        tgui.beginning_datetime_picker.value = dt.datetime(2017, 11, 4)
        self.assertEqual(
            tgui.beginning_datetime_picker.value, dt.datetime(2013, 11, 6, 15)
        )

        # Moving the ending date picker to 2013-11-06T16 should be ok.
        tgui.ending_datetime_picker.value = dt.datetime(2013, 11, 6, 16)
        self.assertEqual(tgui.gather_kwargs()['stop'], "2013-11-06T16:00:00")

        # Moving the hour to 9 should be illegal.  The old value
        # should be restored.
        tgui.ending_datetime_picker.value = dt.datetime(2013, 11, 6, 9)
        self.assertEqual(tgui.gather_kwargs()['stop'], "2013-11-06T16:00:00")

        # Moving the starting value to 2013-11-16 is past the end date,
        # should be illegal.  The result is that we push back to the old value.
        tgui.beginning_datetime_picker.value = dt.datetime(2013, 11, 16, 19)
        self.assertEqual(tgui.gather_kwargs()['start'], "2013-11-06T15:00:00")

    def test_gather_kwargs(self):
        """
        SCENARIO:  Test the time GUI's ability to produce keyword arguments for
        the starting time and the end time.

        EXPECTED RESULT:  The starting time and ending time are verified.
        """
        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with TimeGUI(self.reduced_path) as tgui:
            tgui.run()

            kwargs = tgui.gather_kwargs()

        expected = {
            'start': '2013-11-06T15:00:00',
            'stop': '2013-11-06T20:19:00',
        }
        self.assertDictEqual(kwargs, expected)
