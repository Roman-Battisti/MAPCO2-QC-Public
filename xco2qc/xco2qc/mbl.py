# standard library imports
import pathlib
import time

# 3rd party library imports
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import xarray as xr

# local imports
import xco2qc.core


class MBL(xco2qc.core.MapCO2core):
    """
    Encapsulates access to MBL data

    Attributes
    ----------
    retrieve_remote : bool
        If true, attempt to retrieve the newest version of the MBL data from
        the ESRL website.  Otherwise use the stored version.
    """
    def __init__(self, retrieve_remote=False):

        self.retrieve_mbl(retrieve_remote)

    def retrieve_mbl(self, retrieve_remote):
        """
        Retrieve MBL data from either a local text file or from remote URL
        """
        df = xco2qc.core.data.mbl.read_mbl(retrieve_remote)
        self.ds = self.dataframe_to_dataset(df)
        self.da = self.ds['xCO2']

    def dataframe_to_dataset(self, df):
        """
        """

        # there are two coordinate variables, latitude and time
        t = np.linspace(-1, 1, 41)
        latitude = np.arcsin(t) * 180 / np.pi

        time = df.index

        # the data arrays will be xco2 and xco2_stddev
        #
        # the columns of the dataframe are staggered between xco2 and xco2 STD
        data = df[df.columns[1::2]].values
        xco2 = xr.DataArray(
            data, coords=[time, latitude], dims=['time', 'latitude']
        )

        data = df[df.columns[2::2]].values
        xco2_stddev = xr.DataArray(
            data, coords=[time, latitude], dims=['time', 'latitude']
        )

        ds = xr.Dataset({'xCO2': xco2, 'xCO2_stddev': xco2_stddev})

        return ds

    def interpolate_to_latitude(self, latitude):
        """
        The global MBL xCO2 data is 2D (time x lat).  We need to interpolate
        the MBL data to the same lat coordinate as the MAPCO2
        data.
        """
        da_mbl_l = self.da.interp(latitude=latitude)
        mbl = da_mbl_l.to_series()

        return mbl


