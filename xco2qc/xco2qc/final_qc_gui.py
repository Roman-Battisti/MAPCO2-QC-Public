"""
Provide notebook GUI for performing final socat QC update.
"""
# standard library imports
import pathlib
import time

# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets
import matplotlib.pyplot as plt
from matplotlib.widgets import PolygonSelector
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from . import core
from xco2qc.final_qc import XCO2FinalQC
from . import data_common

WIDGET_COLUMN_LABEL_WIDTH = '33%'


class XCO2FinalQCGUI(data_common.DataCommon):
    """
    Provide notebook GUI core for performing final socat QC update.

    Attributes
    ----------
    merge_ncfile : path or str
        Path to the final merged netCDF file
    trim_dir : path or str
        Path to directory for trimmed netCDF files
    epoff_ncfile : path
        Path to trimmed equilibrium pump off netCDF file
    primary_dropdown : widget
        Displays dropdown menu choice for the primary variable.
    primary_var : str
        The variable currently being QC'd.
    primary_varlist : list
        List of variables that can be QC'd.
    fig, axes : matplotlib figure and axes
        Display the primary and secondary variables.
    qflog : str or path or None
        The qc reason will be stored in this CSV file.
    reason : text widget
        The user types in the reason for a specific change.
    """
    def __init__(
        self, merge_ncfile, trim_dir, use_colorblind=False, verbosity=None, qflog=None
    ):
        super().__init__(
            src_dir=merge_ncfile.parents[0], verbosity=verbosity,
            logger_name='finalqcgui', merge_ncfile=merge_ncfile,
        )

        self.merge_ncfile = pathlib.Path(merge_ncfile)
        self.trim_dir = pathlib.Path(trim_dir)
        self.apon_ncfile = self.trim_dir / core.licor.APON_NCFILE
        self.apoff_ncfile = self.trim_dir / core.licor.APOFF_NCFILE
        self.epon_ncfile = self.trim_dir / core.licor.EPON_NCFILE
        self.epoff_ncfile = self.trim_dir / core.licor.EPOFF_NCFILE
        self.spoff_ncfile = self.trim_dir / core.licor.SPOFF_NCFILE
        self.spostcal_ncfile = self.trim_dir / core.licor.SPOSTCAL_NCFILE
        self.zpoff_ncfile = self.trim_dir / core.licor.ZPOFF_NCFILE
        self.zpostcal_ncfile = self.trim_dir / core.licor.ZPOSTCAL_NCFILE
        self.seafet_ncfile = self.trim_dir / core.SEAFET_NCFILE
        self.cycle_header_ncfile = self.trim_dir / core.CYCLE_HEADER_NCFILE
        self.sami_ncfile = self.trim_dir / core.SAMI_NCFILE
        self.validation_ncfile = self.trim_dir / core.VALIDATION_NCFILE

        if qflog is not None:
            self.qflog = pathlib.Path(qflog)
        else:
            self.qflog = None
        
        self.color_palette = ['dodgerblue', 'orange', 'red', 'black'] if not use_colorblind else ['#0072B2', '#D55E00', '#CC79A7', '#000000']  # from https://scottplot.net/cookbook/4.1/colors/#colorblind-friendly

        self.get_primary_varlist()
        self.primary_var = 'xCO2_air'

        self.secondary_data = {}

        self.reload_data()

        # need this to convert the radio button labels to a numeric value
        self.socat_quality_map = {
            'good': core.quality.SOCAT_GOOD,
            'questionable': core.quality.SOCAT_QUESTIONABLE,
            'bad': core.quality.SOCAT_BAD,
            'missing': core.quality.SOCAT_MISSING
        }

        self.setup_gui()

        self.fig = plt.figure(figsize=(10, 6))

        self.setup_figure()

        self.fig.set_layout_engine('tight')

    def setup_figure(self):
        """
        Set the correct height of the figure as well as the correct position
        of each axis.
        """
        self.fig.clear()

        # In addition to the secondary plots, we have the primary variable
        # plot, of course.
        axes = []

        ax = plt.subplot(1, 1, 1)
        axes.append(ax)

        self.axes = axes

    def setup_gui(self):

        # set up the widgets for the primary variable
        label = widgets.Label(
            value="Primary Variable",
            layout=widgets.Layout(width=WIDGET_COLUMN_LABEL_WIDTH),
        )

        self.primary_dropdown = widgets.Dropdown(
            options=self.primary_varlist,
            value=self.primary_var,
        )
        self.primary_dropdown.observe(
            self.on_primary_dropdown_value_change, names='value'
        )

        primary_box = widgets.VBox([label, self.primary_dropdown])

        # set up the widgets for the socat QC value choice.
        self.radio_label = widgets.Label(
            value=f"{self.primary_var} Quality",
            layout=widgets.Layout(width=WIDGET_COLUMN_LABEL_WIDTH),
        )

        self.radio = widgets.RadioButtons(
            options=['good', 'bad', 'questionable'],
        )

        radio_box = widgets.VBox([self.radio_label, self.radio])

        self.reason = widgets.Text(description="Reason", value="")

        box = widgets.HBox([primary_box, radio_box, self.reason])

        self.gui = box

    def on_primary_dropdown_value_change(self, change):
        """
        Update the secondary dropdown and replot the data.

        Parameters
        ----------
        change : dict
            Describes the new state of the primary dropdown.
        """
        self.primary_var = change['new']

        self.reload_data()

        # update the radio button selection
        self.radio_label.value = f"{self.primary_var} Quality"
        if self.socat_qc_var is None:
            self.radio.options = ('good', 'bad')
        else:
            self.radio.options = ('good', 'bad', 'questionable')

        self.plot()

    def run(self):
        """
        Display the GUI in the notebook and then populate the plots.
        """
        display(self.gui)
        self.plot()

    def plot(self, update=False):
        """
        Display a plot of both the primary and secondary variable(s).  Create
        a new selctor object for doing interactive QC.
        """
        self.reload_data()
        if update and hasattr(self, "axes"):
            # get x & y ranges
            x_range = self.axes[0].get_xlim()
            y_range = self.axes[0].get_ylim()
            self.axes[0].clear()
        else:
            x_range = None
            y_range = None
            self.setup_figure()
        self.plot_primary_variable(x_range, y_range)

        self.poly = PolygonSelector(self.axes[0], self.onselect)
        if self._is_notebook:
            time.sleep(0.1)
            plt.show()

    def plot_primary_variable(self, x_range=None, y_range=None):

        self.logger.info(f'Plotting primary variable {self.primary_var}...')
        # create a palette depending upon how many different QC levels there
        # are.
        if self.socat_qc_var is not None:
            palette = {
                core.quality.SOCAT_GOOD: self.color_palette[0],
                core.quality.SOCAT_QUESTIONABLE: self.color_palette[1],
                core.quality.SOCAT_BAD: self.color_palette[2],
                core.quality.SOCAT_MISSING: self.color_palette[3]
            }

            self.sc = self.axes[0].scatter(
                self.df['time'], self.df[self.primary_var],
                c=self.df[self.socat_qc_var].map(palette)
            )
        else:

            # It may be either SSS or SST in this case, there is no socat QC
            # attached.

            # restrict colors to show only "good" or "not good"
            x = np.where(
                self.df[self.bitmask_qc_var] == core.quality.GOOD, 0, 1
            )
            qc2 = pd.Series(data=x, index=self.df.time)

            palette = {
                0: self.color_palette[0],
                1: self.color_palette[2],
            }

            self.sc = self.axes[0].scatter(
                self.df['time'], self.df[self.primary_var], c=qc2.map(palette)
            )

        # xarray does a bad job of setting ylabels in this case, so we have to
        # do it ourselves.
        self.axes[0].set_ylabel(self.primary_var)

        # the xlabel for the primary variable isn't needed
        self.axes[0].set_xlabel('')

        # Is it pH?  If so, invert the axis.
        # if self.primary_var in ('pH_sw'):
        #     self.axes[0].invert_yaxis()
        
        # set ranges
        if x_range is not None:
            self.axes[0].set_xlim(*x_range)
        if y_range is not None:
            self.axes[0].set_ylim(*y_range)
            

    def onselect(self, verts):
        """
        Toggle the points within the selected polygon.

        Parameters
        ----------
        verts : list
            list of (xdata, ydata) tuples.
        """
        self.logger.info(f'Masking points enclosed in {verts}...')

        user_comment = self.reason.value
        new_socat_qc_value = self.socat_quality_map[self.radio.value]
        
        with XCO2FinalQC(
            self.merge_ncfile, self.primary_var, verts, new_socat_qc_value,
            qflog=self.qflog, user_comment=user_comment, logger=self.logger
        ) as p:
            p.run()

        # Go again.
        self.plot(update=True)
        # self.run()
        

    def get_primary_varlist(self):
        """
        Get the list of variables that have socat qc associated with them
        """

        varlist = []

        with xr.open_dataset(self.merge_ncfile) as ds:
            for ncvar in ds.variables:

                # basically, if the netCDF variable is a time series variable
                # and if it has an ancillary_variables attribute that has the
                # word 'socat' in it, then this is a variable that we are
                # interested in.
                if (
                    ncvar not in ['xco2_air_wet', 'xco2_sw_wet']
                    and 'time' in ds[ncvar].coords
                    and hasattr(ds[ncvar], 'ancillary_variables')
                    and 'socat' in ds[ncvar].ancillary_variables
                ):
                    varlist.append(ncvar)

            # add SSS and SST
            # even though they do not have socat QC associated with them.
            if 'SSS' in ds.variables:
                varlist.append('SSS')
            if 'SST' in ds.variables:
                varlist.append('SST')

        self.primary_varlist = sorted(varlist, key=str.casefold)

    def reload_data(self):
        """
        get the needed data as a pandas dataframe.  We need time, the primary
        variable currently indicated in the dropdown, the secondary variable
        as indicated in the other dropdown, and both quality variables
        associated with the primary variable.

        The 'qc_reason' column will be a string column that has the reasons for
        each of the bitmask flags being set, such as out-of-range, etc.
        """
        self.gather_primary_data()

    def gather_primary_data(self):
        """
        Retrieve the variable that is being QC'd.
        """
        with xr.open_dataset(self.merge_ncfile) as ds:

            ds = ds.load()

            # Get the socat qc variable associated with the primary variable.
            ancillary_attr = ds[self.primary_var].ancillary_variables

            try:
                self.bitmask_qc_var, self.socat_qc_var = ancillary_attr.split()
            except ValueError:
                # ValueError: not enough values to unpack (expected 2, got 1)
                self.bitmask_qc_var = ancillary_attr
                self.socat_qc_var = None

            # get the bit flag masks and reasons
            flag_masks = ds[self.bitmask_qc_var].flag_masks
            flag_meanings = ds[self.bitmask_qc_var].flag_meanings.split()

            df = ds.to_dataframe()

        df = df.reset_index()

        # force the quality variables to be integer
        if self.socat_qc_var is not None:
            df[self.socat_qc_var] = df[self.socat_qc_var].astype(np.uint8)
        df[self.bitmask_qc_var] = df[self.bitmask_qc_var].astype(np.uint32)

        self.df = self.create_qc_reasons(df, flag_masks, flag_meanings)

    def create_qc_reasons(self, df, flag_masks, flag_meanings):
        """
        change the bitflag qc variable to a comma-delimited text of reasons
        for the bit flags
        """
        d = {
            value: meaning
            for value, meaning in zip(flag_masks, flag_meanings)
        }

        df['qc_reason'] = ''
        for mask_value, reason in d.items():

            # where does this mask reason apply
            x = np.bitwise_and(df[self.bitmask_qc_var], mask_value)
            reasons = np.where(x, ',' + reason, '')
            df['qc_reason'] = df['qc_reason'].str.cat(reasons)

        # get rid of the leading comma
        df['qc_reason'] = df['qc_reason'].str.strip(',')

        return df

    def _get_measured_o2(self):
        """
        Get O2 from a netCDF file.
        """
        with xr.open_dataset(self.merge_ncfile) as ds:

            if 'dissolved_oxygen' not in ds:
                msg = (
                    'No dissolved_oxygen variable found in '
                    f'{self.merge_ncfile}'
                )
                raise KeyError(msg)

        o2 = self.get_good_ts(
            ncfile=self.merge_ncfile, varname='dissolved_oxygen'
        )

        return o2

    def _get_maxtec_o2(self, ncfile):
        """

        """
        maxtec = self.get_good_ts(
            ncfile=self.merge_ncfile, varname='dissolved_oxygen'
        )
        maxtec.name = 'maxtec'

        return maxtec
