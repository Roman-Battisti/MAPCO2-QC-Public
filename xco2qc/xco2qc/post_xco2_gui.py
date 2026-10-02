# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets

# local imports
from xco2qc import core


class PostXCO2GUI(core.MapCO2core):
    """
    Create a GUI controls used by the jupyter notebook to control whether
    or not post xco2 will be calculated.  If it is calculated, the user
    may also choose the licor version.

    Attributes
    ----------
    gui_rows : list
        Each list item is a widget that controls some aspect of the metadata.
    gui : ipywidgets.VBox
        The metadata GUI
    calculate_post_xco2_control : ipywidgets.Text
        The value is either True or False
    licor_version_radiobuttons : ipywidgets.RadioButtons
        The value is either 'v1' or 'v2'.
    """

    def __init__(self):
        super().__init__()

    def run(self):

        self.gui_rows = []

        self.setup_calculate_post_xco2_controls()

        # Setup all the rows of the GUI, arranged as a single column.
        self.gui = widgets.VBox(self.gui_rows)

        display(self.gui)

    def setup_calculate_post_xco2_controls(self):
        """
        Setup a checkbox for whether or not to do post xco2.
        """
        label_msg = (
            'Check this box only if you do NOT wish to calculate post xCO2'
        )
        label = widgets.Label(label_msg)
        self.not_calculate_post_xco2_checkbox = widgets.Checkbox(
            value=False, description=""
        )

        layout = widgets.Layout(border='solid 1px')
        items = [label, self.not_calculate_post_xco2_checkbox]
        vbox = widgets.VBox(items, layout=layout)
        row = widgets.HBox([vbox])
        self.gui_rows.append(row)

        label_msg = "Licor Version"
        label = widgets.Label(label_msg)
        self.licor_version_radiobuttons = widgets.RadioButtons(
            options=['820 v1', '820 v2', '830 v1'], value='820 v1'
        )

        layout = widgets.Layout(border='solid 1px')
        items = [label, self.licor_version_radiobuttons]
        vbox = widgets.VBox(items, layout=layout)
        row = widgets.HBox([vbox])
        self.gui_rows.append(row)
    
    def gather_kwargs(self):
        """
        Gather all the values currently set by the GUI.  They are to be passed
        into the QC program.
        """
        
        d = {
             "calculate_post_xco2": not self.not_calculate_post_xco2_checkbox.value,
             "licor_version": self.licor_version_radiobuttons.value,
            }
        
        return d