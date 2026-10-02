""" """
# Standard library imports
import time

# 3rd party library imports
from IPython.display import display
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import xarray as xr

# Local imports
from xco2qc import core
from xco2qc.qc import QCCore


class QCPlots(QCCore):
    """
    Create plots for QC checks performed in the automatic QC.

    Attributes
    ----------
    src_dir : pathlib paths
        Paths to the netCDF files.
    """
    def __init__(self, src_dir, use_colorblind=False, verbosity=None, **kwargs):
        super().__init__(
            src_dir, verbosity=verbosity, logger_name='qc-plots', **kwargs
        )

        self.figsize = (8, 6)
        self.color_palette = None if not use_colorblind else "colorblind"
        self.palette = sns.color_palette(palette=self.color_palette, n_colors=2)

    def run(self):
        """
        Run QC checks.
        """
        self.logger.info("Beginning QC Plots...")

        if self._is_notebook:
            self.loss_of_span_plot()
            self.zpoff_xco2_range_plot()
            self.zpostcal_xco2_range_plot()
            self.spoff_spostcal_xco2_in_span_range_plot()
            self.epoff_xco2_stddev_plot()
            self.apoff_xco2_stddev_plot()
            self.apoff_spoff_epoff_pressure_differences_plot()
            self.epoff_epon_pressure_differences_plot()
            self.apoff_apon_pressure_differences_plot()
            self.spoff_spon_pressure_differences_plot()

            self.rh_stddev_plot(core.licor.APOFF_NCFILE)
            self.rh_stddev_plot(core.licor.EPOFF_NCFILE)
            self.rh_stddev_plot(core.licor.SPOFF_NCFILE)

            self.rh_temp_stddev_plot(core.licor.APOFF_NCFILE)
            self.rh_temp_stddev_plot(core.licor.EPOFF_NCFILE)
            self.rh_temp_stddev_plot(core.licor.SPOFF_NCFILE)

    def rh_temp_stddev_plot(self, stem):
        """
        Parameters
        ----------
        stem : str
            This will the basename one of the LICOR netCDF files.
        """

        ncfile = self.src_dir / stem
        label = core.mapco2core.file2label(ncfile)

        fig, ax = plt.subplots(figsize=self.figsize)

        with xr.open_dataset(ncfile) as ds1:
            data = ds1['rh_temp_stddev'].to_series()

        data.plot(ax=ax, color=self.palette[0])

        xmin, xmax = ax.get_xlim()
        ax.hlines(0, xmin, xmax, colors=self.palette[1])
        ax.hlines(self.max_rh_std, xmin, xmax, colors=self.palette[1])

        ax.set_title(f'{label} RH TEMP STDDEV')
        
        display(fig)

    def rh_stddev_plot(self, stem):

        ncfile = self.src_dir / stem
        label = core.mapco2core.file2label(ncfile)

        fig, ax = plt.subplots(figsize=self.figsize)

        with xr.open_dataset(ncfile) as ds1:
            data = ds1['rh_stddev'].to_series()

        data.plot(ax=ax, color=self.palette[0])

        xmin, xmax = ax.get_xlim()
        ax.hlines(0, xmin, xmax, colors=self.palette[1])
        ax.hlines(self.max_rh_std, xmin, xmax, colors=self.palette[1])

        ax.set_title(f'{label} RH STDDEV')
        
        display(fig)

    def epoff_epon_pressure_differences_plot(self):

        ncfile1 = self.src_dir / core.licor.EPOFF_NCFILE
        ncfile2 = self.src_dir / core.licor.EPON_NCFILE

        min_diff = self.equil_diff_range_lower
        max_diff = self.equil_diff_range_higher

        self._pressure_off_difference_plot(
            ncfile1, ncfile2, "EPOFF", "EPON",
            min_diff=min_diff, max_diff=max_diff
        )

    def apoff_apon_pressure_differences_plot(self):

        ncfile1 = self.src_dir / core.licor.APOFF_NCFILE
        ncfile2 = self.src_dir / core.licor.APON_NCFILE

        min_diff = self.air_diff_range_lower
        max_diff = self.air_diff_range_higher

        self._pressure_off_difference_plot(
            ncfile1, ncfile2, "APOFF", "APON",
            min_diff=min_diff, max_diff=max_diff
        )

    def spoff_spon_pressure_differences_plot(self):

        ncfile1 = self.src_dir / core.licor.SPOFF_NCFILE
        ncfile2 = self.src_dir / core.licor.SPON_NCFILE

        min_diff = self.span_diff_range_lower
        max_diff = self.span_diff_range_higher

        self._pressure_off_difference_plot(
            ncfile1, ncfile2, "SPOFF", "SPON",
            min_diff=min_diff, max_diff=max_diff
        )

    def apoff_spoff_epoff_pressure_differences_plot(self):

        nc_apoff = self.src_dir / core.licor.APOFF_NCFILE
        nc_epoff = self.src_dir / core.licor.EPOFF_NCFILE
        nc_spoff = self.src_dir / core.licor.SPOFF_NCFILE

        self._pressure_off_difference_plot(
            nc_apoff, nc_epoff, "APOFF", "EPOFF",
            min_diff=0, max_diff=self.max_pressoff_diff
        )
        self._pressure_off_difference_plot(
            nc_apoff, nc_spoff, "APOFF", "SPOFF",
            min_diff=0, max_diff=self.max_pressoff_diff
        )
        self._pressure_off_difference_plot(
            nc_epoff, nc_spoff, "EPOFF", "SPOFF",
            min_diff=0, max_diff=self.max_pressoff_diff
        )

    def _pressure_off_difference_plot(
        self, ncfile1, ncfile2, label1, label2, min_diff=None, max_diff=None
    ):
        """
        Plot the difference between two pressure time series.
        """

        fig, ax = plt.subplots(figsize=self.figsize)

        with xr.open_dataset(ncfile1) as ds1:
            press1 = ds1['pressure'].to_series()
        with xr.open_dataset(ncfile2) as ds2:
            press2 = ds2['pressure'].to_series()

        # The two time series indices are usually not the same (off by one
        # minute?).  Just reindex the first one.
        press1 = press1.reindex(press2.index, method='nearest')

        delta = np.abs(press1 - press2)
        delta.plot(ax=ax, color=self.palette[0])

        if min_diff is not None and max_diff is not None:
            # plot the allowed range of values
            xmin, xmax = ax.get_xlim()
            ax.hlines(min_diff, xmin, xmax, colors=self.palette[1])
            ax.hlines(max_diff, xmin, xmax, colors=self.palette[1])

        ax.set_title(f'{label1}/{label2} Pressure Difference')
        
        display(fig)

    def apoff_xco2_stddev_plot(self):

        fig, ax = plt.subplots(figsize=self.figsize)

        ncfile = self.src_dir / core.licor.APOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ds['xco2_wet_stddev'].plot(ax=ax, color=self.palette[0])

        # Plot the maximum allowed value
        xmin, xmax = ax.get_xlim()
        ax.hlines(0, xmin, xmax, color=self.palette[1])
        ax.hlines(self.max_air_xco2_std, xmin, xmax, color=self.palette[1])

        ax.set_title('APOFF xCO2 Wet STDDEV')
        
        display(fig)

    def epoff_xco2_stddev_plot(self):
        """
        Plot the standard deviation of the xco2 wet measurements.
        """

        fig, ax = plt.subplots(figsize=self.figsize)

        ncfile = self.src_dir / core.licor.EPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ds['xco2_wet_stddev'].plot(ax=ax, color=self.palette[0])

        xmin, xmax = ax.get_xlim()
        ax.hlines(0, xmin, xmax, color=self.palette[1])
        ax.hlines(self.max_equil_xco2_std, xmin, xmax, color=self.palette[1])

        ax.set_title('EPOFF xCO2 Wet STDDEV')
        
        display(fig)

    def spoff_spostcal_xco2_in_span_range_plot(self):

        self._xco2_in_span_range_plot(core.licor.SPOFF_NCFILE)
        self._xco2_in_span_range_plot(core.licor.SPOSTCAL_NCFILE)

    def _xco2_in_span_range_plot(self, filename):
        """
        Parameters
        ----------
        filename : str
            Basename of netCDF file, either SPOFF_NCFILE or SPOSTCAL_NCFILE.
        """

        fig, ax = plt.subplots(figsize=self.figsize)

        ncfile = self.src_dir / filename
        with xr.open_dataset(ncfile) as ds:
            ds['xco2_wet'].plot(ax=ax, color=self.palette[0])

        xmin, xmax = ax.get_xlim()
        span_range = [
            self.initial_span_cal - self.ppm_below_span_cal,
            self.initial_span_cal + self.ppm_above_span_cal,
        ]
        ax.hlines(span_range[0], xmin, xmax, colors=self.palette[1])
        ax.hlines(span_range[1], xmin, xmax, colors=self.palette[1])

        label = core.mapco2core.file2label(ncfile)
        title = (
            f'{label} xCO2 Wet Compared to Span Range '
            f'[{span_range[0]:.0f}, {span_range[1]:.0f}]'
        )
        ax.set_title(title)
        
        display(fig)

    def zpostcal_xco2_range_plot(self):

        fig, ax = plt.subplots(figsize=self.figsize)

        ncfile = self.src_dir / core.licor.ZPOSTCAL_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ds['xco2_wet'].plot(ax=ax, color=self.palette[0])

        ax.set_title('ZPOST CAL xCO2 Wet Range')

        xmin, xmax = ax.get_xlim()
        ax.hlines(-self.ppm_below_zero, xmin, xmax, colors=self.palette[1])
        ax.hlines(self.ppm_above_zero, xmin, xmax, colors=self.palette[1])
        
        display(fig)

    def zpoff_xco2_range_plot(self):

        fig, ax = plt.subplots(figsize=self.figsize)

        ncfile = self.src_dir / core.licor.ZPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ds['xco2_wet'].plot(ax=ax, color=self.palette[0])

        ax.set_title('ZPOFF xCO2 Wet Range')

        xmin, xmax = ax.get_xlim()
        ax.hlines(-self.ppm_below_zero, xmin, xmax, colors=self.palette[1])
        ax.hlines(self.ppm_above_zero, xmin, xmax, colors=self.palette[1])
        
        display(fig)

    def loss_of_span_plot(self):

        fig, ax = plt.subplots(nrows=2, sharex=True, figsize=self.figsize)

        ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            ds['span_flag'].plot(ax=ax[0], color=self.palette[0])
            ds['zero_flag'].plot(ax=ax[1], color=self.palette[0])

        fig.suptitle('Span Flag / Zero Flag')
        
        display(fig)
