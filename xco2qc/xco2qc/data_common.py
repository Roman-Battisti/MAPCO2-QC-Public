"""
Common routines for gathering variables into dataframes
"""
# standard library imports

# 3rd party library imports
import pandas as pd
import xarray as xr

# local imports
from . import core
from xco2qc.chl_climatology import CHLClimatology
from xco2qc.o2_climatology import O2Climatology
from xco2qc.remote_climatology import ChlCache, OpenDAPO2Climatology


class DataCommon(core.MapCO2core):

    def __init__(
        self, verbosity=None, logger_name=None, src_dir=None,
        merge_ncfile=None
    ):

        super().__init__(
            verbosity=verbosity, logger_name=logger_name, src_dir=src_dir
        )

        if merge_ncfile is not None:
            self.measured_o2_ncfile = merge_ncfile
            self.latlon_ncfile = merge_ncfile
        else:
            self.measured_o2_ncfile = self.sbe16_ncfile
            self.latlon_ncfile = self.cycle_header_ncfile

        # No matter what, also assign this.
        self.merge_ncfile = merge_ncfile

    def _get_o2__measured_climatology_maxtec(self):
        """
        Retrieve measured O2, maxtec O2, and O2 climatology.
        """
        o2 = self._get_measured_o2()

        # climatology, we should pretty much always get this (???)
        clim = self._get_o2_climatology()
        clim = clim.reindex(o2.index, method='nearest')
        clim.name = 'climatology'

        try:
            maxtec = self._get_maxtec_o2(self.epoff_ncfile)
        except KeyError as e:
            # it's ok if we don't have this, just continue on
            self.logger.warning(f'{e}')
            df = pd.concat([o2, clim], axis=1)
        else:
            maxtec = maxtec.reindex(o2.index, method='nearest')
            df = pd.concat([o2, clim, maxtec], axis=1)

        return df

    def _get_maxtec_o2(self, ncfile):
        """
        Get a cleaned timeseries for maxtec O2.
        """
        with xr.open_dataset(ncfile) as ds:
            maxtec = self.get_good_ts(ds=ds, varname='dissolved_oxygen')

        maxtec.name = 'maxtec'

        return maxtec

    def _get_measured_o2(self):
        """
        Get O2 from a netCDF file.
        """

        # measured O2
        if not self.measured_o2_ncfile.exists():
            msg = ('No netCDF file for O2 exists.')
            raise FileNotFoundError(msg)

        with xr.open_dataset(self.measured_o2_ncfile) as ds:
            ds = ds.load()

            if 'o2' not in ds:
                msg = f'No O2 variable found in {self.measured_o2_ncfile}'
                raise KeyError(msg)

            o2 = self.get_good_ts(ds=ds, varname='o2')

        return o2

    def _get_o2_climatology(self):
        """
        Return the O2 climatology for the current dataset.
        """
        with xr.open_dataset(self.cycle_header_ncfile) as ds:
            deployment_df = ds.to_dataframe()[['longitude', 'latitude']]
            site_id = ds.site_id.lower()

        # Try for the global O2 climatology first
        try:
            with OpenDAPO2Climatology(
                deployment_df, verbosity=self.verbosity
            ) as o:
                o2 = o.run()
        except Exception as e:
            msg = (
                'Unable to retrieve the remote O2 climatology. '
                'Trying via the more-limited excel files...'
            )
            self.logger.warn(msg)
            self.logger.info(e)
        else:
            return o2

        # ok, we don't have remote O2 climatology
        df = O2Climatology(site_id).get_climatology()

        return df['O2']

    def get_chl_climatology(self, index=None):
        """
        Retrieve CHL climatology.  First try to get the climatology from a
        local cache of netCDF files, possibly having to retrieve new files
        from a remote repository.

        If this cannot be done, try to use an excel file that has climatologies
        that are tied to the site ID.
        """
        with xr.open_dataset(self.latlon_ncfile) as ds:
            deployment_df = ds.to_dataframe()[['longitude', 'latitude']]
            site_id = ds.site_id.lower()

        # Try for the chl cache first
        try:
            with ChlCache(
                deployment_df, self.config, verbosity=self.verbosity
            ) as o:
                o.run()
                chl = o.ts
        except KeyError as e:
            msg = (
                'Unable to retrieve the CHL climatology via the netCDF cache. '
                'Trying via the more-limited excel files...'
            )
            self.logger.warning(msg)
            self.logger.info(e)
        else:
            return chl

        # try getting the climatology using the site ID.
        try:
            o = CHLClimatology(site_id)
            clim = o.get_climatology()
        except KeyError as e:
            # breakpoint()
            self.logger.warning(e)
            raise
        else:
            # reindex the data to match the primary variable.
            # breakpoint()
            chl = clim.reindex(index)

        return chl
