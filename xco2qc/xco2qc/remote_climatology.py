# standard library imports
import calendar
import datetime as dt
from ftplib import FTP
import pathlib
import platform
import re


# 3rd party library imports
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd
import xarray as xr
import yaml

# local imports
from . import core


class RemoteClimatology(core.MapCO2core):

    def __init__(
        self, deployment_df, verbosity=None, logger_name=None,
        cache_basename=None
    ):
        super().__init__(verbosity=verbosity, logger_name=logger_name)

        self.deployment = deployment_df

        if platform.system() == 'Darwin':
            self.cachedir = (
                pathlib.Path.home()
                / 'Library' / 'Caches' / 'xco2qc' / cache_basename
            )
        elif platform.system() == 'Linux':
            self.cachedir = (
                pathlib.Path.home()
                / '.cache' / 'xco2qc' / cache_basename
            )
        else:
            # windows
            self.cachedir = (
                pathlib.Path.home()
                / 'AppData' / 'Local' / 'xco2qc' / cache_basename
            )

        self.cachedir.mkdir(parents=True, exist_ok=True)
        self.cache_contents = list(self.cachedir.glob('*.nc'))

    def run(self):
        self.check_coverage()
        self.map_cache_back_to_deployment()
        self.interpolate()

        return self.ts

    def _get_cache_monthly_range(self):
        """
        Get a monthly series of dates that spans the current deployment.
        """
        # Construct the list of dates for which we need a file in the
        # local cache.
        year, month = (
            self.deployment.index[0].year, self.deployment.index[0].month
        )
        start = dt.date(year, month, 1)
        year, month = (
            self.deployment.index[-1].year, self.deployment.index[-1].month
        )
        stop = dt.date(year, month, 1) + relativedelta(months=1)

        return pd.date_range(start=start, end=stop, freq='ME')

    def _check_cache_for_current_date(self, cache_date, ncfile_regex):
        """
        Check whether the current date has a matching file in the local cache.

        Parameters
        ----------
        cache_date : datetime.date
            Check the cache for a file for this particular month.
        regex : regular expression
            The cache files need to match this regular expression.
        """
        current_month_ok = False

        for cache_file in self.cache_contents:
            self.logger.debug(f'Examining {cache_file} in cache...')
            if ncfile_regex.search(cache_file.name):
                current_month_ok = True

        if not current_month_ok:
            self.update_cache(cache_date)
        else:
            msg = f'{cache_date.year}-{cache_date.month:02d} is covered'
            self.logger.debug(msg)


class ChlCache(RemoteClimatology):
    """
    Manager for netCDF-based CHL climatology.

    Attributes
    ----------
    configfile : path
        Path to xco2qc configuration file containing credentials.
    credentials : obj
        has username and password for the external climatology resource
    deployment : pandas dataframe
        timeseries of deployment GPS latitudes and longitudes
    """
    def __init__(self, deployment_df, configfile, verbosity=None):
        """
        Parameters
        ----------
        deployment_df : pandas dataframe
            timeseries of deployment GPS latitudes and longitudes
        ts : pandas series
            timeseries of the chl climatology
        """
        super().__init__(
            deployment_df, verbosity=verbosity, logger_name='chl_climatology',
            cache_basename='chl'
        )

        if isinstance(configfile, dict):
            # ok, the configfile is really the full configuration, so just use
            # it
            self.config = configfile
        else:
            # assume it's really a path to the config file
            configfile = pathlib.Path(configfile)
            with configfile.open() as f:
                self.config = yaml.safe_load(f)

        if 'chl_credentials' not in self.config:
            msg = (
                'The configuration file is missing a chl_credentials section '
                'with a username and password for the remote chl repository.'
            )
            raise KeyError(msg)

        self.ts = None

    def check_coverage(self):
        """
        Check to see that the cache covers each month between the begin
        and end date of the deployment.  If there is a cache miss, download
        the necessary file from the external repository.
        """
        cache_date_range = self._get_cache_monthly_range()

        # if we do not find the month in the local cache files, call out to
        # retrieve a file for that month
        for cache_date in cache_date_range:

            year, month = cache_date.year, cache_date.month
            pattern = (
                f"L3m_{year}{month:02d}"
                r"\d{2}"
                "-"
                f"{year}{month:02d}"
                r"\d{2}__GLOB_4_AV-MOD_CHL1_MO_00.nc"
            )
            self.logger.debug(f'regex pattern is {pattern}')
            ncfile_regex = re.compile(pattern, re.VERBOSE | re.DOTALL)

            self._check_cache_for_current_date(cache_date, ncfile_regex)

    def update_cache(self, date):
        """
        Retrieve the netCDF file from the climatology server for the given
        month.

        Parameters
        ----------
        date : datetime.date
            Specifies the month for which we need climatology data.
        """
        final_day_of_month = calendar.monthrange(date.year, date.month)[1]

        ftp = FTP('ftp.hermes.acri.fr')
        ftp.login(
            user=self.config['chl_credentials']['username'],
            passwd=self.config['chl_credentials']['password']
        )

        # this provides 1x1 degree resolution
        basename = (
            f"L3m_{date.year}{date.month:02d}01"
            "-"
            f"{date.year}{date.month:02d}{final_day_of_month}"
            "__GLOB_4_AV-MOD_CHL1_MO_00.nc"
        )
        remote_filename = (
                f"GLOB/modis/month/{date.year}/{date.month:02d}/01/{basename}"
        )
        local_filename = self.cachedir / basename

        self.logger.info(f'Updating local cache for {local_filename}')

        with open(local_filename, 'wb') as fp:
            ftp.retrbinary(f'RETR {remote_filename}', fp.write)

        ftp.quit()

        # update the local cache
        self.cache_contents.append(local_filename)

    def map_cache_back_to_deployment(self):
        """
        Construct a mapping of the cache files back to the deployment.  This is
        by month, so we don't need the full deployment timeseries.
        """
        year, month = (
            self.deployment.index[0].year, self.deployment.index[0].month
        )
        start = dt.date(year, month, 1)
        year, month = (
            self.deployment.index[-1].year, self.deployment.index[-1].month
        )
        stop = dt.date(year, month, 1)

        index = (
            pd.date_range(start=start, end=stop, freq='MS')
            + pd.DateOffset(days=14)
        )

        data = []

        for date in index:

            pattern = f"{date.year}{date.month:02d}"

            for ncfile in self.cache_contents:
                if pattern in ncfile.name:
                    data.append(ncfile)
                    break

        self.cache_mapping = pd.Series(data, index=index)

    def interpolate(self):
        """
        Interpolate the lat/lon values to the cache timeseries.
        """
        breakpoint()
        index = self.deployment.index.copy()
        tmp_data = np.zeros((len(index),))
        ts = pd.Series(data=tmp_data, index=index, name='CHL Climatology')

        for date, ncfile in self.cache_mapping.items():
            idx = (
               (self.deployment.index.year == date.year)
               & (self.deployment.index.month == date.month)
            )
            if sum(idx) > 0:
                ts.loc[idx] = self.interpolate_cache(idx, ncfile)

        self.ts = ts

    def interpolate_cache(self, index, cache_ncfile):
        """
        Interpolate a series of lat/lon positions to get climatology values
        for a single file in the cache.

        Parameters
        ----------
        df : pandas dataframe
            lat/lon timeseries
        cache_ncfile : str or path
            netCDF file in the climatology cache
        """
        self.logger.debug(f'Interpolating cache file {cache_ncfile}')
        with xr.open_dataset(cache_ncfile) as ds:

            # this is very inefficient, think of something else
            da = ds['CHL1_mean'].interp(
                lat=self.deployment.loc[index, 'latitude'],
                lon=self.deployment.loc[index, 'longitude'],
                method='nearest'
            )
        data = da.values.diagonal()
        # print(data, self.deployment.loc[index, 'latitude'], self.deployment.loc[index, 'longitude'])
        return data


