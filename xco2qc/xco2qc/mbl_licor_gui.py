import re

# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets
import numpy as np

# local imports
from xco2qc import core

ADJUSTMENT_COLUMN_WIDTH = '40%'
ADJUSTMENT_TEXT_WIDTH = '50%'
COMMON_BORDER = 'solid 1px'


class MBLLicorGui(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to map the auxilliary
    sensor data.

    Attributes
    ----------
    """

    def __init__(self, dst_dir=None):
        super().__init__(dst_dir=dst_dir)
        self.gui = None

        self.gui_rows = []

        self.mbl_licor_box = self.setup_mbl_licorpress()

        layout = widgets.Layout(border=COMMON_BORDER)

        self.gui = widgets.VBox([self.mbl_licor_box], layout=layout)

        display(self.gui)

    def run(self):
        pass

    def gather_kwargs(self):
        """
        Gather all the values currently set by the GUI.  They are to be passed
        into the QC program.
        """
        mlbox = self.mbl_licor_box
        d = {
             'mbl_correction': float(mlbox.children[1].children[1].value),
             'licor_pressure_correction': float(mlbox.children[2].children[1].value),
            }
        
        return d
        
        
    def setup_mbl_licorpress(self):
        """
        Setup adjustment factors for MBL and Licor Pressure
        """
        
        # adapted from aux_sensor_gui.py line 159
        text = '<h3>MBL and Licor Pressure Adjustments</h3>'
        layout = widgets.Layout(border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)
        
        layout = widgets.Layout(width=ADJUSTMENT_TEXT_WIDTH, border=COMMON_BORDER)
        
        label = widgets.Label(value='MBL Correction', layout=layout)
        text = widgets.Text(value=str(self.config['adjustments'].get('mbl_correction', 0.0)))
        mbl_correction_box = widgets.HBox([label, text])
        
        label = widgets.Label(value='Licor Pressure Correction', layout=layout)
        text = widgets.Text(value=str(self.config['adjustments'].get('licor_pressure_correction', 0.0)))
        licor_press_box = widgets.HBox([label, text])
        
        items = [html, mbl_correction_box, licor_press_box]
        layout = widgets.Layout(width=ADJUSTMENT_COLUMN_WIDTH, border=COMMON_BORDER)
        box = widgets.VBox(items, layout=layout)
        
        return box