class CompareMBL(xco2qc.core.MapCO2core):
    """
    Read the MBL text file from ESRL with global zonal xCO2.  Match it with
    our APOFF xCO2 to see if there is a bias.

    Attributes
    ----------
    ds_historical : xr.DataSet or None
        dataset for the historical data
    merge_ncfile : path or str
        Path to merge netCDF file produced in xCO2 processing run.
    retrieve_remote : bool
        If true, attempt to retrieve the newest version of the MBL data from
        the ESRL website.  Otherwise use the stored version.
    """

    def __init__(
        self, *, src_dir=None, merge_ncfile=None, historical_ncfile=None, verbosity=None,
        retrieve_remote=False, use_colorblind=False
    ):

        super().__init__(verbosity=verbosity, logger_name='compare-mbl')

        src_dir = pathlib.Path(src_dir)
        self.apoff_ncfile = src_dir / xco2qc.core.licor.APOFF_NCFILE
        with xr.open_dataset(self.apoff_ncfile) as ds:
            self.ds_apoff = ds.load()
        
        self.merge_ncfile = pathlib.Path(merge_ncfile)
        with xr.open_dataset(self.merge_ncfile) as ds:
            self.ds_merge = ds.load()

        if historical_ncfile is not None and historical_ncfile.is_file():
            path = pathlib.Path(historical_ncfile)
            with xr.open_dataset(path) as ds:
                ds = ds.load()

            # This is particular to ERDDAP historical netCDF files.
            if 'station_id' in ds.variables:
                ds = ds.drop_vars('station_id')
            if 'rowSize' in ds.variables:
                ds = ds.drop_vars('rowSize')

            self.ds_historical = ds

        else:

            self.ds_historical = None

        self.mbl = MBL(retrieve_remote=retrieve_remote)
        
        self.color_palette = None if not use_colorblind else "colorblind"
        self.palette = sns.color_palette(palette=self.color_palette, n_colors=3)

    def run(self):

        station, historic_offset = self.compute_offset_of_station_to_mbl()
        _, deployment, deployment_offset = self.compute_offset_of_deployment_to_mbl()  # noqa : E501
        offset = historic_offset - deployment_offset

        mbl_l = self.mbl.interpolate_to_latitude(
            self.ds_merge['latitude'].mean()
        )
        
        self.plot_correction(
            deployment, mbl_l, station, historic_offset, deployment_offset,
            offset
        )

    def compute_offset_of_station_to_mbl(self):
        """
        This is the difference between the historical data and the MBL data.
        """

        if self.ds_historical is None:
            return None, float('nan')

        # extract the mapco2 xco2 data.  There is no associated QC variable.
        df = self.ds_historical.to_dataframe()

        if df.index.name != 'time':
            # we must have an erddap netCDF dataset
            df = df.set_index('time')

        station = df['xCO2_air']

        mbl = self.interpolate_mbl_to_latitude_and_time(station)
        mbl = mbl.drop_duplicates()

        # Some times this is not sorted!!!
        mbl = mbl.sort_index()

        # Try to remove diurnal signal from APOFF data and resample it to the
        # MBL data.  The actual frequency of MBL seems to be 7d 14h 29m 49.48s
        # but pandas doesn't want to accept something that odd.  Try 8 days.
        station_meaned = station.resample('8D').mean()
        mbl_meaned = mbl.reindex(station_meaned.index, method='nearest')
        offset = (station_meaned - mbl_meaned).mean()

        return station, offset

    def compute_offset_of_deployment_to_mbl(self):

        # extract the mapco2 xco2 data, restrict it to where quality is good
        if 'post_xco2_dry' in self.ds_apoff.keys():
            xco2= self.ds_apoff['post_xco2_dry'].to_series()
        else:
            xco2 = self.ds_apoff['xco2_dry'].to_series()
        xco2_qc = self.ds_merge['xCO2_air_qc'].to_series().to_numpy()
        deployment = xco2.iloc[xco2_qc == xco2qc.core.quality.GOOD]
        if len(deployment) == 0:
            msg = "There was no good xCO2_air data to work with."
            raise RuntimeError(msg)

        mbl = self.interpolate_mbl_to_latitude_and_time(deployment)

        # Try to remove diurnal signal from APOFF data and resample it to the
        # MBL data.  The actual frequency of MBL seems to be 7d 14h 29m 49.48s
        # but pandas doesn't want to accept something that odd.  Try 8 days.
        deployment_meaned = deployment.resample('8D').mean()
        mbl_meaned = mbl.reindex(deployment_meaned.index, method='nearest')
        offset = (deployment_meaned - mbl_meaned).mean()

        return mbl, deployment, offset

    def interpolate_mbl_to_latitude_and_time(self, ts):
        """
        The global MBL xCO2 data is 2D (time x lat).  We need to interpolate
        the MBL data to the same time span and lat coordinate as the given
        time series data
        """
        da_mbl_t = self.mbl.da.interp(time=ts.index)
        da_mbl_t_l = da_mbl_t.interp(
            latitude=self.ds_merge['latitude'].mean()
        )

        mbl = da_mbl_t_l.to_series()

        return mbl

    def plot_correction(
        self, deployment, mbl, station, historic_offset, deployment_offset,
        offset
    ):
        """
        Plot the components.  Hopefully the correction factor will be obvious.

        Parameters
        ----------
        deployment : pandas.Series
            xCO2 AIR (wet) from the MAPCO2 deployment
        mbl : pandas.Series
            MBL xCO2 interpolated to the same latitude as the MAPCO2 time
            series
        station : pandas.Series or None
            historical data from the deployment location
        corr : float
            correction factor between MAPCO2 and MBL
        """

        fig, ax = plt.subplots(figsize=(10, 6))

        deployment.name = 'Deployment'
        deployment.plot(ax=ax, color=self.palette[0])
        min_historical_date = min(deployment.index)

        if station is not None:
            station.name = 'Historical'
            station.plot(ax=ax, color=self.palette[1])
            min_historical_date = min(station.index)
        
        mbl.name = 'MBL'
        # limit plotting to year before earliest historic date.
        mbl_restricted = mbl[mbl.index > min_historical_date - np.timedelta64(365, 'D')]
        mbl_restricted.plot(ax=ax, lw=3, color=self.palette[2])

        if station is None:
            title = f"MBL - Deployment = {deployment_offset:.2f} ppm"
        else:
            title = (
                f"MBL offset = historic_offset ({historic_offset:.2f}) "
                f"- deployment_offset ({deployment_offset:.2f}) = {offset:.2f}"
            )

        ax.set_title(title)
        ax.legend()
        
        if self._is_notebook:
            time.sleep(0.1)
            plt.show()
