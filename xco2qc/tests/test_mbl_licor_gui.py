# standard library imports
import datetime as dt
import importlib.resources as ir

# local imports
from xco2qc.mbl_licor_gui import MBLLicorGui
from . import test_core
from xco2qc.raw_text_conversion import RawTextToRawNC


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO: Run the ipython notebook GUI
        
        EXPECTED RESULT: No errors
        """
        
        with MBLLicorGui(dst_dir=self.trimmed_dir) as gui:
            gui.run()
        
        kwargs = gui.gather_kwargs()
        
        self.assertEqual(kwargs['mbl_correction'], 0)
        self.assertEqual(kwargs['licor_pressure_correction'], 0)
    
    def test_set_reasonable_defaults(self):
        """
        SCENARIO:  Run the ipython notebook GUI, set reasonable values

        EXPECTED RESULT:  No errors
        """
        
        with MBLLicorGui(dst_dir=self.trimmed_dir) as gui:
            gui.run()
        
        gui.mbl_licor_box.children[1].children[1].value = '1.4'
        gui.mbl_licor_box.children[2].children[1].value = '0.8'
        
        kwargs = gui.gather_kwargs()
        
        self.assertEqual(kwargs['mbl_correction'], 1.4)
        self.assertEqual(kwargs['licor_pressure_correction'], 0.8)


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
        
        with MBLLicorGui(dst_dir=self.trimmed_dir) as gui:
            gui.run()
            
        actual_mbl = gui.mbl_licor_box.children[1].children[1].value
        expected_mbl = '0.0'
        self.assertEqual(actual_mbl, expected_mbl)
        
        actual_licor = gui.mbl_licor_box.children[2].children[1].value
        expected_licor = '0.0'
        self.assertEqual(actual_licor, expected_licor)
        