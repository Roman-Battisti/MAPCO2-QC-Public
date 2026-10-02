"""
This provides a mechanism for importing SAMI pH in the case that there is no
SAMI buffer in the raw mapco2 text file.
"""
# standard library imports
import datetime as dt
import pathlib

# 3rd party libraries
import netCDF4
import numpy as np
import pandas as pd

# local imports
from xco2qc import core


class ImportExternalSAMI(core.MapCO2core):

    def __init__(self, inputfile, raw_netcdf_path, **kwargs):
        """
        Parameters
        ----------
        inputfile : path or str or file-like
            The input CSV "file" for the pH.
        raw_netcdf_path : path or str
            The output directory where the raw sami netcdf file will be
            created.
        """
        self.inputfile = pathlib.Path(inputfile)
        super().__init__(
            src_dir=self.inputfile.parents[0],
            logger_name='import_external_ph', **kwargs
        )

        self.raw_netcdf_path = pathlib.Path(raw_netcdf_path)

        self.vardefs = core.vardefs.data_dict['external_sami']
        self.time_base = dt.datetime(1970, 1, 1)

    def run(self):

        df = self.read_csv_data()
        ncfile = self.raw_netcdf_path / core.EXTERNAL_SAMI_NCFILE
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
                'SSS', 'temperature', 'ph', 'ph_err', 'external_flag'
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
            nc.data_source = 'external-sami'

    def read_csv_data(self):
        """
        Read the CSV data.  It might have either 3, 4, or 7 header lines.  It might
        have 6 or 7 columns.  Awesome.
        """

        expected_columns = [
            [
                'Date', 'Time', 'ph', 'ph_err', 'temperature', 'SSS',
                'external_flag'
            ],
            [
                'Date', 'Time', 'ph', 'ph_err', 'temperature', 'SSS',
                'battery', 'external_flag'
            ],
        ]

        for columns in expected_columns:
            for skiprows in [3, 4, 7]:

                try:
                    df = pd.read_csv(
                        self.inputfile,
                        sep=r'\s+',
                        skiprows=skiprows,
                        index_col=None,
                        names=columns,
                        # parse_dates={'datetime': ['Date', 'Time']}
                    )
                    
                    df['datetime'] = pd.to_datetime(
                                        df['Date'].astype(str) + ' ' + df['Time'].astype(str),
                                        format = "%m/%d/%Y %H:%M:%S"
                                                   )
                    df = df.drop(columns=['Date', 'Time'])
                except (NotImplementedError, ValueError):
                    # might happen if the column are wrong
                    continue

                # Verify that we read the CSV data correctly.  If the
                # number of header lines are wrong, the datatypes will
                # be wrong.  There should be no 'object' datatype, they
                # should all be either float64, datetime64, or int64.
                if np.dtype('object') in df.dtypes.values:
                    continue
                else:
                    return df

        msg = (
            'Was not able to read the external sami file, check the number of '
            'header rows and columns.'
        )
        raise RuntimeError(msg)
