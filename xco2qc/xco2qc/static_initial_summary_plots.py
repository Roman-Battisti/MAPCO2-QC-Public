# standard library imports
import importlib.resources as ir
import math
import time

# 3rd party library imports
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import seaborn as sns
import xarray as xr
import yaml

# local imports
from . import core
from . import data_common
from .mbl import MBL

# don't print warnings about too many figure windows being kept open.
plt.rcParams.update({'figure.max_open_warning': 0})


class StaticInitialSummaryPlots(data_common.DataCommon):
    """
    Attributes
    ----------
    figsize : tuple
        width and height of plots in inches
    """

    def __init__(self, src_dir, figsize=(8, 6), use_colorblind=False, verbosity=None):
        super().__init__(
            verbosity=verbosity, logger_name='static-initial-plots',
            src_dir=src_dir
        )

        self.figsize = figsize

        self.retrieve_remote = False
        if use_colorblind:
            plt.style.use('tableau-colorblind10')
            self.color_palette = "colorblind"
        else:
            plt.style.use('default')
            self.color_palette = None

        self.palette = sns.color_palette(palette=self.color_palette, n_colors=4)

        if self.historical_ncfile.exists():
            with xr.open_dataset(self.historical_ncfile) as ds:
                ds = ds.load()
                if 'station_id' in ds:
                    ds = ds.drop_vars('station_id')
                if 'rowSize' in ds:
                    ds = ds.drop_vars('rowSize')
                self.historical_df = ds.to_dataframe()
                if 'time' in self.historical_df.columns:
                    # This will only be true of the ERDDAP historical file,
                    # not the PMEL text file.
                    self.historical_df = self.historical_df.set_index('time')
        else:
            self.logger.warning('No historical data provided.')
            self.historical_df = None

        with xr.open_dataset(self.cycle_header_ncfile) as ds:
            station_lat = ds['latitude'].mean()

        mbl = MBL(retrieve_remote=False)
        self.mbl = mbl.interpolate_to_latitude(station_lat)

    def run(self):

        self.plot_full_time_series()
        self.plot_year_overlay_plots()
        self.plot_current_deployment_diagnostics()
        self.plot_property_property()
        self.plot_gps_coordinates()

    def plot_gps_coordinates(self):

        fig, ax1 = plt.subplots(figsize=self.figsize)

        with xr.open_dataset(self.cycle_header_ncfile) as ds:
            df = ds.to_dataframe()
            df = df.query('latitude != 0 and longitude != 0')
            lat = df['latitude']
            lon = df['longitude']

        ax1.cla()
        sns.scatterplot(x=lon, y=lat, ax=ax1, alpha=0.3, palette=self.color_palette)
        ax1.set_title('GPS Watch Circle')

        # Add a red X for the center.
        mean_lon, mean_lat = lon.mean(), lat.mean()
        red = (0.77, 0.31, 0.32)
        ax1.plot(
            mean_lon, mean_lat, color=red, marker='o', fillstyle='full'
        )
        ax1.plot(
            mean_lon, mean_lat, color=red, marker='x', markersize=12
        )

        # has the data been entirely masked out?
        if lon.isnull().sum() == len(lon) and lat.isnull().sum() == len(lat):
            # there is nothing more we can do if all the data has been masked
            ax1.set_title('GPS Watch Circle: all GPS data has been masked')
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

        ax1.set_xlim(left=xlim[0], right=xlim[1])
        ax1.set_ylim(bottom=ylim[0], top=ylim[1])

        # include x and y extents in the labels to give an idea of scale
        d = great_earth_distance(xlim[0], ylim[0], xlim[1], ylim[0])
        ax1.set_xlabel(f"Longitudinal Distance:  {d:.2f} nautical miles")

        d = great_earth_distance(xlim[0], ylim[0], xlim[0], ylim[1])
        ax1.set_ylabel(f"Latitudinal Distance:  {d:.2f} nautical miles")

        # The default ticks are often kind of tough to read due to the small
        # scale.  Just use 3 on both the x and y axis.
        def format_func(value, tick_number):
            return f"{value:.4f}"

        ax1.xaxis.set_major_formatter(plt.FuncFormatter(format_func))
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(format_func))

        (xmin, xmax), xticks = ax1.get_xlim(), ax1.get_xticks()
        xticks = [xmin + scale * dx, mean_lon, xmax - scale * dx]
        ax1.set_xticks(xticks)

        (ymin, ymax), yticks = ax1.get_ylim(), ax1.get_yticks()
        yticks = [ymin + scale * dy, mean_lat, ymax - scale * dy]
        ax1.set_yticks(yticks)

        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_property_property(self):
        self.plot_property_property_sw_xco2_vs_sst()
        self.plot_property_property_o2_vs_sst()
        self.plot_property_property_sw_xco2_vs_ph()

    def plot_property_property_sw_xco2_vs_ph(self):

        with xr.open_dataset(self.epoff_ncfile) as ds:
            ds = ds.load()
            xco2 = self.get_good_ts(ds=ds, varname='xco2_dry')
            xco2_units = ds['xco2_dry'].units

        ph_varname, ncfile = self.determine_src_ph_ncfile()
        if ncfile is None:
            msg = (
                "No source for pH data exists, so no SW xCO2 vs pH plot will "
                "be produced."
            )
            self.logger.warning(msg)
            return

        with xr.open_dataset(ncfile) as ds:
            ds = ds.load()
            ph = self.get_good_ts(ds=ds, varname=ph_varname)
            ph_units = ""  # ds[ph_varname].units

        ph = ph.reindex(xco2.index, method='nearest')

        fig, ax = plt.subplots(figsize=self.figsize)
        title = 'Current Deployment: SW xCO2 (dry) vs pH'
        ax.set_title(title)
        sns.scatterplot(x=xco2, y=ph, ax=ax, palette=self.color_palette)
        ax.set_xlabel(f"xco2_dry ({xco2_units})")
        ax.set_ylabel(f"pH")
        ax.invert_yaxis()
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_property_property_o2_vs_sst(self):
        """
        Make a scatterplot of O2 vs. SST.
        """

        try:
            df = self._get_o2__measured_climatology_maxtec()
        except (FileNotFoundError, KeyError):
            msg = (
                'No O2 data is not available.  '
                'No O2 vs SST plot will be produced.'
            )
            self.logger.warning(msg)
            return
        else:
            o2_units = self.get_units('sbe16.yml', 'o2')

        try:
            dfmet = self._get_met_data()
        except FileNotFoundError:
            msg = (
                'No MET file exists, so no O2 vs SST property plot will be '
                'produced.'
            )
            self.logger.warning(msg)
            return
        else:
            df['sst'] = dfmet['SST'].reindex(df.index, method='nearest')
            sst_units = self.get_units('met.yml', 'SST')

        fig, ax1 = plt.subplots(figsize=self.figsize)
        sns.scatterplot(data=df, x='o2', y='sst', ax=ax1, palette=self.color_palette)
        ax1.set_title('Current Deployment: O2 vs SST')
        ax1.set_xlabel(f'o2 {o2_units}')
        ax1.set_ylabel(f'SST {sst_units}')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_property_property_sw_xco2_vs_sst(self):

        with xr.open_dataset(self.epoff_ncfile) as ds:
            ds = ds.load()
            df = self.get_good_ts(ds=ds, varname='xco2_dry').to_frame()
            xco2_units = ds['xco2_dry'].units

        try:
            dfmet = self._get_met_data()
        except FileNotFoundError:
            msg = (
                'No met file exists.  No SW xCO2 vs SST property plot will '
                'be produced.'
            )
            self.logger.warning(msg)
            return
        else:
            df['sst'] = dfmet['SST'].reindex(df.index, method='nearest')
            sst_units = self.get_units('met.yml', 'SST')

        fig, ax1 = plt.subplots(figsize=self.figsize)
        sns.scatterplot(data=df, x='xco2_dry', y='sst', ax=ax1, palette=self.color_palette)
        ax1.set_title('Current Deployment: SW xCO2 (dry) vs SST')
        ax1.set_xlabel(f"xco2_dry ({xco2_units})")
        ax1.set_ylabel(f"SST ({sst_units})")
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics(self):
        self.plot_current_deployment_diagnostics_pump_on_pressures()
        self.plot_current_deployment_diagnostics_pump_off_pressures()
        self.plot_current_deployment_diagnostics_pump_off_on_pressures()
        self.plot_current_deployment_diagnostics_logic_and_xmitter_voltage()
        self.plot_current_deployment_diagnostics_rh_all_cycles()
        self.plot_current_deployment_diagnostics_rh_temp()
        self.plot_current_deployment_diagnostics_rh_stddev()
        self.plot_current_deployment_diagnostics_rh_temp_stddev()
    
    def plot_pump_qc(self):
        self.plot_current_deployment_diagnostics_pump_off_on_pressures()
    
    def plot_current_deployment_diagnostics_logic_and_xmitter_voltage(self):
        """
        logic and transmitter battery voltage
        """
        with xr.open_dataset(self.cycle_header_ncfile) as ds:
            df = ds.load().to_dataframe()

            if 'battery_logic' not in df or 'battery_trans' not in df:
                msg = (
                    f"No battery logic or battery_trans in "
                    f"{self.cycle_header_ncfile}.  No plot will be created."
                )
                self.logger.warning(msg)
                return

        fig, ax1 = plt.subplots(figsize=self.figsize)

        df['battery_logic'].plot(ax=ax1, color=self.palette[0])
        df['battery_trans'].plot(ax=ax1, color=self.palette[1])

        ax1.legend()
        ax1.set_ylabel('volts')

        ax1.set_title('Logic and Transmitter Battery Voltage')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics_rh_temp_stddev(self):
        """
        RH temp stddev, air and equil cycles
        """
        fig, ax1 = plt.subplots(figsize=self.figsize)

        files = [
            core.licor.APOFF_NCFILE, core.licor.APON_NCFILE,
            core.licor.EPOFF_NCFILE, core.licor.EPON_NCFILE,
        ]
        labels = [
            'apoff', 'apon',
            'epoff', 'epon',
        ]
        for stem, label in zip(files, labels):

            ncfile = self.src_dir / stem
            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                rh_temp = self.get_good_ts(ds=ds, varname='rh_temp_stddev')
                ax1.plot(rh_temp.index, rh_temp, label=label)

        h, _ = ax1.get_legend_handles_labels()
        ax1.legend(h, labels)

        ax1.set_title('RH temperature STDDEV')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics_rh_temp(self):
        """
        RH temp, air and equil cycles
        """
        fig, ax1 = plt.subplots(figsize=self.figsize)

        files = [
            core.licor.APOFF_NCFILE, core.licor.APON_NCFILE,
            core.licor.EPOFF_NCFILE, core.licor.EPON_NCFILE,
        ]
        labels = [
            'apoff', 'apon',
            'epoff', 'epon',
        ]
        for stem, label in zip(files, labels):

            ncfile = self.src_dir / stem
            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                rh_temp = self.get_good_ts(ds=ds, varname='rh_temp')
                units = ds['rh_temp'].units
                ax1.plot(rh_temp.index, rh_temp, label=label)

        h, _ = ax1.get_legend_handles_labels()
        ax1.legend(h, labels)
        ax1.set_ylabel(units)

        ax1.set_title('RH temperature')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics_rh_stddev(self):
        """
        RH stddev (all cycles)
        """
        fig, ax1 = plt.subplots(figsize=self.figsize)

        files = [
            core.licor.APOFF_NCFILE, core.licor.APON_NCFILE,
            core.licor.EPOFF_NCFILE, core.licor.EPON_NCFILE,
            core.licor.ZPOFF_NCFILE, core.licor.ZPON_NCFILE,
            core.licor.SPOFF_NCFILE, core.licor.SPON_NCFILE
        ]
        labels = [
            'apoff', 'apon',
            'epoff', 'epon',
            'zpoff', 'zpon',
            'spoff', 'spon',
        ]
        for stem, label in zip(files, labels):

            ncfile = self.src_dir / stem
            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                rh_stddev = self.get_good_ts(ds=ds, varname='rh_stddev')
                ax1.plot(rh_stddev.index, rh_stddev, label=label)

        h, _ = ax1.get_legend_handles_labels()
        ax1.legend(h, labels)

        ax1.set_title('RH STDDEV (all cycles)')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics_rh_all_cycles(self):
        """
        RH (all cycles)
        """
        fig, ax1 = plt.subplots(figsize=self.figsize)

        files = [
            core.licor.APOFF_NCFILE, core.licor.APON_NCFILE,
            core.licor.EPOFF_NCFILE, core.licor.EPON_NCFILE,
            core.licor.ZPOFF_NCFILE, core.licor.ZPON_NCFILE,
            core.licor.SPOFF_NCFILE, core.licor.SPON_NCFILE
        ]
        labels = [
            'apoff', 'apon',
            'epoff', 'epon',
            'zpoff', 'zpon',
            'spoff', 'spon',
        ]
        for stem, label in zip(files, labels):

            ncfile = self.src_dir / stem
            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                rh = ds['rh'].to_series()
                ax1.plot(rh.index, rh, label=label)

        h, _ = ax1.get_legend_handles_labels()
        ax1.legend(h, labels)
        ax1.set_ylabel('Percent')

        ax1.set_title('RH (all cycles)')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics_pump_off_on_pressures(self):
        """
        air, equil, zero, span DIFFERENCES in pressure
        """
        # fig, ax1 = plt.subplots(figsize=self.figsize)
        
        fig, axes = plt.subplots(figsize=self.figsize, nrows=4, sharex=True)
        
        file_pairs = [
            (core.licor.APOFF_NCFILE, core.licor.APON_NCFILE),
            (core.licor.EPOFF_NCFILE, core.licor.EPON_NCFILE),
            (core.licor.ZPOFF_NCFILE, core.licor.ZPON_NCFILE),
            (core.licor.SPOFF_NCFILE, core.licor.SPON_NCFILE)
        ]
        labels = ['air', 'equil', 'zero', 'span']
        c = ['b', 'orange', 'g', 'r']
        for i, ((off_stem, on_stem), label) in enumerate(zip(file_pairs, labels)):

            ncfile = self.src_dir / off_stem
            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                off_data = self.get_good_ts(ds=ds, varname='pressure')
                units = ds['pressure'].units

            ncfile = self.src_dir / on_stem
            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                on_data = self.get_good_ts(ds=ds, varname='pressure')

            # force the "on" data to have exactly the same time index as the
            # off data
            on_data.index = off_data.index
            difference = off_data - on_data
            # ax1.plot(difference.index, difference, label=label)
            axes[i].plot(difference.index, difference, c=self.palette[i], label=label[i])
            
            h, _ = axes[i].get_legend_handles_labels()
            axes[i].legend(h, [labels[i]])
            axes[i].set_ylabel(units)
        # h, _ = ax1.get_legend_handles_labels()
        # ax1.legend(h, labels)
        # ax1.set_ylabel(units)

        # ax1.set_title('Pump Off-On Pressures')
        # handles, labels = axes[-1].get_legend_handles_labels()
        # fig.legend(handles, labels, loc="upper right")
        fig.suptitle('Pump Off-On Pressures')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics_pump_off_pressures(self):
        """
        air, equil, zero, span
        """
        fig, ax1 = plt.subplots(figsize=self.figsize)

        file_stems = [
            core.licor.APOFF_NCFILE, core.licor.EPOFF_NCFILE,
            core.licor.ZPOFF_NCFILE, core.licor.SPOFF_NCFILE
        ]
        labels = [
            'APOFF Pressure', 'EPOFF PRESSURE', 'ZPOFF Pressure',
            'SPOFF Pressure'
        ]
        for file_stem, label in zip(file_stems, labels):
            ncfile = self.src_dir / file_stem

            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                pressure = self.get_good_ts(ds=ds, varname='pressure')
                units = ds['pressure'].units
                ax1.plot(pressure.index, pressure, label=label)

        h, _ = ax1.get_legend_handles_labels()
        ax1.legend(h, labels)
        ax1.set_ylabel(units)

        ax1.set_title('Pump Off Pressures')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_current_deployment_diagnostics_pump_on_pressures(self):
        """
        air, equil, zero, span
        """
        fig, ax1 = plt.subplots(figsize=self.figsize)

        file_stems = [
            core.licor.APON_NCFILE, core.licor.EPON_NCFILE,
            core.licor.ZPON_NCFILE, core.licor.SPON_NCFILE
        ]
        labels = [
            'APON Pressure', 'EPON PRESSURE', 'ZPON Pressure', 'SPON Pressure'
        ]
        for file_stem, label in zip(file_stems, labels):
            ncfile = self.src_dir / file_stem

            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                ts = self.get_good_ts(ds=ds, varname='pressure')
                ax1.plot(ts.index, ts, label=label)
                ylabel = ds['pressure'].units

        h, _ = ax1.get_legend_handles_labels()
        ax1.legend(h, labels)
        ax1.set_ylabel(ylabel)

        ax1.set_title('Pump On Pressures')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_full_time_series(self):
        self.plot_sw_xco2_and_ph()
        self.plot_air_xco2_and_mbl()
        self.plot_sst_and_sss()
        self.plot_measured_ph_and_calculated_ph()
        self.plot_o2_measured_o2_climatology_maxtec_o2()
        self.plot_chl_all_chl_nighttime_only_chl_climatology()
        self.plot_ntu()

    def plot_year_overlay_plots(self):
        self.year_overlay_plots_air_xco2()
        self.year_overlay_plots_sw_xco2()
        self.year_overlay_plots_ph()
        self.year_overlay_plots_sst()
        self.year_overlay_plots_sss()
        self.year_overlay_plots_o2_measured()
        self.year_overlay_plots_chl_nighttime()
        self.year_overlay_plots_ntu()

    def _yearly_overlay_plot_deployment(self, ncfile, ax, parameter):

        with xr.open_dataset(ncfile) as ds:
            ds = ds.load()

            try:
                deployment_data = self.get_good_ts(ds=ds, varname=parameter)
            except KeyError as e:
                self.logger.warning(f'{e}:  no {parameter} in {ncfile}')
                return

            deployment_data = deployment_data.reset_index()

        years = deployment_data['time'].dt.year.unique()
        for year in years:
            df = deployment_data[deployment_data['time'].dt.year == year]
            df = df.copy()

            # Set the year to be the first one, that way they can be plotted
            # together.  Doesn't really matter what year we choose, so just
            # choose 2000.
            df['time'] = df['time'].apply(lambda dt: dt.replace(year=2000))

            s = df.set_index('time')[parameter]
            ax.plot(s.index, s, label=f"Deployment {year}")

    def _yearly_overlay_plot_historical(self, ncfile, ax, parameter):

        if ncfile is None or not ncfile.exists():
            self.logger.warning('There was no historical data.')
            return

        with xr.open_dataset(ncfile) as ds:
            ds = ds.load()
            if 'station_id' in ds:
                ds = ds.drop_vars('station_id')
            if 'rowSize' in ds:
                ds = ds.drop_vars('rowSize')

            df = ds.to_dataframe()
            if 'time' in df.columns:
                # erddap case
                df = df[['time', parameter]]
            else:
                # text file case
                df = df[parameter].reset_index()

            if hasattr(ds[parameter], 'valid_range'):
                valid_min, valid_max = ds[parameter].valid_range
                df[df[parameter] < valid_min] = np.nan
                df[df[parameter] > valid_max] = np.nan

            historical_data = df

        years = historical_data['time'].dt.year.unique()
        for year in years:
            df = historical_data[historical_data['time'].dt.year == year]
            df = df.copy()

            # Set the year to be the first one, that way they can be plotted
            # together
            df['time'] = df['time'].apply(lambda dt: dt.replace(year=2000))

            ax.plot(df['time'], df[parameter], label=f"Historical {year}")

    def year_overlay_plots_sw_xco2(self):

        fig, ax = plt.subplots(figsize=self.figsize)

        try:

            self._yearly_overlay_plot_deployment(
                self.epoff_ncfile, ax, 'xco2_dry'
            )
            # self._yearly_overlay_plot_historical(
            #     self.historical_ncfile, ax, 'xCO2_air'
            # )  # Note: historic xCO2 SW does not exist, only pCO2 SW
            with xr.open_dataset(self.epoff_ncfile) as ds:
                ylabel = f"xco2_dry ({ds['xco2_dry'].units})"

        except (FileNotFoundError, KeyError) as err:
            msg = f'Encountered a problem:  {err}'
            self.logger.warning(msg)
            ylabel = ''
        else:
            # must fix the xticks, get rid of the year
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))
            ax.legend(bbox_to_anchor=(1.1, 1.05))

        ax.set_title('Year Overlays: SW xCO2')
        ax.set_ylabel(ylabel)
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def year_overlay_plots_air_xco2(self):

        fig, ax = plt.subplots(figsize=self.figsize)
        try:
            self._yearly_overlay_plot_deployment(
                self.apoff_ncfile, ax, 'xco2_dry'
            )
            self._yearly_overlay_plot_historical(
                self.historical_ncfile, ax, 'xCO2_air'
            )

        except (FileNotFoundError, KeyError) as err:
            msg = f'Encountered a problem:  {err}'
            self.logger.warning(msg)
            ylabel = ''
        else:
            # must fix the xticks, get rid of the year
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))
            ax.legend(bbox_to_anchor=(1.1, 1.05))

            with xr.open_dataset(self.apoff_ncfile) as ds:
                ylabel = f"xco2_dry ({ds['xco2_dry'].units})"

        ax.set_title('Year Overlays: Air xCO2')
        ax.set_ylabel(ylabel)
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def year_overlay_plots_ph(self):

        ph_varname, ncfile = self.determine_src_ph_ncfile()
        if ncfile is None:
            self.logger.warning('Could not locate ph data.')
            return

        fig, ax = plt.subplots(figsize=self.figsize)
        ax.set_title('Year Overlays: pH')

        self._yearly_overlay_plot_deployment(ncfile, ax, ph_varname)
        self._yearly_overlay_plot_historical(
            self.historical_ncfile, ax, 'pH_sw'
        )

        with xr.open_dataset(ncfile) as ds:
            ylabel = "pH"  # ds[ph_varname].units
            ax.set_ylabel(ylabel)

        # must fix the xticks, get rid of the year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))

        ax.legend(bbox_to_anchor=(1.1, 1.05))

        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def year_overlay_plots_sst(self):

        ncfile = self.get_met_ncfile()
        if not ncfile.exists():
            msg = (
                'No met netCDF file exists, so no overlay plot for SST '
                'will be produced.'
            )
            self.logger.warning(msg)
            return

        fig, ax = plt.subplots(figsize=self.figsize)
        self._yearly_overlay_plot_deployment(ncfile, ax, 'SST')
        self._yearly_overlay_plot_historical(self.historical_ncfile, ax, 'SST')

        with xr.open_dataset(ncfile) as ds:
            ylabel = f"SST ({ds['SST'].units})"
            ax.set_ylabel(ylabel)

        # must fix the xticks, get rid of the year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))

        ax.legend(bbox_to_anchor=(1.1, 1.05))
        ax.set_title('Year Overlays: SST')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def year_overlay_plots_sss(self):

        ncfile = self.get_met_ncfile()
        if not ncfile.exists():
            msg = (
                'No met netCDF file exists, so no overlay plot for SSS '
                'will be produced.'
            )
            self.logger.warning(msg)
            return

        fig, ax = plt.subplots(figsize=self.figsize)
        self._yearly_overlay_plot_deployment(ncfile, ax, 'SSS')
        self._yearly_overlay_plot_historical(self.historical_ncfile, ax, 'SSS')

        # must fix the xticks, get rid of the year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))

        ax.legend(bbox_to_anchor=(1.1, 1.05))
        ax.set_title('Year Overlays: SSS')
        ax.set_ylabel('SSS (PSU)')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def year_overlay_plots_o2_measured(self):

        ncfile = self.get_o2_ncfile()
        if not ncfile.exists():
            msg = (
                'No O2 data is not available.  '
                'No yearly O2 overlay plots will be produced.'
            )
            self.logger.warning(msg)
            return
        else:
            o2_units = self.get_units('sbe16.yml', 'o2')

        fig, ax = plt.subplots(figsize=self.figsize)

        self._yearly_overlay_plot_deployment(ncfile, ax, 'o2')
        ax.set_ylabel(f"O2 ({o2_units})")

        # No historical data for O2
        msg = 'No historical O2 data available for year overlay plots'
        self.logger.warning(msg)

        # must fix the xticks, get rid of the year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))

        ax.legend(bbox_to_anchor=(1.1, 1.05))
        ax.set_title('Year Overlays: Measured O2')

        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def year_overlay_plots_chl_nighttime(self):

        ncfile = self.sbe16_ncfile
        if not ncfile.exists():
            msg = (
                'No SBE16 netCDF file exists, so no year overlay plots of '
                'chl nighttime will be produced.'
            )
            self.logger.warning(msg)
            return

        with xr.open_dataset(ncfile) as ds:
            if 'chl_nighttime' not in ds:
                msg = (
                    'No chl_nighttime data available, so no year overlay '
                    'plots will be produced.'
                )
                self.logger.warning(msg)
                return

            ylabel = f"CHL ({ds['chl_nighttime'].units})"

        fig, ax = plt.subplots(figsize=self.figsize)

        self._yearly_overlay_plot_deployment(
            self.sbe16_ncfile, ax, 'chl_nighttime'
        )

        ax.set_ylabel(ylabel)

        # there is never any historical data for chl nighttime from erddap
        msg = 'No historical CHL data available for year overlay plots'
        self.logger.warning(msg)

        # must fix the xticks, get rid of the year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))

        ax.legend(bbox_to_anchor=(1.1, 1.05))
        ax.set_title('Year Overlays: Chl Nighttime')

        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def year_overlay_plots_ntu(self):

        ncfile = self.sbe16_ncfile
        if not ncfile.exists():
            msg = (
                'No SBE16 netCDF file exists, so no year overlay plots of '
                'NTU will be produced.'
            )
            self.logger.warning(msg)
            return

        with xr.open_dataset(ncfile) as ds:
            if 'ntu' not in ds:
                msg = (
                    'No ntu data available, so no year overlay '
                    'plots will be produced.'
                )
                self.logger.warning(msg)
                return

            ylabel = "NTU"  # ds['ntu'].units

        fig, ax = plt.subplots(figsize=self.figsize)

        self._yearly_overlay_plot_deployment(self.sbe16_ncfile, ax, 'ntu')
        ax.set_ylabel(ylabel)

        # there is never any historical data for ntu avail from erddap
        msg = 'No historical NTU data available for year overlay plots'
        self.logger.warning(msg)

        # must fix the xticks, get rid of the year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))

        ax.legend(bbox_to_anchor=(1.1, 1.05))
        ax.set_title('Year Overlays: NTU')

        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_o2_measured_o2_climatology_maxtec_o2(self):
        """
        O2-measured along with O2 climatology and Maxtec O2
        """

        try:
            df = self._get_o2__measured_climatology_maxtec()
        except (FileNotFoundError, KeyError) as e:
            self.logger.warning(f'{e}')
            return

        fig, ax1 = plt.subplots(figsize=self.figsize)
        df.plot(ax=ax1)
        ax1.legend(loc='best')
        ax1.set_title('Measured O2, O2 climatology, MAXTEC')

        path = ir.files('xco2qc.core.vardefs.config').joinpath('sbe16.yml')
        with path.open() as f:
            d = yaml.safe_load(f)
            o2_ylabel = d['o2']['attributes']['units']

        ax1.set_ylabel(o2_ylabel)
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_chl_all_chl_nighttime_only_chl_climatology(self):

        if not self.sbe16_ncfile.exists():
            msg = (
                'No SBE16 file, so no CHL nighttime vs CHL climatology plot '
                'will be produced.'
            )
            self.logger.info(msg)
            return

        with xr.open_dataset(self.sbe16_ncfile) as ds:
            ds = ds.load()
            try:
                chl = self.get_good_ts(ds=ds, varname='chl')
                chl_nighttime = self.get_good_ts(
                    ds=ds, varname='chl_nighttime'
                )
            except KeyError as e:
                self.logger.warning(f'{e}:  no chl in {self.sbe16_ncfile}')
                return

            chl_ylabel = f"CHL ({ds['chl'].units})"

        fig, ax1 = plt.subplots(figsize=self.figsize)

        ax1.plot(
            chl.index, chl, color=self.palette[0], label='deployment chl'
        )

        ax1.plot(
            chl_nighttime.index, chl_nighttime,
            color=self.palette[1],
            label='deployment chl nighttime',
        )

        try:
            s = self.get_chl_climatology(index=chl.index)
        except KeyError as e:
            self.logger.warning(f'{e}')
        else:
            ax1.plot(
                s.index, s,
                color=self.palette[2],
                label='CHL Climatology',
            )

        ax1.set_ylabel(chl_ylabel)

        ax1.legend(loc='best')

        ax1.set_title('CHL:  all, nighttime, climatology')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_measured_ph_and_calculated_ph(self):

        ph_varname, ncfile = self.determine_src_ph_ncfile()
        if ncfile is None:
            msg = (
                'No ph data was found, so no plot will be produced.'
                'plot will be produced'
            )
            self.logger.warning(msg)
            return

        fig, ax1 = plt.subplots(figsize=self.figsize)
        ax1.set_title('Measured and Historical pH')

        with xr.open_dataset(ncfile) as ds:
            ds = ds.load()
            ph = self.get_good_ts(ds=ds, varname=ph_varname)
            ph_ylabel = "pH"

        ax1.plot(ph.index, ph, color=self.palette[0], label='deployment pH')

        if self.historical_df is not None:
            ph_sw = self.historical_df['pH_sw']
            ax1.plot(
                ph_sw.index, ph_sw,
                color=self.palette[0],
                label='historical pH',
                linestyle='dashdot',
                alpha=0.5,
            )

        ax1.set_ylabel(ph_ylabel)

        ax1.legend(loc='upper left')

        # self.adjust_ylims([ax1])

        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_ntu(self):

        if not self.sbe16_ncfile.exists():
            msg = 'No NTU data was found, so no plot will be produced.'
            self.logger.warning(msg)
            return

        with xr.open_dataset(self.sbe16_ncfile) as ds:
            try:
                ntu = self.get_good_ts(ds=ds, varname='ntu')
                ntu_ylabel = "NTU"
            except KeyError as e:
                self.logger.warning(f'{e}:  no ntu in {self.sbe16_ncfile}')
                return

        fig, ax1 = plt.subplots(figsize=self.figsize)

        ax1.plot(ntu.index, ntu, color=self.palette[0], label='ntu')

        ax1.set_ylabel(ntu_ylabel)

        ax1.legend(loc='upper left')

        self.adjust_ylims([ax1])

        ax1.set_title('NTU')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_air_xco2_and_mbl(self):

        fig, ax1 = plt.subplots(figsize=self.figsize)

        try:
            with xr.open_dataset(self.apoff_ncfile) as ds:
                xco2_dry = self.get_good_ts(ds=ds, varname='xco2_dry')
                ylabel = f"xCO2 ({ds['xco2_dry'].units})"
        except KeyError:
            self.logger.warning('no xco2 dry data found')
            ylabel = 'xCO2'
        else:
            ax1.plot(
                xco2_dry.index, xco2_dry,
                color=self.palette[0], label='deployment xCO2 air'
            )

        min_historical_date = min(xco2_dry.index) - np.timedelta64(365, 'D')  # need a min date to restrict MBL
        if self.historical_df is not None:
            xco2_air = self.historical_df['xCO2_air']
            min_historical_date = min(xco2_air.index) - np.timedelta64(365, 'D')
            ax1.plot(
                xco2_air.index, xco2_air,
                color=self.palette[1],
                label='historical xco2 air',
                linestyle='dashdot',
                alpha=0.5
            )

        ax1.set_ylabel(ylabel)
        
        plotting_mbl = self.mbl[self.mbl.index >= min_historical_date]
        ax1.plot(
            plotting_mbl.index, plotting_mbl,
            color=self.palette[2],
            linestyle='dashed',
            label='MBL xco2'
        )

        ax1.legend(loc='upper left')

        self.adjust_ylims([ax1])

        ax1.set_title('Air xCO2 and MBL')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_sst_and_sss(self):

        ncfile = self.get_met_ncfile()
        if not ncfile.exists():
            msg = 'No Met file exists, so no SST/SSS plot will be produced.'
            self.logger.warning(msg)
            return

        fig, ax1 = plt.subplots(figsize=self.figsize)

        with xr.open_dataset(ncfile) as ds:
            ds = ds.load()
            sst = self.get_good_ts(ds=ds, varname='SST')
            sss = self.get_good_ts(ds=ds, varname='SSS')
            sss_ylabel = f"SSS (PSU)"
            sst_ylabel = f"SST ({ds['SST'].units})"

        ax1.plot(
            sst.index, sst,
            color=self.palette[0], label='deployment sst'
        )

        if self.historical_df is not None:
            ax1.plot(
                self.historical_df['SST'].index,
                self.historical_df['SST'],
                color=self.palette[0],
                label='historical sst',
                linestyle='dashdot',
                alpha=0.5
            )

        ax1.legend(loc='upper left')
        ax1.set_ylabel(sst_ylabel)

        ax2 = ax1.twinx()

        ax2.plot(
            sss.index, sss,
            color=self.palette[1], label='deployment sss'
        )

        if self.historical_df is not None:
            ax2.plot(
                self.historical_df.index,
                self.historical_df['SSS'],
                color=self.palette[1],
                label='historical sss',
                linestyle='dashdot',
                alpha=0.5,
            )

        ax2.set_ylabel(sss_ylabel)
        ax2.legend(loc='upper right')

        self.adjust_ylims([ax1, ax2])

        ax1.set_title('SST and SSS')
        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def plot_sw_xco2_and_ph(self):

        title = 'SW xCO2 and pH'

        fig, ax1 = plt.subplots(figsize=self.figsize)

        with xr.open_dataset(self.apoff_ncfile) as ds:
            ds = ds.load()
            try:
                xco2_dry = self.get_good_ts(ds=ds, varname='xco2_dry')
            except KeyError as e:
                # No xco2_dry?  Possible if no post xco2 process was run.
                self.logger.warning(f'{e}')
                title += ', no xCO2 dry'
            else:
                ax1.plot(
                    xco2_dry.index, xco2_dry,
                    color=self.palette[1], label='deployment xCO2 dry',
                )

        # if self.historical_df is not None:
        #     xco2_sw = self.historical_df['xCO2_sw']  # note: historic data does not report xCO2_sw, only pCO2_sw
        #     ax1.plot(
        #         xco2_sw.index, xco2_sw,
        #         color=self.palette[1],
        #         label='historical xco2 sw',
        #         linestyle='dashdot',
        #         alpha=0.5
        #     )
        # else:
        #     title += ', no historical data'

        ax1.set_ylabel(f"xco2 ({ds['xco2_dry'].units})")
        ax1.legend(loc='upper left')
        self.adjust_ylims([ax1])

        ax2 = ax1.twinx()

        ph_varname, ncfile = self.determine_src_ph_ncfile()

        if ncfile is None:

            self.logger.warning('No pH file exists.')
            title += ', no pH data available'

        else:

            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()
                ph = self.get_good_ts(ds=ds, varname=ph_varname)
                ax2.plot(
                    ph.index, ph, color=self.palette[0], label='deployment pH'
                )
                ax2.set_ylabel(f"pH")  # ({ds[ph_varname].units})")

            if self.historical_df is not None:
                ph_sw = self.historical_df['pH_sw']
                ax2.plot(
                    ph_sw.index, ph_sw,
                    color=self.palette[0],
                    label='historical pH',
                    linestyle='dashdot',
                    alpha=0.5,
                )
            ax2.invert_yaxis()
            # self.adjust_ylims([ax2])  # This messes up the pH axis
            
            ax2.legend(loc='upper right')

        ax1.set_title(title)
        
        if self._is_notebook:
            plt.show()
            time.sleep(0.1)

    def adjust_ylims(self, axes):
        """
        Adjust the ylims to accomodate the legends without covering the data.
        """

        for ax in axes:
            ymin, ymax = ax.get_ylim()

            ymax += 0.15 * ymax

            ax.set_ylim(bottom=ymin, top=ymax)

    def get_o2_ncfile(self):
        """
        o2 data can come from sbe16, or it can come from an external sbe63
        source.  We will favor the external source.
        """

        mapco2_ncfile = self.src_dir / core.SBE16_NCFILE
        external_ncfile = self.src_dir / core.EXTERNAL_SBE63_NCFILE
        if mapco2_ncfile.exists() and external_ncfile.exists():
            ncfile = external_ncfile
        elif mapco2_ncfile.exists() and not external_ncfile.exists():
            ncfile = mapco2_ncfile
        elif not mapco2_ncfile.exists() and external_ncfile.exists():
            ncfile = external_ncfile
        else:
            # This is ok, it will fail gracefully.
            ncfile = external_ncfile

        return ncfile

    def get_met_ncfile(self):
        """
        sss/sst data can come from mapco2, or it can come from an external
        source.  We will favor the external source.
        """

        if self.met_ncfile.exists() and self.external_met_ncfile.exists():
            ncfile = self.external_met_ncfile
        elif (
            self.met_ncfile.exists()
            and not self.external_met_ncfile.exists()
        ):
            ncfile = self.met_ncfile
        elif not (
            self.met_ncfile.exists()
            and self.external_met_ncfile.exists()
        ):
            ncfile = self.external_met_ncfile
        else:
            # This is ok, it will fail gracefully.
            ncfile = self.external_met_ncfile

        return ncfile

    def _get_met_data(self):
        """
        Retrieve the measured met data.

        Returns:  dataframe with SSS and SST
        """
        ncfile = self.get_met_ncfile()
        if not ncfile.exists():
            raise FileNotFoundError('No met file was found')

        with xr.open_dataset(ncfile) as ds:
            ds = ds.load()
            sss = self.get_good_ts(ds=ds, varname='SSS')
            df = sss.to_frame()
            df['SST'] = self.get_good_ts(ds=ds, varname='SST')

        return df


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
