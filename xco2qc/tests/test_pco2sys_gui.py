# standard library imports

# local imports
import xco2qc.pco2sys_gui
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO:  Run the ipython notebook GUI

        EXPECTED RESULT:  No errors.  The region value is None because nothing
        was chosen.
        """

        with xco2qc.pco2sys_gui.PCO2SYS_Region_Gui(
            src_dir=self.reduced_path
        ) as gui:
            gui.run()

        kwargs = gui.gather_kwargs()

        self.assertIsNone(kwargs['region'])

    def test_choice(self):
        """
        SCENARIO:  Choose the 2nd radio button.

        EXPECTED RESULT:  The region value is 1 (0-indexing).
        """

        with xco2qc.pco2sys_gui.PCO2SYS_Region_Gui(
            src_dir=self.reduced_path
        ) as obj:
            obj.run()
            region = core.pco2sys_region_labels[1]
            obj.gui.children[0].children[1].value = region

        kwargs = obj.gather_kwargs()

        self.assertEqual(kwargs['region'], 1)
