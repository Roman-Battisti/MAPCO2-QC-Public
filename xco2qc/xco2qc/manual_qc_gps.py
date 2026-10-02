"""
Support for manual QC.  This can be run either from within a Jupyter notebook
or from the python command line.
"""
# standard library imports
import math
import pathlib
import time

# 3rd party library imports
from matplotlib.path import Path
import matplotlib.pyplot as plt
from matplotlib.widgets import PolygonSelector
import netCDF4
import numpy as np
import seaborn as sns
import xarray as xr

# local imports
from xco2qc import core


class ManualGpsQC(core.MapCO2core):
    """
    This class is a special case of the polygon selector that is used only on
    gps lat/lon pairs.  It will mask out values that we choose.

    Parameters
    ----------
    ncfile : path
        Path to netCDF file
    fig, ax :
        matplotlib figure and associated axis
    ts, qc : pandas.Series
        time series for xCO2 data and QC
    poly : matplotlib.widgets.PolygonSelector
        Select a polygon region of an axes.
    """

    def __init__(self, ncfile, verbosity=None):
        super().__init__(verbosity=verbosity, logger_name='manual-gps')

        self.ncfile = pathlib.Path(ncfile)
        self.fig, self.ax = plt.subplots(figsize=(8, 6))

        self.first_time = True

    def reload(self):
        self.logger.info('Reloading...')
        with xr.open_dataset(self.ncfile) as ds:
            self.lon = ds['longitude'].to_series()
            self.lon_qc = ds['longitude_qc'].to_series().astype(np.uint32)  # noqa : E501
            self.lat = ds['latitude'].to_series()
            self.lat_qc = ds['latitude_qc'].to_series().astype(np.uint32)  # noqa : E501

    def run(self):

        self.logger.info('Running...')

        # The first time through, we should remove the manual flag bit.
        # This allows us to "start over" with no flags set.
        if self.first_time:
            self.logger.info('Clearing GPS QC flags...')
            self.reset_qc()
            self.first_time = False

        self.reload()
        self.plot()

    def plot(self):

        self.logger.info('Plotting...')

        # we only want to plot where QC is good
        lat = self.lat.copy()
        lon = self.lon.copy()
        lat[self.lat_qc != core.quality.GOOD] = np.nan
        lon[self.lon_qc != core.quality.GOOD] = np.nan

        self.ax.cla()
        sns.scatterplot(x=lon, y=lat, ax=self.ax, alpha=0.3)
        self.ax.set_title('GPS Watch Circle')

        # Add a red X for the center.
        mean_lon, mean_lat = lon.mean(), lat.mean()
        red = (0.77, 0.31, 0.32)
        self.ax.plot(
            mean_lon, mean_lat, color=red, marker='o', fillstyle='full'
        )
        self.ax.plot(
            mean_lon, mean_lat, color=red, marker='x', markersize=12
        )

        # has the data been entirely masked out?
        if lon.isnull().sum() == len(lon) and lat.isnull().sum() == len(lat):
            # there is nothing more we can do if all the data has been masked
            self.ax.set_title('GPS Watch Circle: all GPS data has been masked')
            return

        # Center the data, use margins of 10%.  Use this margin to locate
        # the xticks and yticks as well.
        scale = 0.10

        # force the axis to be centered on the data
        lonmin, lonmax = np.nanmin(lon), np.nanmax(lon)
        dx = lonmax - lonmin
        xlim = (lonmin - scale * dx, lonmax + scale * dx)

        latmin, latmax = np.nanmin(lat), np.nanmax(lat)
        dy = latmax - latmin
        ylim = (latmin - scale * dy, latmax + scale * dy)

        if xlim[0] == xlim[1]:
            # If the data is all the same, i.e. all the gps values are 0, then
            # we need to adjust the axis limits to avoid an unsettling warning.
            xlim = xlim[0] - 1, xlim[1] + 1

        if ylim[0] == ylim[1]:
            ylim = ylim[0] - 1, ylim[1] + 1

        self.ax.set_xlim(left=xlim[0], right=xlim[1])
        self.ax.set_ylim(bottom=ylim[0], top=ylim[1])

        # include x and y extents in the labels to give an idea of scale
        d = great_earth_distance(xlim[0], ylim[0], xlim[1], ylim[0])
        self.ax.set_xlabel(f"Longitudinal Distance:  {d:.2f} nautical miles")

        d = great_earth_distance(xlim[0], ylim[0], xlim[0], ylim[1])
        self.ax.set_ylabel(f"Latitudinal Distance:  {d:.2f} nautical miles")

        # The default ticks are often kind of tough to read due to the small
        # scale.  Just use 3 on both the x and y axis.
        def format_func(value, tick_number):
            return f"{value:.4f}"

        self.ax.xaxis.set_major_formatter(plt.FuncFormatter(format_func))
        self.ax.yaxis.set_major_formatter(plt.FuncFormatter(format_func))

        (xmin, xmax), xticks = self.ax.get_xlim(), self.ax.get_xticks()
        xticks = [xmin + scale * dx, mean_lon, xmax - scale * dx]
        self.ax.set_xticks(xticks)

        (ymin, ymax), yticks = self.ax.get_ylim(), self.ax.get_yticks()
        yticks = [ymin + scale * dy, mean_lat, ymax - scale * dy]
        self.ax.set_yticks(yticks)

        plt.tight_layout()

        self.poly = PolygonSelector(self.ax, self.onselect)
        
        if self._is_notebook:
            time.sleep(0.5)
            plt.show()

    def onselect(self, verts):
        """
        Toggle the points within the selected polygon.

        Parameters
        ----------
        verts : list
            list of (xdata, ydata) tuples.
        """
        self.logger.info(f'Masking points enclosed in {verts}...')

        path = Path(verts)

        # find the points that fall within the polygon and toggle the flag
        data = np.array(list(zip(self.lon, self.lat)))
        idx = np.nonzero(path.contains_points(data))[0]

        self.logger.info(
            f'Flagging {len(idx)} points captured within latest polygon'
        )

        with netCDF4.Dataset(self.ncfile, mode='r+') as nc:

            for qcvar in [
                'latitude_qc', 'longitude_qc'
            ]:
                qc = nc[qcvar][:]
                qc[idx] = np.bitwise_xor(
                    # remove the GOOD flag
                    np.bitwise_xor(qc[idx], core.quality.GOOD),
                    core.quality.MANUALLY_FLAGGED
                )

                nc[qcvar][:] = qc

        # Go again.
        self.run()

    def reset_qc(self):
        """
        Unset the core.quality.MANUALLY_FLAGGED bit.
        """
        with netCDF4.Dataset(self.ncfile, mode='r+') as nc:

            for qcvar in [
                'latitude_qc', 'longitude_qc'
            ]:
                qc = nc[qcvar][:]

                # where is the core.quality.MANUALLY_FLAGGED flag set?
                idx = np.nonzero(
                    np.bitwise_and(qc, core.quality.MANUALLY_FLAGGED)
                )
                idx = idx[0]

                # flip only those elements.
                qc[idx] = np.bitwise_xor(
                    qc[idx], core.quality.MANUALLY_FLAGGED
                )

                nc[qcvar][:] = qc


def great_earth_distance(x1, y1, x2, y2):
    x1 = math.radians(x1)
    x2 = math.radians(x2)
    y1 = math.radians(y1)
    y2 = math.radians(y2)

    a = (
        math.sin((x2 - x1) / 2.0) ** 2.0
        + (math.cos(x1) * math.cos(x2)
            * (math.sin((y2 - y1) / 2.0) ** 2.0))
    )

    # great circle distance in radians
    angle2 = 2.0 * math.asin(min(1.0, math.sqrt(a)))

    # convert back to degrees
    angle2 = math.degrees(angle2)

    # Each degree on a great circle of Earth is 60 nautical miles
    distance2 = 60.0 * angle2
    return distance2
