"""
This provides a mechanism for importing SEAFET pH in the case that there is no
SEAFET buffer in the raw mapco2 text file.
"""
# standard library imports
import datetime as dt
import pathlib

# 3rd party libraries
import netCDF4
import pandas as pd

# local imports
from xco2qc import core


class ImportExternalSeafet(core.MapCO2core):

    def __init__(self, inputfile, dst_dir, **kwargs):
        """
        Parameters
        ----------
        inputfile : path or str or file-like
            The input excel "file" for the pH.
        dst_dir : path or str
            The output directory where the raw seafet netcdf file will be
            created.
        """
        super().__init__(
            dst_dir=dst_dir, logger_name='import_external_seafet', **kwargs
        )
        self.inputfile = pathlib.Path(inputfile)

        self.vardefs = core.vardefs.data_dict['seafet']
        self.time_base = dt.datetime(1970, 1, 1)

    def run(self):

        nrows = 0
        with self.inputfile.open() as f:
            for idx, line in enumerate(f):
                if line.startswith('Frame Header'):
                    nrows = idx

        df = pd.read_csv(
            self.inputfile, skiprows=nrows  # , parse_dates=['DATE TIME']
        )
        df['DATE TIME'] = pd.to_datetime(df['DATE TIME'])

        # Some variables are not important, drop them.
        columns = [
            'Frame Header', 'PH_INT', 'PH_EXT', 'TEMP', 'PRO_PRESSURE',
            'CTD_OXYGEN', 'STATUS', 'CHECK'
        ]
        df = df.drop(columns=columns)

        # rename the remaining variables
        d = dict(
            NEW_PH_INT='ph_int', NEW_PH_EXT='ph', PRO_TEMP='temperature',
            PRO_SALINITY='SSS'
        )
        d['DATE TIME'] = 'datetime'
        df = df.rename(mapper=d, axis='columns')

        ncfile = self.dst_dir / core.EXTERNAL_SEAFET_NCFILE
        self.write_to_netcdf(df, ncfile)

    def write_to_netcdf(self, df, ncfile):
        """
        Write the dataframe to a netCDF file.
        """

        self.logger.info(f'writing out to {ncfile}...')

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            nc.createDimension(core.TIME, 0)

            vardef = self.vardefs[core.TIME]
            ncvar = nc.createVariable(
                core.TIME, vardef['datatype'],
                dimensions=('time',),
                fill_value=vardef['fill_value']
            )
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            timedelta = df['datetime'] - self.time_base
            ncvar[:] = timedelta.dt.total_seconds()

            # define all the data variables
            for varname in [
                'SSS', 'temperature', 'ph_int', 'ph'
            ]:
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

            # mark the data as having come externally, but still from the SAMI
            # data_source
            nc.data_source = 'external-seafet'