class OpenDAPO2Climatology(RemoteClimatology):
    """
    Manager for opendap-based O2 climatology.

    Attributes
    ----------
    deployment : pandas dataframe
        timeseries of deployment GPS latitudes and longitudes
    """
    def __init__(self, deployment_df, verbosity=None):
        """
        Parameters
        ----------
        deployment_df : pandas dataframe
            timeseries of deployment GPS latitudes and longitudes
        ts : pandas series
            timeseries of the O2 climatology
        """
        super().__init__(
            deployment_df, verbosity=verbosity, logger_name='o2_climatology',
            cache_basename='o2'
        )

    def interpolate(self):
        """
        Interpolate the O2 climatology for the current deployment.  All of the
        necessary files should be in the cache.
        """
        o2 = pd.Series(
            name='o2 climatology',
            index=self.deployment.index,
            data=np.full((len(self.deployment)), np.nan)
        )

        # find the months involved
        months = self.deployment.index.month.unique()

        for month in months:

            index = self.deployment.index.month == month

            path = self.cachedir / f"{month:02}.nc"
            with xr.open_dataset(path, decode_times=False) as ds:

                # restrict to that single time value and the surface depth
                da = ds['o_an']
                
                da = da.interp(
                    lat=self.deployment.loc[index, 'latitude'],
                    lon=self.deployment.loc[index, 'longitude'],
                    method='nearest'
                )

                data = da.values.diagonal()
                o2[index] = data

        # How good is the data?
        percent_null = o2.isnull().sum() / len(o2) * 100
        msg = f'{percent_null:.2f}% of the O2 climatology values are null.'
        self.logger.info(msg)

        self.ts = o2

    def check_coverage(self):
        """
        Check what months we currently have in the cache.
        """
        cache_date_range = self._get_cache_monthly_range()

        # if we do not find the month in the local cache files, call out to
        # retrieve a file for that month
        for cache_date in cache_date_range:

            _, month = cache_date.year, cache_date.month
            pattern = f"{month:02d}.nc"
            self.logger.debug(f'regex pattern is {pattern}')
            ncfile_regex = re.compile(pattern, re.VERBOSE | re.DOTALL)

            self._check_cache_for_current_date(cache_date, ncfile_regex)

    def update_cache(self, cache_date):
        """
        Load the O2 dataset for the current month, save it in the cache.
        """
        _, month = cache_date.year, cache_date.month

        url = (
            "https://www.ncei.noaa.gov"
            "/thredds-ocean/dodsC/ncei/woa/oxygen/all/1.00"
            f"/woa18_all_o{month:02}_01.nc"
        )

        msg = f"Retrieving O2 climatology from {url}..."
        self.logger.info(msg)

        with xr.open_dataset(url, decode_times=False) as ds:

            # only save what we need of the dataset
            da = ds['o_an'][0, 0, :, :]
            out_ds = da.to_dataset()

            path = self.cachedir / f"{month:02}.nc"
            out_ds.to_netcdf(path)

    def map_cache_back_to_deployment(self):
        pass
