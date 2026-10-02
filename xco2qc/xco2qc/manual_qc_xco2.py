"""
Support for manual flagging of either pH or xco2.  This can be run either from
within a Jupyter notebook or from the python command line.
"""
# standard library imports
import functools
import pathlib

# 3rd party library imports
import matplotlib.dates as mdates
from matplotlib.path import Path
import matplotlib.pyplot as plt
from matplotlib.widgets import PolygonSelector
import netCDF4
import numpy as np
import seaborn as sns
import xarray as xr

# local imports
from xco2qc import core

BLUE, ORANGE, GREEN = sns.color_palette(n_colors=3)


class XCO2ManualQC(core.MapCO2core):
    """
    Use native matplotlib functionality to select xCO2 data points to manually
    flag.

    This class can be uses for time series data, but not for the special case
    of lat/lon pairs.

    Attributes
    ----------
    ncfile : path
        Path to netCDF file
    variables : list of str
        Names of netCDF variables to manually flag.
    fig, ax :
        matplotlib figure and associated axis
    ts, qc : pandas.Series
        time series for xCO2 data and QC
    poly : matplotlib.widgets.PolygonSelector
        Select a polygon region of an axes.
    """

    def __init__(self, ncfile, variable, verbosity=None):
        super().__init__(verbosity=verbosity, logger_name='manual-xco2')

        self.ncfile = pathlib.Path(ncfile)

        # we need to know if we are running the QC for the first time or if
        # this is a subsequent run.
        self.first_time = True

        # map the input variable to a whole class of variables
        d = {
            'pH_sw': ['pH_sw'],
            'xCO2_air': ['xCO2_air', 'xCO2_sw'],
            'xco2_air_wet': ['xco2_air_wet', 'xco2_sw_wet'],
        }
        self.variables = d[variable]

        # collect all the QC variables names upfront as well.
        self.qc_variables = []
        for variable in self.variables:
            qcvar = self.get_qc_variable(variable)
            self.qc_variables.append(qcvar)

        nrows = len(self.variables)
        self.fig, self.ax = plt.subplots(nrows=nrows, sharex=True)
        if nrows == 1:
            # Must force ax to be a list in the case we are working with just
            # one variable.
            self.ax = [self.ax]

    def reload(self):
        self.logger.debug('Reload')

        # read  in the data, restrict to the data variables and qc variables
        # of interest
        with xr.open_dataset(self.ncfile) as ds:
            df = ds.to_dataframe()

        vars = self.variables + self.qc_variables
        df = df[vars]

        # force the QC columns to be integer.
        for qc_var in self.qc_variables:
            df[qc_var] = df[qc_var].astype(np.uint32)

        self.df = df

    def run(self):
        self.logger.debug('Run')

        if self.first_time:
            self.reset_qc()
            self.first_time = False

        self.reload()
        self.plot()

    def plot(self):

        self.logger.debug('Plot')

        self.poly = []
        for idx in range(len(self.variables)):
            ax = self.ax[idx]
            variable = self.variables[idx]
            qc_variable = self.qc_variables[idx]

            self.logger.debug(f"Looking at {ax}")
            self.logger.debug(f"Looking at {variable}, {qc_variable}")
            ax.cla()

            self._plot_other_qc(ax, variable, qc_variable)
            self._plot_good_data(ax, variable, qc_variable)
            self._plot_manually_flagged(ax, variable, qc_variable)

            # only do a legend for the first plot, it will be sufficient for
            # the subsequent plots
            if idx == 0:
                self._construct_legend(ax)

            # some fun and games with the callback function.  The API is only
            # designed to accept a single input (the vertices), but we also
            # need to pass the data variable and QC variable associated with
            # this axis.
            fcn = functools.partial(
                self.onselect, variable=variable, qc_variable=qc_variable
            )
            poly = PolygonSelector(ax, fcn)
            self.poly.append(poly)

        # last thing, force the xlims to be consistent.
        # I believe this is a bug with matplotlib.  Should not have to do this.
        beginning_datenum = mdates.date2num(self.df.index[0])
        ending_datenum = mdates.date2num(self.df.index[-1])
        delta = ending_datenum - beginning_datenum
        self.ax[0].set_xlim(
            left=beginning_datenum - delta * 0.05,
            right=ending_datenum + delta * 0.05
        )

    def _plot_good_data(self, ax, variable, qc_variable):
        """
        we only want to plot where QC is good or at least not manually
        flagged
        """
        good_data = self.df[variable].copy()
        qc = self.df[qc_variable].copy()
        good_data[qc != core.quality.GOOD] = np.nan

        good_data.plot(
            ax=ax,
            ylabel=variable,
            color=BLUE,
            label='Good Data'
        )

    def _plot_manually_flagged(self, ax, variable, qc_variable):
        """
        we also want to show the data that was manually flagged in a previous
        step for reference
        """
        flagged_data = self.df[variable].copy()
        qc = self.df[qc_variable].copy()
        idx = np.bitwise_and(qc, core.quality.MANUALLY_FLAGGED) == 0
        flagged_data[idx] = np.nan
        flagged_data.plot(
            ax=ax, color=ORANGE, label='Manually Flagged', marker='*'
        )

    def _construct_legend(self, ax):

        good_data_handle = ax.findobj(
            lambda x: x.get_label() == 'Good Data'
        )
        flagged_data_handle = ax.findobj(
            lambda x: x.get_label() == 'Manually Flagged'
        )
        other_qc_handle = ax.findobj(
            lambda x: x.get_label() == 'Other QC'
        )
        handles = [
            good_data_handle[0],
            flagged_data_handle[0],
            other_qc_handle[0]
        ]
        labels = ['Good Data', 'Manually Flagged', 'Other QC']
        ax.legend(handles, labels)

    def _plot_other_qc(self, ax, variable, qc_variable):
        """
        And finally, plot any points that have "other" QC.
        """
        ts = self.df[variable].copy()
        qc = self.df[qc_variable].copy()

        # NaN out any points with good qc
        ts[qc == core.quality.GOOD] = np.nan

        idx = np.nonzero(
            np.bitwise_and(qc.values, core.quality.MANUALLY_FLAGGED)
        )[0]
        ts.iloc[idx] = np.nan

        ts.plot(ax=ax, color=GREEN, label='Other QC', alpha=0.3, marker='*')

    def reset_qc(self):
        """
        The first time we run, we strip the manual flag from the variables.
        We do this in case the user makes a mistake and wishes to start over.
        If the user has already committed one polygon, then the only way to
        accomplish this is to reset the qc variables every "first time"
        through.
        """
        for variable in self.variables:
            qcvar = self.get_qc_variable(variable)
            self.clear_qc(self.ncfile, qcvar, core.quality.MANUALLY_FLAGGED)

    def get_qc_variable(self, data_variable):
        """
        Retrieve the netCDF QC variable that is associated with the data
        variable.
        """
        with netCDF4.Dataset(self.ncfile) as nc:
            # This is a space-delimited list, so split it into a python list
            ancillary_variables = nc[data_variable].ancillary_variables.split()

        for ancillary_variable in ancillary_variables:
            # don't mistakenly grab a socat qc variable!!!
            # we want the bitmask qc variable.
            if 'socat' in ancillary_variable:
                continue

            return ancillary_variable

    def onselect(self, verts, variable=None, qc_variable=None):
        """
        all points within the selected polygon are to be manually flagged

        Parameters
        ----------
        verts : list
            list of (xdata, ydata) tuples.  It is important to realize that
            since this is time series data that has been plotted, the xdata
            is matplotlib dates, i.e. number of days since 0000-01-01 UTC,
            which is different than the time units stored in the netCDF file.
        variable : str
            Name of the netCDF data variable being flagged.
        qc_variable : str
            Name of the netCDF QC variable associated with the data variable
        """

        path = Path(verts)

        # convert the time data into matlab dates.
        x = mdates.date2num(self.df.index)
        y = self.df[variable].values

        # find the points that fall within the polygon
        data = np.array(list(zip(x, y)))
        idx = np.nonzero(path.contains_points(data))[0]

        with netCDF4.Dataset(self.ncfile, mode='r+') as nc:

            qc = self.df.loc[:, qc_variable].copy()
            qc.iloc[idx] = np.bitwise_xor(qc.iloc[idx], core.quality.MANUALLY_FLAGGED)

            nc[qc_variable][:] = qc

        # Go again.
        self.run()
