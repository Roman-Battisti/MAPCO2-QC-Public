# standard library imports

# local imports
from xco2qc.post_xco2_gui import PostXCO2GUI
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO:  Default case, post xco2 is to be calculated

        EXPECTED RESULT:  The checkbox value is True.  The licor version is
        'v1'
        """
        with PostXCO2GUI() as gui:
            gui.run()
            self.assertFalse(gui.not_calculate_post_xco2_checkbox.value)
            self.assertEqual(gui.licor_version_radiobuttons.value, '820 v1')
