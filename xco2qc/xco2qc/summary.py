"""
Display metadata about when the notebook was run as well as what software
packages were used.

This is really only useful from within a jupyter notebook context.
"""

# standard library imports
import datetime as dt
import importlib.metadata
import importlib.resources as ir
import sys

# 3rd party libraries
from IPython.display import display
from IPython.core.display import HTML
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import xarray as xr
import yaml

# local imports
from . import data_common


class XCO2Summary(data_common.DataCommon):

    def __init__(self, merge_ncfile, historical_ncfile=None, use_colorblind=False):
        super().__init__(
            verbosity='INFO', logger_name='summary', merge_ncfile=merge_ncfile
        )

        self.historical_ncfile = historical_ncfile

        with xr.open_dataset(merge_ncfile) as ds:
            ds = ds.load()
            self.merge_ds = ds
            self.merge_df = ds.to_dataframe()

        self.figsize = (8, 6)

        if historical_ncfile is None:
            self.historical_ds = None
            self.historical_df = None
        else:
            with xr.open_dataset(historical_ncfile) as ds:
                ds = ds.load()
                if 'station_id' in ds:
                    ds = ds.drop_vars('station_id')
                if 'rowSize' in ds:
                    ds = ds.drop_vars('rowSize')
                self.historical_ds = ds
                self.historical_df = ds.to_dataframe()

        self.color_palette = None if not use_colorblind else "colorblind"
        self.palette = sns.color_palette(palette=self.color_palette, n_colors=4)

    def run(self):
        self.display_full_time_series()
        self.display_date()
        self.display_software_packages()

    def display_full_time_series(self):
        self.plot_sw_xco2_comparison()
        self.plot_air_xco2_comparison()
        self.plot_sst_and_sss()
        self.plot_dissolved_oxygen()
        self.plot_chl_nighttime()
        self.plot_ntu()

    def plot_air_xco2_comparison(self):

        self.plot_air_xco2_pCO2()
        self.plot_air_xco2_fCO2()

    def plot_sw_xco2_comparison(self):

        self.plot_sw_xco2_pCO2()
        self.plot_sw_xco2_fCO2()
        self.plot_sw_xco2_ph()

    def plot_ntu(self):

        if 'ntu' not in self.merge_ds:
            msg = (
                'There was no NTU data in the merge file.  '
                'Skipping the NTU plot.'
            )
            self.logger.warning(msg)
            return

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'NTU'
        ax1.set_title(title)

        self._plot_vars(var1='ntu', ax1=ax1)

    def plot_chl_nighttime(self):

        if 'chl_nighttime' not in self.merge_ds:
            msg = (
                'There was no nighttime chlorophyll data in the merge file.  '
                'Skipping the nighttime chlorophyll plot.'
            )
            self.logger.warning(msg)
            return

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'CHL Nighttime'
        ax1.set_title(title)

        self._plot_vars(var1='chl_nighttime', ax1=ax1)

    def plot_dissolved_oxygen(self):

        if 'dissolved_oxygen' not in self.merge_ds:
            msg = (
                'There was no dissolved oxygen data in the merge file.  '
                'Skipping the dissolved oxygen plot.'
            )
            self.logger.warning(msg)
            return

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'Dissolved Oxygen'
        ax1.set_title(title)

        self._plot_vars(var1='dissolved_oxygen', ax1=ax1)

    def plot_sw_xco2_ph(self):

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'SW xCO2 and pH'
        ax1.set_title(title)
        ax2 = ax1.twinx()

        self._plot_vars(var1='xCO2_sw', ax1=ax1, var2='pH_sw', ax2=ax2)

    def plot_sw_xco2_fCO2(self):

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'SW xCO2 and fCO2'
        ax1.set_title(title)
        ax2 = ax1.twinx()

        self._plot_vars(var1='xCO2_sw', ax1=ax1, var2='fCO2_sw', ax2=ax2)

    def plot_air_xco2_fCO2(self):

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'Air xCO2 and fCO2'
        ax1.set_title(title)
        ax2 = ax1.twinx()

        self._plot_vars(var1='xCO2_air', ax1=ax1, var2='fCO2_air', ax2=ax2)

    def plot_sst_and_sss(self):

        if 'SSS' not in self.merge_ds and 'SST' not in self.merge_ds:
            msg = (
                'There was no SSS or SST data in the merge file.  Skipping '
                'the SSS/SST comparison plot.'
            )
            self.logger.warning(msg)
            return

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'SST and SSS'
        ax1.set_title(title)
        ax2 = ax1.twinx()

        self._plot_vars(var1='SST', ax1=ax1, var2='SSS', ax2=ax2)

    def _plot_historical_variable(self, ds, varname, axis, color=None):

        if self.historical_df is not None:
            try:
                axis.plot(
                    self.historical_df['time'], self.historical_df[varname],
                    color=color,
                    label=f'historical {varname}',
                    linestyle='dashdot',
                    alpha=0.5,
                )

                if varname == 'ph_SW':
                    axis.invert_yaxis()

            except KeyError:
                # no varname present
                msg = (
                    f'Could not locate {varname} in {self.historical_ncfile}.'
                )
                self.logger.warning(msg)

    def _plot_deployment_variable(self, ds, varname, axis, color=None):

        try:
            ts = self.get_good_ts(ds=ds, varname=varname)
        except KeyError:
            msg = (
                f'Unable to locate {varname} in deployment file '
                f'{self.merge_ncfile}'
            )
            self.logger.warning(msg)
            return

        label = f"deployment {varname}"
        axis.plot(ts.index, ts, color=color, label=label)

        ylabel = f"{varname} ({ds[varname].units})"
        axis.set_ylabel(ylabel)

        if varname == 'ph_SW':
            axis.invert_yaxis()

        axis.legend(loc='upper left')

    def plot_air_xco2_pCO2(self):

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'Air xCO2 and pCO2'
        ax1.set_title(title)
        ax2 = ax1.twinx()

        self._plot_vars(var1='xCO2_air', var2='pCO2_air', ax1=ax1, ax2=ax2)

    def _plot_vars(self, var1=None, var2=None, ax1=None, ax2=None):

        self._plot_deployment_variable(
            self.merge_ds, var1, ax1, color=self.palette[0]
        )
        self._plot_historical_variable(
            self.historical_ds, var1, ax1, color=self.palette[0]
        )
        ax1.legend(loc='upper left')

        if var2 is not None and ax2 is not None:
            self._plot_deployment_variable(
                self.merge_ds, var2, ax2, color=self.palette[1]
            )
            self._plot_historical_variable(
                self.historical_ds, var2, ax2, color=self.palette[1]
            )
            ax2.legend(loc='upper right')

    def plot_sw_xco2_pCO2(self):

        fig, ax1 = plt.subplots(figsize=self.figsize)
        title = 'SW xCO2 and pCO2'
        ax1.set_title(title)
        ax2 = ax1.twinx()

        self._plot_vars(var1='xCO2_sw', var2='pCO2_air', ax1=ax1, ax2=ax2)

    def display_date(self):
        """
        Just display the current time in UTC so that there is a permanent
        record of when the QC work was run.
        """
        now = dt.datetime.now(tz=dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        display(HTML(f'<h3>Date:  {now} UTC</h3>'))

    def retrieve_software_packages(self):
        """
        Retrieve the names and versions of all the 3rd party packages used.

        Return Value
        ------------
        pandas.Series where the index is the package name and the version is
        the data.
        """
        with ir.as_file(ir.files('xco2qc.core.data').joinpath('environment.yml')) as path:
            config = yaml.safe_load(path.open())

        records = []
        for package in config['dependencies']:
            try:
                package = package.split('>=')[0]
            except AttributeError:
                # probaby pip?
                package = package['pip'][0]

            try:
                pversion = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                if package == 'python':
                    pversion = sys.version.split()[0]
                else:
                    pversion = '?'
            finally:
                records.append((package, pversion))

        df = pd.DataFrame(records, columns=['Package', 'Version'])
        s = df.set_index('Package')

        return s

    def display_software_packages(self):
        """
        Display the name and version of 3rd party packages.
        """
        s = self.retrieve_software_packages()

        display(HTML('<h3>Software Packages Used</h3>'))
        display(s)
