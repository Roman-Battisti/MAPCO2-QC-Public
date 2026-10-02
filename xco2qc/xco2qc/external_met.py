"""
This provides a mechanism for importing salinity and temperature data in case
there is no met buffer in the raw mapco2 text file.
"""

# standard library imports
import datetime as dt
import pathlib

# local imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core


class ImportExternalMET(core.MapCO2core):
    """
    Attributes
    ----------
    inputfile : path or str or file-like
        The input CSV "file" for the salinity and temperature
    dst_dir : path
        The output directory where the raw met netcdf file will be created.
    vardefs : dict
        has definitions for salinity and temperature
    """

    def __init__(self, inputfile, dst_dir, **kwargs):
        """
        Parameters
        ----------
        inputfile : path or str or file-like
            The input CSV "file" for the salinity and temperature
        dst_dir : path or str
            The output directory where the raw met netcdf file will be created.
        """
        super().__init__(
            dst_dir=dst_dir, logger_name='import_external_sstc', **kwargs
        )

        if isinstance(inputfile, str):
            # turn a string into a path
            self.inputfile = pathlib.Path(inputfile)
        else:
            # case of path or file-like object
            self.inputfile = inputfile

        self.vardefs = core.vardefs.data_dict['external_met']
        self.time_base = dt.datetime(1970, 1, 1)

    def run(self):

        # Don't run if given a directory
        if (
            isinstance(self.inputfile, pathlib.Path)
            and self.inputfile.is_dir()
        ):
            self.logger.info("No SSS or SST will be imported.")
            return

        self.logger.info(f'parsing {self.inputfile}...')

        df = pd.read_csv(
            self.inputfile, sep='[\t,]', parse_dates=[0], engine='python'
        )
        df = self.post_process(df)
        self.write_netcdf(df)

    def post_process(self, df):
        """
        Do any manipulations needed.
        """
        # convert first column to datetimes
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
        
        # turn the columns to lower case
        df.columns = [col.lower() for col in df.columns]

        # remap if possible
        mapper = {
            'salinity': 'SSS',
            'sss': 'SSS',
            'sst': 'SST',
            'temp': 'SST',
            'temperature': 'SST',
        }
        df = df.rename(mapper=mapper, axis='columns')

        return df

    def write_netcdf(self, df):
        """
        Write the dataframe to the historical netcdf file.  If the file already
        exists, the two timeseries must be meshed together.

        Parameters
        ----------
        df : pandas.Dataframe
            has historical data
        """

        ncfile = self.dst_dir / core.EXTERNAL_MET_NCFILE
        if ncfile.exists():
            df = df.set_index('time')
            self.assimilate_new_data(ncfile, df)
        else:
            self.write_initial_data(ncfile, df)

    def assimilate_new_data(self, ncfile, df1):

        self.logger.info(f'assimilating new data into {ncfile}...')

        with xr.open_dataset(ncfile) as ds:
            df2 = ds.to_dataframe()

            # merge the two dataframes
            df = df1.merge(df2, how='outer', left_index=True, right_index=True)

            df = df.reset_index()

        # rewrite any previously existing variables, and define and write any
        # new variables
        with netCDF4.Dataset(ncfile, mode='r+') as nc:

            timedelta = df['time'] - self.time_base
            nc['time'][:] = timedelta.dt.total_seconds()

            # define all the data variables
            for varname, vardef in self.vardefs.items():

                if varname not in df.columns:
                    continue

                if varname == 'time':
                    continue

                vardef = self.vardefs[varname]

                if varname in nc.variables:
                    # just rewrite the data if the variable already exists
                    nc.variables[varname][:] = df[varname]
                else:
                    # define AND write if the variable is new
                    ncvar = nc.createVariable(
                        varname,
                        vardef['datatype'],
                        dimensions=('time',),
                        fill_value=vardef['fill_value']
                    )

                    for attrname, attrvalue in vardef['attributes'].items():
                        setattr(ncvar, attrname, attrvalue)

                    ncvar[:] = df[varname]

    def write_initial_data(self, ncfile, df):
        """
        Create the netCDF file, write out the dataframe.
        """

        self.logger.info(f'writing out to {ncfile}...')

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            # defining the time dimension is something we can only do once
            nc.createDimension(core.TIME, 0)

            vardef = self.vardefs['time']
            ncvar = nc.createVariable('time', np.int64,
                                      dimensions=('time',),
                                      fill_value=vardef['fill_value'])
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            timedelta = df['time'] - self.time_base
            ncvar[:] = timedelta.dt.total_seconds()

            # define all the other data variables
            for varname, vardef in self.vardefs.items():

                if varname not in df.columns:
                    continue

                if varname == 'time':
                    continue

                vardef = self.vardefs[varname]

                ncvar = nc.createVariable(
                    varname,
                    vardef['datatype'],
                    dimensions=('time',),
                    fill_value=vardef['fill_value']
                )

                for attrname, attrvalue in vardef['attributes'].items():
                    setattr(ncvar, attrname, attrvalue)

                ncvar[:] = df[varname]

            # must write out some global attributes
            nc.data_source = 'external-met'
