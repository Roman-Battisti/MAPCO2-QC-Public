"""
This module displays a number of plots to help the user decide how to trim
the merge file.
"""
# standard library imports
import pathlib
import time

# 3rd party library imports
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import xarray as xr

# local imports
from xco2qc import core


class XCO2PostTrimPlots(core.MapCO2core):
    """
    Attributes
    ----------
    """
    def __init__(self, reduced_path, trimmed_path, use_colorblind=False):
        self._is_notebook = self._check_if_jupyter()
        
        self.reduced_path = pathlib.Path(reduced_path)
        self.trimmed_path = pathlib.Path(trimmed_path)

        self.pre_trim_cycle_header_ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE  # noqa : E501
        self.post_trim_cycle_header_ncfile = self.trimmed_path / core.CYCLE_HEADER_NCFILE  # noqa : E501

        self._apoff_ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        self._epoff_ncfile = self.reduced_path / core.licor.EPOFF_NCFILE

        ext_ncfile = self.reduced_path / core.EXTERNAL_MET_NCFILE
        met_ncfile = self.reduced_path / core.MET_NCFILE

        self.set_met_ncfile(ext_ncfile, met_ncfile)
        
        self.color_palette = None if not use_colorblind else "colorblind"

    def set_met_ncfile(self, ext_ncfile, met_ncfile):
        """
        Set the path to the met netCDF file that is to be used.
        Also set the number of axes in the plot.
        """
        if ext_ncfile.exists():
            # plot apoff, epoff xco2, plus sss/sst
            self._met_ncfile = ext_ncfile
            self.num_axes = 4
        elif met_ncfile.exists():
            # plot apoff, epoff xco2, plus sss/sst
            self._met_ncfile = met_ncfile
            self.num_axes = 4
        else:
            # just plot apoff xco2 and epoff xco2
            self._met_ncfile = None
            self.num_axes = 2

    def run(self):

        self.fig, self.axes = plt.subplots(
            nrows=self.num_axes, sharex=True, figsize=(8, 6)
        )

        self.fig.canvas.mpl_connect('motion_notify_event', self.mouse_move)
        
        if self._is_notebook:
            self.plot_pre_trim()
            self.plot_post_trim()
        
        if self._is_notebook:
            time.sleep(0.2)
            plt.show()

    def plot_pre_trim(self):
        """
        Same as the plot of the post trim netCDF file, except that the colors
        are all red and there is no legend.
        """

        # Use all greys
        self.palette = [(0.5, 0.0, 0.0) for _ in range(10)]

        self.plot_xco2_wet()

        # plot sss/sst if we have it
        if self._met_ncfile is not None:
            self.plot_sss()
            self.plot_sst()

    def plot_post_trim(self):
        """
        Same as the plot of the pre trim netCDF file, except that the colors
        are blue instead of red and there is a legend.
        """
        self.palette = sns.color_palette(palette=self.color_palette)

        self._apoff_ncfile = self.trimmed_path / core.licor.APOFF_NCFILE
        self._epoff_ncfile = self.trimmed_path / core.licor.EPOFF_NCFILE

        ext_ncfile = self.trimmed_path / core.EXTERNAL_MET_NCFILE
        met_ncfile = self.trimmed_path / core.MET_NCFILE
        self.set_met_ncfile(ext_ncfile, met_ncfile)

        self.plot_xco2_wet()

        # plot sss/sst if we have it
        if self._met_ncfile is not None:
            self.plot_sss()
            self.plot_sst()

        self.plot_file_extents()

    def plot_file_extents(self):
        """
        Plot vertical red lines to make it clear what the difference is between
        the pre-trim and post-trim.
        """
        extents_colors = sns.color_palette(palette=self.color_palette, n_colors=2)
        ncfile = self.pre_trim_cycle_header_ncfile
        self._plot_file_extents(ncfile, color=extents_colors[0])

        ncfile = self.post_trim_cycle_header_ncfile
        self._plot_file_extents(ncfile, color=extents_colors[1])

    def _plot_file_extents(self, ncfile, color=None):

        # Get the first and last time values
        with xr.open_dataset(ncfile) as ds:
            time = ds[core.TIME].values[0], ds[core.TIME].values[-1]

        # must convert the timestamps to something matlab can understand
        x = mdates.date2num(time)

        for ax in self.axes:
            ymin, ymax = ax.get_ylim()
            ax.vlines(x, ymin, ymax, colors=color)

    def plot_xco2_wet(self):
        """
        Plot all of the xCO2 variables.
        """
        labels = ['EPOFF\nxCO2 wet', 'APOFF\nxCO2 wet']
        ncfiles = [self._epoff_ncfile, self._apoff_ncfile]
        for idx, (label, ncfile) in enumerate(zip(labels, ncfiles)):

            with xr.open_dataset(ncfile) as ds:
                data = ds['xco2_wet'].to_series()
                data.plot(ax=self.axes[idx], color=self.palette[0])
                self.axes[idx].set_ylabel(label)

    def plot_sss(self):
        """
        Plot salinity.  It's possible that there was no met buffer, meaning
        there would be no salinity.
        """

        with xr.open_dataset(self._met_ncfile) as ds:

            sss = self.get_good_ts(ds=ds, varname='SSS')
            sss.plot.line(
                ax=self.axes[2], color=self.palette[0]
            )
            self.axes[2].set_ylabel('Salinity')
            self.validate_ylim(self.axes[2], ds['SSS'].valid_range)

    def validate_ylim(self, ax, valid_range):
        """
        Check the axis ylims against the valid_range from a variable.  If the
        current ylims exceed the valid range, reset them.  This keeps extreme
        values from corrupting the plot, but still gives the user indication
        of those bad data points.
        """
        ylim = ax.get_ylim()
        bottom = np.max([ylim[0], valid_range[0]])
        top = np.min([ylim[1], valid_range[1]])
        ax.set_ylim(bottom=bottom, top=top)

    def plot_sst(self):
        """
        Plot SST.  It's possible that there was no met buffer, meaning
        there would be no SST.
        """

        with xr.open_dataset(self._met_ncfile) as ds:
            if 'SST' not in ds:
                return

            sst = self.get_good_ts(ds=ds, varname='SST')
            sst.plot.line(
                ax=self.axes[3], color=self.palette[0]
            )
            self.axes[3].set_ylabel('SST')
            self.validate_ylim(self.axes[3], ds['SST'].valid_range)

    def mouse_move(self, event):
        x, y = event.xdata, event.ydata
        t = mdates.num2date(x)
        title = f"{t.strftime('%Y-%m-%dT%H')}, {y:.1f}"
        self.fig.suptitle(title)
