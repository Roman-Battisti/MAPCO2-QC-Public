# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets

# local imports
from xco2qc import core

APON_APOFF_MIN_PRESSURE_DIFFERENCE = 0.1
EPON_EPOFF_MIN_PRESSURE_DIFFERENCE = 0.1
SPON_SPOFF_MIN_PRESSURE_DIFFERENCE = 0.1

HTML_COLUMN_WIDTH = '30%'
CONTROL_COLUMN_WIDTH = '70%'
COMMON_BORDER = 'solid 1px'
WIDGET_COLUMN_LABEL_WIDTH = '30%'
WIDGET_COLUMN_SLIDER_WIDTH = '60%'


class QCGui(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to QC the xco2 data.

    Attributes
    ----------
    [aes]pon_apoff_{min,max}_slider: : ipwidgets.FloatSlider
        Sliders for controlling the min and max values for pressure differences
        across APON and APOFF, EPON and EPOFF, SPON and SPOFF
    {min,max}_air_xco2_std_slider : ipywidgets.FloatSlider
        Sliders for controlling the min and max allowed value for APOFF, EPOFF
        xco2 standard deviation
    max_{rh,rh_temp}_std_slider : ipywidgets.FloatSlider
        Sliders for controlling the largest allowed value for RH and RH_TEMP
        standard deviation
    initial_span_cal_slider : ipywidgets.FloatSlider
        Slider for controlling the initial span calibration.
    """

    def __init__(self, dst_dir=None):
        super().__init__(dst_dir=dst_dir)
        self.gui = None

        self.gui_rows = []

    def run(self):

        # Setup the low level widgets.
        self.setup_initial_span_cal_controls()
        self.setup_apon_apoff_pressure_difference_controls()
        self.setup_epon_epoff_pressure_difference_controls()
        self.setup_spon_spoff_pressure_difference_controls()
        self.setup_max_pressoff_diff_controls()
        self.setup_xco2_zero_range_controls()
        self.setup_xco2_span_cal_range_controls()
        self.setup_xco2_stddev_range_controls()
        self.setup_rh_temp_rh_stddev_range_controls()
        self.setup_xco2_trend_stddev_controls()
        self.setup_spike_detection_controls()

        # Setup all the rows of the GUI, arranged as a single column.
        layout = widgets.Layout(border=COMMON_BORDER)
        self.gui = widgets.VBox(self.gui_rows, layout=layout)

        display(self.gui)

    def setup_spike_detection_controls(self):
        """
        Setup a checkbox for spike detection.
        """
        text = '<h3>Spike Detection</h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        self.spike_detection_checkbox = widgets.Checkbox(
            value=False, description="Use Spike Detection", layout=layout
        )

        row = widgets.HBox([html, self.spike_detection_checkbox])
        self.gui_rows.append(row)

    def setup_xco2_trend_stddev_controls(self):
        """
        Setup just a slider for the APOFF/EPOFF xCO2 trend STD QC.
        """
        text = '<h3>APOFF/EPOFF xCO2 Trend</h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        kwargs = {
            'default_value': self.config['QC']['xco2_trend_std'],
            'callback': None,
            'label_text': '# STDDEVs',
            'slider_min': 0,
            'slider_max': 6,
            'num_type': int
        }
        num_stddevs_box = self.setup_label_slider_text_row(**kwargs)
        self.xco2_trend_std_slider = num_stddevs_box.children[1]

        # create a box for the window size used for the trend
        kwargs = {
            'default_value': self.config['QC']['num_points_eachside'],
            'callback': None,
            'label_text': '1/2 window size',
            'slider_min': 0,
            'slider_max': 15,
            'num_type': int
        }
        window_size_box = self.setup_label_slider_text_row(**kwargs)
        self.xco2_trend_window_size_slider = window_size_box.children[1]

        # and finally, collect the boxes up into a single box
        items = [num_stddevs_box, window_size_box]
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        vbox = widgets.VBox(items, layout=layout)

        row = widgets.HBox([html, vbox])
        self.gui_rows.append(row)

    def setup_initial_span_cal_controls(self):
        """
        Setup a slider and a text box.  Link the two values together.
        """
        # 1st column is the descriptive HTML
        text = '<h3>Initial Span Concentration</h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        kwargs = {
            'default_value': self.config['QC']['initial_span_cal'],
            'callback': self.validate_initial_span_cal_slider_value,
            'label_text': 'SC',
            'slider_min': 400,
            'slider_max': 900,
            'slider_step': 0.01,
            'border': True
        }
        box = self.setup_label_slider_text_row(**kwargs)
        self.initial_span_cal_slider = box.children[1]

        row = widgets.HBox([html, box])

        self.gui_rows.append(row)

    def validate_initial_span_cal_slider_value(self, change):
        """
        Bound the text widget value by the max and min values of the slider.
        """

        if change.new > self.initial_span_cal_slider.max:
            self.initial_span_cal_slider.value = self.initial_span_cal_slider.max  # noqa : E501
        elif change.new < self.initial_span_cal_slider.min:
            self.initial_span_cal_slider.value = self.initial_span_cal_slider.min  # noqa : E501

    def setup_rh_temp_rh_stddev_range_controls(self):
        """
        Put both sliders for controlling the rh_temp and RH maximum STDDEV
        together.
        """

        text = '<h3>RH/RH_TEMP STDDEV Max</h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        kwargs = {
            'default_value': self.config['QC']['max_rh_std'],
            'callback': None,
            'label_text': 'RH',
            'slider_min': 0,
            'slider_max': 8,
        }
        max_rh_std_box = self.setup_label_slider_text_row(**kwargs)
        self.max_rh_std_slider = max_rh_std_box.children[1]

        kwargs = {
            'default_value': self.config['QC']['max_rh_temp_std'],
            'callback': None,
            'label_text': 'RH TEMP',
            'slider_min': 0,
            'slider_max': 8,
        }
        max_rh_temp_std_box = self.setup_label_slider_text_row(**kwargs)
        self.max_rh_temp_std_slider = max_rh_temp_std_box.children[1]

        items = [max_rh_std_box, max_rh_temp_std_box]
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        vbox = widgets.VBox(items, layout=layout)

        row = widgets.HBox([html, vbox])
        self.gui_rows.append(row)

    def setup_xco2_stddev_range_controls(self):
        """
        Put both the APOFF and EPOFF sliders together.
        """

        text = '<h3>xCO2 Raw STDDEV Max</h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        kwargs = {
            'default_value': self.config['QC']['max_air_xco2_std'],
            'callback': None,
            'label_text': 'APOFF',
            'slider_min': 0,
            'slider_max': 40,
        }
        max_air_xco2_std_box = self.setup_label_slider_text_row(**kwargs)
        self.max_air_xco2_std_slider = max_air_xco2_std_box.children[1]

        kwargs = {
            'default_value': self.config['QC']['max_equil_xco2_std'],
            'callback': None,
            'label_text': 'EPOFF',
            'slider_min': 0,
            'slider_max': 40,
        }
        max_equil_xco2_std_box = self.setup_label_slider_text_row(**kwargs)
        self.max_equil_xco2_std_slider = max_equil_xco2_std_box.children[1]

        items = [max_air_xco2_std_box, max_equil_xco2_std_box]
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        vbox = widgets.VBox(items, layout=layout)

        row = widgets.HBox([html, vbox])
        self.gui_rows.append(row)

    def setup_xco2_span_cal_range_controls(self):

        text = '<h3>SPOFF/SPOSTCAL xCO2 Range Around Span Cal</h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        kwargs = {
            'default_value': self.config['QC']['ppm_below_span_cal'],
            'callback': None,
            'label_text': 'PPM Below Span Cal',
            'slider_min': 0,
            'slider_max': 20,
        }
        below_span_cal_box = self.setup_label_slider_text_row(**kwargs)

        kwargs = {
            'default_value': self.config['QC']['ppm_above_span_cal'],
            'callback': None,
            'label_text': 'PPM Above Span Cal',
            'slider_min': 0,
            'slider_max': 20,
        }
        above_span_cal_box = self.setup_label_slider_text_row(**kwargs)

        items = [below_span_cal_box, above_span_cal_box]
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        vbox = widgets.VBox(items, layout=layout)

        row = widgets.HBox([html, vbox])
        self.gui_rows.append(row)

        self.xco2_ppm_below_span_cal_slider = below_span_cal_box.children[1]
        self.xco2_ppm_above_span_cal_slider = above_span_cal_box.children[1]

    def setup_xco2_zero_range_controls(self):

        text = '<h3>ZPOFF xCO2 Range</h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        kwargs = {
            'default_value': self.config['QC']['ppm_below_zero'],
            'callback': None,
            'label_text': 'PPM Below 0',
            'slider_min': 0,
            'slider_max': 20,
        }
        below_zero_box = self.setup_label_slider_text_row(**kwargs)
        self.xco2_ppm_below_zero_slider = below_zero_box.children[1]

        kwargs = {
            'default_value': self.config['QC']['ppm_above_zero'],
            'callback': None,
            'label_text': 'PPM Above 0',
            'slider_min': 0,
            'slider_max': 20,
        }
        above_zero_box = self.setup_label_slider_text_row(**kwargs)
        self.xco2_ppm_above_zero_slider = above_zero_box.children[1]

        items = [below_zero_box, above_zero_box]
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        vbox = widgets.VBox(items, layout=layout)

        row = widgets.HBox([html, vbox])
        self.gui_rows.append(row)

    def setup_max_pressoff_diff_controls(self):
        """
        Setup widgets for APOFF/EPOFF/SPOFF maximum pressure difference.
        """

        text = "<h3>APOFF/EPOFF/SPOFF Maximum Pressure Difference</h3>"
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        kwargs = {
            'default_value': self.config['QC']['max_pressoff_diff'],
            'callback': None,
            'label_text': 'Max',
            'slider_min': 0,
            'slider_max': 1.0,
            'border': True
        }
        box = self.setup_label_slider_text_row(**kwargs)
        self.max_pressoff_diff_slider = box.children[1]

        row = widgets.HBox([html, box])
        self.gui_rows.append(row)

    def setup_apon_apoff_pressure_difference_controls(self):
        """
        Setup a min/max slider pair that controls the range of difference
        allowed between APON and APOFF pressure readings.
        """
        qc = self.config['QC']

        kwargs = {
            'html_box_text': 'APON/APOFF Pressure Difference',
            'min_pressure_default_value': qc['air_diff_range_lower'],
            'max_pressure_default_value': qc['air_diff_range_higher'],
            'min_validate_callback': self.validate_apon_apoff_min_slider_change,  # noqa : E501
            'max_validate_callback': self.validate_apon_apoff_max_slider_change
        }
        d = self.setup_pressure_difference_controls(**kwargs)

        self.apon_apoff_min_slider = d['min_slider']
        self.apon_apoff_max_slider = d['max_slider']

    def setup_spon_spoff_pressure_difference_controls(self):
        """
        Setup a min/max slider pair that controls the range of difference
        allowed between SPON and SPOFF pressure readings.
        """
        qc = self.config['QC']

        kwargs = {
            'html_box_text': 'SPON/SPOFF Pressure Difference',
            'min_pressure_default_value': qc['span_diff_range_lower'],
            'max_pressure_default_value': qc['span_diff_range_higher'],
            'min_validate_callback': self.validate_spon_spoff_min_slider_change,  # noqa : E501
            'max_validate_callback': self.validate_spon_spoff_max_slider_change
        }

        d = self.setup_pressure_difference_controls(**kwargs)
        self.spon_spoff_min_slider = d['min_slider']
        self.spon_spoff_max_slider = d['max_slider']

    def setup_epon_epoff_pressure_difference_controls(self):
        """
        Setup a min/max slider pair that controls the range of difference
        allowed between EPON and EPOFF pressure readings.
        """
        qc = self.config['QC']

        kwargs = {
            'html_box_text': 'EPON/EPOFF Pressure Difference',
            'min_pressure_default_value': qc['equil_diff_range_lower'],
            'max_pressure_default_value': qc['equil_diff_range_higher'],
            'min_validate_callback': self.validate_epon_epoff_min_slider_change,  # noqa : E501
            'max_validate_callback': self.validate_epon_epoff_max_slider_change
        }

        d = self.setup_pressure_difference_controls(**kwargs)
        self.epon_epoff_min_slider = d['min_slider']
        self.epon_epoff_max_slider = d['max_slider']

    def setup_pressure_difference_controls(
        self,
        html_box_text=None,
        min_pressure_default_value=None, max_pressure_default_value=None,
        min_validate_callback=None, max_validate_callback=None,
    ):
        """
        Create a generic row of widgets for controlling pressure differences.
        This will be valid for APON/APOFF, SPON/SPOFF, and EPON/EPOFF pressure
        differences.

        Parameters
        ----------
        html_box_text : str
            Will be displayed in first column of the row of widgets.
        min_pressure_default_value, max_pressure_default_value : float
            Both the slider and the editable text widget will be initially set
            to these values.
        min_validate_callback, max_validate_callback : function
            When the value of the sliders or editable text widgets are changed,
            invoke this callback function to validate.  We don't want the min
            slider value to be greater than the max slider value.

        Returns
        -------
        dict
            We need to access the sliders in the validation callbacks, so these
            must be returned to the calling routine so that the sliders can
            be appropriately referenced.
        """

        # 1st column is the descriptive HTML
        text = f"<h3>{html_box_text}</h3>"
        layout = widgets.Layout(
            width=HTML_COLUMN_WIDTH, border=COMMON_BORDER
        )
        html = widgets.HTML(text, layout=layout)

        min_kwargs = {
            'default_value': min_pressure_default_value,
            'callback': min_validate_callback,
            'label_text': 'min',
            'slider_min': 0,
            'slider_max': 15,
        }
        min_box = self.setup_label_slider_text_row(**min_kwargs)

        max_kwargs = {
            'default_value': max_pressure_default_value,
            'callback': max_validate_callback,
            'label_text': 'max',
            'slider_min': 0,
            'slider_max': 15,
        }
        max_box = self.setup_label_slider_text_row(**max_kwargs)

        # Wrap the min/max rows together
        items = [min_box, max_box]
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        vbox = widgets.VBox(items, layout=layout)

        row = widgets.HBox([html, vbox])
        self.gui_rows.append(row)

        r = {
            'min_slider': min_box.children[1],
            'max_slider': max_box.children[1],
        }
        return r

    def setup_label_slider_text_row(
        self, default_value=None, callback=None, label_text=None, slider_min=0,
        slider_max=0, slider_step=0.1, border=False, num_type = float
    ):

        # 2nd column is the controls
        label = widgets.Label(
            value=label_text,
            layout=widgets.Layout(width=WIDGET_COLUMN_LABEL_WIDTH)
        )
        
        if num_type == float:
            slider = widgets.FloatSlider(
                value=default_value,
                min=slider_min, max=slider_max, step=slider_step,
                layout=widgets.Layout(width=WIDGET_COLUMN_SLIDER_WIDTH),
                readout=False
            )

            text = widgets.FloatText(value=default_value)
        
        elif num_type == int:
            slider = widgets.IntSlider(
                value=default_value,
                min=int(slider_min), max=int(slider_max),
                layout=widgets.Layout(width=WIDGET_COLUMN_SLIDER_WIDTH),
                readout=False
            )

            text = widgets.IntText(value=int(default_value))
        
        else:
            raise TypeError(f"Type {num_type} cannot be set up properly!")

        # Link the slider and the text box together so that a change in one
        # is reflected by the other
        widgets.jslink((slider, 'value'), (text, 'value'))

        # Set up callbacks to validate any change made to the sliders
        if callback is not None:
            slider.observe(callback, names='value')

        if border:
            layout = widgets.Layout(
                width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
            )
            box = widgets.HBox([label, slider, text], layout=layout)
        else:
            box = widgets.HBox([label, slider, text])

        return box

    def validate_spon_spoff_min_slider_change(self, change):
        """
        Do not allow the min slider to get too close to the max slider
        """
        current_value = self.spon_spoff_max_slider.value
        delta = current_value - change.new
        if delta < SPON_SPOFF_MIN_PRESSURE_DIFFERENCE:
            # The new value is NOT ok.  Bound it to the max slider.
            new_value = current_value - SPON_SPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501
            self.spon_spoff_min_slider.value = new_value

    def validate_spon_spoff_max_slider_change(self, change):
        """
        Do not allow the max slider to get too close to the min slider
        """
        delta = change.new - self.spon_spoff_min_slider.value
        if delta < SPON_SPOFF_MIN_PRESSURE_DIFFERENCE:
            # The new value is NOT ok.  Bound it to the min slider.
            self.spon_spoff_max_slider.value = self.spon_spoff_min_slider.value + SPON_SPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501

    def validate_apon_apoff_min_slider_change(self, change):
        """
        Do not allow the min slider too close to the max slider
        """
        delta = self.apon_apoff_max_slider.value - change.new
        if delta < APON_APOFF_MIN_PRESSURE_DIFFERENCE:
            # The new value is NOT ok.  Bound it to the max slider.
            self.apon_apoff_min_slider.value = self.apon_apoff_max_slider.value - APON_APOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501

    def validate_apon_apoff_max_slider_change(self, change):
        """
        Do not allow the max slider to get within 1 of the min slider
        """
        delta = change.new - self.apon_apoff_min_slider.value
        if delta < APON_APOFF_MIN_PRESSURE_DIFFERENCE:
            # The new value is NOT ok.  Bound it to the min slider.
            self.apon_apoff_max_slider.value += self.apon_apoff_min_slider.value + APON_APOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501

    def validate_epon_epoff_min_slider_change(self, change):
        """
        Do not allow the min slider to get within 1 of the max slider
        """
        delta = self.epon_epoff_max_slider.value - change.new
        if delta < EPON_EPOFF_MIN_PRESSURE_DIFFERENCE:
            # The new value is NOT ok.  Bound it to the max slider.
            self.epon_epoff_min_slider.value = self.epon_epoff_max_slider.value - EPON_EPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501

    def validate_epon_epoff_max_slider_change(self, change):
        """
        Do not allow the max slider to get within 1 of the min slider
        """
        delta = change.new - self.epon_epoff_min_slider.value
        if delta < EPON_EPOFF_MIN_PRESSURE_DIFFERENCE:
            # The new value is NOT ok.  Bound it to the min slider.
            self.epon_epoff_max_slider.value = self.epon_epoff_min_slider.value + EPON_EPOFF_MIN_PRESSURE_DIFFERENCE  # noqa : E501

    def gather_kwargs(self):
        """
        Gather all the values currently set by the GUI.  They are to be passed
        into the QC program.
        """

        return {
            'air_diff_range_lower': self.apon_apoff_min_slider.value,
            'air_diff_range_higher': self.apon_apoff_max_slider.value,
            'equil_diff_range_lower': self.epon_epoff_min_slider.value,
            'equil_diff_range_higher': self.epon_epoff_max_slider.value,
            'initial_span_cal': self.initial_span_cal_slider.value,
            'max_air_xco2_std': self.max_air_xco2_std_slider.value,
            'max_equil_xco2_std': self.max_equil_xco2_std_slider.value,
            'max_pressoff_diff': self.max_pressoff_diff_slider.value,
            'max_rh_std': self.max_rh_std_slider.value,
            'max_rh_temp_std': self.max_rh_temp_std_slider.value,
            'ppm_below_span_cal': self.xco2_ppm_below_span_cal_slider.value,
            'ppm_above_span_cal': self.xco2_ppm_above_span_cal_slider.value,
            'ppm_below_zero': self.xco2_ppm_below_zero_slider.value,
            'ppm_above_zero': self.xco2_ppm_above_zero_slider.value,
            'num_points_eachside': self.xco2_trend_window_size_slider.value,
            'span_diff_range_lower': self.spon_spoff_min_slider.value,
            'span_diff_range_higher': self.spon_spoff_max_slider.value,
            'xco2_trend_std': self.xco2_trend_std_slider.value,
            'spike_detection': self.spike_detection_checkbox.value,
        }
