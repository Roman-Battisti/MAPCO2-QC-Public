"""
Plot a number of variable pairs picked from possibly different data_sources
(netcdf files).
"""

# 3rd party library imports
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# local imports
from xco2qc import core


class FeaturePlots(core.MapCO2core):
    """
    Attributes
    ----------
    directory : path
        The netCDF files will be located here.
    pairs : list of tuples
        Each pair is a tuple where the first item is a netCDF file and the
        second is a netCDF variable.
    """

    def __init__(self, directory, pairs, **kwargs):
        super(FeaturePlots, self).__init__(**kwargs)
        self.directory = directory
        self.pairs = pairs

        for ncfile, variable in self.pairs:
            self.logger.debug(f"Plotting {ncfile}:{variable}")

    def run(self):

        nrows = len(self.pairs)

        # make sure the plots share the same time range
        self.fig, self.ax = plt.subplots(
            nrows=nrows, sharex=True, figsize=(10, 6)
        )

        # force ax to be iterable in the case just a single pair is given.
        if nrows == 1:
            self.ax = [self.ax]

        # Go through each pair, plot them together in a twin plot.
        for ax1, pair in zip(self.ax, self.pairs):

            # construct the full path to the 1st netCDF file
            ncfile, data_variable1 = pair[0]
            ncfile1 = self.directory / ncfile

            data1, data_source1 = self.get_data(ncfile1, data_variable1)

            # plot the first variable (blue-ish)
            self.plot(
                data1, data_variable1, data_source1, ax1, (0.30, 0.45, 0.69)
            )

            # instantiate a second axes that shares the same x-axis
            ax2 = ax1.twinx()

            # construct the full path to the 2nd netCDF file
            ncfile, data_variable2 = pair[1]
            ncfile2 = self.directory / ncfile

            data2, data_source2 = self.get_data(ncfile2, data_variable2)

            # plot the second variable (red-ish)
            self.plot(
                data2, data_variable2, data_source2, ax2, (0.87, 0.52, 0.32)
            )

            with xr.open_dataset(ncfile1) as ds1, xr.open_dataset(ncfile2) as ds2:  # noqa : E501
                try:
                    if ds1[data_variable1].standard_name == ds2[data_variable2].standard_name:  # noqa : E501
                        same_standard_name = True
                    else:
                        same_standard_name = False
                except AttributeError:
                    same_standard_name = False

            if data_variable1 == data_variable2 or same_standard_name:

                # make the ylims the same in this case
                ymin1, ymax1 = ax1.get_ylim()
                ymin2, ymax2 = ax2.get_ylim()

                ymin = min(ymin1, ymin2)
                ymax = max(ymax1, ymax2)

                ax1.set_ylim(ymin=ymin, ymax=ymax)
                ax2.set_ylim(ymin=ymin, ymax=ymax)

        self.fig.tight_layout()

    def get_data(self, ncfile, data_variable):
        """
        Retrieve the data, take out anything with bad QC.

        Parameters
        ----------
        ncfile : path
            a netCDF file
        data_variable : str
            a data variable within the netCDF file

        Returns
        -------
        pandas.Series timeseries of the data.  The name of the variable is
        in the name attribute, and we place the "data_source" attribute in
        there as well.
        """

        with xr.open_dataset(ncfile) as ds:
            data_source = ds.data_source

            data = ds[data_variable].to_series()

            # get the data quality, anything with non-zero quality flag will
            # be considered bad
            try:
                qc = None
                for ancvar in ds[data_variable].ancillary_variables.split():
                    if ds[ancvar].standard_name == 'status_flag':
                        qc = ds[ancvar].to_series()
            except AttributeError:
                pass
            else:
                if qc is not None:
                    data[qc != core.quality.GOOD] = np.nan

        return data, data_source

    def plot(self, ts, data_variable, data_source, ax, color):
        """
        Parameters
        ----------
        ts : pandas.Series
            timeseries for the feature variable
        data_variable: str
            a data variable within the netCDF file
        data_source: str
            e.g. 'met' or 'licor', etc.
        ax : matplotlib.axes.Axes
            a pair of variables are plotted in this axis
        color : 3-tuple
            RGB color for the plot
        """

        ts.plot(ax=ax, color=color)
        ax.tick_params(axis='y', labelcolor=color)

        ylabel = f"{data_source}\n{data_variable}"
        ax.set_ylabel(ylabel, color=color)
