import re

# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets
import numpy as np

# local imports
from xco2qc import core

VOLTAGE_CHANNEL_WIDTH = '60%'
RADIO_COLUMN_WIDTH = '15%'

CALIBRATION_COLUMN_WIDTH = '40%'
CALIBRATION_TEXT_WIDTH = '50%'
COMMON_BORDER = 'solid 1px'


class AuxSensorGui(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to map the auxilliary
    sensor data.

    Attributes
    ----------
    """

    def __init__(self, src_dir=None, dst_dir=None):
        super().__init__(src_dir=src_dir, dst_dir=dst_dir)
        self.gui = None

        self.gui_rows = []

        self.mapping_box = self.setup_channel_mapping()
        self.calibration_box = self.setup_chl_ntu_calibration()
        self.skip_checkbox = self.setup_skip_checkbox()

        layout = widgets.Layout(border=COMMON_BORDER)

        row1 = widgets.HBox([self.mapping_box, self.calibration_box])
        row2 = widgets.HBox([self.skip_checkbox])

        self.gui = widgets.VBox([row1, row2], layout=layout)

        display(self.gui)

    def run(self):
        pass

    def gather_kwargs(self):
        """
        Gather all the values currently set by the GUI.  They are to be passed
        into the QC program.

        The chl global conversion control returns a boolean.  We need to turn
        it into 1 or 0.
        """
        mapbox = self.mapping_box
        calbox = self.calibration_box

        # This one is boolean, we need to turn it into a numeric value.

        d = {
            'chl_channel': mapbox.children[1].children[0].children[1].value,
            'ntu_channel': mapbox.children[1].children[1].children[1].value,
            'o2_channel': mapbox.children[1].children[2].children[1].value,
            'o2_temp_channel': mapbox.children[1].children[3].children[1].value,  # noqa : E501
        }

        calbox_items = [
            'chl_scale_factor', 'chl_dark_count', 'ntu_scale_factor',
            'ntu_dark_count', 'o2_salinity_setting'
        ]

        # These are space-delimited char arrays
        for key, idx in zip(calbox_items, [1, 2, 3, 4, 6]):
            value = [
                float(item)
                for item in self._str_to_list(calbox.children[idx].children[1].value)  # calbox.children[idx].children[1].value.split(' ')
            ]
            d.update({key: value})

        d.update({
            'chl_global_conversion': int(calbox.children[5].children[1].value)
        })

        d.update({
            'sbe16_mapping': not self.skip_checkbox.children[1].value
        })

        d.update({
            'instrument_time_split': calbox.children[7].children[1].value
        })

        # If there was a time split, then the user had to supply arrays of
        # items for the dark count / scale factor widgets.
        calbox_item_length = np.array([len(d[item]) for item in calbox_items])
        calbox_integrity = np.all(calbox_item_length == calbox_item_length[0])

        if not calbox_integrity:
            msg = (
                'The scale factor / dark count / O2 salinity settings must '
                'all have the same length.'
            )
            raise RuntimeError(msg)

        if (
            d['instrument_time_split'] is not None
            and calbox_integrity
            and len(d['chl_dark_count']) == 1
        ):
            msg = (
                'Do not supply an instrument split time if not all of the '
                'dark count, scale factor, and O2/salinity settings have '
                'more than one item.'
            )
            raise RuntimeError(msg)

        return d

    def setup_skip_checkbox(self):
        """
        Setup a checkbox for whether or not to skip SBE16 channel processing
        """
        label_msg = (
            'Check this box only if you do NOT wish to process SBE16 '
            'voltage channels.'
        )
        label = widgets.Label(label_msg)
        checkbox = widgets.Checkbox(value=False, description="")

        layout = widgets.Layout(border='solid 1px')
        items = [label, checkbox]
        vbox = widgets.VBox(items, layout=layout)

        return vbox
    
    def _handle_list(self, l: list):
        """
        CHL/NTU/O2 values can come in as lists. So as not to impact
        other code using the config file, convert list to string separated by ,.
        """
        if type(l) in [str, int, float]:
            return l
        return ", ".join([str(i) for i in l])
    
    def _str_to_list(self, s: str):
        """
        Convert string of CHL/NTU/O2 paramters to list based on possible separators
        """
        
        pattern = re.compile(r"[,\s\t;]+")
        return re.split(pattern, s)
    
    def setup_chl_ntu_calibration(self):
        """
        Setup calibration factors for CHL and NTU
        """
        text = '<h3>CHL/NTU Calibration</h3>'
        layout = widgets.Layout(border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        layout = widgets.Layout(
            width=CALIBRATION_TEXT_WIDTH, border=COMMON_BORDER
        )

        label = widgets.Label(value='Chl Scale Factor', layout=layout)
        text = widgets.Text(value=str(self._handle_list(self.config['QC']['chl_scale_factor'])))
        chl_scale_factor_box = widgets.HBox([label, text])

        label = widgets.Label(value='Chl Dark Count', layout=layout)
        text = widgets.Text(value=str(self._handle_list(self.config['QC']['chl_dark_count'])))
        chl_dark_count_box = widgets.HBox([label, text])

        label = widgets.Label(value='NTU Scale Factor', layout=layout)
        text = widgets.Text(value=str(self._handle_list(self.config['QC']['ntu_scale_factor'])))
        ntu_scale_factor_box = widgets.HBox([label, text])

        label = widgets.Label(value='NTU Dark Count', layout=layout)
        text = widgets.Text(value=str(self._handle_list(self.config['QC']['ntu_dark_count'])))
        ntu_dark_count_box = widgets.HBox([label, text])

        label = widgets.Label(value='Chl Global Conversion', layout=layout)
        text = widgets.Checkbox(
            value=self.config['QC']['chl_global_conversion']
        )
        chl_global_conversion_box = widgets.HBox([label, text])

        label = widgets.Label(value='O2 Salinity Setting', layout=layout)
        text = widgets.Text(
            value=str(self._handle_list(self.config['QC']['o2_salinity_setting']))
        )
        o2_salinity_setting_box = widgets.HBox([label, text])

        label = widgets.Label(value='Instrument Split Time', layout=layout)
        kwargs = {'disabled': False}
        try:
            kwargs['value'] = self.config['QC']['instrument_time_split']
        except KeyError:
            pass
        picker = widgets.NaiveDatetimePicker(**kwargs)
        instrument_time_split_box = widgets.HBox([label, picker])

        items = [
            html,
            chl_scale_factor_box, chl_dark_count_box, ntu_scale_factor_box,
            ntu_dark_count_box, chl_global_conversion_box,
            o2_salinity_setting_box, instrument_time_split_box
        ]
        layout = widgets.Layout(
            width=CALIBRATION_COLUMN_WIDTH, border=COMMON_BORDER
        )
        box = widgets.VBox(items, layout=layout)

        return box

    def setup_channel_mapping(self):
        """
        Setup a mapping the channel data to variables.
        """
        text = '<h3>Voltage Channel Mapping</h3>'
        layout = widgets.Layout(border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        options = [0, 1, 2, 3, 4, 5]

        label = widgets.Label(value='Chl')
        radio = widgets.RadioButtons(
            options=options, value=self.config['QC']['chl_channel']
        )
        layout = widgets.Layout(
            width=RADIO_COLUMN_WIDTH, border=COMMON_BORDER
        )
        chl_box = widgets.VBox([label, radio], layout=layout)

        label = widgets.Label(value='NTU')
        radio = widgets.RadioButtons(
            options=options, value=self.config['QC']['ntu_channel']
        )
        layout = widgets.Layout(
            width=RADIO_COLUMN_WIDTH, border=COMMON_BORDER
        )
        ntu_box = widgets.VBox([label, radio], layout=layout)

        label = widgets.Label(value='O2')
        radio = widgets.RadioButtons(
            options=options, value=self.config['QC']['o2_channel']
        )
        layout = widgets.Layout(
            width=RADIO_COLUMN_WIDTH, border=COMMON_BORDER
        )
        o2_box = widgets.VBox([label, radio], layout=layout)

        label = widgets.Label(value='O2 Temp')
        radio = widgets.RadioButtons(
            options=options, value=self.config['QC']['o2_temp_channel']
        )
        layout = widgets.Layout(
            width=RADIO_COLUMN_WIDTH, border=COMMON_BORDER
        )
        o2_temp_box = widgets.VBox([label, radio], layout=layout)

        radio_boxes = widgets.HBox([chl_box, ntu_box, o2_box, o2_temp_box])

        layout = widgets.Layout(
            width=VOLTAGE_CHANNEL_WIDTH,
            border=COMMON_BORDER
        )
        vbox = widgets.VBox([html, radio_boxes], layout=layout)
        return vbox
