# standard library imports
import importlib.resources as ir

# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets
import yaml

# local imports
from xco2qc import core


class DeploymentGUI(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to set the deployment
    number.  While it may be possible to parse this from the filename, that's
    a brittle workflow.

    Attributes
    ----------
    gui : ipywidgets.VBox
        The GUI as presented by the jupyter notebook.
    site_id_control, deployment_number_control : widgets
        The individual GUI controls for deployment number.
    """

    def __init__(self):
        super().__init__()

        with ir.as_file(ir.files('xco2qc.core.data').joinpath('sites.yml')) as sites_file:
            with sites_file.open() as f:
                sites = yaml.safe_load(f)

        # restrict to the primary identifiers, i.e. laparguera and enrique are
        # the same site, so just use laparguera
        primary_keys = [
            key for key, value in sites.items() if value['primary']
        ]
        self.site_ids = primary_keys

    def run(self):

        self._gui_rows = []

        self.setup_deployment_number()

        # Setup all the rows of the GUI, arranged as a single column.
        self.gui = widgets.VBox(self._gui_rows)

        display(self.gui)

    def setup_deployment_number(self):
        """
        Present an input box for entering the deployment number.
        """

        self.deployment_number_control = widgets.BoundedIntText(
            value=1, description='Deployment Number', min=1
        )

        row = widgets.HBox([self.deployment_number_control])

        self._gui_rows.append(row)

    def gather_kwargs(self):
        """
        Gather all the values currently set by the GUI.
        """
        return {
            'deployment_number': self.deployment_number_control.value,
        }
