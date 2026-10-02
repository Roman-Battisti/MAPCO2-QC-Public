# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets

# local imports
from xco2qc import core

COMMON_BORDER = 'solid 1px'
RADIO_COLUMN_WIDTH = '85%'


class PCO2SYS_Region_Gui(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to choose the region
    for the pco2sys calculation.

    Attributes
    ----------
    """

    def __init__(self, src_dir=None):
        super().__init__(src_dir=src_dir)
        self.gui = None

        self.gui_rows = []

        self.region_box = self.setup_region_mapping()
        layout = widgets.Layout(border=COMMON_BORDER)
        self.gui = widgets.VBox([self.region_box], layout=layout)

        display(self.gui)

    def run(self):
        pass

    def gather_kwargs(self):
        """
        Gather all the values currently set by the GUI.  They are to be passed
        into the merge program.

        """
        region = self.region_box.children[1].value
        value = core.pco2sys_region_labels.index(region)

        self.logger.info('The region "{region}" was chosen.')

        if value == 0:
            value = None

        kwargs = {'region': value}

        return kwargs

    def setup_region_mapping(self):
        """
        Setup a mapping from the region description to a number.
        """
        layout = widgets.Layout(border=COMMON_BORDER)

        label = widgets.Label(value='Region')
        radio = widgets.RadioButtons(
            options=core.pco2sys_region_labels,
            value=core.pco2sys_region_labels[0]
        )
        layout = widgets.Layout(
            width=RADIO_COLUMN_WIDTH, border=COMMON_BORDER
        )
        region_box = widgets.VBox([label, radio], layout=layout)

        return region_box
