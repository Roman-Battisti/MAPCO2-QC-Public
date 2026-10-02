"""
Tests for setting the site ID and deployment number.
"""
# standard library imports

# local imports
from xco2qc.deployment_gui import DeploymentGUI
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO:  Set the deployment id to 12

        EXPECTED RESULT:  No errors.
        """

        with DeploymentGUI() as gui:
            gui.run()

            gui.deployment_number_control.value = '12'

            kwargs = gui.gather_kwargs()

        self.assertEqual(kwargs['deployment_number'], 12)
