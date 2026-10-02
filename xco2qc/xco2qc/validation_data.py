# standard library imports
import datetime as dt
import importlib.resources as ir
import pathlib

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
import yaml

# local imports
from . import core


class ValidationData(core.MapCO2core):

    def __init__(
        self, input_file, dst_dir, logger_name='import-validation-data',
        **kwargs
    ):
        super().__init__(
            dst_dir=dst_dir, logger_name=logger_name, **kwargs
        )
        self.time_base = dt.datetime(1970, 1, 1)

        self.input_file = input_file

        self.columns = [
            'chl_nighttime', 'dissolved_oxygen', 'ntu', 'pH_sw', 'SSS', 'SST',
            'time', 'xCO2_air', 'xCO2_sw'
        ]
        self.load_allowed_variable_definitions()

    def load_allowed_variable_definitions(self):
        """
        read allowable variable configuration from the merge file definition
        """
        path = ir.files('xco2qc.core.vardefs.config').joinpath('merge.yml')
        with path.open() as f:
            vardefs = yaml.safe_load(f)

        # only load those variables that we will QC, including time
        self.vardefs = {
            variable: definition for variable, definition in vardefs.items()
            if variable in self.columns
        }

        # remove the ancillary_variables attribute if present because the
        # validation data does not allow for that
        for key in self.vardefs:
            try:
                self.vardefs[key]['attributes'].pop('ancillary_variables')
            except KeyError:
                pass

    def run(self):

        if (
            isinstance(self.input_file, pathlib.Path)
            and self.input_file.is_dir()
        ):
            msg = (
                f"{self.input_file} is a directory.  No validation data will "
                "be imported."
            )
            self.logger.warning(msg)
            return

        df = pd.read_csv(self.input_file, parse_dates=['time'])

        # verify that the CSV file is usable.  if the set intersection between
        # the QC'd variables and the dataframe columns is non-empty, then we
        # have usable data.  The intersection must be more than just 'time'.
        si = set(self.vardefs.keys()).intersection(set(df.columns))
        si.remove('time')
        if len(si) == 0:
            msg = (
                'No usable data variables were found in the validation file '
                f'{self.input_file}.  The following names are allowed:  '
                f'{self.columns}.'
            )
            raise RuntimeError(msg)

        self.write_netcdf(df)

    def write_netcdf(self, df):
        """
        Write the dataframe to the historical netcdf file.  If the file already
        exists, the two timeseries must be meshed together.

        Parameters
        ----------
        df : pandas.Dataframe
            has historical data
        """

        ncfile = self.dst_dir / core.VALIDATION_NCFILE
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

            # must write out some global attributes to identify the file type
            nc.data_source = 'validation'
